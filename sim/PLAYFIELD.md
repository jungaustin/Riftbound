# Playfield format

The single text block a pilot sees each time it must act. The engine renders it
fresh from game state via `view_for(player)` — pilots never touch state directly.

Rendered from the **viewing player's** perspective. `you` / `opp` are always
relative to the viewer, so the same code renders both sides with no special
casing, and a pilot can never accidentally read the other seat's private data.

## Privacy rules

These are the whole point of the format. The renderer must never emit:

| Thing | What the viewer sees |
|---|---|
| Opponent hand | count only |
| Opponent main deck | count remaining only |
| Opponent rune deck | count remaining only |
| Opponent facedown cards | count only, per battlefield — never identity |
| Opponent decklist | **nothing, ever** — not even as a hint |

Everything else is public in Riftbound and is shown to both seats: units and
runes in bases (107.1.d), permanents at battlefields (107.2.c), both trashes,
both scores, the Chain.

The opponent's decklist is the load-bearing one. A pilot learns what the
opponent plays only by watching it hit the board or the trash. This is what
makes the simulation worth running — remove it and both pilots play a game of
open information that no human ever plays.

## Vocabulary

Riftbound-specific names the format uses, because the rules do:

- **Chain**, not "stack" — where played spells and abilities wait to resolve.
- **Focus**, not "priority" — who may act right now.
- **Trash**, not "graveyard".
- **Hold** — scoring a battlefield you control, in your Beginning Phase.
- **Recycle** — send a rune to the *bottom of the Rune Deck* (Power costs), as
  opposed to **exhaust**, which is renewable (Energy costs).

## Turn structure

Every rendered state names its phase. In order (rules 315–317):

| Phase | What happens |
|---|---|
| Awaken | Turn player readies everything they control |
| Beginning | Beginning Step, then **Scoring Step: turn player Holds every battlefield they control** |
| Channel | Turn player channels 2 runes (+1 extra on the second player's first turn) |
| Draw | Turn player draws 1 (empty deck = Burn Out, then still draws) |
| Main | Rune pools empty, then discretionary actions. Only the turn player may act |
| Ending | End-of-turn effects, all units heal, "this turn" effects expire, pools empty |

**Scoring happens at the *start* of your turn, for battlefields you already
control.** You must hold a battlefield through the opponent's entire turn to
score it. This single fact drives most of the strategy, so it is stated
explicitly in the pilot brief rather than left to be inferred.

## Play timing — the four states

This is the part a simulator gets wrong most easily, and getting it wrong
invalidates every conclusion drawn from the logs. The turn is always in exactly
one of four states, formed from two independent axes (rules 308–310):

- **Neutral** (no Showdown or Combat in progress) vs **Showdown** (one is).
- **Open** (the Chain is empty) vs **Closed** (the Chain exists).

| State | Meaning |
|---|---|
| Neutral Open | No Showdown/Combat, empty Chain — the ordinary Main Phase |
| Neutral Closed | No Showdown/Combat, something is on the Chain |
| Showdown Open | Showdown or Combat running, Chain empty |
| Showdown Closed | Showdown or Combat running, something on the Chain |

What may be played in each state is determined by the spell's keyword. The three
tiers are strictly nested — each grants everything the tier above it has:

| Card | Playable in | Rule |
|---|---|---|
| **No keyword** | Neutral Open only, **on your own turn**, holding Priority | 155, 310.1.a |
| **`[Action]`** | Neutral Open **+ Showdown Open** | 159.2.a.1, 308.1.a |
| **`[Reaction]`** | All four states — everything above **+ Neutral Closed + Showdown Closed** | 159.2.b, 309.1.a |

Stated as the two prohibitions the engine must enforce:

- **In any Showdown State, only `[Action]` and `[Reaction]` cards may be played**
  (308.1.a). A plain spell is dead during a Showdown, even on your own turn.
- **In any Closed State — whenever the Chain is non-empty — only `[Reaction]`
  may be played** (309.1.a). This is what makes `[Reaction]` the only true
  counterplay in the game.

`[Reaction]` also **resolves before items already on the Chain** (159.2.b.3) —
last on, first off. A pilot holding a Reaction can answer something mid-Chain;
one holding a plain spell cannot, no matter how much energy it has.

**Activated abilities** default to the same restriction as plain spells — the
controller's own turn, during an Open State (381) — unless the ability itself
carries `[Action]` or `[Reaction]`, which extends it the same way.

### Priority and Focus are not the same thing

Both must be true for a pilot to act, and the distinction matters during
Showdowns (rules 312–313):

- **Priority** is the exclusive right to take a discretionary action. You get it
  in Neutral Open during *your* Main Phase, when you gain Focus, or when you
  control the next Chain item and the current holder passes.
- **Focus** is permission to act specifically during a **Showdown Open** state.
  Gaining Focus also grants Priority (313.2); passing Priority *keeps* Focus
  (313.3); and **you may not act on Focus alone without also holding Priority**
  (313.4).

The renderer shows both, because "I have Focus but not Priority" is a real and
non-obvious state in which the correct and only move is to wait.

Since the engine enumerates legal actions anyway, none of this is left to pilot
judgment — but the pilot is told the state so it can *plan*, e.g. hold a
Reaction rather than dumping it in Neutral Open where a plain spell would do.

## Format

```
=== RIFTBOUND | game <id> | turn <n> | active: <YOU|OPP> | phase: <PHASE> ===
STATE    <Neutral Open | Neutral Closed | Showdown Open | Showdown Closed>
         playable now: <any card | [Action] and [Reaction] only | [Reaction] only>
SCORE    you <n>  |  opp <n>          (first to 8 wins)
CHAIN    <(empty) | numbered, top of Chain LAST — resolves bottom-up>
PRIORITY <you | opp | none>
FOCUS    <you | opp | none>

--- BATTLEFIELDS ---
[B1] <name>                              control: <YOU|OPP|none>  contested: <yes|no>
     you: <unit (n might, ready|exhausted[, n dmg]) | —>
     opp: <same | —>
     facedown: <empty | opp has 1 card facedown here | your <card name>>
[B2] ... same shape

--- YOUR BASE ---
runes    ready <n> | exhausted <n> | rune deck <n>
pool     <n> energy, <n> power
units    <list | —>
gear     <list | —>
legend   <name>
champion <in play at Bn | in champion zone | in trash>

--- OPPONENT BASE ---
   ... same shape, minus anything private

--- YOUR HAND (<n>) ---
  <✓|✗> <name>  <cost>  <type>  <timing>  <might if unit>  <rules text>

  ✓/✗ = playable in the CURRENT state (cost affordable AND timing legal).
  timing = "—" (plain: Neutral Open, your turn) | [Action] | [Reaction]
  A ✗ on an affordable card is a timing block, not a cost problem.

--- TRASH ---
you (<n>):  <names>
opp (<n>):  <names>

--- DECKS ---
you <n> remaining | opp <n> remaining | opp hand <n>

--- LEGAL ACTIONS ---
  1. <action>   (<cost>)
  ...
  n. pass
```

## Contract

The engine **enumerates every legal action** and numbers them. The pilot replies
with a number and one short line of reasoning — nothing else.

This is what makes the pilot unable to cheat: it cannot invent an action, play a
card it cannot pay for, or act out of turn, because the only thing it can emit
is an index into a list the engine built. Rules enforcement lives entirely in
the engine, never in the pilot's good behavior. It also means a pilot that
returns garbage fails loudly instead of silently corrupting the game.

The one-line reason is not decoration — it is the log field that tells you, when
reviewing a loss, whether the deck lost or the pilot misplayed.
