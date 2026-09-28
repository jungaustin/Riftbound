# Riftbound

A rules engine and a self-play reinforcement-learning agent for **Riftbound**,
Riot Games' trading card game, plus a deck-building toolkit that sits on the
same card data.

The core of the project is a from-scratch engine that implements the game's
Core Rules closely enough to replay more than 2,000 real judge rulings. On top
of it is a PPO agent that learns the game by playing against itself across
dozens of real tournament decklists.

## What's in here

| | |
|---|---|
| [`rl/engine/`](rl/engine/) | **The rules engine.** Turn structure, the Chain and priority, combat, triggered and replacement abilities, costs and discounts, hidden information. Every card in the pool is scripted, including all 49 Legends and 66 Battlefields |
| [`rl/`](rl/) | **The agent.** A Gym-style environment, an observation encoder, a policy network, and a PPO trainer with self-play against a pool of frozen past selves. See [`rl/README.md`](rl/README.md) |
| [`riftbound/`](riftbound/) + [`cli.py`](cli.py) | **Deck-building toolkit.** Legality checks (banlist, errata, signature cards), deck statistics, combo detection, and an automated critique pass |
| [`sim/`](sim/) | An earlier referee, now kept only as a rules specification |
| [`decks/`](decks/) | Decklists: tournament lists plus my own builds, with notes and card ratings |

## Highlights

- **Tested against real rulings.** [`rl/tests/test_judge.py`](rl/tests/test_judge.py)
  stages each community judge ruling from RiftJudge as a board state and checks
  that the engine reaches the same answer. The suite has found 62 engine bugs so
  far. When a ruling contradicted the written rules, it was recorded as rejected,
  with the rule number, instead of being encoded.
- **Invariant-checked fuzzing.** [`rl/tests/fuzz.py`](rl/tests/fuzz.py) plays
  random and scripted games on real decklists and checks conservation of cards,
  zone legality, and stalls or livelocks after every action.
- **Cards encoded by behaviour.** The policy sees each card through features
  derived from its scripted abilities, not just a card ID, so it can generalise
  to cards it has rarely seen.
- **Decisions stay with the player.** When the rules give the player a choice
  (trigger ordering, which replacement effect applies, how to split damage), the
  engine suspends and asks the player instead of picking a default.

## Quickstart

Requires Python 3.11+, `numpy`, and `torch`.

```bash
# Deck tools
python3 cli.py legends
python3 cli.py check decks/meta/<deck>.txt

# Engine tests
python3 rl/tests/test_judge.py
python3 rl/tests/fuzz.py --decks

# Train, then play against the agent
python3 rl/ppo.py 150 --real-decks --victory 3 --per-deck 12 --out rl/runs/NAME
python3 rl/play.py vs --ckpt rl/runs/NAME/best.pt --victory 3 --seat 0
```

Design notes, the training log and the backlog are in [`rl/docs/`](rl/docs/).
Repository layout and data conventions are in [`DEVELOPMENT.md`](DEVELOPMENT.md).

## How it was built

This project was built with heavy use of [Claude Code](https://claude.com/claude-code).
[`CLAUDE.md`](CLAUDE.md) and [`CONTEXT.md`](CONTEXT.md) are the working notes that
carry state between sessions, and they're left in on purpose.

## Disclaimer

This is an unofficial fan project. It is not endorsed by, affiliated with, or
sponsored by Riot Games, Inc. Riftbound, its card names, card text, artwork and
rules are the property of Riot Games. Card data and rules text are included only
so the engine can run, and this project is non-commercial.

## License

The source code is released under the [MIT License](LICENSE). The license does
not cover Riot Games' intellectual property described above.
