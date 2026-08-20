"""The environment -- PLAN.md Phase 3, §5.1.

**Not Gymnasium.** Gymnasium is single-agent, and this game is two-player with
alternating priority and a variable-length action list that fits no standard
`Space`. This is a plain class with a PettingZoo-AEC *shape*: one seat is to
move at a time, `step` advances until somebody has a real decision, and the
observation always belongs to whoever that is.

Two API decisions are deliberate and both exist to prevent specific bugs.

**`step` takes an index, not an action.** The policy picks a slot in the list
the env just handed it. That is what makes a variable-length action space
trainable at all (§5.1), and it means an off-by-one in the mask is impossible
to express rather than merely unlikely.

**Rewards are per seat, always both.** `StepResult.rewards[s]` is seat `s`'s
reward -- never "the reward for whoever just moved". The classic self-play bug
is crediting the final actor for the win (§5.3 gotcha 1), and it is a bug you
cannot write against this signature. The trainer keeps one buffer per seat and
writes both entries at game end.

**Auto-pass** collapses priority windows where `pass` is the only legal action.
Those are not decisions, and in v0 (no `[Reaction]` cards yet) every Showdown
window is one, which is most of the step count. The guard is strict and stays
strict: the list must be *literally* `[pass]`. The moment a Reaction is
affordable the window becomes a real decision -- and those windows are exactly
where bluffing lives (§5.3 gotcha 3), so auto-passing one would delete the
phenomenon this project is being built to study.
"""

from __future__ import annotations

from collections import Counter
from typing import NamedTuple

import numpy as np

from rl.config import Config
from rl.engine import actions as A
from rl.engine import game, invariants
from rl.engine.cardtable import CardTable
from rl.engine.state import N_SEATS, GameState
from rl.obs import Encoder, Obs


def should_auto_pass(legal: list[A.Action]) -> bool:
    """Is this priority window a no-op rather than a decision?

    Only when the legal set is *literally* `[pass]`. Deliberately not "any
    single forced action" and deliberately not "pass is available": the instant
    a `[Reaction]` is affordable the window becomes the most interesting
    decision in the game, and collapsing it would delete the bluffing behaviour
    Phase 7 exists to measure (§5.3 gotcha 3).

    A predicate rather than an inline condition because v0 cannot reach a
    Showdown priority window at all -- `combat.run_combat` resolves Combat
    without yielding -- so this rule is untestable through gameplay until
    Reactions land, and an untested rule guarding something that valuable
    should at least be testable on its own.
    """
    return len(legal) == 1 and legal[0].kind == A.A_PASS


class StepResult(NamedTuple):
    obs: Obs | None                  # None at termination
    rewards: tuple[float, float]     # indexed by SEAT, not by actor
    done: bool
    truncated: bool
    info: dict


