"""Every v1 scope knob, in one place.

The plan (PLAN.md §3) freezes v1 scope deliberately, and the main way a project
like this dies is re-opening that scope mid-build. Keeping the knobs here rather
than scattered through the engine means a scope change is a diff you can read.

Two of these are curriculum values rather than rules values -- `victory_score` and
`turn_cap`. The real game is 8 points (rule 194.3); we train at 3 first because
episodes get ~3x shorter and credit assignment over 40 decisions is far easier
than over 150. Anneal with `Config.at_victory_score(5)`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------
# Every bracketed keyword in the card pool, ordered. Index in this tuple IS the
# bit position in a card's keyword mask, so DO NOT reorder -- append only.
ALL_KEYWORDS = (
    "Reaction", "Action", "Empowered", "Equip", "Hidden", "Deflect", "Empower",
    "Ganking", "Add", "Accelerate", "Temporary", "Tank", "Deathknell", "Repeat",
    "Flow", "Assault", "Shield", "Stun", "Ambush", "Weaponmaster", "Legion",
    "Vision", "Mighty", "Buff", "Hunt", "Predict", "Backline", "Unique",
)

# The v1 SCOPE TARGET -- keywords v1 intends to reach. This is an aspiration
# and a filter for the v0 vanilla pool. It is **not** a claim that the engine
# implements them, and reading it as one is what let 169 deck slots be counted
# as fully covered while carrying a keyword nothing ever executes.
#
# `Hidden` and `Deathknell` are in scope deliberately against the "keep v1
# simple" instinct -- see PLAN.md §3. Hidden appears in all ten of the repo's
# decks and is the Facedown Zone mechanic the whole belief experiment rests on
# (PLAN.md Phase 6); cutting it would cut the point of the project.
TIER1_KEYWORDS = (
    "Action", "Reaction", "Tank", "Backline", "Shield", "Assault", "Legion",
    "Mighty", "Deflect", "Temporary", "Hidden", "Deathknell",
)

# The keywords the engine ACTUALLY reads, each with the line that reads it.
# Anything here must be greppable; anything not here is ignored at runtime, so
# a card carrying it is not being played as printed no matter how short its
# text is. Keep this list honest -- it is the input to the coverage metric, and
# a coverage number that flatters itself is worse than no number.
ENGINE_KEYWORDS = {
    "Temporary": "phases.py -- expires in the Beginning Phase",
    "Tank":      "combat._tiers -- assigned combat damage first",
    "Backline":  "combat._tiers -- assigned combat damage last",
    "Ganking":   "combat.can_move -- may move battlefield to battlefield",
    "Hidden":    "chain.hideable -- may be hidden in the Facedown Zone",
    "Accelerate": "actions.legal_actions -- the A_PLAY_AT_FAST variant, and "
                  "cost.accelerate_cost for the additional cost (805)",
    "Shield":    "combat.combat_role_bonus -- +X Might while a defender (814)",
    "Buff":      "combat.might -- a Buff counter is +1 Might (702/703)",
    "Assault":   "combat.combat_role_bonus -- +X Might while an attacker (807)",
    "Action":    "effects.SPEED_ACTION, via a card's DSL spec",
    "Reaction":  "effects.SPEED_REACTION, via a card's DSL spec",
}
# Keywords that ARE a triggered ability rather than a passive property --
# 808.1 makes [Deathknell] short for "When I die, [Effect]", and the effect is
# the card's own text. There is no separate keyword implementation to check: a
# card carrying one is played as printed exactly when its ability is
# transcribed in `effects.ABILITIES`, which `decks.plays_as_printed` tests.
ABILITY_KEYWORDS = ("Deathknell", "Vision", "Hunt")

# In scope, but nothing executes them yet. Named rather than merely absent so
# the gap is legible: Deathknell alone is 94 deck slots and is a trigger, so it
# lands with the triggered-ability machinery rather than on its own.
UNIMPLEMENTED_TIER1 = tuple(k for k in TIER1_KEYWORDS if k not in ENGINE_KEYWORDS)

# Keywords that are pure combat-damage assignment ordering (PLAN.md §1.3.b).
# "I must be assigned combat damage first" / "...last".
DAMAGE_ORDER_FIRST = "Tank"
DAMAGE_ORDER_LAST = "Backline"

DOMAINS = ("Body", "Calm", "Chaos", "Fury", "Mind", "Order")
CARD_TYPES = ("Unit", "Spell", "Gear", "Battlefield", "Legend", "Rune")


@dataclass(frozen=True)
class Config:
    # --- rules constants (real values; do not treat as tunable) -------------
    victory_score_full: int = 8       # rule 194.3
    battlefields_in_play: int = 2     # rule 485.4 -- one chosen by each player
    battlefields_per_player: int = 3  # each player brings 3, burns one per game
    rune_deck_size: int = 12          # rule 103.3.a
    channel_per_turn: int = 2         # rule 315.3.b
    second_player_bonus_runes: int = 1  # rule 485.7

    # --- curriculum --------------------------------------------------------
    # Anneal 5 -> 8. NOT 3 any more: the Final Point restriction (471.1.b)
    # applies once a player is within one point of victory, which at
    # victory_score=3 means from 2 points onward -- most of the game. That
    # turns an endgame rule into a permanent one and makes the curriculum a
    # materially different game. Measured: greedy beats random 97.2% at
    # victory 8 but only 77.3% at victory 3, because the restriction dominates
    # there rather than gating the finish.
    victory_score: int = 5            # anneal 5 -> 8
    turn_cap: int = 30                # truncate -> reward 0

    # --- action space ------------------------------------------------------
    max_actions: int = 64             # assert on overflow, log the distribution
    # Ordinary movement is base <-> battlefield ONLY; lateral battlefield-to-
    # battlefield movement requires [Ganking]. Confirmed with the project owner.
    lateral_movement_needs_ganking: bool = True
    # v0 plays units only. Spells need the effect DSL, which is deliberately
    # built after combat so its hooks are derived rather than guessed.
    units_only: bool = True
    # In v1 the engine solves damage assignment instead of exposing it to the
    # policy: the subgame is separable and reduces to an ordered exact-lethal
    # knapsack, so there is nothing to learn. PLAN.md §5.3 gotcha 8.
    engine_solves_damage_assignment: bool = True

    # --- reward ------------------------------------------------------------
    # Terminal-only, +/-1. gamma=1.0 makes the critic a literal win-probability
    # predictor, which is the deck-evaluator deliverable (PLAN.md §1.2).
    gamma: float = 1.0
    potential_shaping: bool = False   # ablatable; off by default

    def at_victory_score(self, score: int) -> "Config":
        return replace(self, victory_score=score)


DEFAULT = Config()
