#!/usr/bin/env python3
"""Rewrite every decklist into one canonical format.

The repo grew two dialects: the hand-written decks use "Legend: Name" with
"3x Name" quantities, the imported meta decks use a bare "Legend:" header with
the name on the next line and "3 Name" quantities. Anything reading decklists
has to handle both, which is a standing source of silent misparses.

Canonical form (the hand-written dialect, which is the majority and the more
readable of the two):

    # optional comment line
    Legend: Lillia - Bashful Bloom
    Champion: Lillia - Fae Fawn
    Main Deck:
    3x Stupefy
    Battlefields:
    1x Dusk Rose Lab
    Runes:
    9x Mind Rune
    Sideboard:          <- only when the deck has one

Every rewrite is verified by re-parsing the output and comparing it to the
parse of the original. A file whose content would change is left untouched and
reported, so a parser gap can never quietly eat a decklist.

    python3 sim/normalize_decks.py --check   # report only, write nothing
    python3 sim/normalize_decks.py           # rewrite in place
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine.decklist import SECTIONS, parse_deck  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

def comment_header(path: Path) -> str | None:
    for line in path.read_text().splitlines():
        s = line.strip()
        if s.startswith("#"):
            return s
        if s:
            return None
    return None


def render(deck, header: str | None) -> str:
    out: list[str] = []
    if header:
        out.append(header)
    out.append(f"Legend: {deck.legend}")
    out.append(f"Champion: {deck.champion}")
    for key, label in SECTIONS:
        if not deck.section(key):
            continue
        out.append(label)
        for count, name in deck.section(key):
            out.append(f"{count}x {name}")
    return "\n".join(out) + "\n"


def comparable(deck) -> dict:
    """Parsed content, order-insensitive within each section."""
    return deck.comparable()


def main() -> int:
    check_only = "--check" in sys.argv
    paths = sorted((ROOT / "decks").rglob("*.txt"))
    changed = skipped = identical = 0

    for path in paths:
        original = path.read_text()
        before = parse_deck(path)
        text = render(before, comment_header(path))

        if text == original:
            identical += 1
            continue

        # Verify the rewrite round-trips before trusting it.
        tmp = path.with_suffix(".normalizecheck")
        tmp.write_text(text)
        try:
            after = parse_deck(tmp)
        finally:
            tmp.unlink()

        rel = path.relative_to(ROOT)
        if comparable(before) != comparable(after):
            print(f"SKIP  {rel}  (round-trip mismatch — left untouched)")
            for key in ("legend", "champion", *[k for k, _ in SECTIONS]):
                b, a = comparable(before)[key], comparable(after)[key]
                if b != a:
                    print(f"        {key}: {b!r} -> {a!r}")
            skipped += 1
            continue

        if not check_only:
            path.write_text(text)
        print(f"{'WOULD REWRITE' if check_only else 'rewrote'}  {rel}")
        changed += 1

    verb = "would change" if check_only else "rewritten"
    print(f"\n{changed} {verb}, {identical} already canonical, {skipped} skipped")
    return 1 if skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