class RiftboundEnv:
    """One self-play game. Reusable across episodes via `reset`."""

    def __init__(self, table: CardTable, cfg: Config,
                 encoder: Encoder | None = None, auto_pass: bool = True,
                 check: bool = False, privileged: bool = True) -> None:
        self.table = table
        self.cfg = cfg
        self.enc = encoder or Encoder(table, cfg, privileged=privileged)
        self.auto_pass = auto_pass
        self.check = check

        self.state: GameState | None = None
        self._legal: list[A.Action] = []
        self._obs: Obs | None = None
        self.steps = 0            # decisions the policy was asked for
        self.auto_passes = 0      # windows collapsed without asking
        self.n_legal_hist: Counter = Counter()

    # -- properties ------------------------------------------------------

    @property
    def to_move(self) -> int:
        return -1 if self._obs is None else self._obs.to_move

    @property
    def legal(self) -> list[A.Action]:
        """The engine actions backing the current observation, in mask order."""
        return self._legal

    @property
    def done(self) -> bool:
        return self.state is None or A.is_terminal(self.state)

    # -- lifecycle -------------------------------------------------------

    def reset(self, seed: int, decks, rune_decks, battlefields,
              legends=None) -> Obs:
        self.state = game.new_game(self.table, self.cfg, decks, rune_decks,
                                   battlefields, seed=seed, legends=legends)
        self.steps = 0
        self.auto_passes = 0
        self._advance()
        assert self._obs is not None, "game was terminal before the first move"
        return self._obs

    def reset_from(self, state: GameState) -> Obs | None:
        """Attach to an existing position -- for tests, replays and search."""
        self.state = state
        self.steps = 0
        self.auto_passes = 0
        self._advance()
        return self._obs

    def step(self, action_index: int) -> StepResult:
        assert self.state is not None, "step before reset"
        assert self._obs is not None, "step after termination"
        assert 0 <= action_index < len(self._legal), (
            f"action index {action_index} outside the {len(self._legal)} legal "
            f"actions; the policy must sample under the mask")

        act = self._legal[action_index]
        log = A.apply(self.state, self.table, self.cfg, act)
        self.steps += 1
        self._advance()

        s = self.state
        # A loop inside one turn never advances the turn, so `turn_cap` cannot
        # see it. Truncating here makes a livelock cost one episode instead of
        # an entire run, and marks it the same way a too-long game is marked.
        if self.steps > self.cfg.decision_cap and not A.is_terminal(s):
            s.truncated = True
        done = A.is_terminal(s) or bool(s.truncated)
        return StepResult(
            obs=self._obs,
            rewards=A.outcome(s) if done else (0.0, 0.0),
            done=done,
            truncated=bool(s.truncated),
            info={"action": act, "log": log},
        )

    # -- the driver ------------------------------------------------------

    def _advance(self) -> None:
        """Run the engine forward to the next real decision.

        Mirrors `game.play_game`'s loop exactly, because Phase 3's exit test is
        that a random policy here reproduces that loop bit for bit. Any
        divergence in control flow -- an extra invariant call that consumed
        randomness, a different pass ordering -- would show up as a hash
        mismatch there, which is the point of writing the test that way.
        """
        s = self.state
        assert s is not None
        while True:
            if A.is_terminal(s):
                self._legal, self._obs = [], None
                return
            seat = A.acting_seat(s)
            if seat < 0:
                self._legal, self._obs = [], None
                return
            legal = A.legal_actions(s, self.table, self.cfg, seat)
            if self.check:
                invariants.check(s)
                invariants.check_actions(s, self.table, self.cfg, seat, legal)
            if not legal:
                raise invariants.InvariantError(
                    f"seat {seat} to act with no legal actions "
                    f"on turn {s.turn}")

            if self.auto_pass and should_auto_pass(legal):
                A.apply(s, self.table, self.cfg, legal[0])
                self.auto_passes += 1
                continue

            self.n_legal_hist[len(legal)] += 1
            self._legal = legal
            self._obs = self.enc.encode(s, seat, legal)
            return

    # -- convenience -----------------------------------------------------

    def summary(self) -> dict:
        """Same shape as `game.play_game`'s return, so results are comparable."""
        s = self.state
        assert s is not None
        return {
            "winner": int(s.winner),
            "truncated": bool(s.truncated),
            "turns": int(s.turn),
            "steps": self.steps,
            "points": s.points.tolist(),
            "hash": s.state_hash(),
        }


def random_policy(rng: np.random.Generator):
    """Uniform over legal actions, by index.

    Draws exactly one integer per decision from `rng`, in the same order as
    `game.random_agent`, so the two are the same policy under the same seed.
    That equality is what the Phase 3 exit test checks.
    """
    def choose(obs: Obs) -> int:
        return int(rng.integers(obs.n_legal))
    return choose


def policy_from_agent(agent):
    """Adapt an engine-level agent `(state, table, cfg, seat, actions) -> Action`
    into an index policy, so the greedy baseline can drive the env unchanged."""
    def choose(env: "RiftboundEnv") -> int:
        s = env.state
        act = agent(s, env.table, env.cfg, env.to_move, env.legal)
        return env.legal.index(act)
    return choose


def play(env: RiftboundEnv, policies, seed: int, decks, rune_decks,
         battlefields, legends=None) -> dict:
    """Run one episode with per-seat index policies `policies[seat](obs)`."""
    obs = env.reset(seed, decks, rune_decks, battlefields, legends)
    while obs is not None:
        r = env.step(policies[obs.to_move](obs))
        obs = r.obs
    out = env.summary()
    out["rewards"] = A.outcome(env.state)
    out["auto_passes"] = env.auto_passes
    return out
