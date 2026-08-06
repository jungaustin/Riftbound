#!/usr/bin/env python3
"""
Parse saved riftdecks /staples pages into per-Domain inclusion rates.

    python3 scripts/parse_staples.py                     # all saved pages
    python3 scripts/parse_staples.py --threshold 20
    python3 scripts/parse_staples.py --types spell
    python3 scripts/parse_staples.py --coverage          # how many more pages are needed
    python3 scripts/parse_staples.py --selftest

Drop saved pages in html/ under any filename. Domain and type are read from each
card tile, not from the filename, so saves can be filtered or unfiltered and in any order.
Duplicate cards across pages are merged.

WHY THE RAW NUMBER NEEDS CORRECTING
-----------------------------------
riftdecks "Popularity" is not an inclusion rate. Per their own definition it is

    popularity(X) = decks_containing(X) / decks_containing(most_popular_card_overall)

one global denominator shared by all six Domains (the /30 in their wording is a constant and
cancels). Calm Rune is that benchmark, so Calm cards read about right by accident and every
other Domain is deflated -- Fury Rune tops out at 46.26%, not 100%, and the domain filter does
not re-normalise.

The fix uses the Domain's own Rune. Every deck of Domain D runs D Runes and no deck outside D
legally may, so the Rune's popularity is exactly D's share of the benchmark:

    inclusion(X, D) = popularity(X) / popularity(D_Rune)

The global denominator cancels, and this lands on METHODOLOGY.md §1's definition of "decks of
Domain D" -- decks whose Legend identity contains D -- for free.

Checks out on Calm, where the correction is a no-op: Defy 99.52/100 = 99.5%, matching the 99.5%
aggregate.py derives from per-Legend data by a fully independent route.

TYPES AND DOMAINS ARE AUTHORITATIVE HERE
----------------------------------------
Each card tile carries data-types / data-domains / data-sets attributes straight from the site's
own database. That supersedes data/card_types.csv, which was 136-of-137 unverified guesses.

LIMITS
------
- Mono-Domain cards only. A dual-Domain card's denominator is the *intersection* of two Domains,
  which no single Rune gives; those are listed separately and left uncorrected.
- Colorless cards go in any deck and have no Rune -- excluded, per METHODOLOGY §6.
- Slight upward bias: a deck could hold D in identity yet run zero D Runes. Rare, and it shrinks
  the denominator, so treat results as a mild over-estimate.
- /staples is a rolling 30-day window: current format only. There is no Unleashed view here.
"""
import argparse, csv, glob, html, os, re, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML_DIR = os.path.join(ROOT, "html")
DOMAINS = ["fury", "calm", "mind", "body", "chaos", "order"]

# Each card is a bootstrap column div carrying the site's own metadata, then a popularity block.
# The tile BODY also contains inner `<div class="col-6">` wrappers around the popularity and
# copies figures, so the boundary has to key on the data-attributes that only tiles carry.
TILE = re.compile(r'<div class="col-[^"]*"((?:\s+data-[a-z_]+="[^"]*")+)\s*>'
                  r'(.*?)(?=<div class="col-[^"]*"\s+data-|\Z)', re.S | re.I)
ATTR = re.compile(r'data-([a-z_]+)="([^"]*)"', re.I)
GAP = r"(?:<[^>]*>|\s|&nbsp;)*"
POP = re.compile(r"Popularity:" + GAP + r"([\d.]+)" + GAP + r"%", re.I)
COPIES = re.compile(r"Copies\s*/\s*Deck" + GAP + r"([\d.]+)", re.I)
SLUG = re.compile(r"details-([a-z0-9-]+)")


