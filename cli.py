#!/usr/bin/env python3
"""Riftbound deckbuilding toolkit.

    python cli.py sync                          refresh the card database
    python cli.py sets                          what is in the database
    python cli.py legends [--search vi]         list legends
    python cli.py pool "Vi - Piltover Enforcer" show the legal card pool
    python cli.py shortlist <legend> [...]      stage-1 prompt
    python cli.py build <legend> [...]          stage-2 prompt
    python cli.py check deck.txt                legality only, no LLM
    python cli.py stats deck.txt                computed statistics, no LLM
    python cli.py analyze deck.txt [...]        review prompt
    python cli.py combos deck.txt               detect card interactions
    python cli.py critique deck.txt             deterministic self-audit
    python cli.py iterate deck.txt              refinement prompt (audit + protocol)
    python cli.py combos --legend "Ornn - ..."   scan a whole legal pool
    python cli.py rules 103 | rules -s "Legion" read the rules

Prompt-emitting commands print to stdout. Pipe them, or use --out.
Add --meta to enable the meta layer (data/archetypes.md); it is off by default.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from riftbound import DATA_DIR
from riftbound import analyze as analyze_mod
from riftbound import combos as combos_mod
from riftbound import critique as critique_mod
from riftbound import meta as meta_mod
from riftbound import prompt as prompt_mod
from riftbound import rules as rules_mod
from riftbound import sync as sync_mod
from riftbound.db import AmbiguousCard, CardDB, CardNotFound
from riftbound.decklist import DecklistError, parse
from riftbound.model import render_pool
from riftbound.validate import DEFAULT_BATTLEFIELDS, validate


def _emit(text: str, out: str | None):
    if out:
        Path(out).write_text(text)
        print(f"wrote {len(text)} chars (~{len(text)//4} tokens) to {out}", file=sys.stderr)
    else:
        print(text)


def _meta(args, db: CardDB) -> meta_mod.MetaContext:
    ctx = meta_mod.load(DATA_DIR / "archetypes.md", enabled=args.meta)
    if args.meta and not ctx.archetypes:
        print(
            f"warning: --meta requested but {ctx.source_path} has no archetypes; "
            "prompts will forbid matchup claims.",
            file=sys.stderr,
        )
    if db.sets:
        newest = max(db.sets, key=lambda s: s.get("published_on") or "")
        w = meta_mod.staleness_warning(
            ctx, newest.get("name", "?"), newest.get("published_on") or ""
        )
        if w:
            print(f"warning: {w}", file=sys.stderr)
    return ctx


def _legend(db: CardDB, name: str):
    """Resolve a Legend, accepting a champion unit as a stand-in.

    Asking for "a Jinx deck" naturally means naming the champion, not the
    Legend, so a champion unit resolves to the Legend sharing its tag whenever
    that is unambiguous.
    """
    try:
        card = db.get(name)
    except (CardNotFound, AmbiguousCard) as e:
        sys.exit(f"error: {e}")

    if card.is_legend:
        return card

    if card.is_champion_unit:
        matches = [l for l in db.legends if set(l.tags) & set(card.tags)]
        if len(matches) == 1:
            print(
                f"note: {card.name} is a champion unit; using Legend "
                f"{matches[0].name} ({'+'.join(matches[0].domains)}).",
                file=sys.stderr,
            )
            return matches[0]
        if len(matches) > 1:
            opts = "\n  ".join(f"{l.name} ({'+'.join(l.domains)})" for l in matches)
            sys.exit(
                f"error: {card.name} matches several Legends. Pick one:\n  {opts}"
            )
        sys.exit(
            f"error: no Legend shares a tag with {card.name} "
            f"(tags: {', '.join(card.tags) or 'none'})."
        )

    sys.exit(f"error: {card.name} is a {card.type}, not a Legend or champion unit.")


def _implied_champion(db: CardDB, name: str):
    """If the user named a champion unit as the deck's focus, honour it."""
    try:
        c = db.get(name)
    except Exception:
        return None
    return c if c.is_champion_unit else None


def _load_deck(db: CardDB, path: str):
    try:
        return parse(Path(path).read_text(), db, name=Path(path).stem)
    except DecklistError as e:
        sys.exit(f"error: {e}")


# ---------- commands ----------


def cmd_sync(args):
    sync_mod.sync(DATA_DIR)


