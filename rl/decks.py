"""Real decklists -> playable decks, with every approximation made visible.

The engine implements 17 spells and no unit text, so most real decks contain
cards it cannot fully play. There are three honest options and only one of them
is usable:

  drop them      the deck shrinks below 39 and stops being the same deck
  refuse         nothing is evaluable until the pool is complete
  **approximate** keep the size and shape, and report exactly what was faked

A deck is faked in **two different ways**, and conflating them is what made the
old coverage number wrong:

  substituted    the card is gone, replaced by a different card. Spells with no
                 DSL spec and all Gear -- the engine has nothing to resolve.
  approximated   the card is present with the right cost, domain and body, but
                 printed text or keywords the engine never reads. Every unit
                 with rules text is in here.

`coverage` counts only cards played **as printed**, so it now excludes the
second category. It previously did not: `v1_legal` accepted any card whose
keywords were in the v1 scope target and whose text ran under 90 characters,
which counted 317 of 327 unit slots as covered while executing none of their
text. Reported coverage fell from ~54% to the low 30s when this was fixed --
the decks did not get worse, the number got honest.

**A deck at 50% coverage is a proxy, not that deck**, and any evaluation of it
is a statement about the proxy. That caveat has to travel with the number,
which is why `DeckLoad` carries all three counts rather than a bare list of
card ids.
"""

from __future__ import annotations

import re

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sim"))
from engine.cards import find  # noqa: E402

from rl.config import ABILITY_KEYWORDS, DOMAINS  # noqa: E402
from rl.engine.cardtable import CardTable, read_decklist  # noqa: E402
from rl.engine.effects import (BF_ABILITIES, BF_STATICS,
                               ABILITIES, ABILITY_BORROWERS,  # noqa: E402
                               COND_EMPOWERED,
                               COND_LEGION, OP_EMPOWER, OP_LOOK_TOP,
                               ENTERS_READY_IF, PLAY_PERMISSIONS, SPECS,
                               STATICS, TEMPORARY_SUPPRESSORS, TOKEN_DOUBLERS)

_DOMAIN_ID = {d.lower(): i for i, d in enumerate(DOMAINS)}


@dataclass
class DeckLoad:
    name: str
    main: list[int]                 # card ids, length = printed deck size
    runes: list[int]                # domain ids
    battlefields: list[int]         # card ids, in printed order
    coverage: float                 # fraction of the MAIN DECK played as printed
    # 103.1 -- the Champion Legend, which every decklist declares and which is
    # in the Legend Zone from turn 1 (111). -1 when the list did not name one.
    legend: int = -1
    # 103.1.b's Champion Unit. Recorded but not yet read by the engine: the
    # Champion Zone (107.5) and its interactions are not built, and a field
    # that looks live but is never consulted is worse than an absent one, so
    # this is here only because the decklists carry it.
    champion: int = -1
    # **`coverage` deliberately excludes battlefields**, and that is a
    # reporting hazard, not a convenience: every deck in the corpus prints 3,
    # none of the 66 battlefield cards has an encoded ability, and every one of
    # them has rules text. So a deck at `coverage == 1.0` still has three cards
    # doing nothing, and a round robin cannot tell two decks apart when they
    # differ ONLY in battlefields -- which is exactly what `lillia-fae-fawn/v6`
    # and `v7` are, and they scored identically against all six opponents.
    #
    # The split is kept because `coverage` is what `--min-coverage` filters
    # training decks on, and folding battlefields in would drop every deck
    # below any useful threshold at once. `bf_coverage` carries the other half
    # so that anything REPORTING a number can report an honest one.
    bf_coverage: float = 0.0
    substituted: dict = field(default_factory=dict)   # printed name -> count
    # Kept in the deck, but with printed behaviour the engine ignores. This is
    # the category the old coverage number hid: the card is *there*, its cost
    # and body are right, and the text that makes it worth playing does
    # nothing. Tracked separately from `substituted` because the two fail
    # differently -- a substitution changes the deck, an approximation changes
    # the card.
    approximated: dict = field(default_factory=dict)   # printed name -> count
    missing: list[str] = field(default_factory=list)  # names not in the table

    def report(self) -> str:
        def top(d):
            return ", ".join(f"{n}x{c}" for n, c in
                             sorted(d.items(), key=lambda t: -t[1])[:4])
        return (f"{self.name}: {len(self.main)} cards, coverage "
                f"{self.coverage:.0%}"
                + (f", substituted {sum(self.substituted.values())} "
                   f"({top(self.substituted)})" if self.substituted else "")
                + (f", approximated {sum(self.approximated.values())} "
                   f"({top(self.approximated)})" if self.approximated else "")
                + (f", MISSING {self.missing}" if self.missing else ""))


