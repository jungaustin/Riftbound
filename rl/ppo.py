"""PPO with self-play -- PLAN.md Phase 4, §5.3, §6.5.

Run: python3 rl/ppo.py [iterations] [--victory 3] [--envs 64] [--device cpu]

Three decisions here are specific to this game rather than to PPO, and each one
removes a class of bug the plan warns about.

**Only complete episodes are ever trained on.** Reward is terminal-only and
`gamma = 1.0` (§1.2 -- it makes the critic a literal win-probability predictor,
which is the deck-evaluator deliverable). So a transition's target does not
depend on *when* it is harvested, and there is no reason to bootstrap a
half-finished game. Per-env buffers carry across rollout boundaries and are
flushed only when the game ends. That deletes truncation-boundary handling
entirely -- the single most bug-prone part of a PPO implementation -- at the
cost of some transitions being one policy version stale, which is exactly what
PPO's ratio clipping already exists to handle (and the stored `logp` makes the
ratio correct regardless).

**Every seat keeps its own trajectory, and GAE runs inside it** (§5.3 gotchas
1-2). Between two of a seat's decisions the opponent moved, possibly several
times. Bootstrapping across that would have the critic predict its own value
from a position its opponent chose. Each seat's subsequence is treated as its
own episode with the opponent folded into the dynamics, so `V(s_{t+1})` is
always *that seat's* next decision.

**Rewards are written to both seats at once from the game result**, never
credited to whoever moved last (§5.3 gotcha 1).

When it does not learn, §4 Phase 4 gives the debug order: mask alignment, reward
sign and seat attribution, observation canonicalization, advantage
normalization, learning rate -- in that order, and it is one of the first three
about 90% of the time. Tests [1]-[5] in `rl/tests/test_env.py` and [1]-[3] in
`rl/tests/test_ppo.py` cover those first three, so a failure here should be
looked for further down the list than instinct suggests.
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass, field
from dataclasses import replace as dc_replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch
import torch.nn as nn

from rl.config import Config
from rl.engine.cardtable import full_table
from rl.eval import report
from rl.nets import RiftboundNet, count_params, to_torch
from rl.pool import Ladder, OpponentPool, elo_from_winrate
from rl.tests.fuzz import v0_pool
from rl.vec import BatchObs, VecRiftbound, batch


@dataclass
class HP:
    """§6.5, unchanged except where the note says why."""
    gamma: float = 1.0            # terminal-only reward; critic = win prob
    gae_lambda: float = 0.95
    lr: float = 3e-4
    n_envs: int = 64
    rollout: int = 2048           # transitions per update, not steps per env
    minibatches: int = 4
    update_epochs: int = 4
    clip_coef: float = 0.2
    ent_coef: float = 0.01        # applied to the NORMALIZED entropy (§6.3)
    vf_coef: float = 0.5
    max_grad_norm: float = 0.5
    anneal_lr: bool = True

    # --- opponent pool (Phase 5) ------------------------------------------
    # `pool_frac` of envs play a sampled frozen past self; the rest are pure
    # self-play. Mixing rather than replacing: pure pool play loses the
    # sharpening that comes from facing your exact current strength, pure
    # self-play is what produced the 8.8-point drift against greedy.
    pool_frac: float = 0.5
    pool_every: int = 10          # snapshot the learner every N iterations
    pool_capacity: int = 20
    pfsp_p: float = 2.0


# ---------------------------------------------------------------------------
# Rollout storage
# ---------------------------------------------------------------------------

def slice_obs(b: BatchObs, i: int) -> dict:
    """One env's observation, detached from the batch."""
    return {
        "zones": {k: v[i].copy() for k, v in b.zones.items()},
        "zone_mask": {k: v[i].copy() for k, v in b.zone_mask.items()},
        "globals": b.globals[i].copy(),
        "legal_actions": b.legal_actions[i].copy(),
        "action_mask": b.action_mask[i].copy(),
        "privileged": None if b.privileged is None else b.privileged[i].copy(),
    }


