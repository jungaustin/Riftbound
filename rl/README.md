# `rl/` — the agent

Start here, then pick the document you need.

| document | |
|---|---|
| [`LEARNING.md`](docs/LEARNING.md) | **What the algorithm is** (PPO), the network, how to read a training run, how to change things and know whether it helped |
| [`PLAYING.md`](docs/PLAYING.md) | Playing against it and asking it for advice |
| [`RUNS.md`](docs/RUNS.md) | The run log — results, the self-play drift measurements, per-deck breakdowns |
| [`BACKLOG.md`](docs/BACKLOG.md) | Everything deferred or half-finished, including the audit of decisions the engine makes for the player |
| [`PLAN.md`](docs/PLAN.md) | The design reasoning behind all of it. Long, and the source of truth for *why* |

## Layout

```
engine/     the rules engine -- the real one. 2017 judge calls pass against it
tests/      nine engine suites + tests/judge/ (80 case files) + fuzz.py
agents/     hand-written baselines (greedy.py is the yardstick, not a learner)
tools/      triage.py
runs/       training output. gitignored -- 51M of checkpoints
```

Modules: `env.py` (gym wrapper) → `obs.py` (state → tensors) → `nets.py`
(network) → `ppo.py` (trainer), with `vec.py` batching, `eval.py` measuring,
`pool.py` holding frozen opponents, `decks.py` loading decklists, and `play.py` /
`viewer.py` for humans.

## Quickstart

```bash
python3 rl/ppo.py 150 --real-decks --victory 3 --per-deck 12 --out rl/runs/NAME
python3 rl/play.py vs --ckpt rl/runs/NAME/best.pt --victory 3 --seat 0
```

One iteration is ~2048 transitions, roughly 9s on CPU. Use `best.pt`, not
`last.pt` — see the drift finding in `RUNS.md`.
