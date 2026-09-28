# Sanction stack — every card, and why

`sanction-stack-v1.txt` · Calm+Chaos (green/purple) · 7 Calm / 5 Chaos
Legend **Vex - Gloomist** / Champion **Vex - Apathetic**
avg 2.98 runes · **attrition 8** — the lowest of the three builds

**Plan in one sentence:** use Tornado Warrior and Sanction together to make an Empower
**permanent**, then either block behind a `{1}` card that is now a 7-Might wall, or take
two points a turn off Reckoner's Arena.

---

## The combo the deck is named for

**Tornado Warrior** empowers a unit → queues *"disempower at end of turn."*
**Sanction** mode 2 disempowers it **now** → queues *"empower at end of turn."*
At the Ending Step (**317.1.a**) you control both delayed effects, so **383.3.d** lets
you order them. Resolve Tornado Warrior's disempower **first** — **442.1.a.1** makes it
do nothing against an already-disempowered unit — then Sanction's empower resolves and
sticks, with no disempower left queued.

**Two different prizes, and you pick by picking the target:**

- **Permanence** — the `[Empowered][>]` ability survives into the opponent's turn. This
  is the *only* way this archetype ever gets a defensive Empower ability to matter.
- **A second trigger** — **441.2.a**: becoming Empowered is an **event**. Sanction's
  end-of-turn empower is a *fresh* become-Empowered event, so "When I become Empowered"
  fires a second time in the same turn.

**Ordering trap:** if Sanction's empower resolves first, Tornado Warrior's disempower
resolves second and undoes everything. The chain is LIFO, so place Sanction's effect
**first**. Verify at your table.

## The Legend and Champion — and why NOT Irelia

Calm+Chaos offers three Legends: **Irelia - Blade Dancer**, **Vex - Gloomist**, and
**Yasuo - Unforgiven**. This list originally ran Irelia. **That was a mistake, and it is
now corrected to Vex.** The reasoning both ways is worth recording.

**Why I first picked Irelia - Blade Dancer.** *"When you choose a friendly unit, you may
exhaust me and pay `{any rune}` to ready it."* **Sanction chooses a friendly unit**, so
every Sanction could also ready that unit. That is a real interaction — I just badly
over-valued what the ready buys:

- It does **not** enable a double conquest. 144.4 restricts a Standard Move to
  base↔battlefield, so a readied unit at a battlefield can only go *back to base*.
  Battlefield→battlefield needs **Ganking**, which Calm+Chaos does not have.
- It is **not needed for defence or scoring**. Exhausted units still defend (464.2.c.3,
  presence-based) and still hold (469.2, control-based). Being exhausted only stops
  moving and attacking.
- So the ready is really only for repeat **activated** abilities — and this deck has
  almost none.

**Why Vex - Gloomist is correct.** *"When you or an ally hold, you may exhaust me to draw
1."* This deck's entire plan is **holding** — Reckoner's Arena plus Nasus is a hold
engine, and 190.4.c means persistent bodies hold every turn rather than re-conquering.
So Vex fires **every single turn from the moment you take a battlefield**, and it patches
the list's genuine weakness: Calm and Chaos are both poor at raw card draw, and before
this change the deck's only draw was 3 Scuttle Crab plus a conditional clause on Back Off.

**And the Champion is the bigger upgrade. Vex - Apathetic** `{4}` 4M — *"[Deflect]. When
an opponent plays a unit while I'm at a battlefield, **[Stun]** it. They can't move it
this turn."* Compare what it replaced, Irelia, Fervent `{5}` 4M, whose text was "+1 Might
when chosen or readied."

Vex - Apathetic is a **soft lock** in a deck built to hold: every unit they deploy
arrives stunned (423.1.b — contributes no combat damage) **and cannot move**, so it can
neither trade with your holder nor go take the other battlefield. It is also a rune
cheaper and carries Deflect on a body you are guaranteed every game.

*(Third option, Yasuo - Unforgiven: "`{2}`, Exhaust: Move a friendly unit to or from its
base." A repositioning tool with no card advantage and no protection. Weakest of the
three here.)*

## 1-rune slots (6)