def _subset(b: BatchObs, slots: list[int]) -> BatchObs:
    """A BatchObs restricted to some env slots, for a per-opponent forward."""
    return BatchObs(
        zones={k: v[slots] for k, v in b.zones.items()},
        zone_mask={k: v[slots] for k, v in b.zone_mask.items()},
        globals=b.globals[slots],
        legal_actions=b.legal_actions[slots],
        action_mask=b.action_mask[slots],
        to_move=b.to_move[slots],
        n_legal=b.n_legal[slots],
        privileged=None if b.privileged is None else b.privileged[slots],
    )


def stack_obs(rows: list[dict], device: str) -> dict:
    keys = rows[0]["zones"].keys()
    b = BatchObs(
        zones={k: np.stack([r["zones"][k] for r in rows]) for k in keys},
        zone_mask={k: np.stack([r["zone_mask"][k] for r in rows]) for k in keys},
        globals=np.stack([r["globals"] for r in rows]),
        legal_actions=np.stack([r["legal_actions"] for r in rows]),
        action_mask=np.stack([r["action_mask"] for r in rows]),
        to_move=np.zeros(len(rows), np.int8),
        n_legal=np.zeros(len(rows), np.int16),
        privileged=(None if rows[0]["privileged"] is None
                    else np.stack([r["privileged"] for r in rows])),
    )
    return to_torch(b, device)


@dataclass
class Step:
    obs: dict
    action: int
    logp: float
    value: float
    seat: int
    adv: float = 0.0
    ret: float = 0.0


@dataclass
class Rollout:
    steps: list[Step] = field(default_factory=list)
    episodes: int = 0
    ep_len: list[int] = field(default_factory=list)
    ep_turns: list[int] = field(default_factory=list)
    truncated: int = 0
    seat0_wins: int = 0


def finish_episode(pending: list[Step], rewards, hp: HP) -> None:
    """Assign returns and advantages, one seat's subsequence at a time.

    `rewards` is indexed by seat and both entries are filled from the game
    result -- the seat that moved last has no special status here, which is the
    whole point (§5.3 gotcha 1).
    """
    for seat in (0, 1):
        own = [s for s in pending if s.seat == seat]
        if not own:
            continue
        r_terminal = float(rewards[seat])
        adv = 0.0
        for t in reversed(range(len(own))):
            last = t == len(own) - 1
            # Terminal-only reward: every delta but the last is pure value
            # bootstrap from THIS seat's next decision, never the opponent's.
            next_v = 0.0 if last else own[t + 1].value
            r = r_terminal if last else 0.0
            delta = r + hp.gamma * next_v - own[t].value
            adv = delta + hp.gamma * hp.gae_lambda * adv
            own[t].adv = adv
            own[t].ret = adv + own[t].value


