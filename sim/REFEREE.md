# Running a game without API calls

## Can one chat play both decks?

**No — not with real hidden information.** This is worth being blunt about
because the failure is invisible.

A chat is one context window. If both decklists have been shown in it, whoever
is reasoning has read both, and there is no way to un-read them. "I'll pretend
I don't know what's in their deck" is not information hiding; it is a model
predicting what a player who didn't know would do, which is a different and much
worse thing. Every decision comes out contaminated — playing around a card
because it's *in the list*, not because the board implies it — and nothing in the
logs would show you it happened. You would get plausible games, plausible losses,
and lessons that don't transfer to a real opponent.

Hidden information has to be enforced structurally, by never letting the two
decklists into the same context. That means two contexts.

## Three setups that work

**1. Two browser chats** — the no-setup option. Paste
`sim/briefs/lillia-fae-fawn-v7.txt` into one chat and
`sim/briefs/meta-darius-fury-order.txt` into another. You act as the referee:
render the state, paste each seat's view into its own chat, read back the
`ACTION:` line. Correct isolation, entirely manual. Fine for a handful of games
while you're still debugging the engine and want to read every decision anyway.

**2. Two Claude Code subagents** — the automatable option, and the one that fits
how you want to pay for this. Each subagent starts from a cold context, so
giving one the Lillia brief and the other the Darius brief gives genuine
isolation for free. The orchestrator drives both without either seeing the
other's deck, and it runs on your Claude Code plan rather than per-call API
billing. This is the version to build toward once the engine is real.

**3. One chat, one pilot** — Claude plays a single seat and a scripted heuristic
plays the other. Isolation is trivially preserved because the opponent has no
context at all. Cheapest way to get real games, and the right first milestone.

## The referee is supposed to know everything

The asymmetry is the design, not a compromise. The referee holds full state —
both decks, both hands, both libraries — because it has to enforce legality and
resolve cards. The pilots hold partial state. That maps exactly onto the
engine/policy split: the engine is the source of truth and cannot be lied to;
the pilot only ever receives `view_for(player)` and can only ever reply with an
index into a list the engine built.

So a referee that knows both decks is not a leak. A *pilot* that knows both
decks is the leak, and the brief generator is what prevents it — it takes one
decklist and emits one file, with no parameter that would let both in.

## The loop

Per decision:

1. Engine computes the four-state (Neutral/Showdown × Open/Closed), determines
   who holds Priority and Focus, and enumerates legal actions — filtered for
   both cost and timing.
2. Engine renders `view_for(active)` per `PLAYFIELD.md` and sends it to that
   seat's context only.
3. Pilot replies with exactly `ACTION: <n>` and `WHY: <one line>`.
4. Engine validates the index, applies the action, logs `(state hash, actions
   offered, action taken, why)`.
5. Repeat.

If a pilot returns an invalid index, fail loudly — don't coerce it to a default.
A pilot that can't read the state is a bug in the brief or the renderer, and
silently substituting `pass` would bury it.

**Auto-pass every window where the only legal action is to pass.** That single
optimization is what takes a game from 400+ decisions to roughly 200, and most
of the eliminated windows are Closed-State priority passes where the pilot holds
no `[Reaction]` and has nothing it could legally do anyway.

## Regenerating briefs

```sh
python3 sim/make_brief.py decks/lillia-fae-fawn/v7.txt > sim/briefs/lillia-fae-fawn-v7.txt
```

Card text is pulled live from `data/cards.json`, so a brief regenerated after a
set update reflects current text. Regenerate after any deck edit — a stale brief
means the pilot is playing a deck that no longer exists, which is exactly the
kind of mismatch that produces confident, wrong conclusions.

Missing cards are reported on stderr and rendered as `(card text not found)`
rather than silently omitted.

## Decklist format

All 27 decklists were normalized to a single format
(`python3 sim/normalize_decks.py`). The repo previously carried two dialects,
which meant every reader had to handle both or silently misparse one. Canonical
form:

```
# optional comment
Legend: Lillia - Bashful Bloom
Champion: Lillia - Fae Fawn
Main Deck:
3x Stupefy
Battlefields:
1x Dusk Rose Lab
Runes:
9x Mind Rune
```

`Sideboard:` is emitted only when a deck has one, and is parsed separately —
sideboard cards never reach a pilot brief, since they can't be drawn.

**Main deck lists show 39 cards, and that is correct.** The Chosen Champion
counts toward the 40-card minimum (103.2) but starts in the Champion Zone rather
than the deck, so the list holds the other 39. Any legality check that expects
40 listed cards will wrongly fail every deck in this repo.
