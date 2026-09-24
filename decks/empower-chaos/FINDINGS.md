# Empower/Chaos — full findings

Research pass 2026-09-10. Four builds, every claim rules-cited. All three
`cli.py check` **LEGAL**.

| Build | File | Identity | Legend / Champion |
|---|---|---|---|
| **Mel — Breach triggers** | `mel-breach-v1.txt` | Mind+Chaos (blue/purple) | Mel - Soul's Reflection / Mel, Defiant Soul |
| **Teemo — Hidden engine** | `teemo-hidden-v1.txt` | Mind+Chaos (blue/purple) | Teemo - Swift Scout / Teemo - Strategist |
| **Sanction stack** | `sanction-stack-v1.txt` | Calm+Chaos (green/purple) | Vex - Gloomist / Vex - Apathetic |
| **Kennen — Flow & wide** | `kennen-flow-v1.txt` | Order+Chaos (yellow/purple) | Yordle, Kennen - Heart of the Tempest / Fizz - Trickster |

Each deck has a `<name>-explanations.md` covering every slot.

---

# PART 1 — The Sanction / Tornado Warrior stack

**Your read is correct, and the payoff is bigger than the version you were given.**

## The rules chain, verified

1. **Tornado Warrior** empowers unit X → queues *"Disempower it at end of turn."*
2. **Sanction** mode 2 — *"Disempower a unit that's [Empowered]. Empower it at end of
   turn."* — disempowers X **now**, queues *"Empower it at end of turn."*
3. **317.1.a** — both delayed effects fire in the **Ending Step**: *"At the end of the
   turn Game Effects take place."*
4. **383.3.d** — *"If more than one Triggered Ability is Triggered simultaneously, then
   the player that controls the Abilities selects the order to place them on the Chain."*
   You control both, so you choose.
5. Resolve **Tornado Warrior's disempower first**. **442.1.a.1** — *"Game effects that
   instruct a player to Disempower a card that is not currently Empowered will do
   nothing."* It fizzles harmlessly.
6. Resolve **Sanction's empower second**. X becomes Empowered with **no disempower left
   queued against it.**

## What you actually win — two prizes, not one

**Prize A — the Empower becomes permanent.** X stays Empowered through the opponent's
turn, which is the *only* way this archetype ever gets a defensive `[Empowered][>]`
ability to matter. Normally Tornado Warrior strips it at end of turn, before their
attack ever happens.

**Prize B — and this is the one your source missed — you get a SECOND trigger.**
**441.2.a**: *"When a Game Object becomes Empowered as a result of the Empower game
action, that is an event that can similarly be referenced by game effects and
abilities."* **828.1.d** confirms "When I become Empowered" fires on that event.

So Sanction mode 2 does not merely restore the status — it creates a **fresh
become-Empowered event** in the Ending Step. On **Kharox** that is a second
*"opponent Burns 3, then play a unit from their trash free"* **in the same turn.**

One Sanction, and you choose which prize by choosing the target:

| Target | Prize A (permanent) | Prize B (2nd trigger) |
|---|---|---|
| **Steel Paws** `{1}` 0M | **+7 Might on defence** — a `{1}` card blocking as a 7-Might Deflect wall | — |
| **Nasus, Ascended** | "When I conquer, score 1 point" survives to your next Beginning Phase | — |
| **Kharox** | — | **Burn 3 + steal a unit from their trash, twice** |
| **Tail-Cloaked Matriarch** | — | Play a unit from your trash, twice |
| **Mel, Defiant Soul** | — | Banish an enemy unit ≤3 Might, twice |

**The ordering trap:** if Sanction's empower resolves *first*, Tornado Warrior's
disempower resolves second and **undoes the whole thing**. You must place them so the
disempower resolves first. Per the repo's ordering note, the chain is LIFO — placed
last resolves first — so place **Sanction's effect first**. Check this at the table.

---

# PART 2 — Is there an infinite? No. Here is the proof.

I searched for every loop shape. **There is no true infinite combo in Mind/Chaos or
Calm/Chaos.** Five structural blockers, all rules-cited:

1. **315.1.b — only your Awaken readies.** Every Exhaust-cost engine (Pack of Wonders,
   the Teemo Legend, Hextech Formula) is hard-capped at once per turn.
2. **820.1.b — Repeat executes an effect "a second time."** Exactly one extra
   execution. It is not an N-times loop; no Repeat card can be chained.
3. **Recycle goes to the bottom of the Main Deck, not the trash.** Every "play a card
   from your trash" engine self-terminates. Fizz - Trickster says so explicitly:
   *"Recycle that spell after you play it."*
4. **Power is permanent attrition.** Even a free-*energy* loop bleeds runes out of the
   pool every iteration, so it is bounded by your rune count at worst.
5. **No zero-cost, non-Exhaust repeatable ability exists in either pool.** I scanned
   both for activated abilities whose cost contains neither Exhaust nor a resource
   symbol. Nothing came back.

## The best BOUNDED loops (these are real and strong)