class Trainer:
    def __init__(self, table, cfg: Config, deal_fn, hp: HP,
                 device: str = "cpu", seed: int = 0) -> None:
        self.table, self.cfg, self.hp, self.device = table, cfg, hp, device
        self.deal_fn = deal_fn
        self.vec = VecRiftbound(table, cfg, hp.n_envs, deal_fn, seed0=seed)
        self.net = RiftboundNet(self.vec.shapes()).to(device)
        self.opt = torch.optim.Adam(self.net.parameters(), lr=hp.lr, eps=1e-5)
        self.gen = torch.Generator(device="cpu").manual_seed(seed)
        self.obs = self.vec.reset()
        self.pending: list[list[Step]] = [[] for _ in range(hp.n_envs)]
        self.global_step = 0

        # Opponent pool. `env_opp[i]` is the frozen opponent assigned to slot i
        # (None = pure self-play) and `learner_seat[i]` which side the learner
        # is on there -- alternated, because a learner that always sits in seat
        # 0 would never train the going-second game, and victory 3 has a large
        # first-player edge (measured 64% self-play seat 0).
        self.pool = OpponentPool(capacity=hp.pool_capacity, p=hp.pfsp_p)
        self.rng = np.random.default_rng(seed)
        self.env_opp: list = [None] * hp.n_envs
        self.learner_seat = [i % 2 for i in range(hp.n_envs)]
        self._opp_cache: dict[int, RiftboundNet] = {}

    def _opp_net(self, entry) -> RiftboundNet:
        """Instantiate (and cache) a frozen opponent."""
        key = id(entry)
        net = self._opp_cache.get(key)
        if net is None:
            net = RiftboundNet(self.vec.shapes()).to(self.device)
            net.load_state_dict(entry.state_dict)
            net.eval()
            if len(self._opp_cache) > self.hp.pool_capacity + 2:
                self._opp_cache.clear()
            self._opp_cache[key] = net
        return net

    def _assign(self, i: int) -> None:
        """Pick who slot i plays next episode, and which seat the learner takes."""
        self.learner_seat[i] = int(self.rng.integers(2))
        self.env_opp[i] = (self.pool.sample(self.rng)
                           if self.pool.entries
                           and self.rng.random() < self.hp.pool_frac else None)

    # -- collect ---------------------------------------------------------

    @torch.no_grad()
    def collect(self) -> Rollout:
        hp, out = self.hp, Rollout()
        while len(out.steps) < hp.rollout:
            # Which slots is the learner acting in? The rest are driven by a
            # frozen opponent and produce no training data -- recording them
            # would teach the learner to imitate an old checkpoint.
            mine = [i for i in range(hp.n_envs)
                    if self.env_opp[i] is None
                    or int(self.obs.to_move[i]) == self.learner_seat[i]]
            idx_np = np.zeros(hp.n_envs, np.int64)

            if mine:
                t = to_torch(self.obs, self.device)
                idx, logp, _, value = self.net.act(t, generator=self.gen)
                idx_np[mine] = idx.cpu().numpy()[mine]
                logp_np = logp.cpu().numpy()
                val_np = value.cpu().numpy()
                for i in mine:
                    self.pending[i].append(Step(
                        obs=slice_obs(self.obs, i), action=int(idx_np[i]),
                        logp=float(logp_np[i]), value=float(val_np[i]),
                        seat=int(self.obs.to_move[i])))

            # Group the remaining slots by opponent so each frozen net runs one
            # batched forward rather than one per slot.
            others: dict[int, list[int]] = {}
            for i in range(hp.n_envs):
                if i not in mine:
                    others.setdefault(id(self.env_opp[i]), []).append(i)
            for _, slots in others.items():
                opp = self._opp_net(self.env_opp[slots[0]])
                sub = to_torch(_subset(self.obs, slots), self.device)
                with torch.no_grad():
                    oidx, *_ = opp.act(sub, generator=self.gen)
                idx_np[slots] = oidx.cpu().numpy()

            self.obs, rewards, done, infos = self.vec.step(idx_np)
            self.global_step += hp.n_envs

            for i in np.flatnonzero(done):
                if self.env_opp[i] is not None:
                    self.pool.record(
                        self.env_opp[i],
                        learner_won=(rewards[i][self.learner_seat[i]] > 0))
                self._assign(i)
                finish_episode(self.pending[i], rewards[i], hp)
                ep = infos[i]["episode"]
                out.steps.extend(self.pending[i])
                out.episodes += 1
                out.ep_len.append(len(self.pending[i]))
                out.ep_turns.append(ep["turns"])
                out.truncated += int(ep["truncated"])
                out.seat0_wins += int(ep["winner"] == 0)
                self.pending[i] = []
        return out

    # -- update ----------------------------------------------------------

    def update(self, roll: Rollout, frac_done: float) -> dict:
        hp, dev = self.hp, self.device
        steps = roll.steps
        n = len(steps)

        if hp.anneal_lr:
            # Cosine to 10% rather than to 0: a run that ends with a dead
            # learning rate cannot recover if it is extended.
            lr = hp.lr * (0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * frac_done)))
            for g in self.opt.param_groups:
                g["lr"] = lr
        else:
            lr = hp.lr

        obs = stack_obs([s.obs for s in steps], dev)
        act = torch.as_tensor([s.action for s in steps], device=dev)
        old_logp = torch.as_tensor([s.logp for s in steps], dtype=torch.float32,
                                   device=dev)
        adv_all = torch.as_tensor([s.adv for s in steps], dtype=torch.float32,
                                  device=dev)
        ret_all = torch.as_tensor([s.ret for s in steps], dtype=torch.float32,
                                  device=dev)

        stats = {"pg": 0.0, "vf": 0.0, "ent": 0.0, "kl": 0.0, "clipfrac": 0.0}
        nb = 0
        for _ in range(hp.update_epochs):
            order = torch.randperm(n, generator=self.gen).to(dev)
            # Even splits, not a fixed stride. A stride leaves a remainder
            # minibatch that can hold a single transition, whose advantage
            # std is undefined -- that produced a NaN policy loss which then
            # spread to every parameter through one optimizer step, with no
            # error and no crash.
            for mb in torch.tensor_split(order, hp.minibatches):
                if mb.numel() < 2:
                    continue
                sub = {
                    "zones": {k: v[mb] for k, v in obs["zones"].items()},
                    "zone_mask": {k: v[mb] for k, v in obs["zone_mask"].items()},
                    "globals": obs["globals"][mb],
                    "actions": obs["actions"][mb],
                    "action_mask": obs["action_mask"][mb],
                }
                if "privileged" in obs:
                    sub["privileged"] = obs["privileged"][mb]

                logp, ent, value = self.net.evaluate(sub, act[mb])
                ratio = (logp - old_logp[mb]).exp()

                # Normalized per minibatch, which is what CleanRL does and what
                # the §4 debug list means by "advantage normalization".
                a = adv_all[mb]
                a = (a - a.mean()) / (a.std(unbiased=False) + 1e-8)

                pg = torch.max(-a * ratio,
                               -a * ratio.clamp(1 - hp.clip_coef,
                                                1 + hp.clip_coef)).mean()
                vf = 0.5 * (value - ret_all[mb]).pow(2).mean()
                loss = pg - hp.ent_coef * ent.mean() + hp.vf_coef * vf
                # A single NaN reaches every parameter through one Adam step
                # and the run continues producing plausible-looking output
                # forever after. Cheap to check, impossible to notice later.
                assert torch.isfinite(loss), (
                    f"non-finite loss (pg={pg.item()}, vf={vf.item()}, "
                    f"ent={ent.mean().item()}, minibatch of {mb.numel()})")

                self.opt.zero_grad(set_to_none=True)
                loss.backward()
                nn.utils.clip_grad_norm_(self.net.parameters(), hp.max_grad_norm)
                self.opt.step()

                with torch.no_grad():
                    stats["pg"] += pg.item()
                    stats["vf"] += vf.item()
                    stats["ent"] += ent.mean().item()
                    # Schulman's low-variance KL estimator.
                    d = old_logp[mb] - logp
                    stats["kl"] += ((d.exp() - 1) - d).mean().item()
                    stats["clipfrac"] += ((ratio - 1).abs()
                                          > hp.clip_coef).float().mean().item()
                nb += 1

        for k in stats:
            stats[k] /= max(1, nb)
        stats["lr"] = lr
        stats["explained_var"] = explained_variance(
            np.array([s.value for s in steps]), np.array([s.ret for s in steps]))
        return stats


