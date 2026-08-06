"""Game state and the four-state calculator.

State is the single source of truth. Pilots never see it — they see
`render.view_for(state, player)`, which strips the other seat's private zones.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from .cards import Card

# Phases in turn order (rules 315-317).
AWAKEN, BEGINNING, CHANNEL, DRAW, MAIN, ENDING = (
    "Awaken", "Beginning", "Channel", "Draw", "Main", "Ending"
)
PHASE_ORDER = (AWAKEN, BEGINNING, CHANNEL, DRAW, MAIN, ENDING)

VICTORY_SCORE = 8      # rules 194.3, 485.3
BATTLEFIELDS_1V1 = 2   # rule 485.4 — each player brings 3, one each is used
RUNE_DECK_SIZE = 12    # rule 103.3.a

_ids = itertools.count(1)


def _new_id(prefix: str) -> str:
    return f"{prefix}{next(_ids)}"


@dataclass
class Rune:
    domain: str
    ready: bool = True
    id: str = field(default_factory=lambda: _new_id("r"))


@dataclass
class Permanent:
    """A unit or gear on the board."""
    card: Card
    controller: int
    location: str                 # "base:0" | "bf:0" | "bf:1"
    ready: bool = True
    damage: int = 0
    temporary: bool = False
    attached_to: str | None = None
    id: str = field(default_factory=lambda: _new_id("p"))

    @property
    def might(self) -> int:
        return self.card.might or 0

    @property
    def remaining(self) -> int:
        return self.might - self.damage


@dataclass
class Battlefield:
    card: Card
    index: int
    controller: int | None = None
    contested: bool = False
    # Facedown Zone: max occupancy 1 (107.3.b), private to its owner (107.3.f).
    facedown: tuple[int, Card] | None = None

    @property
    def key(self) -> str:
        return f"bf:{self.index}"


@dataclass
class ChainItem:
    """A played spell or activated ability awaiting resolution."""
    source: Card
    controller: int
    description: str
    id: str = field(default_factory=lambda: _new_id("c"))


@dataclass
class Pool:
    """Rune Pool — emptied at each Main Phase start and each turn end (167)."""
    energy: int = 0
    power: dict[str, int] = field(default_factory=dict)

    def clear(self) -> None:
        self.energy = 0
        self.power.clear()

    def total_power(self) -> int:
        return sum(self.power.values())


@dataclass
class PlayerState:
    seat: int
    name: str
    legend: Card
    champion: Card
    deck: list[Card] = field(default_factory=list)
    hand: list[Card] = field(default_factory=list)
    trash: list[Card] = field(default_factory=list)
    rune_deck: list[str] = field(default_factory=list)   # domains, ordered
    runes: list[Rune] = field(default_factory=list)      # channelled, in base
    pool: Pool = field(default_factory=Pool)
    points: int = 0
    champion_in_zone: bool = True
    burned_out: bool = False

    @property
    def ready_runes(self) -> list[Rune]:
        return [r for r in self.runes if r.ready]

    def ready_runes_of(self, domain: str) -> list[Rune]:
        return [r for r in self.runes if r.ready and r.domain == domain]


@dataclass
class GameState:
    players: tuple[PlayerState, PlayerState]
    battlefields: list[Battlefield]
    permanents: list[Permanent] = field(default_factory=list)
    chain: list[ChainItem] = field(default_factory=list)
    turn: int = 1
    active: int = 0
    phase: str = MAIN
    priority: int | None = 0
    focus: int | None = None
    showdown: bool = False        # a Showdown or Combat is in progress (308.1)
    seed: int = 0
    game_id: str = "game"
    winner: int | None = None

    # ---- the four states (rules 308-310) -------------------------------

    @property
    def is_open(self) -> bool:
        """Open iff no Chain exists (309.2)."""
        return not self.chain

    @property
    def is_neutral(self) -> bool:
        """Neutral iff no Showdown or Combat is in progress (308.2)."""
        return not self.showdown

    @property
    def state_name(self) -> str:
        return (f"{'Neutral' if self.is_neutral else 'Showdown'} "
                f"{'Open' if self.is_open else 'Closed'}")

    def playable_timings(self) -> set[str]:
        """Which timing tiers may legally be played right now.

        Closed State  -> Reaction only            (309.1.a)
        Showdown State-> Action or Reaction only  (308.1.a)
        Neutral Open  -> anything                 (310.1.a)

        Both restrictions apply, so a Showdown Closed state is Reaction-only by
        the stricter of the two.
        """
        from .cards import ACTION, PLAIN, REACTION
        if not self.is_open:
            return {REACTION}
        if not self.is_neutral:
            return {ACTION, REACTION}
        return {PLAIN, ACTION, REACTION}

    def timing_note(self) -> str:
        from .cards import PLAIN
        allowed = self.playable_timings()
        if PLAIN in allowed:
            return "any card"
        if len(allowed) == 2:
            return "[Action] and [Reaction] only"
        return "[Reaction] only"

    # ---- accessors ------------------------------------------------------

    def player(self, seat: int) -> PlayerState:
        return self.players[seat]

    def opponent_of(self, seat: int) -> PlayerState:
        return self.players[1 - seat]

    def at(self, location: str, seat: int | None = None) -> list[Permanent]:
        out = [p for p in self.permanents if p.location == location]
        if seat is not None:
            out = [p for p in out if p.controller == seat]
        return out

    def battlefield(self, index: int) -> Battlefield:
        return self.battlefields[index]

    def locations_for(self, seat: int) -> list[str]:
        return [f"base:{seat}"] + [bf.key for bf in self.battlefields]

    def check_winner(self) -> int | None:
        """A player wins at a cleanup with points >= Victory Score (194.2)."""
        qualified = [p for p in self.players if p.points >= VICTORY_SCORE]
        if not qualified:
            return None
        best = max(p.points for p in qualified)
        leaders = [p for p in qualified if p.points == best]
        return leaders[0].seat if len(leaders) == 1 else None