def includable(table: CardTable, cid: int) -> bool:
    """Can this card sit in a deck without the engine choking on it?

    A **unit** always can. Every unit is a body with a cost, a domain and a
    Might, and the engine plays those correctly whether or not it executes the
    card's text -- so keeping Lillia as a vanilla 3-Might Calm body is strictly
    closer to the real deck than swapping her for a different 3-drop. Tokens
    are the exception: 185.3 makes them non-cards that only effects create.

    A **spell** cannot. Without a DSL spec there is nothing to resolve, so it
    has to be substituted. Gear likewise, until Gear exists at all.
    """
    if table.is_type(cid, "Unit"):
        return not table.is_token(cid)
    if table.is_type(cid, "Spell"):
        return table.names[cid] in SPECS
    if table.is_type(cid, "Gear"):
        # Gear is a permanent the engine can now play (149.2, base only), so a
        # gear whose text is transcribed goes in as itself. One without a spec
        # would sit on the board doing nothing, which is a worse lie than a
        # substitution, so it still has to be swapped out.
        return table.names[cid] in ABILITIES or table.names[cid] in STATICS
    return False


def _encodes_legion(name: str) -> bool:
    """Does this card's transcription actually carry the [Legion] gate?"""
    for ab in ABILITIES.get(name, ()):
        if any(op.cond == COND_LEGION for op in ab.ops):
            return True
    return any(st.cond == COND_LEGION for st in STATICS.get(name, ()))


def _encodes_predict(name: str) -> bool:
    """Does this card's transcription actually perform the [Predict]?

    Credited the same way [Legion] is, and NOT through `ABILITY_KEYWORDS`.
    Blanket-crediting a keyword to any card that has a spec is how Hunt and
    Vision were once forgiven on cards that never implemented them: the spec
    covers the rest of the text and the keyword silently rides along. 436.1
    makes Predicting a real action -- look at the top card, choose whether to
    Recycle it -- so the only honest test is whether an OP_LOOK_TOP is there.
    """
    for entry in list(ABILITIES.get(name, ())) + (
            [SPECS[name]] if name in SPECS else []):
        if any(op.op == OP_LOOK_TOP for op in entry.ops):
            return True
    return False


_PLAY_PERM_CLAUSE = re.compile(
    r"(?:You may play me|I can be played) to an? [^.]*\.?", re.I)


def _encodes_empower(name: str) -> bool:
    """Does this card's transcription carry the [Empower] activated ability?

    827.1.c.1 makes [Empower Cost] short for "[Cost]: Empower this", and the
    cost is different on every card -- {2 energy}, "{1 energy} or {Body rune}",
    "Kill a friendly unit". So the ENGINE implements the mechanism (the status,
    the once-only gate, the dependent-ability condition) while each card still
    has to state its own cost. That makes it a Deathknell-shaped keyword, not a
    Deflect-shaped one, and blanket-crediting it in `ENGINE_KEYWORDS` would
    pass ~35 cards that never transcribed a cost.
    """
    return any(op.op == OP_EMPOWER
               for ab in ABILITIES.get(name, ()) for op in ab.ops)


def _encodes_empowered(name: str) -> bool:
    """Does it carry the [Empowered] dependent ability (828.1.b.1)?"""
    return any(st.cond == COND_EMPOWERED for st in STATICS.get(name, ())) or \
        any(op.cond == COND_EMPOWERED
            for ab in ABILITIES.get(name, ()) for op in ab.ops)