def explained_variance(pred: np.ndarray, target: np.ndarray) -> float:
    """1 - Var(target - pred) / Var(target). The critic's health in one number:
    0 means it is no better than predicting the mean, 1 means perfect."""
    var = target.var()
    return float("nan") if var == 0 else float(1 - (target - pred).var() / var)


# ---------------------------------------------------------------------------

# Derived from SPECS, not listed. This was a hand-maintained tuple, which meant
# every spell transcribed into the DSL had to be remembered here too or it
# would never appear in a training deck -- a silent omission that looks like
# nothing at all, since the card simply never gets drawn. The DSL is the single
# source of truth for "the engine can play this".
def _spell_pool() -> tuple[str, ...]:
    from rl.engine.cardtable import full_table
    from rl.engine.effects import SPECS
    t = full_table()
    return tuple(sorted(n for n in SPECS if t.is_type(t.id_of(n), "Spell")))


SPELLS = _spell_pool()


# Measured from the 29 decklists in `decks/`, not assumed:
#   main deck   39 cards, every single deck
#   copies      at most 3 of any one card
#   spells      28% - 67% of the main deck, median 49% (33 decks)
#
# An earlier version of this file used 30 cards and called a 30% spell rate
# "well above what a real decklist would run". Both were wrong, and the second
# was wrong in the opposite direction -- 30% is near the LOW end of the real
# range. The project owner's Lillia lists run 54%.
MAIN_DECK_SIZE = 39
MAX_COPIES = 3
SPELL_RATE_RANGE = (0.28, 0.67)


