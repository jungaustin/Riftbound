# Mel — Breach triggers: every card, and why

`mel-breach-v1.txt` · Mind+Chaos · 8 Mind / 4 Chaos · avg 2.92 runes · attrition 18

**Plan in one sentence:** banish one or two enemy units every turn by Empowering Mel,
resetting her with Temporal Breach, and Empowering her again — then walk onto the
battlefields they can no longer defend.

---

## How this deck was built, in order

The deck was not built around Hidden. It was built in five steps, and Hidden only
appears at step 5 as a consequence.

**1. Start from the only Legend+Champion pair that are BOTH Empower cards.**
Mel - Soul's Reflection and Mel, Defiant Soul interlock: the Champion banishes, the
Legend shrinks. Nothing else in the format does this.

**2. Find the constraint that shapes the list.** Mel, Defiant Soul banishes *"an enemy
unit at a battlefield with **3 Might or less**."* Almost nothing worth banishing is 3
Might. **That single clause is what half the deck exists to solve.**

**3. Fill the deck with -Might so the banish has targets.**

| Card | Effect | Copies |
|---|---|---|
| Mel - Soul's Reflection (Legend) | **-2**, free, every turn | — |
| **Smoke Screen** | **-4** — the largest in the pool | 3 |
| **Blastcone Fae** | **-2** | 2 |
| **Mel, Newly Awakened** (Empowered) | every -Might effect gets **-1 more** | 2 |

Stacked with Newly Awakened Empowered: Smoke Screen becomes -5 and the Legend -3, so
**-8 total. An 11-Might unit drops to 3 and gets banished.**

**4. Notice the Empower cost is a CARD, not runes.** Mel's cost is *"Discard a spell"* —
zero runes. That is what lets you Empower her on a turn you have already spent everything,
and what lets you do it twice.

**5. Add a way to re-trigger, and a free Empower.** 441.1.b stops an Empowered thing being
Empowered again, so Mel banishes once per game unless the status is cleared. **Temporal
Breach** clears it (124.1/124.2 — a zone change wipes statuses, and 124.2 lists Empowered
by name). **Tornado Warrior** supplies a free Empower so you do not always pay a card.

**Step 5 is the ONLY reason any Hidden card is in this deck.**

## Why there is no "Hidden theme" here — 10 cards, 1 requirement

Ten of the 40 cards have the Hidden keyword, but **only one of them needs it**:

| Card | Copies | Does it need the facedown slot? |
|---|---|---|
| **Tornado Warrior** | 3 | **YES** — its trigger literally reads *"when you play me **from face down**"* |
| Temporal Breach | 3 | No — hard-cast for `{2}{P1}`, which is what you usually do |
| Consult the Past | 2 | No — hard-cast `{4}` to draw 2 |
| Blastcone Fae | 2 | No — hard-cast `{2}{P1}` |

**811.3**: *"Instead of being hidden, a card with Hidden may be played for its cost as
normal, at its normal timing with no restrictions on targeting."* So for those three,
Hidden is an **optional discount** — pre-pay a rune now, flip for `{0}` at Reaction speed
later — not a plan.

**Mushroom Pouch** is not a Hidden card at all. It reads *"At the start of your Beginning
Phase, if you control a facedown card at a battlefield, draw 1"* — it is paid for by the
Tornado Warrior that is **already** sitting face-down, so it costs the deck nothing extra.

*(If you counted 12 with a text search: **Pack of Wonders** does not have Hidden either.
Its text mentions returning a "[Hidden] card" — a known false positive.)*

## The Legend and Champion — why they are the deck

**Mel - Soul's Reflection** *(Legend)* — *"When you empower something else, empower me.
Disempower me, Exhaust: Give a unit at a battlefield −2 Might this turn."*

This is the only Legend in the format that **pays you for the act of Empowering itself**,
regardless of what you Empowered or why. Every Empower anywhere on your board arms her,
and the disempower re-arms for next turn. It is a free −2 Might every single turn.

**Mel, Defiant Soul** *(Chosen Champion, `{5}` 4M)* — *"[Empower] — **Discard a spell.**
When I become Empowered, banish an enemy unit at a battlefield with 3 Might or less."*