def plays_as_printed(table: CardTable, cid: int) -> bool:
    """Does the engine execute **everything** this card says?

    The honest coverage question, and it is stricter than `includable` by a
    long way. This used to be `table.v1_legal(cid)` -- keywords in the v1 scope
    target plus text under 90 characters -- which counted 317 of 327 unit slots
    as covered while ignoring their rules text entirely. "When you play me,
    draw 1." is 25 characters. So is most of what makes a unit worth playing.

    Two exact checks replace the length heuristic:

      residual_text    anything printed beyond keywords needs a DSL spec
      unread_keywords  a keyword nothing consults is not being played
    """
    # A BATTLEFIELD is never `includable` -- it does not go in the main deck --
    # so it is judged on its own terms before that check. It counts as played
    # only when its text is transcribed -- as a static in `BF_STATICS`, as a
    # triggered ability in `BF_ABILITIES`, or both. Every one of the 66
    # battlefields prints rules text, so none is covered by default.
    if table.is_type(cid, "Battlefield"):
        name = table.names[cid]
        if name not in BF_STATICS and name not in BF_ABILITIES:
            return False
        return not table.unread_keywords(cid)
    if not includable(table, cid):
        return False
    if table.is_type(cid, "Spell"):
        return True                       # a spec transcribes the whole text
    name = table.names[cid]
    unread = set(table.unread_keywords(cid))
    if name in ABILITIES:
        # 808.1 -- [Deathknell] IS the ability, not a property alongside it, so
        # transcribing the ability is what implements the keyword.
        unread -= set(ABILITY_KEYWORDS)
    # [Legion] is a GATE on an ability or static rather than an ability of its
    # own, so it is credited only when the transcription actually carries the
    # gate. Blanket-crediting it the way Deathknell is credited would pass any
    # card that merely has a spec, including one that transcribed the effect
    # and quietly dropped the "if you've played another card this turn".
    if "Legion" in unread and _encodes_legion(name):
        unread.discard("Legion")
    if "Predict" in unread and _encodes_predict(name):
        unread.discard("Predict")
    if "Empower" in unread and _encodes_empower(name):
        unread.discard("Empower")
    if "Empowered" in unread and _encodes_empowered(name):
        unread.discard("Empowered")
    if unread:
        return False
    # Presence in ABILITIES or STATICS means the same thing presence in SPECS
    # does: the card's whole text is transcribed. Cards with one implemented
    # ability and one unimplemented one (Scuttle Crab: an ETB draw and a
    # Deathknell) are deliberately absent, so this stays an allowlist rather
    # than a guess.
    # A printed play-destination permission (806.3's exceptions) is executed
    # by `actions.play_destinations`, so it counts as implemented -- but it
    # only ever covers its OWN sentence. Ocean Drake says "You may play me
    # to an open battlefield" AND "you may return a non-Dragon unit to its
    # owner's hand"; forgiving the whole residual because the first half is
    # handled would credit a card whose second half does nothing. So strip
    # just that clause and let whatever is left be judged normally.
    residual = table.residual_text(cid)
    if name in PLAY_PERMISSIONS:
        residual = _PLAY_PERM_CLAUSE.sub("", residual).strip()
    # `TOKEN_DOUBLERS` sits alongside ABILITIES/STATICS for the same reason:
    # membership asserts that the card's whole text is the thing the engine
    # implements. That is true of Zilean, whose text is nothing but the
    # replacement clause. A future doubler with extra text would need an
    # ABILITIES entry for that text, exactly as any other card does.
    if residual and not (name in ABILITIES or name in STATICS
                         or name in TOKEN_DOUBLERS
                         or name in TEMPORARY_SUPPRESSORS
                         or name in ENTERS_READY_IF
                         or name in ABILITY_BORROWERS):
        return False
    # A card that creates a token it cannot play correctly is approximating,
    # exactly as a card whose own text is ignored would be. The Bird token
    # carries [Deflect] and the Gold token an activated ability with a "Kill
    # this" cost, neither of which the engine reads -- so Carrion Dredger
    # "playing a Bird" really plays a vanilla 1-Might body.
    return all(_token_ok(table, op.token)
               for spec in list(ABILITIES.get(name, ())) + ([SPECS[name]]
                                                            if name in SPECS else [])
               for op in spec.ops if op.token)


def _token_ok(table: CardTable, token_name: str) -> bool:
    """Is the token this op creates itself played as printed?"""
    try:
        tid = table.id_of(token_name)
    except KeyError:
        return False
    if table.unread_keywords(tid):
        return False
    return (not table.residual_text(tid)
            or token_name in ABILITIES or token_name in STATICS)