def cmd_sets(args):
    db = CardDB.load(DATA_DIR)
    print(f"fetched {db.fetched_at}  |  {len(db.cards)} unique cards")
    for s in sorted(db.sets, key=lambda s: s.get("published_on") or "", reverse=True):
        print(f"  {s['set_id']:5} {s['name'][:44]:46} {s['card_count']:4}  "
              f"{str(s.get('published_on'))[:10]}")


def cmd_upcoming(args):
    """Show the unreleased sets on disk and whether they are currently visible."""
    from riftbound import upcoming
    print(upcoming.status())
    if upcoming.set_files():
        print(f"\n  set {upcoming.ENV_FLAG}=1 to include them everywhere "
              f"(deckbuilding, ratings, the RL engine) while scripting:")
        print(f"    {upcoming.ENV_FLAG}=1 python cli.py pool <legend>")
        print(f"    {upcoming.ENV_FLAG}=1 python -m rl.tests.test_judge")
        print("\n  each set becomes visible on its own released_on with no "
              "flag and no code change.")
    else:
        print(f"\n  add one as data/upcoming/<SET_ID>.json -- see "
              f"riftbound/upcoming.py for the schema.")


def cmd_legends(args):
    db = CardDB.load(DATA_DIR)
    rows = db.legends
    if args.search:
        q = args.search.lower()
        rows = [c for c in rows if q in c.name.lower() or any(q in t.lower() for t in c.tags)]
    for c in sorted(rows, key=lambda c: c.name):
        print(f"{c.name:44} {'+'.join(c.domains):16} tags: {', '.join(c.tags)}")
    print(f"\n{len(rows)} legends", file=sys.stderr)


def cmd_pool(args):
    db = CardDB.load(DATA_DIR)
    pool = db.legal_pool(_legend(db, args.legend))
    print(f"# {pool.legend.name} — identity {'+'.join(sorted(pool.identity))}")
    print(f"# champions {len(pool.champion_options)} | main-deck pool "
          f"{len(pool.main_deck)} | battlefields {len(pool.battlefields)}")
    if args.champions:
        print(render_pool(pool.champion_options))
    else:
        print(render_pool(pool.all_buildable))


def cmd_shortlist(args):
    db = CardDB.load(DATA_DIR)
    legend = _legend(db, args.legend)
    pool = db.legal_pool(legend)
    champ = db.get(args.champion) if args.champion else _implied_champion(db, args.legend)
    _emit(prompt_mod.shortlist_prompt(pool, champ, _meta(args, db)), args.out)


def cmd_build(args):
    db = CardDB.load(DATA_DIR)
    legend = _legend(db, args.legend)
    pool = db.legal_pool(legend)
    champ = db.get(args.champion) if args.champion else _implied_champion(db, args.legend)
    shortlist = Path(args.shortlist).read_text() if args.shortlist else None
    _emit(
        prompt_mod.build_prompt(pool, champ, _meta(args, db), shortlist, args.notes or ""),
        args.out,
    )


def cmd_check(args):
    db = CardDB.load(DATA_DIR)
    deck = _load_deck(db, args.deck)
    report = validate(deck, battlefields=args.battlefields)
    print(report.render())
    sys.exit(0 if report.legal else 1)


def cmd_stats(args):
    db = CardDB.load(DATA_DIR)
    deck = _load_deck(db, args.deck)
    print(validate(deck, battlefields=args.battlefields).render())
    print()
    print(analyze_mod.analyze(deck).render())


def cmd_analyze(args):
    db = CardDB.load(DATA_DIR)
    deck = _load_deck(db, args.deck)
    report = validate(deck, battlefields=args.battlefields)
    stats = analyze_mod.analyze(deck)
    _emit(
        prompt_mod.analyze_prompt(deck, stats, report, _meta(args, db), args.question or ""),
        args.out,
    )


def cmd_combos(args):
    db = CardDB.load(DATA_DIR)
    if args.legend:
        legend = _legend(db, args.legend)
        pool = db.legal_pool(legend)
        cards = pool.all_buildable
        header = f"# combos available to {legend.name} ({len(cards)} legal cards)"
    else:
        deck = _load_deck(db, args.deck)
        legend = deck.legend
        cards = [deck.card(n) for n in deck.main] + [deck.card(n) for n in deck.battlefields]
        header = f"# combos in {deck.name}"
    print(header)
    findings = combos_mod.find_combos(cards, legend, limit_per_rule=args.limit)
    print(combos_mod.render(findings, combos_mod.special_findings(cards, legend)))