**Her Empower cost is zero runes.** That is the single most important line in this
deck. Every other Empower payoff in the format charges energy or Power; hers charges a
card. So you can Empower her on a turn where you have already spent everything, and you
can do it *repeatedly* if you have the cards.

**The two halves lock together.** The Legend's −2 Might is exactly what turns an
out-of-range unit into a legal target for the Champion's ≤3-Might banish. A 5-Might unit
becomes a 3. With **Mel, Newly Awakened** Empowered in the main deck it is **−3**
(*"if a spell or ability you control would give −Might to a unit it chooses, it gives an
additional −1"*), so 6-Might units die.

**Why banish rather than kill:** banish is the strictest of the three destinations. It
dodges every trash-recursion card in the format — including the ones this archetype
itself runs.

## The facedown-slot rule — why this deck runs FEW Hidden cards

**811.1.b** allows **one facedown card per battlefield**, and **486.4** gives 1v1 exactly
**two battlefields**. So you have at most two facedown slots, often one.

**Tornado Warrior is the only card here that *requires* a slot** — its trigger reads
"when you play me **from face down**." Every other Hidden card in the deck is fine
hard-cast (811.3: a Hidden card may always be played normally, at normal timing, with no
targeting restriction). Temporal Breach hard-casts for `{2}{P1}`, Consult the Past for
`{4}`, Blastcone Fae for `{2}{P1}`.

**That makes any Hidden card whose payoff *scales with Hidden count* actively wrong
here** — it competes with Tornado Warrior for a scarce slot AND asks the deck to be
something it is not. Teemo - Strategist was exactly that card, and it was a leftover from
an earlier generic Mind/Chaos list. At 13 Hidden cards its top-5 reveal averaged ~1.6
Hidden, so 1-2 damage, while eating the slot the engine needs.

**The Teemo build is the opposite deck**: 19 Hidden cards, Guerilla Warfare to rebuy
them, and a Legend that discounts hiding. There, Hidden density *is* the payoff. Here,
the correct number of Hidden cards is "enough to reliably have Tornado Warrior."

## The core loop, and the card that powers it

**3x Temporal Breach** `{2}{P1}` Hidden — *"Banish a unit, then its owner plays it to the
same location, ignoring its cost."*

**124.1 and 124.2** are the rules that matter: changing zones to a non-board zone clears
all temporary modifications, and **124.2 lists Empowered explicitly as a status.** So
Temporal Breach *un-Empowers* whatever it targets.

The loop: Empower Mel (discard a spell) → banish an enemy unit → **Temporal Breach Mel**
→ her Empowered status is cleared → Empower her again (discard another spell) → **banish
a second unit.** Cost: `{2}{P1}` and two cards, for two removals a turn.

It also replays your own expensive units for free — used on Kharox that is 6 runes saved.

## 1-rune slots (5)

**3x Gust** `{1}` [Reaction] — cheap Reaction removal against ≤3-Might units, a combat
trick, and your cheapest way to return Tornado Warrior to hand for re-hiding (he is
exactly 3 Might). Also, critically, it can save **your own** Mel from a removal spell.

**2x Retreat** `{1}` [Reaction] — friendly-only bounce that **refunds a rune**, which
pays part of the re-hide cost. At 2 because it is dead with nothing worth saving.

## 2-rune slots (10)

**3x Smoke Screen** `{2}{P1}` [Reaction] — *"Give a unit **-4 Might** this turn, to a
minimum of 1 Might."* The **largest -Might effect in the pool**, and the single best
enabler this deck has: -4 drags a 7-Might unit down to 3, exactly into Mel, Defiant
Soul's banish range. With **Mel, Newly Awakened** Empowered it is **-5**, so 8-Might
units become banishable. Being a [Reaction] means you can apply it *after* the opponent
commits, and it stacks with the Legend's -2 and Blastcone Fae's -2.

*(This slot previously held 3x Teemo - Strategist. See "The facedown-slot rule" below
for why that was wrong.)*

**2x Blastcone Fae** `{2}{P1}` 2M Hidden — *"give a unit −2 Might."* A **second copy of
the Legend's ability, on a body.** Stacking Blastcone with the Legend is −4, which drags
a 7-Might unit into Mel's banish range.

**2x Pack of Wonders** `{2}` gear — free repeatable bounce (readies each Awaken), the
non-rune half of the Tornado Warrior loop. It can also rescue a facedown card off a
battlefield you are about to lose, which 811.1.b would otherwise delete.

**3x Temporal Breach** — above.

## 3-rune slots (8)

**3x Apprentice Mage** `{3}` 3M — Empower `{2}` → Predict 2 on becoming Empowered. The
cheapest re-triggerable payoff in the format. Note what it does *for this deck
specifically*: every Empower also arms the Legend, so Apprentice Mage is really "pay
`{2}`: filter two cards **and** get a free −2 Might."

**2x Mushroom Pouch** `{2}` gear — *"At the start of your Beginning Phase, if you
control a facedown card at a battlefield, draw 1."* A **free card every turn for doing
what the deck already does.** Tornado Warrior lives face-down, so this is on almost
every turn from turn 2 onward. Critically it rewards the Hidden engine **without
competing for the facedown slot** — the exact profile this deck wants.

*(This slot previously held 2x Covert Informant, whose payoff is a static
`[Empowered][>]` ability — the category that does not want free Empowers.)*

**3x Tornado Warrior** `{3}` 3M Hidden — the free Empower. 3 copies despite the
2-facedown cap because drawing it early compounds.

**3x Wind and Ghosts** `{3}{P1}` [Action] — banish ≤3 Might, otherwise bounce. Your
second banish effect, and it lines up with the same −Might package Mel uses. Never dead.

**2x Portal Rescue** `{3}{P1}` [Action] — *"Banish a friendly unit, then play it to base,
ignoring its cost."* A **second Temporal Breach for the reset half of the loop**, and it
rescues a unit from removal. Weaker than Breach (it sends the unit to base rather than
leaving it in place, and it is [Action] rather than Hidden-Reaction), hence 2 not 3.

## 4-rune slots (7)

**2x Mel, Newly Awakened** `{4}{P1}` 4M — *"When you play me, draw 1."* Empower `{3}` →
*"Your spells and abilities can't be countered. If a spell or ability you control would
give −Might to a unit it chooses, it gives an additional −1."* The −1 upgrades the whole
−Might package. The uncountable clause protects the combo turn. Only 2 because it is a
build-around you do not want to draw twice early.

**3x Tail-Cloaked Matriarch** `{4}` 4M — Empower `{2}{Chaos}` → play a unit from your
trash (≤`{3}`/`{P1}`) free. At **3**, up from 2, because `critique` correctly flagged it
as an engine piece: it is the second cheapest re-triggerable Empower and the deck's only
way to rebuild a board. Temporal Breach resets her for multiple activations per turn.

**2x Consult the Past** `{4}` Hidden [Reaction] — draw 2 for `{0}` off a facedown flip.

## 5- and 6-rune slots

**2x Mel, Defiant Soul** *(extra copies)* — above. 1 in the Champion Zone + 2 here = the
legal maximum of 3, and they are not dead draws: a second copy in hand is another
zero-rune Empower engine if the first is answered.

**2x Kharox** `{6}` 5M — Empower `{6}{Chaos}{Chaos}` → opponent Burns 3, then you play a
unit from **their** trash free. The biggest cheat available, and self-fuelling. 2 copies.

## Battlefields

**Risen Altar** *(neutral, game 1)* — Empower costs `{1}` less for your units here. Turns
Tail-Cloaked Matriarch's Empower into `{1}{Chaos}` and Apprentice Mage's into `{1}`.
Near-blank in an opponent's hands.

**Seat of Power** *(on the play)* — conquer the other battlefield first, then this one.

**Minefield** *(on the play)* — self-mill 2 on conquer. A **cost** for them, **fuel** for
you: it stocks Tail-Cloaked Matriarch's targets and Kharox does not care.

## What this deck does badly

- **Attrition 18**, the highest of the three. 15 Mind pips forced the 8/4 rune skew, and
  a bad Chaos draw can strand Tail-Cloaked Matriarch's `{Chaos}` Empower.
- **No answer to a unit above 6 Might** once the −Might package is exhausted.
- **The loop costs cards.** Mel's Empower discards a spell every time. Consult the Past
  is the only real refill, and 2 copies may not be enough.
