"""Deck legality. Deterministic, and the only authority on counting.

Rule references are to the Riftbound Core Rules (2025-06-02), section 103.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .decklist import Deck
from .model import champion_tags

BANLIST_PATH = Path(__file__).resolve().parent.parent / "data" / "banlist.json"


@lru_cache(maxsize=1)
def _banlist() -> dict[str, str]:
    """Banned card name -> effective date, for Constructed.

    Bans arrive in waves, so an entry may carry its own "effective"; the
    file-level date is the fallback for the wave that has none.

    2v2-only bans are deliberately excluded: they are printing-specific and
    apply to a Mode of Play this tool does not model.
    """
    try:
        data = json.loads(BANLIST_PATH.read_text())
    except (OSError, ValueError):
        return {}
    default = data.get("effective", "unknown")
    return {e["name"]: e.get("effective", default)
            for e in data.get("constructed", [])}

MIN_MAIN_DECK = 40
RUNE_DECK_SIZE = 12
MAX_COPIES = 3
MAX_SIGNATURES = 3
# Organized-play update 2026-07-24: sideboard is 0 up to 10 cards (was 8).
MAX_SIDEBOARD = 10
# 103.4.a: the count is set by the Mode of Play, not by the core rules.
# Three is standard 1v1; override per format.
DEFAULT_BATTLEFIELDS = 3


@dataclass
class Issue:
    rule: str
    severity: str  # "error" | "warning"
    message: str

    def __str__(self) -> str:
        return f"[{self.severity.upper()} {self.rule}] {self.message}"


@dataclass
class Report:
    issues: list[Issue]

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def legal(self) -> bool:
        return not self.errors

    def render(self) -> str:
        if not self.issues:
            return "LEGAL - no issues."
        head = "LEGAL (with warnings)" if self.legal else "ILLEGAL"
        return head + "\n" + "\n".join(f"  {i}" for i in self.issues)


def validate(deck: Deck, battlefields: int = DEFAULT_BATTLEFIELDS) -> Report:
    issues: list[Issue] = []

    def err(rule, msg):
        issues.append(Issue(rule, "error", msg))

    def warn(rule, msg):
        issues.append(Issue(rule, "warning", msg))

    if deck.legend is None:
        err("103.1", "No Champion Legend declared.")
        return Report(issues)

    identity = deck.identity
    # 133.8.b: a faction tag (Yordle) is not a Champion Tag and cannot
    # satisfy 103.2.a.2 or 103.2.d.2, even when a Legend prints it.
    legend_tags = champion_tags(deck.legend.tags)

    # 103.2 - main deck size. 40 is both the legal minimum and the default
    # target: a smaller deck draws its best cards more often, so going over
    # requires a justification rather than being a neutral choice.
    if deck.main_count < MIN_MAIN_DECK:
        err("103.2", f"Main deck has {deck.main_count} cards; minimum is {MIN_MAIN_DECK}.")
    elif deck.main_count > MIN_MAIN_DECK:
        over = deck.main_count - MIN_MAIN_DECK
        warn(
            "consistency",
            f"Main deck is {deck.main_count} cards, {over} over the {MIN_MAIN_DECK}-card "
            f"minimum. Each extra card dilutes the deck; cut to {MIN_MAIN_DECK} unless "
            f"there is a stated reason to run more.",
        )

    # 103.2.a - chosen champion
    if deck.champion is None:
        err(
            "103.2.a",
            "No Chosen Champion. Declare one, or the deck contains no champion "
            "unit whose tag matches the Legend.",
        )
    else:
        ch = deck.champion
        if not ch.is_champion_unit:
            err(
                "103.2.a.2",
                f"Chosen Champion {ch.name} is a {ch.type}"
                f"{'/' + ch.supertype if ch.supertype else ''}, not a champion unit.",
            )
        elif not (legend_tags & champion_tags(ch.tags)):
            err(
                "103.2.a.2",
                f"Chosen Champion {ch.name} (tags: {', '.join(ch.tags) or 'none'}) "
                f"shares no champion tag with Legend {deck.legend.name} "
                f"(champion tags: {', '.join(sorted(legend_tags)) or 'none'}).",
            )
        if ch.name not in deck.main:
            err("103.2", f"Chosen Champion {ch.name} is not counted in the main deck.")

    # 103.2.b - copy limit
    for name, n in deck.main.items():
        if n > MAX_COPIES:
            err("103.2.b", f"{n} copies of {name}; maximum is {MAX_COPIES}.")

    # 103.1.b / 103.2.c - domain identity
    for name, _ in deck.main.items():
        c = deck.card(name)
        if not c.legal_under(identity):
            err(
                "103.1.b.4",
                f"{c.name} ({'+'.join(c.domains)}) is outside the deck's domain "
                f"identity ({'+'.join(sorted(identity)) or 'none'}).",
            )
    for name in deck.battlefields:
        c = deck.card(name)
        if not c.legal_under(identity):
            err("103.4.b", f"Battlefield {c.name} is outside the domain identity.")

    # 103.2.d - signature cards
    sigs = Counter()
    for name, n in deck.main.items():
        if deck.card(name).is_signature:
            sigs[name] += n
    total_sigs = sum(sigs.values())
    if total_sigs > MAX_SIGNATURES:
        err(
            "103.2.d.1",
            f"{total_sigs} signature cards; maximum is {MAX_SIGNATURES} total "
            f"({', '.join(f'{v}x {k}' for k, v in sigs.items())}).",
        )
    for name in sigs:
        c = deck.card(name)
        if not (legend_tags & champion_tags(c.tags)):
            err(
                "103.2.d.2",
                f"Signature card {c.name} does not carry the Legend's champion tag.",
            )

    # 103.3 - rune deck
    if deck.rune_count != RUNE_DECK_SIZE:
        err("103.3.a", f"Rune deck has {deck.rune_count} runes; must be exactly {RUNE_DECK_SIZE}.")
    for name in deck.runes:
        c = deck.card(name)
        if not c.legal_under(identity):
            err("103.3.a.1", f"Rune {c.name} is outside the domain identity.")

    # 103.4 - battlefields
    if deck.battlefield_count != battlefields:
        sev = err if deck.battlefield_count > battlefields else warn
        sev(
            "103.4.a",
            f"{deck.battlefield_count} battlefields; this Mode of Play expects "
            f"{battlefields}.",
        )

    # Sideboard (organized-play rules, 2026-07-24): 0 up to 10 cards. Domain
    # identity applies, and the 3-copy limit spans main deck + sideboard
    # COMBINED — the classic deck-check trap. Battlefields are legal here.
    if deck.sideboard_count > MAX_SIDEBOARD:
        err(
            "sideboard",
            f"Sideboard has {deck.sideboard_count} cards; maximum is {MAX_SIDEBOARD}.",
        )
    for name, n in deck.sideboard.items():
        c = deck.card(name)
        if not c.legal_under(identity):
            err(
                "sideboard",
                f"Sideboard card {c.name} ({'+'.join(c.domains)}) is outside the "
                f"deck's domain identity.",
            )
        combined = n + deck.main.get(name, 0)
        if combined > MAX_COPIES:
            err(
                "103.2.b",
                f"{combined} total copies of {name} across main deck + sideboard; "
                f"maximum is {MAX_COPIES} combined.",
            )
    sb_sigs = sum(
        n for name, n in deck.sideboard.items() if deck.card(name).is_signature
    )
    main_sigs = sum(
        n for name, n in deck.main.items() if deck.card(name).is_signature
    )
    if main_sigs + sb_sigs > MAX_SIGNATURES:
        warn(
            "103.2.d",
            f"{main_sigs} main + {sb_sigs} sideboard signature cards: any "
            f"post-board configuration may not exceed {MAX_SIGNATURES} signatures "
            f"in the deck — plan the swaps so the total stays legal.",
        )

    # Banned cards. Not a core rule - it is organized-play policy, and it moves,
    # so it lives in data/banlist.json rather than in code. Every zone counts:
    # battlefields and sideboard cards are the ones that survive a copied list.
    banned = _banlist()
    if banned:
        zones = (
            ("main deck", deck.main),
            ("sideboard", deck.sideboard),
            ("battlefields", Counter(deck.battlefields)),
            ("runes", deck.runes),
        )
        seen: set[str] = set()
        for zone, pile in zones:
            for name in pile:
                if name in banned and name not in seen:
                    seen.add(name)
                    err(
                        "banlist",
                        f"{name} is BANNED in Constructed (effective {banned[name]}) "
                        f"and is in the {zone}.",
                    )
        if deck.legend is not None and deck.legend.name in banned:
            err(
                "banlist",
                f"Legend {deck.legend.name} is BANNED in Constructed "
                f"(effective {banned[deck.legend.name]}).",
            )

    return Report(issues)


def repair_prompt(report: Report, deck: Deck) -> str:
    """Feedback block for the model's single repair pass."""
    return (
        "The decklist you produced is not legal. Fix ONLY these problems and "
        "return the complete corrected decklist in the same format. Do not "
        "restate your reasoning.\n\n"
        + "\n".join(f"- {i}" for i in report.errors)
        + f"\n\nCurrent list ({deck.main_count} main / {deck.rune_count} runes / "
        f"{deck.battlefield_count} battlefields):\n{deck.to_text()}"
    )
