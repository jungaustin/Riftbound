"""Opponent pool with PFSP sampling, and an Elo ladder -- PLAN.md Phase 5.

**Why this is not optional.** The spell-enabled run peaked against greedy at
iteration 100 and was 8.8 points worse by 150, with non-overlapping intervals,
while its win rate against random stayed flat. Nothing had got worse in any
absolute sense -- the policy had co-adapted to its own current self and lost
ground against a *fixed, different* opponent. Training only against your latest
self is what causes that: the opponent distribution is one point, it moves with
you, and there is no pressure to stay good against anything you have left
behind.

**PFSP, not uniform and not latest-only** (AlphaStar's scheme, §4 Phase 5).
Sample past checkpoints in proportion to how *informative* they are, which means
prioritising opponents you beat around half the time:

    weight(o) = f(P[win against o])        f(x) = (1 - x)^p

An opponent you beat 99% of the time teaches almost nothing; one that beats you
99% of the time gives gradients you cannot act on. `p` controls the sharpness --
p=2 is a reasonable default and 0 recovers uniform sampling.

**Elo is measured against a frozen held-out set, never against the pool.**
Elo computed inside a moving population can rise while the population gets
weaker -- everyone beating everyone slightly better proves nothing. A held-out
ladder that never trains is the only version of the number that can be compared
across a run.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import torch


@dataclass
class Entry:
    """One frozen opponent."""
    name: str
    state_dict: dict
    iteration: int
    wins: float = 0.0        # decayed win count for the *learner*
    games: float = 0.0

    @property
    def learner_winrate(self) -> float:
        # Optimistic prior at 0.5 so a brand-new opponent is sampled before it
        # has any record, rather than being ignored or over-weighted.
        return (self.wins + 1.0) / (self.games + 2.0)


@dataclass
class OpponentPool:
    """Frozen past selves, sampled by PFSP."""
    capacity: int = 20
    p: float = 2.0
    decay: float = 0.98        # forget old results; the learner has moved on
    entries: list[Entry] = field(default_factory=list)

    def add(self, net, iteration: int, name: str | None = None) -> Entry:
        e = Entry(name=name or f"iter{iteration}",
                  state_dict={k: v.detach().clone().cpu()
                              for k, v in net.state_dict().items()},
                  iteration=iteration)
        self.entries.append(e)
        if len(self.entries) > self.capacity:
            # Drop the oldest rather than the weakest: keeping a spread of
            # ages is the point, and the weakest are often the most useful
            # reminders of what not to forget.
            self.entries.pop(0)
        return e

    def weights(self) -> np.ndarray:
        if not self.entries:
            return np.zeros(0)
        w = np.array([(1.0 - e.learner_winrate) ** self.p for e in self.entries],
                     dtype=np.float64)
        total = w.sum()
        if total <= 0:
            return np.full(len(w), 1.0 / len(w))
        return w / total

    def sample(self, rng: np.random.Generator) -> Entry | None:
        if not self.entries:
            return None
        return self.entries[int(rng.choice(len(self.entries), p=self.weights()))]

    def record(self, entry: Entry, learner_won: bool) -> None:
        for e in self.entries:               # decay everything, not just this one
            e.wins *= self.decay
            e.games *= self.decay
        entry.games += 1.0
        entry.wins += float(learner_won)

    def summary(self) -> str:
        if not self.entries:
            return "pool: empty"
        w = self.weights()
        top = sorted(zip(self.entries, w), key=lambda t: -t[1])[:3]
        return "pool: " + "  ".join(
            f"{e.name}@{e.learner_winrate:.0%}(w{p:.2f})" for e, p in top)


# ---------------------------------------------------------------------------
# Elo
# ---------------------------------------------------------------------------

def elo_update(ra: float, rb: float, score_a: float, k: float = 24.0):
    """One head-to-head result. `score_a` is A's score in [0, 1]."""
    ea = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
    return ra + k * (score_a - ea), rb + k * ((1 - score_a) - (1 - ea))


def elo_from_winrate(p: float, anchor: float = 0.0) -> float:
    """Elo difference implied by a win rate. The natural way to report a duel.

    Clamped away from 0 and 1: a 100% result implies infinite Elo, which is an
    artefact of a finite sample rather than a measurement.
    """
    p = min(max(p, 1e-3), 1 - 1e-3)
    return anchor + 400.0 * math.log10(p / (1.0 - p))


@dataclass
class Ladder:
    """A frozen set of reference opponents, rated once and never retrained.

    Elo measured *inside* a self-play population can climb while the whole
    population weakens. This is the version of the number that can be trusted
    across a run, because the reference points never move.
    """
    names: list[str] = field(default_factory=list)
    ratings: dict[str, float] = field(default_factory=dict)

    def add(self, name: str, rating: float = 0.0) -> None:
        self.names.append(name)
        self.ratings[name] = rating

    def rate(self, results: dict[str, float]) -> dict:
        """`results` maps opponent name -> learner win rate. Returns a report.

        The learner's rating is the sample-size-weighted mean of the Elo implied
        by each duel, which is a cheap approximation to a proper maximum-
        likelihood fit and is stable enough to plot.
        """
        est = [elo_from_winrate(p, self.ratings.get(n, 0.0))
               for n, p in results.items() if n in self.ratings]
        rating = float(np.mean(est)) if est else float("nan")
        return {"elo": rating, "vs": dict(results),
                "per_opponent_elo": {n: elo_from_winrate(p, self.ratings.get(n, 0.0))
                                     for n, p in results.items()}}