def parse_page(raw):
    """{slug: card} for every card tile. Type/domain come from the tile's own data-attributes."""
    out = {}
    for attrs, body in TILE.findall(raw):
        pop = POP.search(body)
        slug = SLUG.search(body)
        if not pop or not slug:
            continue
        d = defaultdict(list)
        for k, v in ATTR.findall(attrs):
            d[k].append(html.unescape(v).strip())
        cop = COPIES.search(body)
        name = d["name"][0] if d["name"] else slug.group(1).replace("-", " ").title()
        out[slug.group(1)] = {
            "slug": slug.group(1),
            "name": name,
            "pop": float(pop.group(1)),
            "copies": float(cop.group(1)) if cop else None,
            "types": [t.lower() for t in d.get("types", [])],
            "domains": [x.lower() for x in d.get("domains", [])],
            "sets": d.get("sets", []),
            "cost": d["cost"][0] if d["cost"] else None,
        }
    return out


def load_all():
    cards, files = {}, []
    for path in sorted(glob.glob(os.path.join(HTML_DIR, "*.html"))):
        with open(path, encoding="utf-8", errors="replace") as fh:
            found = parse_page(fh.read())
        cards.update(found)
        files.append((os.path.basename(path), len(found)))
    return cards, files


def rune_for(cards, dom):
    for c in cards.values():
        if "rune" in c["types"] and c["domains"] == [dom]:
            return c
    return cards.get(f"{dom}-rune")


