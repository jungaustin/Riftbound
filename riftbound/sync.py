"""Pull the Riftbound card database from Riftcodex and normalize it to disk.

The API is public, unauthenticated, and paginates at 50 items regardless of the
`limit` you ask for. It 403s without a browser-ish User-Agent.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from .model import Card, canonical_name, loose_key, normalize_text

API = "https://api.riftcodex.com"
HEADERS = {"User-Agent": "riftbound-deckbuilder/0.1", "Accept": "application/json"}
PAGE_SIZE = 50


_TYPE_LINE = re.compile(r"^Riftbound ([A-Za-z, ]+?):")


def printed_types(raw: dict) -> list[str]:
    """Recover the full printed type line.

    `classification.type` reports only the first type, so a dual-type card like
    Patched Porobot ("Unit Gear") comes back as plain "Unit" and every
    gear-counting effect silently misses it. The accessibility text preserves
    the whole line, so it is the authority here.
    """
    at = ((raw.get("media") or {}).get("accessibility_text") or "").strip()
    m = _TYPE_LINE.match(at)
    if m:
        parts = [p.strip() for p in m.group(1).split(",") if p.strip()]
        if parts:
            return parts
    t = (raw.get("classification") or {}).get("type")
    return [t] if t else []


def _get(path: str, retries: int = 3) -> dict:
    url = f"{API}{path}"
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=45) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed after {retries} attempts: {last}")


def fetch_sets() -> list[dict]:
    return _get("/sets")["items"]


def fetch_raw_cards(progress=None) -> list[dict]:
    first = _get(f"/cards?limit={PAGE_SIZE}&page=1")
    pages = first["pages"]
    items = list(first["items"])
    for p in range(2, pages + 1):
        items += _get(f"/cards?limit={PAGE_SIZE}&page={p}")["items"]
        if progress:
            progress(p, pages)
        time.sleep(0.15)
    return items


def fetch_indexes() -> dict[str, list]:
    names = [
        "keywords",
        "card-types",
        "card-supertypes",
        "domains",
        "rarities",
        "tags",
    ]
    return {n: _get(f"/index/{n}")["values"] for n in names}


def normalize(raw: list[dict], set_dates: dict[str, str] | None = None) -> list[Card]:
    """Collapse printings to one Card per gameplay-distinct card.

    Bucketing is by `loose_key`, not by display name, so "Lux - Crownguard" and
    the Vendetta reprint "Lux, Crownguard" become one card. They are the same
    card, and keeping them apart would let a deck run six copies of a 3-of.

    The surviving printing is the NEWEST non-variant one, because reprints carry
    errata ("ready 4 friendly runes" became "ready up to 4"). Older printings'
    reminder text is lost; the keyword glossary in rules.py covers that.
    """
    set_dates = set_dates or {}
    buckets: dict[str, list[dict]] = {}
    for r in raw:
        buckets.setdefault(loose_key(r["name"]), []).append(r)

    cards: list[Card] = []
    for _, group in sorted(buckets.items()):
        group.sort(
            key=lambda r: (
                bool(r["metadata"].get("alternate_art")),
                bool(r["metadata"].get("overnumbered")),
                # newest set first: errata-correct wording wins
                _neg_date(set_dates.get((r.get("set") or {}).get("set_id", ""), "")),
                r.get("collector_number") or 10**6,
            )
        )
        best = group[0]
        cname = canonical_name(best["name"])
        attrs = best.get("attributes") or {}
        cls = best.get("classification") or {}
        txt = best.get("text") or {}
        media = best.get("media") or {}
        cards.append(
            Card(
                id=best["id"],
                name=cname,
                riftbound_id=best.get("riftbound_id") or "",
                set_id=(best.get("set") or {}).get("set_id") or "",
                collector_number=best.get("collector_number"),
                type=(printed_types(best) or ["Unknown"])[0],
                types=printed_types(best),
                supertype=cls.get("supertype"),
                rarity=cls.get("rarity"),
                domains=list(cls.get("domain") or []),
                energy=attrs.get("energy"),
                power=attrs.get("power"),
                might=attrs.get("might"),
                tags=list(best.get("tags") or []),
                text=normalize_text(txt.get("plain") or ""),
                flavour=normalize_text(txt.get("flavour") or "") or None,
                image_url=media.get("image_url"),
                printings=sorted(
                    {r.get("riftbound_id") for r in group if r.get("riftbound_id")}
                ),
                aliases=sorted(
                    {canonical_name(r["name"]) for r in group} - {cname}
                ),
            )
        )
    return _merge_prefix_variants(cards)


def _merge_prefix_variants(cards: list[Card]) -> list[Card]:
    """Merge entries that are one card rendered under two names.

    Some Legends appear twice: once as the printed title ("Heart of the
    Tempest") and once with the champion prefix ("Yordle, Kennen - Heart of the
    Tempest"). Both are the same card.

    The test is deliberately narrow — identical printed characteristics AND one
    name being a suffix of the other. Characteristics alone are not enough:
    Brutalizer and Guardian Angel are different Equipment with identical vanilla
    text, and merging those would silently delete a card.
    """
    def key(c: Card):
        return (c.set_id, tuple(c.all_types), c.supertype, tuple(c.domains),
                c.energy, c.power, c.might, (c.text or "").strip())

    groups: dict[tuple, list[Card]] = {}
    for c in cards:
        if (c.text or "").strip():
            groups.setdefault(key(c), []).append(c)

    drop: set[str] = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        for a in group:
            for b in group:
                if a is b or a.name in drop or b.name in drop:
                    continue
                # keep the longer, more specific name; alias the shorter
                if len(a.name) > len(b.name) and a.name.endswith(b.name):
                    a.aliases = sorted(set(a.aliases) | {b.name})
                    drop.add(b.name)
    return [c for c in cards if c.name not in drop]


def sync(data_dir: Path, verbose: bool = True) -> dict:
    data_dir.mkdir(parents=True, exist_ok=True)

    def prog(p, total):
        if verbose:
            print(f"  cards page {p}/{total}", end="\r", flush=True)

    sets = fetch_sets()
    set_dates = {s["set_id"]: (s.get("published_on") or "") for s in sets}
    raw = fetch_raw_cards(progress=prog)
    if verbose:
        print()
    indexes = fetch_indexes()
    cards = normalize(raw, set_dates)

    payload = {
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": API,
        "raw_entry_count": len(raw),
        "sets": sets,
        "indexes": indexes,
        "cards": [c.to_dict() for c in cards],
    }
    (data_dir / "cards.json").write_text(json.dumps(payload, indent=1))

    summary = {
        "raw_entries": len(raw),
        "unique_cards": len(cards),
        "sets": len(sets),
        "newest_set": max(sets, key=lambda s: s.get("published_on") or "")["name"],
    }
    if verbose:
        print(
            f"  {summary['raw_entries']} printings -> {summary['unique_cards']} "
            f"unique cards across {summary['sets']} sets"
        )
    return summary


def _neg_date(d: str) -> str:
    """Sort key that puts later dates first."""
    return "".join(chr(0x7E - ord(c) % 0x5E) for c in (d or "")[:10]) or "~" * 10
