# Verified rulings and sequencing — Sprite Press

Rule numbers are **RUP4 (2026-07-16)**, extracted at `data/rules.txt`.
Interaction lines marked (ref §N) are from
`reference/riftbound_temporary_interactions.txt` (RiftJudge-cited).

## THE RUNE ECONOMY — read this before costing any turn

**Runes needed to cast = max(energy, power). NOT energy + power.**

A Basic Rune has two *independent* abilities (164.2):

- `[E]: [Reaction] — Add {1}` — exhaust it for 1 Energy.
- `Recycle this: [Reaction] — Add {Power}` — recycle it for 1 Power of its domain.

The recycle ability's cost is **only** "Recycle this". It carries no
ready-state requirement, and Recycle (416) is defined purely as putting the
card on the bottom of the Rune Deck. So a rune that has **already been
exhausted for Energy can still be recycled for Power in the same turn** —
one physical rune produces both.

Consequences, all verified 2026-07-31 (user-corrected; the tooling was wrong
before this date and has been fixed in `analyze.py` / `critique.py`):

- `{2}{P1}` (Sprite Fountain) is a **2-rune** play — exhaust both for Energy,
  recycle one of them for the Power. It is castable on **turn 1**.
- `{2}{P2}` (Lilting Lullaby) is a **2-rune** play, not a 4-rune play.
- `{1}{P1}` (Defy) is a **1-rune** play.
- Accelerated Fae Fawn = 4 Energy + 1 Mind Power = **4 runes = turn 2 on the
  play**, exactly as the published guides claim. (An earlier note here said
  this was impossible; that was based on the wrong model.)
- Accelerated Thousand-Tailed Watcher = 8 Energy + 2 Mind = **8 runes**, turn 4.

**The real price of a Power cost is ATTRITION, not a later cast turn.** Every
recycled rune goes to the bottom of the Rune Deck and must be re-channelled
(2 per turn) before it works again, so your board of runes SHRINKS:

- Sprite Fountain on turn 1 → turn 2 you have 3 runes, not 4.
- Sprite Fountain on turn 2 → turn 3 you have 5 runes, not 6.

So plan Power-heavy turns one turn ahead: ask what next turn's rune count is
before committing. `cli.py stats` now prints total deck attrition.

## Turn structure the deck lives on

- Awaken Phase readies everything FIRST (315.1), **then** Beginning Phase:
  Beginning Step (315.2.a) → Scoring Step (315.2.b). Temporary kills and Dusk
  Rose Lab both trigger in the Beginning Step, BEFORE scoring.
- **Temporary is a triggered ability on the chain, not silent removal**
  (816.1). It can be responded to. It checks once, at the start of your
  Beginning Phase — tokens created after that check (mid-turn) survive until
  your NEXT Beginning Phase (ref §1).
- A lone Sprite can therefore never hold-score by itself: it dies in
  315.2.a before the 315.2.b scoring step. It CAN conquer the turn it's made,
  defend all through the opponent's turn, and deny their conquests.

## The save line (ref §3, verified vs 811)

Temporary trigger on the chain, your only unit at that battlefield is the
dying token, Sprite Call is Hidden there:

1. RESPOND to the trigger — never let it resolve first. While it is pending
   the old token is alive, you still control the battlefield, the Hidden card
   is still valid.
2. Flip Sprite Call: Hidden grants [Reaction] facedown (811.6), plays for 0,
   must play to that same battlefield (811.1.d.1).
3. New ready Sprite enters → old token dies to the trigger → you keep control
   → Scoring Step: you hold and score.

Only Reaction-speed responses work in that window — Action and Neutral spells
cannot respond to a chain item no matter the energy available (ref §4,
159.2, 813).

## Dusk Rose Lab (ref §6, RiftJudge FAQ #9231 / ruling #9428)