def coverage(cards, threshold):
    """Per Domain: is the saved data deep enough to reach the threshold?"""
    print("# Coverage check\n")
    print("A Domain is complete once the saved pages reach a raw popularity of")
    print("`threshold x rune`. Cards are listed in descending popularity, so the lowest raw")
    print("value you have captured tells you whether to keep paging.\n")
    print("| Domain | Rune | Need raw >= | Lowest saved | Cards | Status |")
    print("|---|---|---|---|---|---|")
    for dom in DOMAINS:
        rune = rune_for(cards, dom)
        mine = [c for c in cards.values() if dom in c["domains"]]
        if not rune:
            print(f"| {dom} | — | — | — | {len(mine)} | **no Rune captured — cannot normalise** |")
            continue
        need = threshold / 100 * rune["pop"]
        low = min(c["pop"] for c in mine)
        done = low <= need
        print(f"| {dom} | {rune['pop']}% | {need:.2f}% | {low:.2f}% | {len(mine)} | "
              f"{'complete' if done else '**keep paging**'} |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=20.0)
    ap.add_argument("--types", help="comma-separated type filter, e.g. spell")
    ap.add_argument("--coverage", action="store_true")
    ap.add_argument("--csv", default=os.path.join(ROOT, "inclusion_vendetta.csv"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    cards, files = load_all()
    if not cards:
        sys.exit(f"no card tiles parsed from {HTML_DIR}\n"
                 f"Save domain-filtered /staples pages there (any filename).")
    print(f"<!-- {len(cards)} unique cards from " +
          ", ".join(f"{n} ({k})" for n, k in files) + " -->\n")

    if a.coverage:
        return coverage(cards, a.threshold)

    want = [t.strip().lower() for t in a.types.split(",")] if a.types else None
    rows, dual = [], []
    print(f"# Per-Domain Inclusion, current format (>={a.threshold:g}%)\n")
    print("Rune-normalised: `inclusion = popularity / popularity(Domain Rune)`. "
          "riftdecks /staples, rolling 30-day window.\n")

    for dom in DOMAINS:
        rune = rune_for(cards, dom)
        print(f"\n## {dom.capitalize()}")
        if not rune:
            print(f"\n_No {dom} Rune in the saved pages — cannot normalise this Domain._")
            continue
        print(f"\nDivisor: {rune['name']} @ {rune['pop']}%")
        if rune["pop"] < 5:
            print("\n**Divisor is tiny — small errors amplify. Directional only.**")

        listed = []
        for c in cards.values():
            if dom not in c["domains"] or "rune" in c["types"]:
                continue
            if want and not any(t in want for t in c["types"]):
                continue
            incl = c["pop"] / rune["pop"] * 100
            if incl < a.threshold:
                continue
            if len(c["domains"]) > 1:
                dual.append((dom, c, incl))
            else:
                listed.append((incl, c))
        listed.sort(key=lambda x: -x[0])

        if listed:
            print("\n| Card | Inclusion | Type | Raw | Copies |")
            print("|---|---|---|---|---|")
            for incl, c in listed:
                cop = f"{c['copies']:.2f}" if c["copies"] else "—"
                print(f"| {c['name']} | {incl:.1f}% | {'/'.join(c['types']) or '?'} | "
                      f"{c['pop']}% | {cop} |")
                rows.append({"domain": dom, "card": c["name"], "slug": c["slug"],
                             "type": "/".join(c["types"]), "inclusion_pct": round(incl, 1),
                             "raw_popularity_pct": c["pop"], "copies_per_deck": c["copies"],
                             "divisor_rune_pct": rune["pop"]})
        else:
            print("\n_Nothing above threshold._")

    if dual:
        print("\n\n## Dual-Domain cards (not normalised)\n")
        print("Their correct denominator is the intersection of two Domains, which no single "
              "Rune supplies. Raw popularity shown; treat the implied rate as a ceiling.\n")
        print("| Card | Domains | Type | Raw | Naive vs |")
        print("|---|---|---|---|---|")
        for dom, c, incl in sorted({(d, x["slug"]): (d, x, i) for d, x, i in dual}.values(),
                                   key=lambda t: -t[2]):
            print(f"| {c['name']} | {'/'.join(c['domains'])} | {'/'.join(c['types']) or '?'} | "
                  f"{c['pop']}% | {incl:.1f}% vs {dom} |")

    if rows:
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"\nwrote {a.csv} ({len(rows)} rows)", file=sys.stderr)


def selftest():
    fixture = '''
<div class="col-xl-5th col-12"  data-name="Calm Rune"  data-domains="calm"  data-types="rune" >
  <a href="/cards/details-calm-rune"><img alt="Calm Rune"/></a>
  <div class="row"><div class="col-6"><b>Popularity:<br /> <span>100</span>%</b></div>
  <div class="col-6"><b>Copies/Deck<br /><span> 5.78 </span></b></div></div>
</div>
<div class="col-xl-5th col-12"  data-name="Fury Rune"  data-domains="fury"  data-types="rune" >
  <a href="/cards/details-fury-rune"><img alt="Fury Rune"/></a>
  <div class="row"><div class="col-6"><b>Popularity:<br /> <span>46.26</span>%</b></div>
  <div class="col-6"><b>Copies/Deck<br /><span> 6.01 </span></b></div></div>
</div>
<div class="col-xl-5th col-12"  data-name="Falling Star"  data-domains="fury"  data-types="spell" >
  <a href="/cards/details-falling-star"><img alt="Falling Star"/></a>
  <div class="row"><div class="col-6"><b>Popularity:<br /> <span>35.93</span>%</b></div>
  <div class="col-6"><b>Copies/Deck<br /><span> 2.31 </span></b></div></div>
</div>
<div class="col-xl-5th col-12"  data-name="Defy"  data-domains="calm"  data-types="spell" >
  <a href="/cards/details-defy"><img alt="Defy"/></a>
  <div class="row"><div class="col-6"><b>Popularity:<br /> <span>99.52</span>%</b></div>
  <div class="col-6"><b>Copies/Deck<br /><span> 2.96 </span></b></div></div>
</div>
'''
    cards = parse_page(fixture)
    assert len(cards) == 4, cards.keys()
    fury, calm = rune_for(cards, "fury"), rune_for(cards, "calm")
    assert fury["pop"] == 46.26 and calm["pop"] == 100.0
    fs = round(cards["falling-star"]["pop"] / fury["pop"] * 100, 1)
    dfy = round(cards["defy"]["pop"] / calm["pop"] * 100, 1)
    assert fs == 77.7, fs
    assert dfy == 99.5, dfy
    assert cards["falling-star"]["types"] == ["spell"]
    assert cards["defy"]["domains"] == ["calm"]
    print(f"Falling Star {fs}% of Fury · Defy {dfy}% of Calm · types/domains read from tiles")
    print("selftest OK")


if __name__ == "__main__":
    main()
