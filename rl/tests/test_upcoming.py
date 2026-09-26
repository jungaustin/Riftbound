"""The unreleased-set gate. Run from the repo root: python -m rl.tests.test_upcoming

This suite exists because the gate is a NEGATIVE guarantee -- "these cards do
not reach the pool" -- and nothing else in the repo notices when a negative
guarantee stops holding. A card that leaks into the corpus looks exactly like a
card that was legitimately released: `cli.py pool` recommends it, the RL dealer
deals it, and the only symptom is an agent fluent in a format that does not
exist yet.

So the gate gets the same treatment as `mirror.SEAT_AXIS` and `obs.OBS_UNREAD`:
every reader of the corpus is enumerated here, and a new one fails the suite by
name rather than silently bypassing the gate.
"""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from riftbound import upcoming                                   # noqa: E402


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Every module that reads the card corpus must go through the gate. Adding a
# reader means adding it here AND gating it; the scan below is what makes
# forgetting the second part impossible to do quietly.
GATED_READERS = {
    "riftbound/db.py",            # deckbuilding pool, ratings, cli.py
    "rl/engine/cardtable.py",     # the RL engine's compiled rows
    "sim/engine/cards.py",        # card_index/find -- rl/decks.py name resolution
}
# Files that may mention cards.json without reading it: the writer, the gate's
# own documentation, and this scanner -- which matches itself, because it holds
# the search pattern as a literal.
ALLOWED_MENTIONS = {"riftbound/sync.py", "riftbound/upcoming.py",
                    "rl/tests/test_upcoming.py"}

print("\n[1] every corpus reader is gated")
_hits = subprocess.run(
    ["grep", "-rln", "--include=*.py", 'data" / "cards.json\\|data_dir / "cards.json',
     "riftbound", "rl", "sim", "engine"],
    cwd=ROOT, capture_output=True, text=True).stdout.split()
_readers = {h for h in _hits if not h.startswith("rl/runs/")}
_unknown = _readers - GATED_READERS - ALLOWED_MENTIONS
if _unknown:
    die("readers",
        f"these read data/cards.json but are not listed in GATED_READERS: "
        f"{sorted(_unknown)}. Gate them through riftbound.upcoming.extra_cards() "
        f"and add them above, or an unreleased card will leak through them.")
_missing = {r for r in GATED_READERS if r not in _readers}
if _missing:
    die("readers", f"GATED_READERS names files that no longer read the corpus: "
                   f"{sorted(_missing)} -- stale entries hide the next real one")
for _r in sorted(GATED_READERS):
    if "upcoming" not in (ROOT / _r).read_text():
        die("readers", f"{_r} reads the corpus but never consults riftbound.upcoming")
ok(f"{len(GATED_READERS)} corpus readers, all consulting the gate")


# ---------------------------------------------------------------------------
print("\n[2] a future set is invisible, and the flag reveals it")

_probe = ROOT / "data" / "upcoming" / "_ZZTEST.json"
_probe.parent.mkdir(parents=True, exist_ok=True)
_FAKE = "Zztest Probe Construct"
_probe.write_text(json.dumps({
    "set_id": "ZZT",
    "name": "Gate Probe (test fixture)",
    "released_on": "2099-01-01",
    "source": "written and deleted by rl/tests/test_upcoming.py",
    "cards": [{
        "id": "zzt-probe-0001", "name": _FAKE, "aliases": [],
        "collector_number": "001", "domains": ["Fury"], "energy": 2, "power": 0,
        "might": 3, "rarity": "Common", "supertype": None, "type": "Unit",
        "types": ["Unit"], "tags": [], "text": "", "flavour": "",
        "image_url": "", "printings": ["zzt-001"], "riftbound_id": "zzt-001",
        "set_id": "ZZT",
    }],
}, indent=1))