def v1_deal(table, deck_size: int = MAIN_DECK_SIZE,
            spell_rate: tuple[float, float] | float = SPELL_RATE_RANGE):
    """Decks built to the real constraints, with the implemented spells.

    `spell_rate` may be a fixed fraction or a (lo, hi) range sampled per deal.
    A range is the default because the real decks span 28-62% and an agent
    trained on one density would be tuned for one archetype.

    **The card pool used to be what limited realism, and no longer is.** With
    only three spells implemented the 3-copy limit capped a deck at 9 spells --
    23% of 39, below even the lowest real deck -- so this function silently
    fell short of whatever rate it was asked for. The DSL now holds enough
    spells that the measured output spans the real range: mean 48%, max 67%
    against a corpus of 28-67%, median 49%. `deal_stats` still reports the
    actual distribution rather than the requested one, because that gap is
    exactly the sort of thing that comes back.
    """
    spells = [table.id_of(n) for n in SPELLS]
    units = v0_pool(table)
    bfs = [c for c in range(table.n) if table.is_type(c, "Battlefield")][:2]

    def _build(rng, want_spells: int) -> list[int]:
        """Fill a deck respecting the 3-copy limit, spells first."""
        deck: list[int] = []
        counts: dict[int, int] = {}

        def take(pool, n):
            tries = 0
            while n > 0 and tries < 500:
                tries += 1
                c = int(rng.choice(pool))
                if counts.get(c, 0) >= MAX_COPIES:
                    continue
                counts[c] = counts.get(c, 0) + 1
                deck.append(c)
                n -= 1
            return n

        take(spells, want_spells)
        take(units, deck_size - len(deck))
        return deck

    def deal(seed):
        rng = np.random.default_rng(seed)
        decks = []
        for _ in range(2):
            rate = (rng.uniform(*spell_rate)
                    if isinstance(spell_rate, tuple) else spell_rate)
            decks.append(_build(rng, int(round(deck_size * rate))))
        runes = [[int(rng.integers(6)) for _ in range(12)] for _ in range(2)]
        # No decklist, so no Champion Legend (103.1). A random pool has no
        # domain identity to take one from, and a game without one is legal.
        return decks, runes, bfs, [-1, -1]
    return deal


