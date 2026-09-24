# Mel — Kharox cheat: reasoning and every card

`mel-kharox-v1.txt` · Mind+Chaos · 7 Mind / 5 Chaos · avg 2.80 runes · **attrition 9**
21 of 40 cards cost ≤2 runes.

**Core, as requested:** Tornado Warrior cheating in an expensive Empower trigger, every
turn. Shrink-and-banish is the **subtheme**, not the plan.

This is a second Mel build. `mel-breach-v1.txt` is the shrink-and-banish version and
stays as-is.

---

## The constraint you need to know before reading the list

I ranked **every** Empower cost in the Mind+Chaos pool by how much cheating it saves.
Here is the whole list:

| Empower cost | Card | Payoff type |
|---|---|---|
| `{12}` −1 per rune | Grumpy Rockbear | static, **defensive** |
| **`{6}{Chaos}{Chaos}`** | **Kharox** | **become-trigger** |
| `{2}{Chaos}` | Tail-Cloaked Matriarch | become-trigger |
| `{3}` | Mel Newly Awakened / Covert Informant / Applied Researchers | static |
| `{2}` | Kinkou Lifeblade, Apprentice Mage | static / small |
| Exhaust | Questionable Tome | static |
| Discard a spell | Mel, Defiant Soul | become-trigger |

**Mind+Chaos contains exactly one genuinely expensive Empower worth cheating: Kharox.**
Everything else is `{2}`–`{3}`, which you can simply hard-cast. That is the honest
ceiling of this colour pair — the `{7}` and `{8}` Empowers (Steel Paws, Nasus) live in
**Calm**, which is why `sanction-stack-v1.txt` exists.

**Grumpy Rockbear is the trap.** It has the biggest printed number, `{12}`, and it is
still wrong here for two independent reasons:
1. Its payoff is `[Empowered][>] Deflect and Shield 3` — **defensive and static.**
   Tornado Warrior strips it at end of *your* turn, before the opponent ever attacks. It
   is exactly the category we established does not work with free Empowers.
2. The cost *shrinks as the game goes on* (`{1}` less per rune you control), so by the
   time your engine is running it costs almost nothing to hard-cast anyway. Cheating a
   cost that is already falling to zero is not cheating.

So the deck is built to **do the one good thing as many times as possible.**

## What you are actually cheating

**Kharox** `{6}` 5M — `[Empower] {6 energy}{Chaos rune}{Chaos rune}` →
*"When I become [Empowered], choose an opponent. **They [Burn 3]. Then you may do this:
Choose a unit in their trash and play it, ignoring its cost.**"*

Paying that Empower normally costs **6 runes plus 2 permanent attrition** (max(6,2) = 6
runes to activate, and the two Chaos pips recycle out of your pool for good). Tornado
Warrior does it for **`{0}`**.

And it is **self-fuelling**: the Burn 3 fills the opponent's trash, and then you steal a
unit out of the trash you just filled. Every activation both mills them and hands you a
free body. Two activations is 6 cards of their deck and 2 free units.

## The core loop — two Kharox triggers in one turn

**811.1.b** allows one facedown **per battlefield**, and **486.4** gives 1v1 two
battlefields. Control both, and you can have **two Tornado Warriors hidden at once.**

But **441.1.b** stops an already-Empowered object being Empowered again, so the second
Tornado Warrior cannot simply hit Kharox a second time. **Temporal Breach solves it:**

1. Flip **Tornado Warrior #1** for `{0}` → empower **Kharox** → *Burn 3, steal a unit.*
2. **Temporal Breach** on your own Kharox (`{2}{P1}`) → **124.1/124.2**: changing zones
   clears all statuses, and 124.2 names **Empowered**. He is replayed **ignoring his
   cost** and is no longer Empowered.
3. Flip **Tornado Warrior #2** for `{0}` → empower Kharox again → **second Burn 3 and a
   second stolen unit.**

Total cost for two activations of a `{6}{Chaos}{Chaos}` ability: **two hide costs paid on
earlier turns, plus `{2}{P1}` for the Breach.** That is the deck.

**The trap in step 3:** do **not** try to reset Tornado Warrior with Temporal Breach. His
trigger reads *"when you play me **from face down**"* — a Breach replays him from
**banishment**, so the trigger does not fire. Tornado Warrior only ever comes back by
returning to **hand** and being re-hidden.

## Card by card

### The engine (12 cards)

**3x Tornado Warrior** `{3}` 3M Hidden — the cheat. Three copies because you want two in
play at once and one in reserve.

**3x Kharox** `{6}` 5M — the payoff, at the maximum. In `mel-breach-v1` he is a 2-of
finisher; **here he is the deck**, so he goes to 3. You want to draw him early, and a
second copy on the board means Tornado Warrior #2 has its own target without needing a
Breach.