**3x Gust** `{1}` [Reaction] — cheap removal on ≤3-Might units, a combat trick, and the
cheapest way to return Tornado Warrior to hand for re-hiding.

**3x Steel Paws** `{1}` **0 Might**, Deflect — Empower `{7}` → **+7 Might.**
The best cheat-target-to-cost ratio in the format: a one-rune card whose Empower cost is
seven. Two things people get wrong about it:
- **Without the Sanction stack it is a one-turn trick.** `[Empowered][>] I have +7 Might`
  is stripped at end of your turn, so Tornado Warrior alone makes it a 7-Might *attacker*
  and a 0-Might blank on defence.
- **With the stack it becomes a permanent 7-Might Deflect wall for `{1}`.** That is the
  single best use of the combo in the deck.
- Even unempowered it is not dead: **0-Might units can conquer and hold**, so it is a
  one-rune body that takes and keeps a battlefield.

## 2-rune slots (9)

**3x Scuttle Crab** `{2}` 0M — *"When you play me, draw 1. [Deathknell] choose an
opponent, they reveal their hand, you can look at their **facedown cards** this turn,
gain 1 XP."* A cantrip body that also holds (0 Might can hold). The facedown-reveal
clause is genuinely relevant in a format where the mirror hides cards.

**2x Treasure Trove** `{2}` gear — *"When this leaves the board, draw 1 and channel 1
rune exhausted. {Chaos rune}, Exhaust: Kill this."* **Cut Mournful Witness for this.**
Two reasons.

First, it pairs with Pack of Wonders. Pack returns it to **hand**, not the trash, so the
leave-the-board trigger pays out and you still own the card: 2 energy per cycle for
`draw 1 + channel 1`. That is a repeatable draw *and ramp* engine off two cards the deck
already wanted, and it needs no facedown slot and no battlefield.

Second, it is the answer to this deck's real tax. The list runs 13 attrition — every
Power cost sends a rune to the bottom of a 12-card Rune Deck (`riftbound-rune-economy`).
Channelling is the only effect that reverses that. Treasure Trove is the deck's sole
ramp, and it is what makes the Fizz package affordable.

Note it does not even need Pack: `{Chaos rune}, Exhaust: Kill this` self-triggers, so a
lone Trove is still a cantrip that ramps. Pack just makes it repeatable.

*What Mournful Witness lost the slot for:* its self-empower is real and permanent, but
it is **not part of the plan** — nothing in the deck cares that the Witness specifically
is Empowered, and it is a **trap for the Tornado Warrior trigger**. TW's Empower carries
a delayed disempower, so spending the trigger on a `[Empowered][>]` static hands it +2
Might for one turn and then takes it back. That is the same defect that cut Kayle,
Justified. The Witness was a fine 2-drop attached to nothing.

**2x Pack of Wonders** `{2}` gear — free repeatable bounce (readies at each Awaken), the
non-rune half of the Tornado Warrior loop, and a way to rescue a facedown card off a
battlefield you are about to lose.

**2x Windsinger** `{2}` 1M Hidden — *"When you play me, you may return another unit at a
battlefield with 3 Might or less to its owner's hand."* A Hidden body that bounces —
including **your own Tornado Warrior**, so it is a re-hide enabler that also leaves a
body behind. 1 Might is the price.

**2x Block** `{2}` Hidden [Action] — *"Give a unit [Shield 3] and [Tank] this turn."*
Cheap Hidden protection for whichever unit is carrying the permanent Empower. Tank
(must be assigned damage first) is the clause that actually saves Nasus.

## 3-rune slots (11)

**3x Tornado Warrior** `{3}` 3M Hidden — half the combo. 3 copies even though 811.1.b
caps you at 2 facedowns, because drawing it early compounds.

**3x Sanction** `{3}{P1}` **[Reaction]** — the other half, and **the best support card in
the whole archetype** for one reason: it needs **no facedown slot.** The Hidden cap (one
per battlefield, two battlefields per 486.4) is the engine's hard bottleneck, and
Sanction ignores it entirely. Being a Reaction also means you can fire it during your own
Beginning Phase — which is what makes the Reckoner's Arena line work. 3 copies, no doubt.