def deck_pool_deal(table, min_coverage: float = 0.0, seed_decks=None):
    """Sample a matchup from the REAL decklists each episode.

    This is what makes domain identity learnable. `v1_deal` builds decks by
    sampling the implemented pool at random, which produces 6-domain soup with
    an unrelated rune deck -- cards are frequently uncastable and no archetype
    signal exists to condition on. Real decks commit: a rune deck of 8 Order /
    4 Body *is* the deck's identity, and it is what makes Fury play like Fury
    and Mind play like Mind.

    The network can already represent this -- cards carry a 6-dim domain
    multi-hot and the globals carry per-domain rune counts for both seats -- so
    the missing piece was never the architecture, it was the training
    distribution. Sampling a different matchup per episode is also what stops
    the policy overfitting to one archetype, which is the failure the project
    owner asked about: swap the deck and it should not suddenly play worse.
    """
    from rl.decks import load_all, matchup
    # `latest_only`: eight iterations of one Lillia list were eight independent
    # draws, so 46% of the training pool was a single archetype and 71% of
    # matchups contained it. That is exactly the overfitting this function's
    # docstring says it exists to prevent -- swap the deck and the policy should
    # not suddenly play worse -- and it was being manufactured by the loader.
    pool = [d for d in (seed_decks or load_all(table, latest_only=True))
            if d.coverage >= min_coverage]
    assert pool, f"no decks at coverage >= {min_coverage:.0%}"

    def deal(seed):
        rng = np.random.default_rng(seed)
        i, j = rng.integers(len(pool)), rng.integers(len(pool))
        # WHICH of its three battlefields each deck presents is sampled too
        # (486.5). It used to be each deck's first, always -- so two thirds of
        # every decklist's battlefields never appeared in training at all, and
        # the policy could not learn to play on ground it had never seen. Free
        # to vary now that battlefields are distinguishable in the observation;
        # before that they all encoded identically and this would have changed
        # nothing.
        picks = (int(rng.integers(3)), int(rng.integers(3)))
        return matchup(pool[int(i)], pool[int(j)], picks=picks)
    return deal


def deal_stats(table, deal_fn, n: int = 500) -> dict:
    """What the deal function actually produces, as opposed to what it was asked
    for. Worth checking whenever the card pool changes."""
    spells = {table.id_of(x) for x in SPELLS}
    fracs, sizes, copies = [], [], []
    for i in range(n):
        for deck in deal_fn(i)[0]:
            sizes.append(len(deck))
            fracs.append(sum(c in spells for c in deck) / max(1, len(deck)))
            counts: dict[int, int] = {}
            for c in deck:
                counts[c] = counts.get(c, 0) + 1
            copies.append(max(counts.values()))
    return {"deck_size": sorted(set(sizes)),
            "spell_frac_mean": float(np.mean(fracs)),
            "spell_frac_max": float(np.max(fracs)),
            "max_copies": int(np.max(copies))}


