"""Cards from sets that are not out yet.

**The problem this solves.** A set can be scripted, tested and rated long before
it is legal to play. But every consumer in this repo reads one card corpus:
`riftbound/db.py` builds the deckbuilding pool from it and `rl/engine/cardtable`
compiles the engine's rows from it. Drop an unreleased card into that corpus and
it silently becomes buildable, rateable and trainable -- the RL agent starts
learning a format that does not exist, and `cli.py pool` starts recommending
cards nobody can own.

So unreleased cards live here instead, and are merged in only when something
explicitly asks for them.

## Where they go

One file per set, `data/upcoming/<SET_ID>.json`:

    {
      "set_id":      "XXX",
      "name":        "Set Name",
      "released_on": "2026-11-13",
      "source":      "where these came from -- previews, spoiler season, a leak",
      "cards":       [ ... same record schema as cards.json's "cards" ... ]
    }

**Not inside `data/cards.json`.** `cli.py sync` regenerates that file wholesale
from upstream, so anything hand-written into it is destroyed by the next sync.
`data/tokens.json` and `data/errata.json` already exist for exactly this reason;
this is the third file in that pattern, and the only one that is conditional.

## When they become visible

Two independent switches, checked per set, so several upcoming sets can sit at
different stages at once:

  * **`released_on` has passed.** The set becomes legal on its release date with
    no action required -- which is the point of recording the date rather than a
    boolean. A set file whose date has passed should eventually be folded into
    `cards.json` by a `cli.py sync`, and deleting it then changes nothing.
  * **`RIFTBOUND_UPCOMING=1`** in the environment. The scripting switch: it
    merges every upcoming set regardless of date, for writing card specs,
    running the judge suite against them, and rating the new pool.

Nothing else turns them on. In particular there is no config field and no
function argument threaded through the loaders, because a default-off flag that
can be passed at a call site is a flag that will eventually be passed by
accident -- and the failure is silent.

## What is deliberately NOT gated

Writing a `CardSpec` in `rl/engine/effects.py` for a card that is not in the
table is already harmless: specs are keyed by card name and an entry nothing
matches is never reached. So scripting can begin before a set file exists, and
the gate is only about the card ROWS.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPCOMING_DIR = ROOT / "data" / "upcoming"

#: Environment variable that merges every upcoming set regardless of its date.
ENV_FLAG = "RIFTBOUND_UPCOMING"


def opted_in() -> bool:
    """Is the scripting switch on?

    Anything other than an explicit falsey string counts as on, so
    `RIFTBOUND_UPCOMING=1`, `=true` and `=yes` all work and a bare `=` or `=0`
    does not.
    """
    v = os.environ.get(ENV_FLAG, "").strip().lower()
    return v not in ("", "0", "false", "no", "off")


def set_files() -> list[Path]:
    """Every upcoming-set file on disk, whether or not it is visible."""
    if not UPCOMING_DIR.is_dir():
        return []
    return sorted(p for p in UPCOMING_DIR.glob("*.json"))


def _parse(path: Path) -> dict:
    raw = json.loads(path.read_text())
    for key in ("set_id", "released_on", "cards"):
        if key not in raw:
            raise ValueError(f"{path.name} is missing required key {key!r}")
    try:
        raw["_released"] = _dt.date.fromisoformat(str(raw["released_on"])[:10])
    except ValueError as e:
        raise ValueError(
            f"{path.name}: released_on must be ISO (YYYY-MM-DD), "
            f"got {raw['released_on']!r}") from e
    return raw


def all_sets() -> list[dict]:
    """Every upcoming set, parsed. Raises on a malformed file rather than
    skipping it -- a set that silently fails to load is a set whose cards
    quietly vanish from the scripting run that was meant to test them."""
    return [_parse(p) for p in set_files()]


def visible_sets(today: _dt.date | None = None) -> list[dict]:
    """The upcoming sets that should be merged into the corpus right now."""
    day = today or _dt.date.today()
    flag = opted_in()
    return [s for s in all_sets() if flag or s["_released"] <= day]


def extra_cards(today: _dt.date | None = None) -> list[dict]:
    """Card records to append to `cards.json`'s own, or `[]` when none apply.

    Each record is stamped with its `set_id` if the file did not already, so a
    merged card is still traceable to the set it came from.
    """
    out: list[dict] = []
    for s in visible_sets(today):
        for c in s["cards"]:
            c.setdefault("set_id", s["set_id"])
            out.append(c)
    return out


def status(today: _dt.date | None = None) -> str:
    """One line per upcoming set, for `cli.py` and for a run's provenance."""
    day = today or _dt.date.today()
    sets = all_sets()
    if not sets:
        return "no upcoming sets on disk"
    vis = {s["set_id"] for s in visible_sets(day)}
    lines = []
    for s in sets:
        why = ("visible: released" if s["_released"] <= day
               else f"visible: {ENV_FLAG}" if s["set_id"] in vis
               else f"hidden until {s['_released']}")
        lines.append(f"  {s['set_id']:<5} {s.get('name', '?'):<28} "
                     f"{len(s['cards']):>4} cards  [{why}]")
    return "\n".join(lines)
