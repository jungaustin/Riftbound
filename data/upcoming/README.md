# Unreleased sets

Cards for a set that is **not out yet**. Nothing in this folder reaches
deckbuilding, ratings or RL training until it is released or you ask for it
explicitly.

## Why it is a separate folder

`cli.py sync` regenerates `data/cards.json` wholesale from upstream, so a card
hand-written into that file is destroyed by the next sync. `data/tokens.json`
and `data/errata.json` already exist for that reason; this is the third file in
that pattern and the only one that is conditional.

The other half of the reason is that a leak is silent. An unreleased card in
the corpus looks exactly like a released one: `cli.py pool` recommends it, the
RL dealer deals it, and the only symptom is an agent fluent in a format that
does not exist.

## Adding a set

One file per set, `data/upcoming/<SET_ID>.json`:

```json
{
  "set_id": "RAD",
  "name": "...",
  "released_on": "2026-11-13",
  "source": "where these came from",
  "cards": [ { ... } ]
}
```

Each entry in `cards` uses **exactly** the record schema of `cards.json`'s own
`cards` — `riftbound/model.py` constructs `Card(**record)`, so an unknown key
is a `TypeError` and a missing one is too. Copy a record of the same type out
of `cards.json` and edit it.

Any other top-level key is free: `RAD.json` carries a `verification` block
listing what still needs checking against the official gallery.

## Seeing them

```
python cli.py upcoming                    # what is on disk, and its status
RIFTBOUND_UPCOMING=1 python cli.py pool <legend>
RIFTBOUND_UPCOMING=1 python -m rl.tests.test_judge
```

Two independent switches, checked per set:

* **`released_on` has passed** — the set goes live on its own date, with no
  flag and no code change. That is why the date is recorded rather than a
  boolean.
* **`RIFTBOUND_UPCOMING=1`** — the scripting switch. Merges every upcoming set
  regardless of date, for writing card specs and running the suites against
  them.

`decks/upcoming/` is the matching folder for decklists, and it is excluded from
training *even with the flag set*: the flag exists so the engine can see the
cards, not so the agent can practise an illegal format.

Once a set is really out, a `cli.py sync` picks it up into `cards.json` and the
file here can simply be deleted.

`rl/tests/test_upcoming.py` enumerates every module that reads the corpus and
fails by name if a new one appears ungated.
