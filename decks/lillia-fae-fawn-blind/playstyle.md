# Playing Sprite Tempo (v6)

## The one combat fact that governs everything

Combat damage is simultaneous and equal to Might. **A 3-Might Sprite attacking
a 3-Might blocker trades — both die, nobody controls the battlefield.** A
5-Might Sprite kills the blocker and *survives at full Might to hold it*.

So before every attack, ask: does this Sprite **win**, or only **trade**? If it
only trades, either pump it, shrink theirs, move the blocker, or don't attack.
The whole 1-rune interaction layer exists to answer that question:

| card | runes | what it does to the math |
|---|---|---|
| Stupefy | 1 | −1 Might to theirs, **and draws** |
| Charm | 1 | moves the blocker away — **no combat happens at all** |
| Discipline | 2 | +2 Might at Reaction speed, **and draws** |
| Heart of Dark Ice | 0 | +3 Might, free, every turn — but **your turn only** |
| Wages of Pain | 3 (or **0** hidden) | kills a 3-Might blocker **before** combat — no trick war happens at all. Leaves a Gold token = a stored Power pip |

| Smoke and Mirrors | 2 (or **0** hidden) | swap Fae Fawn to base: she leaves a Sprite behind *and* the base Sprite arrives — two bodies, Lillia safe, and a card |

**Why the pump cards were trimmed to 2 Discipline and En Garde cut entirely.** A Standard Move
costs zero runes (144.4) and only the Turn Player readies (315.1.b), so whoever
is attacking has a full pool and the defender has leftovers. This deck *spends*
2-4 runes manufacturing its attacker before it can move, so it enters every
showdown behind on runes — in both seats. You lose Might arms races structurally.
The cards that don't care are the ones that end the combat before it starts
(Wages of Pain, Charm), the ones that are already paid for (anything Hidden), and
Defy, which counters their trick outright.

## Rune posture — the habit that matters most

**A rune you spend on your turn is gone for the opponent's turn too.** You only
ready at your own Awaken Phase (315.1.b), so runes exhausted in your Main Phase
leave you defenceless until your next turn.

This deck holds up **eight 1-rune cards** (3 Stupefy, 3 Defy, 2 Charm) plus
2 Lilting Lullaby at 2 — **and a hidden card, which costs nothing at all to
flip.** With four Seals, the Power half of those costs is free too. So **leaving 2 runes live threatens two
different answers**, and 3 covers nearly everything. Target posture after the
opening turns: spend down to **2-3 runes live, not to zero.**

- Turn 3 (6 runes): Legend activation (4, or 3 if you moved Fae Fawn first)
  leaves 2-3 live. The model turn.
- Turn 4 (8 runes): Legend + a 3-rune body = 7, leaving 1 — only if you need
  the board. Legend + hold 4 is often stronger.
- Heart of Dark Ice is the exception that proves the rule: its activation costs
  **no runes**, so it pumps without touching the live-rune budget. Install it
  when you can spare the 3 runes; it pays every turn after.
- **The Seals are the other exception, and they change the posture.** Once
  Seal of Focus and Seal of Insight are down, each gives 1 Power per turn at
  Reaction speed for free — so a held-up Defy costs you an exhausted rune
  instead of a recycled one. Play them early; they are free on any turn you were
  spending a Power pip anyway (see `patterns.md`).
- Watch attrition on {P2} cards specifically. You channel 2 runes a turn, so a
  card recycling 2 costs a **whole turn of channelling** on top of its cast —
  Riptide Rex on turn 4 leaves you at 8 runes on turn 5 instead of 10.

**When to tap out anyway:** to contest a battlefield you must have, to land a
bomb that ends it, or against a deck with no instant-speed interaction. A turn
spent holding runes for a trick that never comes is also wasted. Judgement, not
a rule.

## Battlefields — which to present, and how to play each

Selection reasoning lives in the README. This is the in-game half.

**Which to present.** In **Bo3 (Match)** you choose one per game and the used
ones are burned (486.5), so present in this order:

