#!/usr/bin/env python3
"""Re-derive NON_CHAMPION_TAGS (riftbound/model.py) from the card pool.

133.8.b defines Champion Tags as the tags that LINK Legends, Champion Units and
Signature cards. Species/faction tags (Yordle, Bandle City, ...) are not Champion
Tags even when a Legend prints one, and must not satisfy 103.2.a.2 / 103.2.d.2.

Test: a genuine Champion Tag belongs to exactly one champion family, so it never
co-occurs with two or more OTHER legend tags on a champion unit.

Run after every `cli.py sync` that adds a set.
"""
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from riftbound.db import CardDB  # noqa: E402

db = CardDB.load(Path(__file__).resolve().parent.parent / "data")
legend_tags = {t for c in db.legends for t in (c.tags or [])}

co = defaultdict(set)
for card in db.cards:
    if not getattr(card, "is_champion_unit", False):
        continue
    shared = set(card.tags or []) & legend_tags
    for tag in shared:
        co[tag] |= shared - {tag}

faction = sorted(t for t, others in co.items() if len(others) >= 2)
print("NON_CHAMPION_TAGS = frozenset({%s})" % ", ".join(repr(t) for t in faction))
for tag in faction:
    print(f"  {tag}: co-occurs with {sorted(co[tag])}")
if not faction:
    print("  (none found -- every legend tag is a genuine Champion Tag)")