**3x Fizz - Trickster** `{3}{P1}` 3M — *"When you play me, you may play a spell from
your trash with Energy cost no more than {3 energy}, ignoring its Energy cost. Then
recycle it."* **Cut Allay for this.** Fizz is the deck's Reaction-speed conversion of a
dead trash spell into tempo, and the line runs through Tail-Cloaked Matriarch:

1. Matriarch is Empowered at Reaction speed — by a flipped **Tornado Warrior** (Hidden is
   a Reaction, so `{0}`) or by **Sanction**, which is printed [Reaction].
2. `When I become [Empowered]` → *"choose a unit in your trash with Energy cost no more
   than {3 energy} and Power cost no more than {any rune}. Play it to your base."*
   Fizz is `{3}{P1}` — he fits **both** clauses exactly, at the ceiling of each.
3. Fizz's own play trigger then plays **Ride The Wind** out of the trash for just its
   Power cost.
4. Ride The Wind is *"Move a friendly unit and ready it"* — resolving **on the opponent's
   turn**.

Step 4 is the payoff and it is a genuine timing cheat. Ride The Wind is printed
**[Action]**, so it is normally illegal on their turn. It resolves anyway because an
effect that *instructs* you to play a card never re-checks that card's timing
(806.1.b, 353-355, 354.3) — see `timing-cheats.md`. Fizz is the initiator that launders
an Action into a Reaction.

What that buys, via `riftbound-effect-moves-vs-standard-moves`: the move needs no Ganking
(449.1), does not exhaust (144.2, and RtW readies on top), **conquers** an empty
battlefield (450), and **causes Combat** if the destination has enemy units (452). Doing
it on their turn means they have already committed their turn before the battlefield
changes hands, and you carry that control into your own Scoring Step. It is also the
cleanest way to make **Nasus** conquer, which is the one thing his Empowered ability
needs and never gets on its own.

Fizz is fine on raw rate too — a 3-Might body that rebuys a spell the turn you hard-cast
him. And he wants to *be* in the trash, which the deck does naturally.

