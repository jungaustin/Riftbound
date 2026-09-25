# Working in this repo

## Keep `CONTEXT.md` current — this is the standing job

`CONTEXT.md` is how Austin starts a fresh chat without asking for a summary.
**Read it at the start of every session, and update it whenever the state it
describes stops being true.** Do not wait to be asked.

Update it when any of these change:

- a training run starts, finishes, or dies (`rl/runs/<name>`)
- a measurement produces a result worth acting on
- something known-broken gets fixed, or a new one is found
- a decision is made that would otherwise have to be re-explained
- work is committed, or the uncommitted pile changes materially

It is **state, not a log**. Rewrite, condense and delete freely — a finding that
has been acted on becomes one line or goes away. If it grows past ~120 lines it
has become a log; prune it. Keep "Last updated" honest.

Prefer updating it *as you go* rather than at the end of a turn: a session can be
interrupted, and the value is entirely in it being current when that happens.

## Orientation

| | |
|---|---|
| `CONTEXT.md` | current state — **read first** |
| `README.md` | what the three sub-projects are |
| `rl/README.md` | index into `rl/docs/` (PLAN, LEARNING, PLAYING, RUNS, BACKLOG) |
| `rl/docs/BACKLOG.md` | everything deferred, with effort estimates |

## Rules that will bite you

- **Never wrap `python3` in `timeout`** — it breaks numpy here. Use the Bash
  tool's own `timeout` parameter.
- **Measure rather than assume.** Repeatedly this session, reading the code gave
  the wrong answer and a probe gave the right one: a field declared but never
  read, a flag that looked implemented, a per-deck gap that turned out to be deck
  strength. If a claim matters, test it.
- **Austin's rules corrections come from play and have been reliable.** Verify
  against `data/rules.txt` (Core) and `data/tournament_rules.txt` (the authority
  for sideboarding and competition rules — Core never mentions them), then save
  the result to memory. A ruling that contradicts `data/rules.txt` goes in
  `rl/tests/judge/rejected.json` with the rule number.
- **`decks/banned/` must never reach training.** `rl.decks.decklist_files`
  excludes it; do not bypass that at a call site.
