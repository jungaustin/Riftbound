"""Ask the agent what to do, or play against it.

    python3 rl/play.py advise --ckpt rl/runs/v1s/best.pt [--seed 0]
    python3 rl/play.py vs     --ckpt rl/runs/v1s/best.pt [--seed 0] [--seat 0]

**Which head is allowed to answer matters.** This used to be a warning about an
asymmetric critic fed the opponent's hand. That is no longer the default: since
the two-critic change, `value_sym` sees exactly what the policy sees and drives
learning, and `net.win_prob()` returns it specifically so a number shown to a
person is one a person could have worked out. `value_priv` still exists as a
diagnostic and is never consulted here.

So everything on screen is legitimate: advice comes from the policy head, and
both value columns come from `win_prob`. Nothing displayed depends on the
opponent's hand, which is what makes it usable for studying a position rather
than just admiring it.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch
import torch.nn.functional as F

from rl.config import Config
from rl.engine import actions as A
from rl.engine.cardtable import full_table
from rl.env import RiftboundEnv
from rl.nets import RiftboundNet, to_torch
from rl.obs import Encoder
from rl.ppo import deck_pool_deal, select_decks, v1_deal
from rl.vec import batch
from rl.viewer import describe, view


def load(ckpt: str, table, cfg):
    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    enc = Encoder(table, cfg)
    if ck["shapes"] != enc.shapes():
        raise SystemExit(
            f"checkpoint observation layout does not match the current encoder.\n"
            f"  ckpt {ck['shapes']}\n  here {enc.shapes()}\n"
            f"The encoder changed since this checkpoint was trained; retrain, or "
            f"check out the commit it came from.")
    net = RiftboundNet(ck["shapes"])
    net.load_state_dict(ck["net"])
    net.eval()
    return net, enc


@torch.no_grad()
def rank(net, env: RiftboundEnv, obs, top: int = 6) -> list[tuple]:
    """Rank the legal moves as the POLICY sees them.

    Returns (action, policy_probability, honest_value_after), best first. The
    value column is computed with the privileged input withheld, so it is what
    a player could work out rather than what the training critic knows.
    """
    t = to_torch(batch([obs]), "cpu")
    logits, _, _ = net(t)   # (logits, value, value_aux)
    probs = F.softmax(logits, -1)[0, :obs.n_legal].numpy()

    seat = obs.to_move
    rows = []
    for i, act in enumerate(env.legal):
        # 1-ply lookahead on a clone -- `GameState.clone()` is cheap by design.
        s2 = env.state.clone()
        try:
            A.apply(s2, env.table, env.cfg, act)
        except Exception:
            rows.append((act, float(probs[i]), float("nan")))
            continue
        v = float("nan")
        if not A.is_terminal(s2):
            nxt = A.acting_seat(s2)
            if nxt >= 0:
                legal2 = A.legal_actions(s2, env.table, env.cfg, nxt)
                if legal2:
                    o2 = env.enc.encode(s2, nxt, legal2)
                    t2 = to_torch(batch([o2]), "cpu", privileged=False)
                    h = net.encode(t2["zones"], t2["zone_mask"], t2["globals"])
                    # the HONEST head -- `value_of` went away with the
                    # single critic, and `value_priv` would need the
                    # opponent's hand, which a player does not have.
                    v = float(net.value_sym(h).item())
                    if nxt != seat:
                        v = -v          # value is always "good for whoever moves"
        else:
            v = A.outcome(s2)[seat]
        rows.append((act, float(probs[i]), v))
    rows.sort(key=lambda r: -r[1])
    return rows[:top]


def show_advice(net, env, obs, table, cfg) -> None:
    seat = obs.to_move
    print(view(env.state, table, cfg, seat))
    print("\n--- the agent's ranking (policy head; legitimate information only) ---")
    print(f"  {'':>4} {'move':<44}{'policy':>8}{'value after':>13}")
    for act, p, v in rank(net, env, obs):
        vs = "  --  " if v != v else f"{v:+.3f}"
        print(f"  {'':>4} {describe(act, env.state, table, seat).strip():<44}"
              f"{p:>7.1%}{vs:>13}")
    with torch.no_grad():
        val = net.win_prob(to_torch(batch([obs]), "cpu", privileged=False))
    print(f"\n  critic (policy-side -- legitimate information only): "
          f"{float(val.item()):+.3f}")
    print("  value is in [-1, +1] and is a win-probability estimate for the "
          "side to move (gamma=1.0, §1.2).")


def cmd_advise(a) -> int:
    table = full_table()
    cfg = Config().at_victory_score(a.victory)
    if a.spells:
        from dataclasses import replace
        cfg = replace(cfg, units_only=False)
    net, enc = load(a.ckpt, table, cfg)
    env = RiftboundEnv(table, cfg, encoder=enc)
    obs = env.reset(a.seed, *_deal_for(a, table)(a.seed))
    rng = np.random.default_rng(a.seed)
    for _ in range(a.ply):                    # fast-forward to a live position
        if obs is None:
            break
        obs = env.step(int(rng.integers(obs.n_legal))).obs
    if obs is None:
        print("game ended before that ply; try a smaller --ply")
        return 1
    show_advice(net, env, obs, table, cfg)
    return 0


def _deal_for(a, table):
    """The deal to play out. Real decklists unless asked otherwise.

    `v1_deal`'s procedural decks are 6-domain soup with an unrelated rune deck --
    fine as a training curriculum, no fun at all to sit across from, and not a
    fair test of the agent either. `--decks` narrows to one list by substring,
    so a specific matchup can be replayed.
    """
    if a.procedural:
        return v1_deal(table)
    pool = select_decks(table, a.decks)
    return deck_pool_deal(table, 0.0, seed_decks=pool)


def cmd_vs(a) -> int:
    """Play a game against the agent from the terminal."""
    table = full_table()
    cfg = Config().at_victory_score(a.victory)
    if a.spells:
        from dataclasses import replace
        cfg = replace(cfg, units_only=False)
    net, enc = load(a.ckpt, table, cfg)
    env = RiftboundEnv(table, cfg, encoder=enc)
    obs = env.reset(a.seed, *_deal_for(a, table)(a.seed))
    you = a.seat

    while obs is not None:
        if obs.to_move != you:
            with torch.no_grad():
                t = to_torch(batch([obs]), "cpu")
                idx, *_ = net.act(t, deterministic=a.deterministic)
            act = env.legal[int(idx.item())]
            print(f"\n  agent: {describe(act, env.state, table, obs.to_move).strip()}")
            obs = env.step(int(idx.item())).obs
            continue

        print("\n" + view(env.state, table, cfg, you, env.legal))
        raw = input("\n  your move (index, '?' for advice, 'q' to quit): ").strip()
        if raw == "q":
            return 0
        if raw == "?":
            show_advice(net, env, obs, table, cfg)
            continue
        if not raw.isdigit() or int(raw) >= obs.n_legal:
            print("  not a legal index")
            continue
        obs = env.step(int(raw)).obs

    w = env.state.winner
    print(f"\n  === {'you win' if w == you else 'agent wins' if w >= 0 else 'draw'}"
          f"  {env.state.points.tolist()} in {env.state.turn} turns ===")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("advise", "vs"))
    p.add_argument("--ckpt", default="rl/runs/v1s/best.pt")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--victory", type=int, default=3)
    p.add_argument("--seat", type=int, default=0)
    p.add_argument("--ply", type=int, default=6)
    p.add_argument("--spells", action="store_true", default=True)
    p.add_argument("--deterministic", action="store_true",
                   help="always take the agent's top move. Off by default: the "
                        "policy is stochastic on purpose, and sampling is what "
                        "keeps it from playing the same game every time.")
    p.add_argument("--procedural", action="store_true",
                   help="deal v1_deal's random-pool decks instead of the real "
                        "decklists (training curriculum, not a real game)")
    p.add_argument("--decks", default=None,
                   help="narrow the decklist pool by substring, e.g. 'lillia'")
    a = p.parse_args(argv)
    return cmd_advise(a) if a.mode == "advise" else cmd_vs(a)


if __name__ == "__main__":
    sys.exit(main())