# Deliberately still 30, not MAIN_DECK_SIZE. Every Phase 1-4 number was
# measured with 30-card decks, and `fuzz.make_game`'s golden outcome pins that.
# Changing it would silently invalidate the whole gate suite. Recorded as a
# known caveat instead: the v0 results describe a 30-card game, which is not
# the real one.
def v0_deal(table, deck_size: int = 30):
    """The Phase 1-3 deal, so training results stay comparable to the gates."""
    pool = v0_pool(table)
    bfs = [c for c in range(table.n) if table.is_type(c, "Battlefield")][:2]

    def deal(seed):
        rng = np.random.default_rng(seed)
        decks = [[int(rng.choice(pool)) for _ in range(deck_size)]
                 for _ in range(2)]
        runes = [[int(rng.integers(6)) for _ in range(12)] for _ in range(2)]
        return decks, runes, bfs, [-1, -1]
    return deal


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("iterations", nargs="?", type=int, default=100)
    p.add_argument("--victory", type=int, default=3)
    p.add_argument("--spells", action="store_true",
                   help="enable the DSL spell pool (units_only=False)")
    p.add_argument("--real-decks", action="store_true",
                   help="train on sampled real decklists, so domain "
                        "identity is learnable")
    p.add_argument("--min-coverage", type=float, default=0.6)
    p.add_argument("--envs", type=int, default=64)
    p.add_argument("--rollout", type=int, default=2048)
    p.add_argument("--device", default="cpu")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--eval-every", type=int, default=10)
    p.add_argument("--eval-games", type=int, default=100)
    p.add_argument("--out", default="rl/runs/ppo")
    p.add_argument("--init", default=None,
                   help="checkpoint to warm-start from -- this is how the "
                        "victory-score curriculum (§1.3) is annealed 3 -> 5 -> 8")
    a = p.parse_args(argv)

    torch.manual_seed(a.seed)
    table = full_table()
    cfg = Config().at_victory_score(a.victory)
    if a.spells:
        cfg = dc_replace(cfg, units_only=False)
    hp = HP(n_envs=a.envs, rollout=a.rollout)
    if a.real_decks:
        deal = deck_pool_deal(table, a.min_coverage)
    else:
        deal = v1_deal(table) if a.spells else v0_deal(table)

    tr = Trainer(table, cfg, deal, hp, device=a.device, seed=a.seed)
    if a.init:
        ck = torch.load(a.init, map_location=a.device, weights_only=False)
        # The observation layout is baked into the first and last layers, so a
        # checkpoint from a different encoder would load into the wrong shapes
        # or, worse, the right shapes with different meanings.
        assert ck["shapes"] == tr.vec.shapes(), (
            f"checkpoint was trained on a different observation layout:\n"
            f"  ckpt {ck['shapes']}\n  here {tr.vec.shapes()}")
        tr.net.load_state_dict(ck["net"])
        print(f"warm-started from {a.init} (iter {ck.get('iter')}, "
              f"eval {ck.get('eval')})")

    print(f"PPO: victory={a.victory} envs={hp.n_envs} rollout={hp.rollout} "
          f"device={a.device} params={count_params(tr.net):,}")
    print(f"     exit criteria: >=90% vs random, >=65% vs greedy")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    best = -1.0
    for it in range(1, a.iterations + 1):
        roll = tr.collect()
        stats = tr.update(roll, (it - 1) / max(1, a.iterations))
        dt = time.time() - t0
        print(f"[{it:4d}/{a.iterations}] steps={tr.global_step:>8,} "
              f"eps={roll.episodes:>4} len={np.mean(roll.ep_len):5.1f} "
              f"turns={np.mean(roll.ep_turns):4.1f} "
              f"seat0={roll.seat0_wins / max(1, roll.episodes):.0%} "
              f"trunc={roll.truncated / max(1, roll.episodes):.1%} | "
              f"ent={stats['ent']:.3f} kl={stats['kl']:.4f} "
              f"clip={stats['clipfrac']:.2f} ev={stats['explained_var']:+.2f} "
              f"| {tr.global_step / dt:.0f} st/s", flush=True)

        if hp.pool_every and it % hp.pool_every == 0:
            tr.pool.add(tr.net, it)

        if a.eval_every and it % a.eval_every == 0:
            r = report(tr.net, table, cfg, deal, n=a.eval_games, device=a.device)
            flag = "  <-- PHASE 4 EXIT MET" if r["pass"] else ""
            lock = (f"  livelocked {r['livelocks']}" if r.get("livelocks")
                    else "")
            print(f"       eval: vs_random {r['vs_random']:.1%}  "
                  f"vs_greedy {r['vs_greedy']:.1%}  "
                  f"elo(greedy=0) {elo_from_winrate(r['vs_greedy']):+.0f}"
                  f"{lock}{flag}\n       {tr.pool.summary()}", flush=True)
            score = r["vs_random"] + r["vs_greedy"]
            if score > best:
                best = score
                torch.save({"net": tr.net.state_dict(), "shapes": tr.vec.shapes(),
                            "iter": it, "eval": r}, out / "best.pt")
    torch.save({"net": tr.net.state_dict(), "shapes": tr.vec.shapes(),
                "iter": a.iterations}, out / "last.pt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