*What Allay lost the slot for:* Deflect is a **1-rune tax, not protection**. It costs the
opponent one rune to proceed and then their removal resolves anyway. It also only touches
effects that **choose** — the Sigil of the Storm erratum (*"This doesn't choose
anything"*) is a reminder that "choose" is a term of art, so Deflect is blank against
sweepers, combat damage, and every "each unit" effect. Paying 3 energy and a congested
3-slot for a 3-Might body that taxes one rune was the worst rate in the deck.

**2x Back Off** `{3}` Hidden [Action] — *"[Stun] a unit. If you played this from your
hand, draw 1."* Stun (423.1.b: no combat damage) is your answer to a big untargetable
threat — it never chooses the unit's controller's permissions, it just turns it off for
a turn. The draw clause means hard-casting it is not a waste.

**3x Wind and Ghosts** `{3}{P1}` [Action] — banish ≤3 Might, otherwise bounce. The only
unconditional answer in the deck, and never dead.

## 4-rune slots (4)

**2x Ride The Wind** `{2}{P1}` [Action] — *"Move a friendly unit **and ready it**."*
**This is the card that makes Nasus's Empowered ability function at all** — see the
Nasus section below. It is also general tempo: ready a blocker, or reposition a unit
after it has already moved. Replaced 2x Navori Scout (a vanilla Deflect body).

**2x Tail-Cloaked Matriarch** `{4}` 4M — Empower `{2}{Chaos}` → play a unit from your
trash free. The cheap re-triggerable payoff, and the best Sanction mode-2 target for the
"second trigger" prize. Only 2 because this list's trash fills slowly.

## 6- and 8-rune slots (4)

**2x Kharox** `{6}` 5M — Empower `{6}{Chaos}{Chaos}` → opponent Burns 3, then you play a
unit from **their** trash free. Sanction turns this into two activations a turn.

**2x Nasus, Ascended** `{8}{P1}` 8M **Deflect 2** — Empower `{8}` → *"When I conquer, you
score 1 point."*

> **User-caught problem, and it is a real one.** **469.1**: *"Conquer: A player gains
> Control of a Battlefield they did not yet Score this turn."* **190.4.a**: you keep
> control for as long as you have units there. So once Nasus takes a battlefield he
> **holds** it and never *gains* control again — **his Empowered ability fires once and
> then never.** This is rules-fact 9 (the conquer/hold inversion) working against us:
> persistent bodies hold, they do not re-conquer.
>
> **Two consequences.** (1) His `{8}` Empower is **not** the reliable payoff I first sold
> it as — it is a one-off burst on the turn he takes new ground. (2) He is still an
> excellent card: `{8}{P1}` for an **8-Might Deflect 2** body is close to unkillable and
> holds a battlefield for the rest of the game. Run him for the body; treat the extra
> point as a bonus.
>
> **How to actually get the trigger — Ride The Wind.** **144.2** makes exhausting the unit
> the *cost* of a Standard Move, so Nasus normally moves once per turn. Ride The Wind
> *"moves a friendly unit **and readies it**"*, so: move Nasus off the battlefield → the
> following cleanup takes your control of it (190.4.c) → **Standard Move him back in →
> that is a Conquer** → the Empowered trigger fires.
>
> **The catch:** 469.1 says "did not yet Score this turn", and **471.2.c** caps score
> abilities at once per turn. So this line only pays out on a battlefield you have **not**
> already scored by holding this turn — you cannot bank the hold point and the conquer
> point on the same battlefield in the same turn.

## Battlefields

**Risen Altar** *(neutral, game 1)* — Empower costs `{1}` less for your units here. Turns
Nasus's `{8}` into `{7}` and the Matriarch's into `{1}{Chaos}`. Near-blank for opponents.

**Seat of Power** *(on the play)* — conquer the other battlefield first, then this one.

**Reckoner's Arena** *(on the draw / grind)* — a **bonus, not the engine.** Under 486.5 a
Bo3 presents one battlefield per game and burns it, so any single battlefield is live in
**at most one game of three**. Never build the main plan around one. That said, in the
game you do present it:
*"When you hold here, activate the conquer effects of units here."* Nasus Empowered has
a **conquer** trigger, but 190.4.c means a persistent body like him **holds** every turn
and conquers almost never. The Arena converts the trigger he never gets into one he gets
every turn. Sequence: your Beginning Phase, the hold trigger goes on the chain, you
**respond** with Sanction to Empower Nasus, then the hold resolves and activates his
conquer effect. **471.2.c** caps it at once per turn — two points a turn, not more.
Do not let the hold trigger resolve before you Sanction.

**Use Sanction here, not Tornado Warrior** — a second user-caught point. Tornado Warrior
disempowers *at end of the turn it was played*, so a flip on the **opponent's** turn is
already undone before your Beginning Phase arrives. Flipping it during your **own**
Beginning Phase does work (the hold trigger is a chain item you can react to, and Hidden
grants Reaction), but 811.1.d.1 forces it to be played to the battlefield it was hidden
at, so Tornado Warrior must be hidden at Reckoner's Arena specifically with Nasus standing
there. Sanction is printed `[Reaction]`, comes from **hand**, and needs no facedown slot —
it is strictly the better tool for this window.

**On the "Hidden battlefield":** the only battlefield in the format that references Hidden
is **Mystic Vortex** — *"During showdowns here, cards with [Reaction] cost `{any rune}`
more to play. (Hidden cards have [Reaction].)"* It is a **tax, not an enabler**, and it is
symmetric — it makes your own flips more expensive too. One narrow upside worth knowing:
it only applies **during showdowns**, so a Beginning-Phase flip or Sanction is untaxed,
which makes it one-sided against a deck whose reactions are combat tricks.

## What this deck does badly

- **Slowest of the three.** Nasus is an 8-rune card in a deck that averages 2.98.
- **The combo needs two specific cards** (Tornado Warrior + Sanction) or one Sanction plus
  an already-Empowered unit. Sanction alone still works; Tornado Warrior alone gives you
  one turn.
- **Only 8 attrition**, which is the deck's real strength — it can play a long game where
  the other two run out of runes.