def cmd_critique(args):
    db = CardDB.load(DATA_DIR)
    deck = _load_deck(db, args.deck)
    print(validate(deck, battlefields=args.battlefields).render())
    print()
    print(critique_mod.critique(deck).render())


def cmd_iterate(args):
    """Emit a refinement prompt: everything known about the deck, plus the
    critique protocol that produced the good revisions by hand."""
    db = CardDB.load(DATA_DIR)
    deck = _load_deck(db, args.deck)
    report = validate(deck, battlefields=args.battlefields)
    stats = analyze_mod.analyze(deck)
    cards = [deck.card(n) for n in deck.main] + [deck.card(n) for n in deck.battlefields]
    findings = combos_mod.find_combos(cards, deck.legend, limit_per_rule=5)
    combo_text = combos_mod.render(findings, combos_mod.special_findings(cards, deck.legend))
    _emit(
        prompt_mod.iterate_prompt(
            deck, stats, report, combo_text,
            critique_mod.critique(deck).render(),
            _meta(args, db), args.notes or "",
        ),
        args.out,
    )


def cmd_rules(args):
    if args.search:
        print(rules_mod.lookup(DATA_DIR, args.search))
    elif args.section:
        print(rules_mod.section(DATA_DIR, args.section))
    else:
        print(rules_mod.constitution())


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_meta(sp):
        sp.add_argument("--meta", action="store_true",
                        help="enable meta/archetype context (default: off)")
        sp.add_argument("--out", help="write prompt to a file instead of stdout")

    def add_bf(sp):
        sp.add_argument("--battlefields", type=int, default=DEFAULT_BATTLEFIELDS,
                        help=f"battlefields for this Mode of Play (default {DEFAULT_BATTLEFIELDS})")

    sub.add_parser("sync").set_defaults(func=cmd_sync)
    sub.add_parser("sets").set_defaults(func=cmd_sets)
    sub.add_parser("upcoming").set_defaults(func=cmd_upcoming)

    sp = sub.add_parser("legends")
    sp.add_argument("--search")
    sp.set_defaults(func=cmd_legends)

    sp = sub.add_parser("pool")
    sp.add_argument("legend")
    sp.add_argument("--champions", action="store_true", help="only champion options")
    sp.set_defaults(func=cmd_pool)

    sp = sub.add_parser("shortlist")
    sp.add_argument("legend")
    sp.add_argument("--champion")
    add_meta(sp)
    sp.set_defaults(func=cmd_shortlist)

    sp = sub.add_parser("build")
    sp.add_argument("legend")
    sp.add_argument("--champion")
    sp.add_argument("--shortlist", help="file with stage-1 output")
    sp.add_argument("--notes", help="extra direction for the build")
    add_meta(sp)
    sp.set_defaults(func=cmd_build)

    sp = sub.add_parser("check")
    sp.add_argument("deck")
    add_bf(sp)
    sp.set_defaults(func=cmd_check)

    sp = sub.add_parser("stats")
    sp.add_argument("deck")
    add_bf(sp)
    sp.set_defaults(func=cmd_stats)

    sp = sub.add_parser("analyze")
    sp.add_argument("deck")
    sp.add_argument("--question", help="a specific question to answer")
    add_bf(sp)
    add_meta(sp)
    sp.set_defaults(func=cmd_analyze)

    sp = sub.add_parser("combos")
    sp.add_argument("deck", nargs="?", help="decklist file")
    sp.add_argument("--legend", help="scan a Legend's whole legal pool instead")
    sp.add_argument("--limit", type=int, default=6, help="max pairs per rule")
    sp.set_defaults(func=cmd_combos)

    sp = sub.add_parser("critique")
    sp.add_argument("deck")
    add_bf(sp)
    sp.set_defaults(func=cmd_critique)

    sp = sub.add_parser("iterate")
    sp.add_argument("deck")
    sp.add_argument("--notes", help="what you want this pass to focus on")
    add_bf(sp)
    add_meta(sp)
    sp.set_defaults(func=cmd_iterate)

    sp = sub.add_parser("rules")
    sp.add_argument("section", nargs="?", help='rule number, e.g. "103"')
    sp.add_argument("-s", "--search", help="grep the full rules text")
    sp.set_defaults(func=cmd_rules)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