**3x Temporal Breach** `{2}{P1}` Hidden — the reset. Doubles every Kharox turn, and
replays him free. Usually hard-cast (811.3) so it does not eat a facedown slot.

**3x Tail-Cloaked Matriarch** `{4}` 4M — Empower `{2}{Chaos}` → play a unit from **your**
trash. The backup payoff when Kharox is not out, cheap enough to hard-cast, and a legal
Tornado Warrior target on turns Kharox is already Empowered.

### Re-hiding Tornado Warrior (9 cards)

Every one of these exists to get Tornado Warrior back into your **hand**, because that is
the only zone 811.1.b lets you hide from.

**2x Pack of Wonders** `{2}` gear — *"Exhaust: Return another friendly gear, unit, or
[Hidden] card to its owner's hand."* Free, and it readies every Awaken (315.1.b). It can
also rescue a facedown card off a battlefield you are losing, which 811.1.b would delete.

**3x Gust** `{1}` [Reaction] — returns a unit **with 3 Might or less**, and Tornado
Warrior is exactly 3. Doubles as removal on their small units.

**2x Retreat** `{1}` [Reaction] — friendly-only, but **refunds a rune**, which pays most
of the re-hide cost.

**2x Mesmerize** `{1}{P1}` [Reaction] — modal: *"Return a friendly unit to hand"* **or**
*"Give an enemy unit −2 Might."* It is a re-hide enabler **and** a banish-enabler for the
subtheme, so it is never dead.

### Battlefield control (5 cards)

The engine needs you to **control two battlefields** — no control, no facedown slots.
These are cheap bodies that stay.

**3x Ravenbloom Student** `{2}` 2M — *"When you play a spell, give me +1 Might this
turn."* The deck runs 16 spells, so it regularly defends as a 3 or 4.

**2x Mystic Poro** `{2}` 2M — [Vision], a body with a free look at the top card.

### Draw (4 cards)

**2x Mushroom Pouch** `{2}` gear — *"At the start of your Beginning Phase, if you control
a facedown card at a battlefield, draw 1."* This deck **always** has a facedown card —
that is its entire plan — so this is a free card every turn from turn 2 onward. It is the
single best "reward the engine" card in the pool and it costs the deck nothing extra.

**2x Consult the Past** `{4}` Hidden [Reaction] — draw 2. Hard-cast unless a slot is
genuinely free.

### The subtheme — shrink and banish (9 cards)

Kept deliberately small, because you asked for it to be the subtheme.

**2x Mel, Defiant Soul** (+1 in the Champion Zone) — Empower cost is **"Discard a spell,"**
zero runes, so she never competes with Kharox for the Tornado Warrior activation. Banish
an enemy ≤3 Might.

**2x Smoke Screen** `{2}{P1}` [Reaction] — **−4 Might**, the largest in the pool. Drags a
7-Might unit into Mel's range.

**2x Wind and Ghosts** `{3}{P1}` [Action] — banish ≤3 Might, otherwise bounce. Never dead.

**3x Apprentice Mage** `{3}` 3M — Empower `{2}` → Predict 2. A cheap become-trigger that
also arms the **Legend** (every Empower empowers Mel - Soul's Reflection, and disempowering
her gives a free −2 Might). It is the glue between the core and the subtheme.

## Battlefields

**Risen Altar** *(neutral, game 1)* — *"[Empower] costs of your units here cost `{1}` or
`{any rune}` less."* Makes a **hard-cast** Kharox `{5}{Chaos}` instead of `{6}{Chaos}{Chaos}`
— the fallback plan for games where Tornado Warrior never shows up. Near-blank for an
opponent with no Empower cards.

**Minefield** *(on the play)* — self-mill 2 on conquer. Fuel for Tail-Cloaked Matriarch;
a cost for almost every other deck.

**Seat of Power** *(on the play, vs slow decks)* — conquer the other battlefield first,
then this one.

## How this differs from `mel-breach-v1.txt`

| | `mel-breach` | `mel-kharox` (this) |
|---|---|---|
| Core | shrink & banish | **cheat Kharox with Tornado Warrior** |
| Kharox | 2 (finisher) | **3 (the plan)** |
| −Might package | 7 cards | 4 cards (subtheme) |
| Attrition | 15 | **9** |
| Avg runes | 2.92 | **2.80** |

## What this deck does badly

- **One point of failure.** If Kharox is answered and the second is not drawn, the deck is
  a pile of 2-Might bodies. Three copies is the mitigation, not a fix.
- **Kharox's first trigger can whiff.** You steal from **their** trash — if it is empty
  early, the Burn 3 is all you get. It improves every activation.
- **Needs two controlled battlefields** to reach its ceiling. Against a deck that takes one
  off you, the engine halves.
- **Slow.** Kharox is a 6-drop; the loop is not online before turn 5-6.