def _pool(table: CardTable) -> tuple[list[int], list[int]]:
    """Substitution pools -- what a missing card may be replaced *with*.

    Deliberately `plays_as_printed`, not `includable`: a substitute is already
    an approximation, and picking one whose own text is ignored would stack a
    second silent approximation on top of the first.
    """
    units = [c for c in range(table.n)
             if table.is_type(c, "Unit") and plays_as_printed(table, c)]
    spells = [c for c in range(table.n)
              if table.is_type(c, "Spell") and plays_as_printed(table, c)]
    return units, spells


def _closest(table: CardTable, pool: list[int], want: int) -> int:
    """Nearest implemented card by domain first, then cost.

    Domain leads because the rune deck is what gives a deck its identity: an
    off-colour substitute is often uncastable and dilutes exactly the archetype
    signal the substitution is supposed to preserve. Cost breaks ties so the
    curve still survives.
    """
    e, p = int(table.energy[want]), int(table.power[want])
    mask = int(table.domain_mask[want])
    return min(pool, key=lambda c: (
        0 if (int(table.domain_mask[c]) & mask) else 1,      # shares a domain
        abs(int(table.energy[c]) - e) + abs(int(table.power[c]) - p),
        int(table.energy[c]), c))


# A main deck is 40 cards (39 + the Champion in every list in the corpus).
# Anything far outside that is a parse failure rather than a deck -- a flat
# export with no section headers puts battlefields and runes in the main list
# too, which produced a "131-card deck" that crashed a fuzz 1,500 games in
# rather than failing at load.
LEGAL_MAIN = (30, 45)


def _split_flat(parsed: dict, table: CardTable) -> dict:
    """Route a headerless export into sections by CARD TYPE.

    Some exports are a bare list -- "3 Petal Pixie [UNL] 76" -- with no
    `MainDeck:` header, so everything lands in one bucket including the
    battlefields and the rune pool. The card table already knows what each one
    is, so classify rather than guess.
    """
    if any(k in parsed for k in ("Battlefields", "Runes")):
        return parsed
    main, bfs, runes = [], [], []
    for count, name in parsed.get("MainDeck", []):
        if name.lower().endswith("rune"):
            runes.append((count, name))
            continue
        card = find(name)
        cid = table._index.get(card.name) if card else None
        if cid is not None and table.is_type(cid, "Battlefield"):
            bfs.append((count, name))
        else:
            main.append((count, name))
    return {**parsed, "MainDeck": main, "Battlefields": bfs, "Runes": runes}


def load_deck(path: Path, table: CardTable) -> DeckLoad:
    """Read a decklist and make it playable, recording every substitution."""
    parsed = _split_flat(read_decklist(Path(path)), table)
    units, spells = _pool(table)

    main: list[int] = []
    subs: dict[str, int] = {}
    approx: dict[str, int] = {}
    missing: list[str] = []
    as_printed = 0

    for count, name in parsed.get("MainDeck", []):
        card = find(name)
        cid = table._index.get(card.name) if card else None
        if cid is None:
            missing.append(name)
            main.extend([_closest(table, units, units[0])] * count)
            subs[name] = subs.get(name, 0) + count
            continue
        if includable(table, cid):
            # The card itself goes in either way; the only question is whether
            # it counts as covered.
            main.extend([cid] * count)
            if plays_as_printed(table, cid):
                as_printed += count
            else:
                approx[name] = approx.get(name, 0) + count
            continue
        pool = spells if table.is_type(cid, "Spell") else units
        # Gear has no implementation at all yet, so it becomes a unit -- the
        # least wrong option, and counted as a substitution either way.
        main.extend([_closest(table, pool or units, cid)] * count)
        subs[name] = subs.get(name, 0) + count

    runes: list[int] = []
    for count, name in parsed.get("Runes", []):
        dom = name.lower().replace(" rune", "").strip()
        if dom in _DOMAIN_ID:
            runes.extend([_DOMAIN_ID[dom]] * count)
    if not runes:
        runes = [0] * 12

    bfs: list[int] = []
    for count, name in parsed.get("Battlefields", []):
        card = find(name)
        cid = table._index.get(card.name) if card else None
        if cid is not None:
            bfs.extend([cid] * count)

    def _one(section: str) -> int:
        """The single card named in a one-line section, or -1."""
        for _count, nm in parsed.get(section, []):
            card = find(nm)
            cid = table._index.get(card.name) if card else None
            if cid is not None:
                return int(cid)
        return -1

    total = len(main) or 1
    bf_ok = sum(1 for c in bfs if plays_as_printed(table, c))
    return DeckLoad(name=Path(path).parent.name + "/" + Path(path).stem,
                    main=main, runes=runes, battlefields=bfs,
                    coverage=as_printed / total,
                    bf_coverage=bf_ok / (len(bfs) or 1),
                    legend=_one("Legend"), champion=_one("Champion"),
                    substituted=subs,
                    approximated=approx, missing=missing)