| game | present | because |
|---|---|---|
| 1 | **Dusk Rose Lab** | the blind pick — turn order isn't known yet (115 comes *after* battlefield setup, 113), and the Lab doesn't care |
| 2-3, on the play | **Hall of Legends** | conquer-gated; going first is what gets you the first conquer |
| 2-3, on the draw | **Ravenbloom Conservatory** | on the draw they take the first field, so you'll be defending — and every defence is better than a coin flip for a free card |

One override, from Riot's question 2 (*what if they had it?*): **Ravenbloom is
worth roughly what it is worth to you times their spell density.** Against VEN
Kai'Sa Burn — the densest spell deck in the format — it is as good for them as
for you. Present Hall of Legends in both seats in that matchup.

In **Bo1 (Duel)** one of your three is chosen at random (485.5) — nothing to
decide, so ignore the table.

**Dusk Rose Lab — a card every turn, but sequence it or you throw away a point.**

At the start of your Beginning Phase both the Lab trigger and the Temporary
trigger go on the chain; you control both, so **you order them** (RiftJudge FAQ
#9231). Resolve the Lab first — kill the doomed Sprite as its cost, draw 1, and
the Temporary trigger then finds nothing.

- With **two units there** (Trevor plus a Sprite, say): Lab-kill the Sprite,
  keep Trevor, still hold and score. This is the line you want — a card *and* a
  point.
- With **one unit there**: you were losing the field anyway (190.4.c — no units
  means you lose control at the next cleanup), so the draw is free. Take it.
- With a **Hidden Sprite Call** at the Lab: flip the replacement first, *then*
  Lab-kill the old token. Draw 1, keep the field, score the hold.
- **Never Lab-kill your only unit there before the replacement is in.**

**Hall of Legends — hold it in reserve for the turn you close.**

Every conquest here offers "pay {1}, ready your Legend." Do the arithmetic before
you take it: the second activation costs {4} minus one per friendly Temporary
unit, so realistically {2}-{3}, and 1 + 3 = **4 runes for a second Sprite** on
top of whatever the first one cost. That is a tap-out turn, and tapping out
surrenders the opponent's turn. Take it when the extra Sprite converts to a
point or a needed block; skip it and keep your runes live when it doesn't.

The turn it is worth tapping out for is **the 8th point**, and Hall of Legends is
what manufactures the extra ready Sprite for it without spending a card.

**The double conquest (v6's declared plan), from 7 points:**

1. Conquer battlefield A. You are at 7, so 471.1.b.1 converts the point to a
   card draw — that is expected, not a misplay. **A has still been Scored**
   (469.1 defines the Conquer itself as the Score).
2. Hall of Legends triggers: pay {1}, ready your Legend, activate again for
   {2}-{3} → a second ready Sprite in base.
3. Conquer battlefield B. Every battlefield is now Scored this turn, so the
   Final Point lands. **Win.**

**The easier version if you control anything at all:** hold one battlefield in
your Beginning Phase — non-Conquer points are exempt from the restriction
entirely (471.1.a.1), so a hold at 7 just wins. Take that line whenever it is
available; the double conquest is what you do when it isn't.

Confirm step 1 with a judge before an event. The rules support it, but the whole
plan rests on it.

**Ravenbloom Conservatory — free cards for being attacked.**

"When you defend here, reveal the top card of your Main Deck. If it's a spell,
put it in your hand. Otherwise, recycle it."

- **21 of your 40 are spells (52.5%)**, so it hits more often than not. Recycle
  is bottom-of-deck (416.1), not a discard — the miss costs you nothing
  permanent.
- It fires on **their** turn, so it costs you no tempo and no runes. Nothing else
  in the deck generates cards without spending a turn.
- The real cost is the 47.5% where you bottom a unit or gear. Bottoming your last
  Thousand-Tailed Watcher on the turn you needed it is a genuine loss — accept it
  as the price, don't play around it.
- It only fires when they **attack this battlefield**. Against a passive opponent
  it does nothing, which is fine: a passive opponent is one you are already
  beating on points.

## Mulligan

Keep any hand with a turn-1 or turn-2 play:

- **Scuttle Crab / Petal Pixie turn 1** → move it turn 2, conquer. Scuttle Crab
  already drew you a card and 0 Might still conquers and holds.
- **Sprite Fountain turn 1** (2 runes) → a **ready** Sprite that moves and
  conquers on turn 2.
- Hands with a 1-rune trick plus any body are fine — you can develop and
  interact in the same turn from turn 2 onward.

Ship hands with both Thousand-Tailed Watchers. One 7-rune card is fine; two is a
stalled start. **A hand with a Seal and any turn-1 body is a keep** — the Seal
costs nothing on the turn you were spending a Power pip anyway.

## Early game (turns 1-3)

- **Move Fae Fawn first, then activate the Legend.** Her move costs nothing and
  leaves a Temporary Sprite, dropping the Legend from 4 runes to 3. Free
  discount every turn she's on board.
- Accelerated Fae Fawn is 4 runes = a **turn-2 play on the play**; she enters
  ready, moves and conquers the turn she lands.
- Play Sprites to **base** when you intend to conquer, and onto a controlled
  battlefield only to reinforce — see the movement table in `patterns.md`.
- Hide Smoke and Mirrors at Lillia's battlefield once you can spare a rune.

## Mid game (turns 4-6)

- **Trevor Snoozebottom is denial, not the plan** (down to 2 in v6). He survives
  your Beginning Phase and holds a battlefield the opponent then has to spend
  real cards to take; his hold trigger fires in the Scoring Step, *after* the
  Temporary check, so the Sprite he makes lives through their whole turn as a
  renewing bodyguard. **That Sprite can never leave** — Standard Move is
  Base↔Battlefield only (144.4). Park him on the field you are *not* planning to
  re-conquer, and take the other one twice.
- **Keep two ready Sprites in base whenever you can afford it.** That is the
  double conquest, and the opponent has to respect both battlefields every turn
  once you show it.
- **Charm has two modes.** Defensively/offensively: move their blocker to base
  and conquer uncontested. Aggressively: move a unit *out of their base* onto a
  battlefield you control — that makes it Contested (450) and causes combat
  (452), so your units kill it. That's your only reach into their base.
- Install Heart of Dark Ice on a turn you can spare 3 runes; from then on every
  attacking turn has a free +3.

## The bombs

- **Riptide Rex is gone from the main deck** (v6) and lives in the sideboard as
  the Vex - Apathetic answer. {6}{P2} recycles 2 runes against a channel rate of
  2 a turn, so it cost a whole turn of ramp on top of its cast.
- **Thousand-Tailed Watcher** (7 runes, turn 4): every enemy unit **board-wide**
  gets −3 Might this turn. Play it on the turn you attack, not as a body. It
  never kills (minimum 1 Might) — it opens the board.
- **Unchecked Power was cut in v6.** It exhausts all friendly units, so you sweep
  and then cannot take the empty battlefields — the opposite of what the double
  conquest wants. There is no reset button now; the Watcher is the only way
  through a board you cannot beat.

## The Smoke and Mirrors fork (hidden at Lillia's battlefield)

If Lillia is alone at a battlefield with a Sprite in your base and they attack
her, flip Smoke and Mirrors as a reaction. Swap her with the base Sprite; the
swap **is a move**, so she leaves another Sprite behind. You defend with two
3-Might Sprites, Lillia is safe at base, and you drew a card. Rules chain in
`patterns.md`. Cap: one Hidden card per battlefield, two battlefields in 1v1 —
Smoke and Mirrors at Lillia's, Sprite Call at the other.

## Closing — read before you reach 7 points

Rule 471.1.b.1: at 7 points, winning by **Conquer** requires that you scored
*every* battlefield that turn. **Holding has no such restriction.** Plan the
last point as either:

1. a **hold** with a real body (Trevor, Petal Pixie, Scuttle Crab, Rex, the
   Watcher), or
2. a **double conquest** — which needs **two ready Sprites in your BASE**,
   because units already at a battlefield cannot split up without Ganking.
   The cheap line is Sprite Fountain ({2}{P1}, forced to base) followed by the
   Legend activation, now discounted to {3} by the Fountain's Sprite: **5 runes,
   two ready Sprites in base, live from turn 3.**

Thousand-Tailed Watcher is the closing button for this: -3 Might to *every*
enemy unit opens **both** battlefields in the same turn, which is exactly what
the double conquest needs. Save it for the turn you go for 8.

## Showdown priority

1. **Lilting Lullaby** on the first meaningful trick — it counters *and* locks
   them out of spells for the turn, ending the whole showdown. Only 2 runes.
2. **Defy** (1 rune) on anything in the ≤4-energy bracket — where most removal
   and tricks live.
3. **Discipline** to win the combat outright; it also draws.
4. **Stupefy** to flip a combat within 1 Might; it cantrips, so never wasted.
5. Flipped **Sprite Call** or a hand Sprite Call at Action speed adds a ready
   3-Might body at a battlefield you control, mid-showdown.

## Matchups (data/archetypes.md)

- **VEN Kai'Sa Burn** — hardest. Every Sprite dies to their cheap spells; win on
  economics (their card per your free token). Board in Akali + Crescent Strike.
- **VEN Master Yi Solo** — good: free chump blockers blank a "defends alone"
  plan. Board in Janna.
- **VEN Azir Equipment** — your Sprites outclass 2-Might Sand Soldiers. Board
  the gear hate; their Arise! bursts are still dangerous.
- **VEN Kennen Movement** — grind race. Lullaby their Ride the Wind turns.
- **Vex - Apathetic** (user play data) — **the hardest lock in the format for
  this deck. Treat it as "kill it or move it, or you do not conquer."**

  "When an opponent plays a unit while I'm at a battlefield, [Stun] it. They
  can't move it this turn." Vex only has to be at *a* battlefield — either
  one, yours or theirs.

  The reason this is a lock and not a tax: **every Sprite you could move is one
  you played this turn.** Temporary kills at the start of your Beginning Phase,
  before your Main Phase, so there is never a Sprite left over from last turn to
  move. Every Sprite is born stunned and rooted, and dies before it is ever
  allowed to move. The Sprite conquest plan is switched off, not slowed.

  What still works while Vex stands at a battlefield:

  - **Stunned Sprites are still walls.** They deal no damage (423.1.b) but they
    must still be dealt damage equal to their full Might to die (423.1.c). Three
    stunned Sprites still cost the opponent 9 damage to clear.
  - **Sprites played straight onto a battlefield you already control** never
    needed to move. They reinforce; they just can't take anything new.
  - **Permanent units** — Trevor, Petal Pixie, Scuttle Crab, Fae Fawn, Rex, the
    Watcher. They are stunned the turn they land, then act normally every turn
    after. Under Vex these are the whole deck.

  The three answers, in order of preference:

  1. **Charm Vex to its base, then make your Sprites.** Vex has Deflect, so Charm
     costs {1}{P1} + {P1} = **2 runes** (809.1.c). With Vex at base the trigger
     has no condition and the Sprites you play after are free to move. Order
     matters: Charm first, then generate. 2 runes answers their 4-drop for a
     turn — the best rate in the deck.
  2. **Crescent Strike** (sideboard): 3 energy + its Power + Deflect's Power =
     **3 runes**, and 4 damage kills a 4-Might Vex exactly. Action speed.
  3. **Riptide Rex** (sideboard only since v6): 6 damage on entry, 6 runes.
     Whether Deflect taxes Rex is
     an open question — Deflect charges "spells and abilities … **to play**"
     (809.1.c) and Rex's damage is a triggered play-effect, not something you
     play. Judge check. Either way Rex costs 6 runes and Vex dies.

  Boarding stays as listed above, but bring the Crescent Strikes in for this
  matchup specifically, not just the Rex.
