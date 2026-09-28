# Riftbound — developer guide

> **Picking this up in a new chat?** Read [`CONTEXT.md`](CONTEXT.md) first —
> it holds current state, what is running, and what is known-broken.

Two working projects and one specification, sharing one set of card data.

| | what it is | entry point |
|---|---|---|
| **`riftbound/`** + `cli.py` | Deck building, legality, meta analysis | `python3 cli.py --help` |
| **`rl/`** | A reinforcement-learning agent that plays the game | [`rl/README.md`](rl/README.md), docs in [`rl/docs/`](rl/docs/) |
| **`sim/`** | An older referee, kept as a **rules spec** — do not build on it | [`sim/README.md`](sim/README.md) |

`rl/` does not import `riftbound/` or `sim/`. The only thing all three share is
`data/`.

## Shared data — `data/`

| file | |
|---|---|
| `cards.json` | the card pool as **printed** |
| `errata.json` | official errata, re-applied on every load. **`cards.json` alone is not the data** — 50 cards have errata and four change behaviour, so grepping the raw file will mislead you |
| `rules.txt` | Core Rules (RUP4, 2026-07-16) |
| `tournament_rules.txt` | Tournament Rules (2026-07-16) — the authority for **sideboarding**, which the Core Rules never mention |
| `banlist.json` | 7 cards + 5 battlefields, verified 2026-09-25; enforced by `cli.py check` and excluded from RL training |
| `tokens.json`, `archetypes.md`, `staples/` | token definitions, meta notes, staple analysis |

## `decks/`

- `decks/meta/` — flat folder, one file per netdeck.
- `decks/<name>/` — one folder per personal deck, holding `v1..vN` plus notes.
- **`decks/banned/`** — real lists that are illegal under the current banlist.
  Kept for reference, **never trained on**; `rl.decks.decklist_files` excludes
  the folder outright rather than relying on call sites to remember.

## `reference/`

Source material, not derived data: scraped guides. The rules PDFs are local-only
(gitignored, as is anything else third-party) — download them from Riot. Read these
before a build — they are the reason several "obvious" assumptions turned out to
be wrong. Two claims in `riftbound-deckbuilding-tips.txt` are annotated in place
as corrected against the Tournament Rules.

## Tests

```bash
python3 rl/tests/test_judge.py     # 2017 community judge calls replayed
python3 rl/tests/test_env.py       # gym wrapper, canonicalization, info leaks
python3 rl/tests/fuzz.py --decks   # random games on real decklists
```

`rl/tests/` holds nine engine suites plus the judge audit; each runs standalone.
