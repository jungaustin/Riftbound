# `sim/` is a rules SPECIFICATION, not the engine

**Do not build on this.** The working engine is `rl/engine/`. This directory is
kept because it is a readable, rules-cited referee that is useful to *read*
against the rulebook — `rl/docs/PLAN.md` §2 puts it plainly:

> Treat `sim/engine/` as a rules specification that happens to be written in
> Python.

## Why it cannot be the foundation

- **No combat, no Chain, no [Hidden].** `rl/docs/PLAN.md` notes it "cannot serve as
  the oracle" for exactly this reason, which is why `rl/tests/fuzz.py` is the
  oracle instead.
- **It has known rules bugs the RL engine already fixed.** `sim/engine/actions.py:93`
  removes recycled runes from the ready pool before checking Energy, so it
  overcounts what a card costs — a card needs `max(energy, power)` runes, not
  their sum (164.2, and Recycle carries no ready requirement).

## What it is still good for

Reading. When a rule is unclear, `sim/engine/` often states it in one place with
the rule number attached, and that is faster than re-deriving it. `PLAYFIELD.md`
and `REFEREE.md` are the prose versions of the same thing.

`sim/briefs/` holds two hand-written game briefs (`make_brief.py` generates
them) used when this was the demo path.
