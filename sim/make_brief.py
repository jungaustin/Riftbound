#!/usr/bin/env python3
"""Generate a pilot brief for one deck.

The brief is the whole setup message for one bot's chat: rules primer, its own
card pool, the playfield format, and the reply contract.

It deliberately contains ONE decklist. Two pilots must be briefed in two
separate contexts, or the hidden information the simulation exists to model is
gone. See sim/PLAYFIELD.md.

    python3 sim/make_brief.py decks/lillia-fae-fawn/v7.txt > sim/briefs/lillia-v7.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine.cards import ACTION, REACTION, Card, find     # noqa: E402
from engine.decklist import Decklist, parse_deck         # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


RULES_PRIMER = """\
## Riftbound — what you need to know

**Win condition.** First to **8 victory points**. Points come almost entirely
from *Holding* battlefields.

**The scoring rule that drives everything.** In your **Beginning Phase**, you
Hold every battlefield you *already control* and score it. You do NOT score a
battlefield by taking it on your own turn — you score it by having held it
through the opponent's entire turn. Taking a battlefield late in your turn is
worth nothing unless you can keep it. Defending what you hold is usually worth
more than grabbing something new.

**Turn structure** (your turn, in order):
  1. **Awaken**  — you ready everything you control.
  2. **Beginning** — you Hold and score every battlefield you control. ← points
  3. **Channel** — you channel 2 runes. (Going second: +1 on your first turn.)
  4. **Draw**    — you draw 1.
  5. **Main**    — rune pools empty, then you act freely. Only you may act.
  6. **Ending**  — all units heal, "this turn" effects expire, pools empty.

**Rune economy.** Your Rune Deck is exactly 12, and you channel 2 per turn — so
you are fully channelled by turn 6 and gain nothing after. Each rune gives you
a choice:
  - **Exhaust for 1 Energy** — renewable, it readies again next Awaken.
  - **Recycle for 1 Power** — the rune leaves play and goes to the *bottom of
    your Rune Deck*.
Energy is rent; Power is a sale. A Power cost permanently shrinks your board of
runes until you re-channel it, so a card costing Power is meaningfully more
expensive than its energy number suggests.

**Combat and Showdowns.** Units of two opposing players at the same battlefield
stage a **Combat**. Contesting control of a battlefield opens a **Showdown**.
Both put the turn into a *Showdown State*, which restricts what can be played.

## Play timing — read this before planning any turn

The turn is always in one of four states, from two independent axes:
  - **Neutral** (no Showdown/Combat) vs **Showdown** (one is running)
  - **Open** (Chain is empty) vs **Closed** (something is on the Chain)

What you may play depends on your card's keyword. The tiers are strictly nested:

  | Card         | Playable in                                              |
  |--------------|----------------------------------------------------------|
  | no keyword   | **Neutral Open only, on your own turn**                   |
  | `[Action]`   | Neutral Open **+ Showdown Open**                          |
  | `[Reaction]` | **All four states** — including both Closed States        |

The two hard prohibitions:
  - **In a Showdown State, only `[Action]` and `[Reaction]` can be played.**
    Your plain spells are dead during a Showdown, even on your own turn.
  - **In a Closed State — any time the Chain is not empty — only `[Reaction]`
    can be played.** Reaction is your only real counterplay.

`[Reaction]` also resolves **before** whatever is already on the Chain (last on,
first off). That is what lets it counter or pre-empt.

**Plan around this.** Do not dump a `[Reaction]` in Neutral Open when a plain
spell would have done the same job — you are spending your only interaction
window. Conversely, holding a plain spell "for the right moment" is a mistake:
there is no later window for it. Plain spells are use-them-on-your-turn cards.

**Priority vs Focus.** Both are needed to act. You hold **Priority** in your own
Main Phase; you gain **Focus** during Showdowns. Gaining Focus grants Priority,
but holding Focus *without* Priority means you must wait. The state header tells
you both.
"""

CONTRACT = """\
## The playfield