def _subprocess_probe(env_flag: str | None, today: str | None = None) -> dict:
    """Ask a FRESH interpreter what it can see.

    A subprocess rather than an in-process reload, because both corpora are
    cached (`CardDB.load` is called once per process and `card_index` is
    `lru_cache`d), so flipping the environment inside this process would test
    the cache rather than the gate.
    """
    env = dict(os.environ)
    env.pop(upcoming.ENV_FLAG, None)
    if env_flag is not None:
        env[upcoming.ENV_FLAG] = env_flag
    code = f'''
import sys, json
sys.path.insert(0, {str(ROOT)!r})
from pathlib import Path
from riftbound.db import CardDB
from rl.engine.cardtable import full_table
from engine.cards import find
db = CardDB.load(Path({str(ROOT / "data")!r}))
T = full_table()
print(json.dumps({{
    "db":    any(c.name == {_FAKE!r} for c in db.cards),
    "table": {_FAKE!r} in set(T.names),
    "find":  find({_FAKE!r}) is not None,
    "n_db":  len(db.cards),
}}))
'''
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env,
                       capture_output=True, text=True)
    if r.returncode != 0:
        die("probe", f"subprocess failed:\n{r.stderr[-1500:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


try:
    _off = _subprocess_probe(None)
    if any((_off["db"], _off["table"], _off["find"])):
        die("gate-off", f"a set dated 2099 leaked into the corpus: {_off}")
    ok("released_on in the future -> absent from db, engine table and find()")

    _on = _subprocess_probe("1")
    if not all((_on["db"], _on["table"], _on["find"])):
        die("gate-on", f"{upcoming.ENV_FLAG}=1 did not reveal the set: {_on}")
    # The delta is every card in every upcoming set on disk, not just the
    # probe's one -- real spoiler sets live here too, and hardcoding 1 would
    # make this suite fail the day one is added rather than the day the gate
    # breaks. Counted by NAME, because a card already in `cards.json` under the
    # same name would be deduplicated away by the engine table.
    _expected = len({c["name"] for s_ in upcoming.all_sets() for c in s_["cards"]})
    if _on["n_db"] - _off["n_db"] != _expected:
        die("gate-on", f"expected {_expected} extra cards (every upcoming set), "
                       f"got {_on['n_db'] - _off['n_db']}")
    ok(f"{upcoming.ENV_FLAG}=1 -> present in all three, "
       f"{_expected} card(s) added and none otherwise")

    for _falsey in ("", "0", "false", "no", "off"):
        if _subprocess_probe(_falsey)["db"]:
            die("gate-off", f"{upcoming.ENV_FLAG}={_falsey!r} counted as opted in")
    ok("an empty or falsey flag value is still off")

    # The date switch, without the flag. `visible_sets` takes `today` so this is
    # checked in-process -- it reads the file, not a cached corpus.
    if upcoming.visible_sets(dt.date(2098, 12, 31)):
        die("date", "a set was visible the day before its release")
    if not upcoming.visible_sets(dt.date(2099, 1, 1)):
        die("date", "a set was still hidden ON its release date")
    if not upcoming.visible_sets(dt.date(2099, 6, 1)):
        die("date", "a set was hidden after its release date")
    ok("released_on flips on the day itself, with no flag and no code change")
finally:
    _probe.unlink(missing_ok=True)
    try:
        _probe.parent.rmdir()            # only if the test created it empty
    except OSError:
        pass


# ---------------------------------------------------------------------------
print("\n[3] a malformed set file fails loudly")
_probe.parent.mkdir(parents=True, exist_ok=True)
try:
    _probe.write_text(json.dumps({"set_id": "ZZT", "cards": []}))
    try:
        upcoming.all_sets()
        die("malformed", "a file with no released_on loaded silently")
    except ValueError:
        pass
    _probe.write_text(json.dumps(
        {"set_id": "ZZT", "released_on": "next Tuesday", "cards": []}))
    try:
        upcoming.all_sets()
        die("malformed", "a non-ISO released_on loaded silently")
    except ValueError:
        pass
    ok("a missing or unparseable released_on raises rather than skipping the set")
finally:
    _probe.unlink(missing_ok=True)
    try:
        _probe.parent.rmdir()
    except OSError:
        pass


# ---------------------------------------------------------------------------
print("\n[4] decks/upcoming/ never reaches training")
from rl.decks import decklist_files                              # noqa: E402

_d = ROOT / "decks" / "upcoming" / "_zztest" / "v1.txt"
_d.parent.mkdir(parents=True, exist_ok=True)
try:
    _d.write_text("Legend: Kennen - Heart of the Tempest\n")
    _all = decklist_files()
    _latest = decklist_files(latest_only=True)
    if any("upcoming" in f.parts for f in _all + _latest):
        die("decks", "a deck under decks/upcoming/ was offered for training")
    # ...and the flag must NOT change that: it exists so the ENGINE can see the
    # cards for scripting, not so the agent can practise an illegal format.
    os.environ[upcoming.ENV_FLAG] = "1"
    try:
        if any("upcoming" in f.parts for f in decklist_files()):
            die("decks", f"{upcoming.ENV_FLAG} let decks/upcoming/ into training")
    finally:
        os.environ.pop(upcoming.ENV_FLAG, None)
    ok("excluded from both globs, and the flag does not override it")
finally:
    _d.unlink(missing_ok=True)
    for _p in (_d.parent, _d.parent.parent):
        try:
            _p.rmdir()
        except OSError:
            pass


print("\n\033[32mall upcoming-set gate tests passed\033[0m")