Lab trigger + Temporary trigger both go on the chain at your Beginning Step;
you control both, YOU order them. Resolve the Lab first: kill the doomed
Sprite as its cost → draw 1 → the Temporary trigger finds nothing and is
ignored. With a Hidden Sprite Call too: flip the replacement FIRST (while the
old token still lives), then Lab-kill the old token, then Temporary fizzles —
draw 1 + battlefield kept + hold point (ref §6).
NEVER Lab-kill your only unit there before the replacement is in.

## WHICH SPRITES CAN ACTUALLY CONQUER — movement is the constraint

**A Standard Move goes Base → Battlefield or Battlefield → Base. That is all**
(144.4.a / 144.4.b). Battlefield → Battlefield requires **Ganking** (144.4.c,
810), which no card in v4 has. A Temporary Sprite therefore cannot make a
two-turn journey — it dies at your next Beginning Phase — so **where a Sprite
is created decides, permanently, whether it can ever conquer.**

| Source | Enters where | Ready? | Can conquer? |
|---|---|---|---|
| Legend activation | base **or** a battlefield you control (355.2.a) | ready | **YES** if played to base |
| Sprite Fountain | forced **to your base** | ready | **YES** |
| Sprite Call (from hand) | base or a controlled battlefield | ready | **YES** if played to base |
| Sprite Call (from Hidden) | the battlefield it was hidden at (811.1.d.1) | ready | no — locked there |
| Lillia - Fae Fawn's move | the location she moved **from** | NOT ready | no — blocker only |
| Trevor Snoozebottom's hold | **"here"**, Trevor's battlefield | ready | no — cannot leave |

Consequences to play around:

- The conquest engine is **Legend + Sprite Fountain + Sprite Call from hand**.
  Play those Sprites to **base** whenever the plan is to take a battlefield;
  play them straight onto a controlled battlefield only to reinforce a hold.
- **Double conquest in one turn** (the rule-471.1.b.1 route to the 8th point)
  needs **two ready Sprites sitting in your BASE**, e.g. Legend activation plus
  Sprite Fountain. Two Sprites at a battlefield cannot split up.
- Trevor's and Fae Fawn's Sprites are defensive value only. That is not a
  knock on either card — it is what makes their battlefields hold — but never
  plan a conquest around them.

## The rune engine — Seals, and why attrition is not what the tool prints

**A Seal is free on the turn you play it, if you needed a Power pip that turn
anyway.** Seal of Focus (Calm) / Seal of Insight (Mind) are {0}{P1} gear reading
`Exhaust: [Reaction] — Add 1 Power of that domain`.

- **359.2.d: a non-unit gear enters the board READY at your base.** So it works
  the turn it lands.
- Pay the Seal's {P1} by recycling a rune, then immediately Exhaust the Seal for
  that same Power and spend it on the real card. Net rune cost is identical to
  having recycled that rune directly — and you keep the Seal.
- **315.1.b readies every Game Object you control** at Awaken, so it recurs.
- The Add is **[Reaction]**, so a Seal produces Power on the OPPONENT's turn —
  it funds Defy without shrinking your rune board.

So `cli.py stats` overstates this deck's attrition: it counts each Seal's own
pip but cannot see the pip coming back. Read the printed number as one-time,
minus 1 per Seal per turn thereafter.

**Power pips are domain-specific.** Seal of Focus only pays Calm pips, Seal of
Insight only Mind. v6's split is 8 hard Calm / 12 hard Mind (+4 hybrid from
Lilting Lullaby, payable by either).

**The hidden cost of a {P2} card:** you channel 2 runes per turn, so a card that
recycles 2 costs a FULL TURN of channelling on top of its cast. Riptide Rex
{6}{P2} on turn 4 (8 runes) leaves you with 8 again on turn 5 instead of 10.
Thousand-Tailed Watcher is {7}{P1} — one rune, half the bleed — and its -3 Might
to all enemy units opens BOTH battlefields, which is why it is the better top
end under a double-conquer plan.

## Retreat — cut in v6, ruling kept for reference

