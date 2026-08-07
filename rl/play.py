"""Ask the agent what to do, or play against it.

    python3 rl/play.py advise --ckpt rl/runs/v1s/best.pt [--seed 0]
    python3 rl/play.py vs     --ckpt rl/runs/v1s/best.pt [--seed 0] [--seat 0]

**Which head is allowed to answer matters.** The value head is an *asymmetric
critic*: during training it is fed the opponent's hand and every facedown card
(PLAN.md §6.4), because it is discarded at play time. So ranking moves by the
value head would be ranking them with information a player does not have -- the
advice would be excellent and useless, and worse, it would look right.

So **advice comes from the policy head**, which sees only what
`viewer.view(state, table, cfg, seat)` shows. The critic's number is displayed
separately and labelled, because it is genuinely interesting (it is the
win-probability estimate of §1.2) but it is an oracle's opinion, not a player's.

The 1-ply value column has the same problem and is handled the same way: it
re-evaluates each candidate position with the privileged input withheld, which
is what a player could actually compute.
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
from rl.ppo import v1_deal
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
    logits, _ = net(t)
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
                    v = float(net.value_of(h, None).item())
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
        t = to_torch(batch([obs]), "cpu")
        _, val = net(t)
    print(f"\n  critic (ORACLE -- sees the opponent's hand, training-only): "
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
    obs = env.reset(a.seed, *v1_deal(table)(a.seed))
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


def cmd_vs(a) -> int:
    """Play a game against the agent from the terminal."""
    table = full_table()
    cfg = Config().at_victory_score(a.victory)
    if a.spells:
        from dataclasses import replace
        cfg = replace(cfg, units_only=False)
    net, enc = load(a.ckpt, table, cfg)
    env = RiftboundEnv(table, cfg, encoder=enc)
    obs = env.reset(a.seed, *v1_deal(table)(a.seed))
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
    p.add_argument("--deterministic", action="store_true")
    a = p.parse_args(argv)
    return cmd_advise(a) if a.mode == "advise" else cmd_vs(a)


if __name__ == "__main__":
    sys.exit(main())
