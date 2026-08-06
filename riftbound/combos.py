"""Mechanical interaction detection.

This is a heuristic pattern matcher, not a rules engine. It reads card text,
tags each card with traits, and reports pairs whose traits are known to
interact. It finds CANDIDATES — it does not know whether a combo is good, and
it cannot see interactions that depend on rules text it has no pattern for.

Treat output the way you'd treat the role buckets in analyze.py: a prompt for
your own judgement, never a conclusion. Everything it prints is labelled with
the trait that triggered it so you can check the reasoning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations

from .model import Card

# ---------------------------------------------------------------------------
# Traits. Each is (name, predicate). Predicates read normalized card text.
# ---------------------------------------------------------------------------

TRAIT_PATTERNS: dict[str, list[str]] = {
    # token production / payoff
    "makes_token": [r"play (a|two|three|four|an additional) .{0,40}token"],
    "token_payoff": [r"your token units", r"when you play a token unit"],
    "makes_temporary": [r"token with \[temporary\]", r"give it \[temporary\]"],
    # A payoff must BENEFIT from Temporary units existing. Merely printing
    # "token with [Temporary]" makes a card a source, not a payoff, and
    # matching that pairs every token maker with every other token maker.
    "temporary_payoff": [
        r"for each .{0,30}\[temporary\]",
        r"\[temporary\] effects .{0,30}don't trigger",
        r"(if|when) at least one of them has \[temporary\]",
        r"units here with \[temporary\]",
        r"less for each friendly unit with \[temporary\]",
    ],
    # replay / blink
    "blinks_unit": [r"banish a (friendly )?unit, then .{0,30}plays? it"],
    "plays_unit_from_trash": [r"play a unit from your trash"],
    "strong_etb": [r"when you play me,"],
    "deathknell": [r"\[deathknell\]"],
    # a spell that puts a unit onto the board covers two card types at once
    "spell_that_plays_unit": [r"play a unit", r"plays? it", r"play a .{0,25}unit token"],
    # movement
    "move_trigger": [r"when i move", r"when i move to", r"when a unit moves from"],
    "move_enabler": [r"move (a|any number of|up to \w+) friendly unit", r"move me to",
                     r"move a different unit", r"\[ganking\]"],
    # combat state pairs
    "stuns": [r"\[stun\]", r"stun a unit", r"stun an enemy"],
    "stun_payoff": [r"stunned (enemy )?unit"],
    "buffs": [r"buff (a|me|all|another|it)", r"\[buff\]"],
    "buff_payoff": [r"buffed", r"spend (a|my|its) buff"],
    "empowers": [r"\[empower\]", r"empower (a|me|another|something)"],
    "empowered_payoff": [r"\[empowered\]", r"if this is \[empowered\]", r"that's \[empowered\]"],
    "mighty_payoff": [r"\[mighty\]"],
    "hidden": [r"\[hidden\]"],
    "hidden_payoff": [r"with \[hidden\]", r"facedown"],
    # equipment
    "equipment": [r"\[equip\]"],
    "equipment_payoff": [r"\[weaponmaster\]", r"equipment attached", r"attach an? .{0,20}equipment"],
    # gear
    "gear_payoff": [r"\d+ or more other gear", r"for each friendly gear", r"if you control a mech",
                    r"if you control two or more gear", r"non-token gear"],
    # resources
    "readies_legend": [r"ready your legend", r"ready or exhaust a legend"],
    "legend_ability": [],   # filled in for Legends with an Exhaust ability
    "rune_ramp": [r"channel \d+ rune", r"ready (up to )?\d+ (friendly )?runes", r"\[add\]"],
    "cost_reduction": [r"costs? \{?\d* ?energy\}? less", r"cost .{0,20}less", r"ignoring its cost",
                       r"ignoring its energy cost"],
    "expensive": [],        # filled in by cost, not text
    # sacrifice loops
    "kills_own": [r"kill a friendly", r"kill one of their units", r"kill a unit you control",
                  r"as an additional cost .{0,30}kill"],
    "dies_payoff": [r"\[deathknell\]", r"when another friendly unit dies", r"when a friendly unit dies",
                    r"the first time a friendly unit dies"],
    # scoring
    "conquer_trigger": [r"when (i|you) conquer"],
    "hold_trigger": [r"when (i|you) hold"],
    "scores_point": [r"score 1 point", r"you win the game"],
}


@dataclass
class Rule:
    name: str
    a: str
    b: str
    why: str
    same_card_ok: bool = False


# Ordered roughly by how reliably the pattern means what it says.
RULES: list[Rule] = [
    Rule("Token engine", "makes_token", "token_payoff",
         "one card makes the bodies, the other turns them into value"),
    Rule("Persistent tokens", "makes_temporary", "temporary_payoff",
         "Temporary units die before scoring, so anything that shuts that off or "
         "rewards them mid-turn is what makes them matter"),
    Rule("Blink loop", "blinks_unit", "strong_etb",
         "replaying the unit re-triggers its enter-the-board ability"),
    Rule("Recursion", "plays_unit_from_trash", "deathknell",
         "the unit's death effect pays you, then you get the unit back"),
    Rule("Movement engine", "move_enabler", "move_trigger",
         "one card supplies the movement the other is waiting for"),
    Rule("Stun package", "stuns", "stun_payoff",
         "the payoff only reads as text until something applies the stun"),
    Rule("Buff package", "buffs", "buff_payoff",
         "the payoff needs a buff on the board to do anything"),
    Rule("Empower package", "empowers", "empowered_payoff",
         "external empower sources turn the payoff on earlier than paying its own cost"),
    Rule("Big-body payoff", "mighty_payoff", "mighty_payoff",
         "Mighty is 5+ Might; these want large units on board", same_card_ok=False),
    Rule("Equipment package", "equipment", "equipment_payoff",
         "the payoff scales with attached Equipment"),
    Rule("Hidden package", "hidden", "hidden_payoff",
         "the payoff counts or reveals facedown cards"),
    Rule("Gear payoff", "gear_payoff", "gear_payoff",
         "these count gear; run enough cheap gear to switch them on"),
    Rule("Legend re-use", "readies_legend", "legend_ability",
         "readying the Legend gets a second activation of its Exhaust ability"),
    Rule("Sacrifice loop", "kills_own", "dies_payoff",
         "one card provides the deaths the other is paid for"),
    Rule("Ramp into top end", "rune_ramp", "expensive",
         "the ramp exists to deploy the expensive card ahead of schedule"),
    Rule("Cost reduction", "cost_reduction", "expensive",
         "the discount is worth a card only if there is something big to discount"),
]


def traits_of(card: Card, legend: Card | None = None) -> set[str]:
    text = (card.text or "").lower()
    found: set[str] = set()
    for trait, pats in TRAIT_PATTERNS.items():
        if any(re.search(p, text) for p in pats):
            found.add(trait)

    # Structural traits that text patterns cannot see.
    if card.is_a("Spell") and "spell_that_plays_unit" in found:
        found.add("dual_type_turn")     # covers 'spell' and 'unit' in one card
    if card.is_a("Gear") and (card.energy or 0) <= 1:
        found.add("cheap_gear")
    if (card.energy or 0) >= 6:
        found.add("expensive")
    if (card.might or 0) >= 5:
        found.add("big_body")
    if card.is_a("Gear") and card.is_a("Unit"):
        found.add("dual_unit_gear")
    if card.is_legend and "exhaust:" in text:
        found.add("legend_ability")
    # A token-producing effect does not satisfy "non-token" requirements.
    if "makes_token" in found and card.is_a("Spell"):
        found.add("makes_token_only")
    return found


@dataclass
class Finding:
    rule: str
    cards: tuple[str, ...]
    why: str
    phase: str
    cost: int

    def render(self) -> str:
        return f"  [{self.phase:6}] {' + '.join(self.cards)}\n      {self.rule}: {self.why}"


def _phase(total_cost: int) -> str:
    if total_cost <= 4:
        return "early"
    if total_cost <= 8:
        return "mid"
    return "late"


def find_combos(
    cards: list[Card],
    legend: Card | None = None,
    limit_per_rule: int = 6,
) -> list[Finding]:
    """Detect interacting pairs among `cards`.

    `legend` is included as a participant so Legend abilities show up in the
    results, which is where a surprising number of the real interactions live.
    """
    pool = list(cards)
    if legend is not None:
        pool = [legend] + pool

    tmap = {c.name: traits_of(c, legend) for c in pool}
    by_name = {c.name: c for c in pool}

    findings: list[Finding] = []
    for rule in RULES:
        hits: list[Finding] = []
        for x, y in combinations(pool, 2):
            tx, ty = tmap[x.name], tmap[y.name]
            forward = rule.a in tx and rule.b in ty
            backward = rule.b in tx and rule.a in ty
            if not (forward or backward):
                continue
            if rule.a == rule.b and x.name == y.name:
                continue
            cost = (x.energy or 0) + (y.energy or 0)
            hits.append(
                Finding(rule.name, (x.name, y.name), rule.why, _phase(cost), cost)
            )
        hits.sort(key=lambda f: f.cost)
        findings.extend(hits[:limit_per_rule])
    return findings


def special_findings(cards: list[Card], legend: Card | None = None) -> list[str]:
    """Named interactions worth calling out explicitly.

    These encode specific card-text readings that the generic rules miss, and
    each one states the reasoning so it can be checked.
    """
    out: list[str] = []
    names = {c.name for c in cards}
    pool = list(cards) + ([legend] if legend else [])

    # A spell that plays a non-token unit covers two card types with one card.
    duals = [
        c for c in cards
        if c.is_a("Spell")
        and re.search(r"(play a unit|plays? it)", (c.text or "").lower())
        and "token" not in (c.text or "").lower()
    ]
    if duals:
        out.append(
            "Spells that play a NON-TOKEN unit — one card counts as both a spell "
            "and a unit for 'played all three types this turn' effects:\n    "
            + ", ".join(sorted(c.name for c in duals))
        )

    token_units = [
        c for c in cards
        if c.is_a("Spell") and re.search(r"unit token", (c.text or "").lower())
    ]
    if token_units and duals:
        out.append(
            "TRAP: these play TOKEN units, which do NOT satisfy 'non-token unit' "
            "requirements:\n    " + ", ".join(sorted(c.name for c in token_units))
        )

    # Dual-type cards satisfy two "played a X this turn" clauses at once.
    dual = [c for c in cards if len(c.all_types) > 1]
    if dual:
        out.append(
            "DUAL-TYPE CARDS — these count as EVERY type they print, so one card "
            "satisfies two 'played a <type> this turn' clauses and is counted by "
            "every effect that tallies either type:\n    "
            + ", ".join(f"{c.name} ({c.type_line})" for c in dual)
        )

    # A spell that plays a dual-type unit covers THREE card-type clauses with
    # a single card. Worth calling out on its own: it is the difference between
    # a three-card turn and a one-card turn.
    if dual and duals:
        dual_units = [c for c in dual if c.is_a("Unit")]
        if dual_units:
            out.append(
                "ONE-CARD TRIPLE — playing one of these spells on one of these "
                "dual-type units counts as playing a spell AND a unit AND a gear "
                "in a single card:\n    spells: "
                + ", ".join(sorted(c.name for c in duals))
                + "\n    targets: "
                + ", ".join(f"{c.name} ({c.type_line})" for c in dual_units)
                + "\n    This satisfies every 'played all three types this turn' "
                "clause by itself."
            )

    # 0-cost gear + a Legend that pays rune costs for gear = a free gear play.
    free_gear = [c for c in cards if c.is_a("Gear") and (c.energy or 0) == 0 and (c.power or 0) > 0]
    if free_gear and legend and re.search(r"only to play gear", (legend.text or "").lower()):
        out.append(
            f"FREE GEAR EVERY TURN: {legend.name} adds a rune usable only on gear, "
            f"and these cost 0 energy with a Power cost:\n    "
            + ", ".join(sorted(c.name for c in free_gear))
            + "\n    Net cost of playing one: nothing."
        )

    # Temporary tokens cannot hold for points; find the cards that fix that.
    if any("temporary" in (c.text or "").lower() for c in cards):
        fixers = [
            c for c in cards
            if re.search(r"\[temporary\] effects .{0,30}don't trigger", (c.text or "").lower())
        ]
        note = (
            "Temporary units die at the start of your Beginning Phase, BEFORE the "
            "Scoring Step (rules 315.2.a.1 / 315.2.b.1), so they can never Hold for "
            "a point."
        )
        if fixers:
            note += " Cards that switch that off: " + ", ".join(c.name for c in fixers)
        else:
            note += " Nothing in this list switches that off."
        out.append(note)

    return out


def render(findings: list[Finding], specials: list[str]) -> str:
    L = [
        "COMBO DETECTION — heuristic pattern match over card text.",
        "Finds candidates, not conclusions. Verify each against the actual card.",
        "",
    ]
    if specials:
        L.append("== Notable interactions ==")
        for s in specials:
            L.append("  * " + s)
        L.append("")

    for phase in ("early", "mid", "late"):
        rows = [f for f in findings if f.phase == phase]
        if not rows:
            continue
        label = {"early": "EARLY (combined cost <=4)",
                 "mid": "MID (5-8)",
                 "late": "LATE (9+)"}[phase]
        L.append(f"== {label} ==")
        seen = set()
        for f in sorted(rows, key=lambda f: (f.rule, f.cost)):
            key = (f.rule, f.cards)
            if key in seen:
                continue
            seen.add(key)
            L.append(f.render())
        L.append("")
    if not findings:
        L.append("No interacting pairs matched. That is a result worth noticing.")
    return "\n".join(L)