def load_all(table: CardTable, root: Path | None = None,
             warn: bool = True) -> list[DeckLoad]:
    """Every decklist under `root` that parses to a plausible deck.

    A file that parses to a main deck far off 40 cards is rejected here, and
    loudly. It used to be admitted on `len(main) >= 10` and would then blow up
    deep inside a training run on `MAX_DECK` -- a parse failure surfacing as an
    engine crash thousands of games later, with nothing pointing at the file.
    """
    root = root or (ROOT / "decks")
    out, bad = [], []
    for f in sorted(Path(root).rglob("*.txt")):
        d = load_deck(f, table)
        if LEGAL_MAIN[0] <= len(d.main) <= LEGAL_MAIN[1]:
            out.append(d)
        elif len(d.main) >= 10:
            bad.append((d.name, len(d.main)))
    if bad and warn:
        import sys as _sys
        print(f"  skipped {len(bad)} unparseable decklist(s): "
              + ", ".join(f"{n} ({k} cards)" for n, k in bad),
              file=_sys.stderr)
    return out


def present(deck: DeckLoad, pick: int = 0,
            fallback: DeckLoad | None = None) -> int:
    """The battlefield `deck` presents, by 486.5: ONE of its own three.

    `pick` indexes the deck's printed battlefield list and wraps, so a caller
    sweeping 0..2 works on a deck that printed fewer than three. A deck that
    printed none borrows from `fallback` -- an incomplete decklist should not
    block a matchup -- and returns -1 if there is nothing anywhere.
    """
    pool = deck.battlefields or (fallback.battlefields if fallback else [])
    return pool[pick % len(pool)] if pool else -1


def matchup(a: DeckLoad, b: DeckLoad, rune_size: int = 12,
            n_bf: int = 2, picks: tuple[int, int] = (0, 0)
            ) -> tuple[list, list, list, list]:
    """Two DeckLoads as `game.new_game` arguments.

    486.5: **each player selects one of their OWN three battlefields**, and the
    two are placed simultaneously. With N_BF=2 that is exactly one from each
    deck, in seat order -- `bfs[0]` is what seat 0 brought.

    `picks` is which of its three each deck presents. It is a parameter rather
    than a fixed index because choosing is the decision the format is built
    around ([[riftbound-builds-for-bo3]]): a caller that wants to know which
    battlefield a deck should bring sweeps the 3x3 grid, and one that does not
    care gets each deck's first.

    This used to read deck A's FIRST battlefield and deck B's SECOND from a
    pool that fell back to whichever deck had any -- two bugs in one line. A
    deck with no battlefields listed supplied BOTH, and, worse, the pair
    depended on argument order: `matchup(a, b)` gave `[a[0], b[1]]` while
    `matchup(b, a)` gave `[b[0], a[1]]`. Every evaluator here averages over a
    seat swap to cancel the first-player advantage, so each half of that
    average was played on a DIFFERENT pair of battlefields. Presenting per deck
    makes the swap change only the seats, which is what it is for.
    """
    decks = [list(a.main), list(b.main)]
    runes = [(a.runes * 3)[:rune_size], (b.runes * 3)[:rune_size]]
    bfs = [present(a, picks[0], b), present(b, picks[1], a)][:n_bf]
    legends = [a.legend, b.legend]
    return decks, runes, bfs, legends