`{1}` P0 Mind, [Reaction]: return a friendly unit to hand, its owner channels 1
rune exhausted.

- Rune-neutral: 1 rune exhausted to cast, 1 rune channelled back. The channelled
  rune enters **exhausted**, readies at your next Awaken (315.1.b), so it is
  live on your following turn and can help pay Fae Fawn's Accelerate.
- **It does NOT save a hold.** If the retreated unit was your only one there you
  lose the battlefield exactly as you would have by dying (190.4.c). It saves
  the card, not the field.
- Returning to hand is **not a move**, so it does not trigger Fae Fawn's
  "when I move from a location" Sprite spawn.
- Best against targeted removal, where the alternative is losing the card for
  nothing.

## Hidden — the rune-asymmetry fix, and the constraint on it

**Why the deck wants Hidden cards at all.** A Standard Move costs **zero runes**
(144.4) and **only the Turn Player readies** (315.1.b), so whoever attacks does
so with a full rune pool while the defender holds only what they declined to
spend last turn. This deck is on the wrong side of that in both seats: it must
spend 2-4 runes *manufacturing* an attacker before it can move, and it defends on
leftovers. A Hidden card is bought on your turn and flips for **{0}** on theirs —
it moves your surplus window into their window. Hiding costs 1 **Power**, which a
Seal produces free at Reaction speed, so the whole loop costs nothing.

**The constraint, and it is severe:**

- **811.1.b** — you may only hide "at a battlefield **you control** that doesn't
  already have a facedown card hidden there, **for as long as you control that
  battlefield**." One facedown per battlefield, two battlefields in 1v1.
- **107.3.d** — "If a player loses Control of a Battlefield, any cards in the
  Facedown Zone associated with that Battlefield are **removed** during the next
  Cleanup."
- Your Sprites die at your Beginning Phase, so you lose the battlefield
  (190.4.c) and the hidden card goes with it.

So in a pure-Sprite deck a hidden card lives for **exactly one opponent turn**.
That is still enough — 811.6 grants Reaction while facedown, so you can always
cash it during their turn (even at their end step, purely for value) before it
expires. But it means **Trevor's battlefield is the only place a facedown card
persists across turns.** That is the second reason Trevor stays at 2.

- **811.1.b: it does not gain Reaction until the NEXT turn.** You cannot hide and
  flip on the same turn.
- **811.1.d.2:** a hidden spell's targets must be chosen from the battlefield it
  was hidden at. The rules use Blastcone Fae as the worked example.
- **811.3:** you may always just hard-cast a Hidden card normally instead.

## Signature cards — the deckbuilding trap

**103.2.d.2: every Signature card in a deck must carry the Champion tag matching
the deck's Legend.** An off-tag Signature card does not merely fail to work — the
**decklist is illegal**. **Lilting Lullaby is the only Signature card legal in
this deck.** Five others pass a Calm+Mind *domain* filter and fail the tag rule:
Fox-Fire (Ahri), Siphoning Strike (Nasus), and Forgefire Cape / Rabadon's
Deathcrown / Shurelya's Requiem (Ornn). Enumerate candidates through
`cli.py pool`, never a raw read of `data/cards.json`.

## Battlefield control and score triggers