**Loop 1 — Fizz + Temporal Breach** *(Mind/Chaos)*
Fizz - Trickster `{3}{P1}` enters → plays **Temporal Breach** from trash ignoring its
Energy cost (Temporal Breach is `{2}`, under Fizz's `{3}` cap) → Temporal Breach banishes
Fizz and replays him **ignoring his cost** → Fizz's trigger fires again.
**Bounded by:** Fizz recycles each spell to the bottom of your deck, so you need one
more Temporal Breach in the trash per iteration. Max 3. Each iteration costs `{P1}`
(Fizz: *"You must still pay its Power cost"*).

**Loop 2 — Tail-Cloaked Matriarch + Temporal Breach** *(the real Mind/Chaos engine)*
**124.1/124.2** — changing zones clears all statuses, and **Empowered is listed as a
status**. So Temporal Breach *resets* Empowered. The Matriarch's Empower is only
`{2}{Chaos}`, cheap enough to re-pay:
Empower (`{2}{Chaos}`) → play a unit from trash → Temporal Breach her (`{2}{P1}`) →
status cleared → Empower again → **another unit from trash.**
~4 runes and 2 attrition per extra trigger. Repeat until runes run out.

**Loop 3 — Mel, Defiant Soul, the cheapest of all**
Her Empower cost is **"Discard a spell"** — *zero runes*. Empower → banish an enemy unit
≤3 Might → Temporal Breach her → Empower again by discarding → **banish again.** The
only cost is cards. This is the highest trigger-count line in the format.

---

# PART 3 — The three builds

## Build A — Mel: Breach triggers (blue/purple)

`mel-breach-v1.txt` · 8 Mind / 4 Chaos · avg 2.92 runes · attrition 18

**What you cheat in:** Empower costs, repeatedly, by *resetting* rather than paying.

**Why the Legend and Champion are the point.** Mel - Soul's Reflection: *"When you
empower something else, empower me. Disempower me, Exhaust: give a unit at a
battlefield −2 Might this turn."* Mel, Defiant Soul: *"When I become Empowered, banish
an enemy unit at a battlefield with 3 Might or less."*

Every Empower you perform anywhere also arms the Legend, and her −2 Might **drags the
next target into banish range**. With **Mel, Newly Awakened** Empowered in the main
deck that becomes −3 (*"if a spell or ability you control would give −Might to a unit
it chooses, it gives an additional −1"*), so 6-Might units die.

**Win condition:** banish their board one or two units per turn while Tail-Cloaked
Matriarch rebuilds yours from the trash; take uncontested battlefields.

**Play pattern:** T1-2 cheap Hidden body, hide Temporal Breach or Tornado Warrior.
T3-4 Mel, Defiant Soul from the Champion Zone; Empower by discarding a spell; banish.
T5+ each turn: free-Empower via Tornado Warrior → banish → Temporal Breach → Empower
again → banish again. Legend fires between each for −2.

## Build B — Teemo: the Hidden engine (blue/purple)

`teemo-hidden-v1.txt` · 8 Mind / 4 Chaos · avg **2.60** runes (lowest) · attrition 16
23 of 40 cards cost ≤2 runes.

**What you cheat in:** the *hide tax itself*, and then everything downstream of it.

**Teemo - Swift Scout is the only Legend that makes the engine free.** *"You may pay
`{1 energy}` to hide a card with [Hidden] instead of `{any rune}`."* The re-hide loop
normally costs one rune of **attrition** every turn; Teemo converts that into energy,
which refreshes. Over a ten-turn game that is roughly six runes you keep.

**And Teemo alone can run Guerilla Warfare.** `{2}{P1}` — *"Return up to two cards with
[Hidden] from your trash to your hand. **You can hide cards ignoring costs this
turn.**"* It is a **Signature card with the Teemo tag**, so **103.2.d.2** makes it legal
under Teemo - Swift Scout and illegal everywhere else. It rebuys two dead engine pieces
*and* makes that turn's hiding free.

Second Legend ability: *"{1 energy}, Exhaust: Put a Teemo unit you own into your hand
from your Champion Zone **or the board**."* Teemo - Scout and Teemo - Strategist are both
Hidden, so this is a dedicated re-hide loop for them.

**Win condition:** grind. Teemo - Strategist re-flipped every turn (*"when I'm played
from [Hidden], reveal the top 5, deal 1 to an enemy unit here for each card with
[Hidden]"*) is 2-3 damage per turn in a deck that is 40% Hidden, plus Ember Monk
growing +2 each flip.

**Play pattern:** hide on turn 1 and never stop. Keep two facedowns live at all times.
Leave runes up — everything you own is Reaction speed once hidden.

## Build C — Sanction stack (green/purple)

`sanction-stack-v1.txt` · 7 Calm / 5 Chaos · avg 2.98 runes · **attrition 8** (lowest)

**What you cheat in:** an `{8}` and a `{7}` Empower cost, and the disempower clause itself.

Six free-Empower cards — the most of any pairing — because **Sanction needs no facedown
slot**, which is the archetype's one hard bottleneck (811.1.b: one facedown per
battlefield, and 486.4 gives you two battlefields).

The two biggest Empower costs in the format are both Calm and both here:
- **Nasus, Ascended** `{8}{P1}` 8M Deflect 2 — Empower `{8}` → *"When I conquer, you
  score 1 point."*
- **Steel Paws** `{1}` **0 Might** — Empower `{7}` → *"+7 Might."* With the Sanction
  stack making it permanent, a one-drop **blocks as a 7-Might Deflect wall**.

**Second combo — Reckoner's Arena.** *"When you hold here, activate the conquer effects
of units here."* Nasus holds every turn and conquers almost never (**190.4.c**), so the
Arena converts his conquer trigger into a **per-turn hold trigger**. Sanction is a
`[Reaction]`, so empower Nasus *in response to the hold trigger* during your Beginning
Phase. **471.2.c** caps it at once per turn — two points per turn, not more.

**Win condition:** two points a turn off Reckoner's Arena, or a hold-lock behind Deflect
bodies while Kharox strips their trash.

---

## Build D — Kennen: Flow & wide (yellow/purple)

`kennen-flow-v1.txt` · 6 Order / 6 Chaos · avg 3.08 runes · attrition 18

**What you cheat in:** the Empower itself, over and over, by playing cards from zones
other than your hand.

**Kennen's Assault 2 is capped at once per turn.** *"Disempower me, **Exhaust**: Give a
unit [Assault 2]."* Exhaust is part of the cost and only your Awaken readies (315.1.b).
**Hall of Legends** — *"When you conquer here, you may pay `{1}` to ready your legend"* —
is the **only card in the format that readies a Legend**, and it takes you to two per
turn. That is the ceiling.

So the swing comes from **Order's go-wide package plus an anthem**, not from the Legend:
Vanguard Captain (`{3}` for three bodies), Up from the Deep, Guards!, Noxian Emissary,
under Garen - Commander (+1) or Undertitan (+2 this turn). Per rules-fact 5 an anthem on
a token board converts every trade into a conquest.

**The engine** is the trash: Lightning Rush and Kennen, Storm of Shuriken fill it, then
every **[Flow]** cast (Up from the Deep and Dragon Form both have Flow costs equal to
their printed cost) is a card played from a non-hand zone that re-empowers Kennen.
Tornado Warrior does it best of all — flipping it is a non-hand play **and** a free
Empower in one action.

# PART 4 — Corrections logged this pass

- **Kayle, Justified does not work with free Empowers.** 442.1 removes the status, so
  she never accumulates. She wants hard-cast Empowers. *(User caught this.)*
- **`[Empowered][>]` defensive abilities do not work with free Empowers** either —
  stripped at end of your turn, before the opponent attacks. Cut Serene Ascetic and
  Frostcoat Mother for this.
- **Guerilla Warfare is Teemo-exclusive.** I earlier said "the Mind/Chaos build can run
  it"; it is narrower — only the **Teemo** Legend. The DB states this plainly
  (`supertype: Signature`, and `cli.py pool` prints `Spell/Signature`); the error was
  reading `db.cards` directly instead of `legal_pool`.
- **The Calm/Chaos Legend was wrong.** Originally Irelia - Blade Dancer, picked because
  Sanction *chooses a friendly unit* and Irelia readies chosen units. Over-valued: 144.4
  means a readied unit cannot cross to another battlefield without Ganking, and exhausted
  units already defend (464.2.c.3) and hold (469.2). Replaced with **Vex - Gloomist**
  (draw on every hold — and this deck holds by design) and **Vex - Apathetic** as
  Champion (Deflect body that stuns every unit they play and stops it moving).
- **The Mel deck ran Teemo - Strategist and surplus Hidden cards.** Leftovers from a
  generic Mind/Chaos list. The rule they broke: **811.1.b gives one facedown per
  battlefield and 486.4 gives two battlefields**, so a Hidden card whose payoff *scales
  with Hidden count* competes with Tornado Warrior for the only slot the engine needs.
  Replaced with 3x Smoke Screen (`-4` Might, the largest in the pool, and the exact
  enabler for Mel's `≤3` Might banish) and 2x Mushroom Pouch (a free card every turn for
  controlling a facedown — rewards the engine **without** competing for the slot).
- **Teemo - Scout cut 3 → 2**, freed slot to a third Ember Monk.
- **Tornado Warrior is illegal in Mind+Calm** (`[ERROR 103.1.b.4]`). Tornado Warrior +
  Sanction exists only in **Calm+Chaos**.

# PART 5 — Open questions for a judge

1. **Ordering direction at the Ending Step.** 383.3.d gives you the choice; confirm
   whether placing an ability *first* means it resolves *last* (LIFO) at your table.
   The combo depends on Tornado Warrior's disempower resolving **before** Sanction's
   empower.
2. **Does Nasus's extra point dodge the Final Point rule?** 471.1.a.1 exempts points
   "from sources that are not Conquer"; his is granted by his own ability but triggered
   by a conquer. Unresolved.
3. **Does 442.1 Disempower strip one instance or all** of a multi-stacked Empowered
   status? Decides whether Kayle is ever buildable.