Each turn you receive one state block. Everything in it is what you can see:
public board, both trashes, both scores, and **your own hand**. You do not see
the opponent's hand, deck, or facedown cards, and you have never been told their
decklist. You learn what they play by watching it resolve. Reason from what is
visible and from what their revealed cards imply — never assume a specific card.

The `STATE` line tells you which of the four states you are in and therefore
what class of card is playable. In `YOUR HAND`, each card is marked ✓ or ✗ for
playable *right now* — a ✗ on a card you can afford is a **timing** block.

## How to reply

The engine lists every legal action, numbered. It has already filtered for cost
and timing, so anything listed is legal and anything absent is not.

**Reply with exactly two lines:**

```
ACTION: <number>
WHY: <one short sentence>
```

Nothing else. No preamble, no analysis, no markdown. If you want to explain your
plan, compress it into the WHY line.

Pick only from the numbered list. Do not invent actions, name cards not listed,
or describe a sequence — you will be asked again after each one resolves.

Your WHY line is logged and read back when reviewing losses. Make it say what
you were actually trying to do ("holding Reaction for their Showdown" beats
"good play"), because it is how a human tells a bad deck from a bad pilot.
"""


def render(deck: Decklist) -> str:
    L: list[str] = []
    A = L.append

    A(f"# Riftbound pilot — {deck.name}")
    A("")
    A("You are piloting one deck in a game of Riftbound against an opponent whose")
    A("decklist you have not seen and will not be told. Play to win.")
    A("")
    A(RULES_PRIMER)
    A("")
    A("## Your deck")
    A("")
    main_count = sum(c for c, _ in deck.main)
    A(f"**Legend:** {deck.legend} — starts in your Legend Zone and never leaves it.")
    A(f"**Chosen Champion:** {deck.champion} — starts in your **Champion Zone**, "
      "not shuffled into your deck. You can deploy it from there; you do not have "
      "to draw it.")
    A("")
    A(f"Your Champion counts toward the 40-card minimum, so the list below is "
      f"**{main_count} cards** — that is what you actually draw from.")
    A("")

    missing: list[str] = []

    def emit(count: int, name: str) -> None:
        card = find(name)
        if not card:
            missing.append(name)
            A(f"- {count}x **{name}** — (card text not found)")
            return
        head = f"- {count}x **{name}** · {card.cost_str()} · {card.type}"
        if card.might is not None:
            head += f" · {card.might} might"
        label = card.timing_label()
        if label != "—":
            head += f" · **{label}**"
        head += f" · {'/'.join(card.domains) or 'Colorless'}"
        A(head)
        if card.text:
            A(f"    {card.text}")

    A("### Main deck")
    for count, name in deck.main:
        emit(count, name)
    A("")
    A("### Battlefields (you bring 3; ONE is chosen at random at setup)")
    for count, name in deck.battlefields:
        emit(count, name)
    A("")
    A("### Rune deck (12 total)")
    for count, name in deck.runes:
        A(f"- {count}x {name}")
    A("")

    def tier_count(tier: str) -> int:
        return sum(c for c, n in deck.main
                   if (card := find(n)) is not None and card.timing == tier)

    reactions, acts = tier_count(REACTION), tier_count(ACTION)

    A("### Your interaction budget")
    A("")
    A(f"This deck runs **{reactions} `[Reaction]` cards** (playable in any state,")
    A(f"including with the Chain full) and **{acts} `[Action]` cards** (playable in")
    A("Showdown Open as well as your own Neutral Open). Every other card in the")
    A("deck can only be played in **Neutral Open on your own turn**.")
    A("")
    A("That count is your entire ability to interact on the opponent's turn. Spend")
    A("it deliberately.")
    A("")
    A(CONTRACT)

    if missing:
        sys.stderr.write(f"WARNING: {len(missing)} card(s) not found: {', '.join(missing)}\n")
    return "\n".join(L)


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write(__doc__ + "\n")
        return 2
    path = Path(sys.argv[1])
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        sys.stderr.write(f"no such decklist: {path}\n")
        return 1
    print(render(parse_deck(path)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