- **You lose a battlefield the moment you have nothing standing on it.**
  190.4.c: a player with no units at a battlefield loses control of it in the
  following cleanup (190.4.a: you keep control only "for as long as you have
  Units at that Battlefield"). Our Sprites die in the Beginning Step, so we lose
  the field before the Scoring Step and have to **retake** it.
- **Consequence — this deck conquers far more often than a normal deck.** A
  normal deck conquers a field once and holds it for six turns; the Temporary
  churn means we re-conquer the same field repeatedly. So **conquer-triggered
  battlefields (471.2.a) are worth more to us than to almost anyone we face**,
  and hold-triggered ones (471.2.b) are worth *less*. That inverts the usual
  "hold triggers fire more often" heuristic — check it per deck.
- **Conquer triggers never fire while you keep the battlefield.** 469.1 defines
  Conquer as gaining control of a field you did not yet score this turn; if you
  already control it you can only Hold. Emperor's Dais and Hall of Legends fire
  on capture, not on upkeep.
- **A battlefield's controller controls its abilities** (190.6.a). An
  uncontrolled battlefield's abilities are run by the Turn Player (190.6.b). So
  Dusk Rose Lab only ever draws for whoever has a body there — which is us.
- **The clean 8th-point line** (471.1.a.1 + 471.1.b.1): score one battlefield by
  **Hold** in your Beginning Phase (non-Conquer points are exempt from the final
  point restriction), then **Conquer** the other in your Main Phase — every
  battlefield has now been scored this turn, so the Conquer wins.
- **The double-conquer 8th point WORKS** (re-read 2026-08-05; an earlier note
  here called it unsafe, which was too pessimistic). **469.1 makes the Conquer
  itself the Score** — "A player Scores in one of two ways: Conquer: A player
  gains Control of a Battlefield they did not yet Score this turn." 471 is
  downstream of that, and 471.1 says the player "Gains **up to one** Point,"
  which is the language that lets the Score happen while the point is converted
  to a draw. So at 7: conquer A (Score A, gain 0, draw 1) → conquer B (Score B,
  every battlefield now Scored → Final Point → win).
  Still worth a judge check before an event, because it is the whole gameplan.

## Stun, and why Vex - Apathetic is a hard lock here

Vex - Apathetic: "When an opponent plays a unit while I'm at a battlefield,
[Stun] it. They can't move it this turn." Either battlefield, either side.

- **Every Sprite we could move is one we played this turn.** Temporary kills at
  the start of our Beginning Phase, *before* the Main Phase, so there is never a
  leftover Sprite from last turn. Every Sprite is born stunned and rooted and
  dies before it is ever allowed to move. The Sprite conquest plan is switched
  **off**, not taxed. (Corrected 2026-08-05; the earlier note here claiming
  "last turn's Sprites move freely" was wrong.)
- **Stunned units are still walls.** 423.1.b — no Might contributed in the
  combat damage step; 423.1.c — they must still be dealt damage equal to their
  full Might to die. A stunned 3-Might Sprite still costs 3 damage to remove.
- **Stunned wears off in step 3d of the end-of-turn cleanup** (423.1.a.2), so
  our permanents (Trevor, Pixie, Scuttle Crab, Fae Fawn, Rex, the Watcher) are
  stunned only on the turn they land and act normally forever after. Under Vex
  they are the entire deck.
- **Deflect costs Power, and Power is priced by max(), so it is often free in
  rune count.** 809.1.c: spells and abilities an opponent controls that choose
  the Deflect permanent cost that much more Power *to play*. Charm becomes
  {1}{P2} = still **2 runes**; Crescent Strike becomes {3}{P2} = still **3
  runes**. The tax lands entirely on attrition, not on the cast turn.
  *Open question:* Riptide Rex's damage is a triggered play-effect, not
  something "played", so whether Deflect taxes it at all is unclear. Judge check.

## Token facts

- Tokens enter **exhausted** by default (185.2.d). Printed "ready" overrides:
  Legend's Sprite, Sprite Call's, Trevor's hold-Sprite. **Fae Fawn's
  move-spawn Sprite is NOT ready** — it is a holder/blocker.
- Units (tokens included) are played to your base OR a battlefield you
  already control (355.2.a). Ready Sprites MOVE to conquer new battlefields;
  they can be played straight onto a held one to reinforce.
- Standard move cannot go battlefield→battlefield — that needs [Ganking]
  (810) or an effect (Windswept Hillock).
- Exhausted units still defend (defender designation is presence-based,
  464.2.c.3) and still hold (holding checks control, 469.2, not ready state).
- Tokens cannot exist off the board (186): Emperor's Dais "return a unit to
  hand" on a Sprite just evaporates it — the Sand Soldier still arrives
  (cost was paid), and IT is permanent and holds.

## Engine cards (cards in the current v5 list)

- **Legend discount** counts friendly **units** with Temporary, and it does
  NOT carry between turns — your Temporary units die in the Beginning Step,
  before your Main Phase. The free way to get it is sequencing: move Fae Fawn
  first (her move costs nothing and leaves a Temporary Sprite), then activate
  for 3 instead of 4. Sprite Fountain is a **gear**, so it does not count.
- **Fae Fawn + Accelerate** (805): pay {1}{Mind} extra → she enters ready
  (a replacement effect — she was never exhausted, 805.6). Total 4 Energy +
  1 Mind Power = **4 runes = turn 2 on the play**; unaccelerated she is 3
  runes, turn 2, but enters exhausted.
- **Smoke and Mirrors' swap IS a move** (355.4/420) — swapping Fae Fawn
  triggers her "when I move from a location" Sprite spawn at her origin.
- **Heart of Dark Ice**'s activation cost is `Exhaust:` with **no rune
  component**, and rule **381** limits activated abilities to your own turn.
  So it is a free +3 Might every turn, on offence only, that never competes
  with runes held up for reactions.
- **Charm forces combat**: moving an enemy unit from their base onto a
  battlefield you control makes that battlefield Contested (450) and causes
  combat (452). It is this deck's only reach into an opponent's base.
  *Open question:* who is attacker vs defender when your effect moves their
  unit (464.2.c.2 keys off who applied Contested). Worth a judge check.
- **Unchecked Power** deals 12 to all units **at battlefields** — units in a
  base are untouched, yours included.

## Cards no longer in the deck (rulings kept for reference)

- **Heimerdinger - Inventor** has all Exhaust abilities of friendly LEGENDS, so
  he casts Bashful Bloom's Sprite ability, discount included. He enters
  exhausted, so he only starts working the turn AFTER he lands. Cut in v4.
- **Keeper of Masks** + its 2 Reflections = 3 Temporary units, so the Legend's
  activation drops to {1} — but all three enter **exhausted** and die at your
  next Beginning Phase, so they only ever block once. Cut in v4.
- **LeBlanc - Everywhere At Once**: "YOUR Temporary effects at my battlefield
  don't trigger" — Sprites at her battlefield never die. Cut in v4 because
  Sprite Fountain forces its Sprite to base and Fae Fawn's spawns where she
  left, so two of four Sprite sources cannot feed her.

## Mode facts (1v1 Duel, 485)

- Victory Score 8 (485.3). Each player brings 3 battlefields; ONE of yours is
  randomly selected (485.4-485.5) — all three picks must stand alone.
- Player going second channels +1 rune on their first turn (485.7).
- Scoring: Conquer = gain control of a battlefield not yet scored this turn;
  Hold = still controlling it at your Scoring Step; once per battlefield per
  turn total (469-470). Final-point restriction: a Conquer for the winning
  point requires having scored every battlefield this turn, else it draws a
  card instead (471.1.b.1) — plan the last point around a HOLD or score both
  fields that turn.

## Tool-numbering note

**Fixed 2026-08-05** — `cli.py`/`riftbound/*.py` used to cite pre-RUP4 numbers
(e.g. "rule 644.5" for battlefield selection, "515.2" for Beginning Phase).
Those are now corrected in `prompt.py`, `rules.py`, `critique.py`, and
`combos.py`. `data/rules.txt` is RUP4-current (Last Updated 2026-07-16).

The battlefield one was not just a renumbering: old 644.5 said "chosen at
random," which is now only **485.5 (Duel, Bo1)**. In **486.5 (Match, Bo3)** you
*choose* which of your three to present, and one used in a game someone won is
burned for the match. Anything reasoned from "battlefields are random" is worth
re-checking for Bo3 play.
