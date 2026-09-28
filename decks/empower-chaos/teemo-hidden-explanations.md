# Teemo — Hidden engine: every card, and why

`teemo-hidden-v1.txt` · Mind+Chaos · 8 Mind / 4 Chaos · avg 2.60 runes · attrition 16
23 of 40 cards cost ≤2 runes — the cheapest of the three builds.

**Plan in one sentence:** hide a card every turn at zero attrition, flip it for `{0}`,
and win the long game on the accumulated free value.

---

## Your question: why so many Teemo units?

The deck runs **3 Teemo - Strategist** (1 in the Champion Zone + 2 in the main deck) and
**3 Teemo - Scout** — six Teemo cards in 40. Here is the actual reasoning, and where it
is weaker than it looks.

**1. The Champion Zone copy is nearly free deck space.** 103.2.a.1 puts it on the table
at the start of every game, and 103.2.b.1 counts it against your 3-copy limit. So of the
three Strategists, **one is guaranteed every game without ever being drawn.** That is
why the Chosen Champion is worth building around at all.

**2. Extra copies are normally just insurance — but here they are engine pieces.** Most
decks run 2 extra Champion copies because opponents kill the first one. This deck has a
second reason: the Legend reads *"{1 energy}, Exhaust: Put a Teemo unit you own into
your hand from your Champion Zone **or the board**."* A Teemo unit in hand is never a
dead card, because you can re-hide it and flip it again for `{0}`. Drawing your second
Strategist is drawing another engine turn.

**3. Hidden density is itself a payoff.** Strategist reads *"reveal the top 5 cards of
your Main Deck. Deal 1 to an enemy unit here **for each card with [Hidden]**."* The deck
runs **18 Hidden cards in 40** (~45%), so a top-5 reveal averages **~2.25 Hidden** →
about 2 damage per flip. Every Hidden card in the list is also feeding that number,
which is why cheap Hidden bodies beat better non-Hidden ones here.

**Where the reasoning gets thin — and my honest read.** Points 2 and 3 justify the
*Strategists* completely. They justify **Teemo - Scout much less well.** Scout is a
`{2}` **1-Might** body whose entire text is "+3 Might this turn" — so a 4-Might attacker
on the turn it flips and a 1-Might blank afterwards. It is in the deck for Hidden count
and Legend recursion, not for what it does.

**This has now been actioned: Teemo - Scout is at 2, and the freed slot is a third Ember
Monk.** Scout stays at 2 rather than 0 because cutting Hidden density directly shrinks
Strategist's damage and Ember Monk's trigger rate — the deck cannot afford to gut it.

---

## The Legend and Champion

**Teemo - Swift Scout** *(Legend)* — the whole reason this build exists.
*"You may pay `{1 energy}` to hide a card with [Hidden] instead of `{any rune}`."*
Hiding normally costs a **recycled rune**, which is permanent attrition (416: it goes to
the bottom of the Rune Deck and must be re-channelled at 2/turn). Teemo converts that
into **energy**, which refreshes every Awaken. Over a ten-turn game where you hide most
turns, that is roughly **six runes you keep** — the difference between an engine you
can run every turn and one you can run half the time.
Second ability: the Teemo bounce, covered above.

**Teemo - Strategist** *(Chosen Champion, `{2}{P1}` 2M)* — chosen over Teemo - Scout for
the Champion slot because its trigger fires on **two** conditions: *"When I defend **or**
I'm played from [Hidden]."* Even sitting on a battlefield doing nothing, it pings every
time the opponent attacks into it. Scout would give you a 4-Might body once.

## 1-rune slots (5 cards)

**3x Gust** `{1}` [Reaction] — *"Return a unit at a battlefield with 3 Might or less to
its owner's hand."* Three jobs at once: cheap removal against small bodies, a combat
trick at Reaction speed, and **your cheapest way to return Tornado Warrior to hand**
(he is exactly 3 Might). Competes with Retreat; Gust wins because it can also hit
*their* units.

**2x Retreat** `{1}` [Reaction] — *"Return a friendly unit to hand. Its owner channels 1
rune exhausted."* Friendly-only, but it **refunds a rune**, which partially pays for the
re-hide. The reason for 2 rather than 3: it is dead when you have nothing worth saving.

## 2-rune slots — the engine core

**2x Teemo - Scout** — see above. **Cut from 3 to 2**, with the freed slot going to a
third Ember Monk. Kept at 2 rather than 0 because Hidden density directly feeds
Strategist's damage count and Ember Monk's trigger.

**2x Teemo - Strategist** — see above.

**2x Blastcone Fae** `{2}{P1}` 2M Hidden — *"When you play me, give a unit −2 Might."*
A Hidden body that is also removal-assist: −2 turns a 5-Might attacker into a 3, which
is exactly the line **Wind and Ghosts** banishes. 811.1.d.2 restricts the target to the
battlefield it was hidden at, which is fine — that is where your fights are.

**2x Bone Skewer** `{2}{P1}` Hidden — *"An opponent reveals their hand. You may choose a
unit from it. They play that unit to that battlefield, ignoring any and all costs. When
they do, [Stun] it."* Two roles: **perfect information** on their hand, and it drags
their best unit onto the board **stunned** (423.1.b: contributes no combat damage), where
your removal can answer it before it ever acts. At 2 because it is card-disadvantage if
you misread the board.

**2x Pack of Wonders** `{2}` gear — *"Exhaust: Return another friendly gear, unit, or
[Hidden] card to its owner's hand."* The free half of the Tornado Warrior loop. It
readies at every Awaken (315.1.b), so it is one free bounce per turn forever. Note it
can return a **facedown card** — so you can pick up a hidden card at a battlefield you
are about to lose, rather than letting 811.1.b delete it. At 2 because it does nothing
on an empty board.

**3x Guerilla Warfare** `{2}{P1}` — **the card only this deck can legally run.**
*"Return up to two cards with [Hidden] from your trash to your hand. You can hide cards
ignoring costs this turn."* It is a **Signature card with the Teemo tag**, so 103.2.d.2
makes it legal under Teemo - Swift Scout and illegal under every other Legend. It rebuys
two spent engine pieces **and** makes that turn's hiding free. 3 copies without
hesitation — the deckbuilding doctrine says default Signature cards to the maximum, and
this one is a genuine engine card rather than a value card.

**3x Temporal Breach** `{2}{P1}` Hidden — *"Banish a unit, then its owner plays it to the
same location, ignoring its cost."* Two jobs. **(a)** 124.1/124.2: changing zones clears
all statuses **including Empowered**, so this resets an Empower payoff for re-triggering.
**(b)** It replays your own expensive unit for free — on Kharox that is 6 runes saved.
It also works on an *enemy* unit to clear its damage, so read the board before firing it.

## 3-rune slots

**3x Apprentice Mage** `{3}` 3M — Empower `{2}` → *"When I become Empowered, [Predict 2]."*
The **cheapest re-triggerable Empower payoff in the format**, which is why it is at 3.
Predict 2 every turn is real deck-smoothing, and at `{2}` you can hard-cast the Empower
rather than spending the engine on it. On **Risen Altar** it drops to `{1}`.

**3x Tornado Warrior** `{3}` 3M Hidden — the engine seed. *"When you play me from face
down, you may empower something here. Disempower it at end of turn."* 3 copies despite
811.1.b capping you at 2 facedowns, because you want to draw one **early** — the loop
compounds, so turn 2 is worth far more than turn 6.

**3x Wind and Ghosts** `{3}{P1}` [Action] — *"Choose a unit at a battlefield. If it has 3
Might or less, banish it. Otherwise, return it to its owner's hand."* Your only
unconditional answer. **Banish** beats trash: it dodges every recursion card. And the
"otherwise bounce" clause means it is **never dead** against a big unit. Pairs directly
with Blastcone Fae's −2.

## 4-rune slots

**3x Ember Monk** `{4}` 4M — *"When you play a card from [Hidden], give me +2 Might this
turn."* The only card that turns Hidden density into raw combat power. With 19 Hidden
cards he regularly attacks as a 6- or 8-Might. At **3** (up from 2): with the deck at 18 Hidden cards he is
live nearly every turn, and he is the only card converting Hidden density into raw
combat power rather than incremental value.

**2x Tail-Cloaked Matriarch** `{4}` 4M — Empower `{2}{Chaos}` → *"play a unit from your
trash (≤`{3}`/`{P1}`), ignoring its cost."* The Empower is cheap enough to hard-cast
repeatedly, and with Temporal Breach resetting her you get multiple activations a turn.
Only 2 because this deck's trash fills slowly — Minefield helps.

**2x Consult the Past** `{4}` Hidden [Reaction] — draw 2 for `{0}` when flipped from
Hidden. Pure card advantage at the deck's best rate, and it holds up a bluff: an
opponent looking at your facedown cannot tell this from Tornado Warrior.

## 6-rune slot

**2x Kharox** `{6}` 5M — Empower `{6}{Chaos}{Chaos}` → *"opponent Burns 3, then play a
unit from their trash, ignoring its cost."* The biggest cost in the archetype and the
only card that steals from the **opponent's** trash — and its own Burn 3 fills that
trash first, so it is self-fuelling. 2 copies: a 6-drop you want to draw exactly one of.

## Battlefields

**Risen Altar** *(neutral, game 1)* — Empower costs `{1}` less for your units here.
Near-blank for an opponent who runs no Empower cards, which is most of the field.

**Seat of Power** *(on the play)* — conquer the *other* battlefield first, then this one
the same turn, so "draw 1 for each other battlefield" pays more than one card.

**Minefield** *(on the play, vs grindy decks)* — *"when you conquer here, put the top 2
cards into your trash."* Self-mill is a **cost** for almost every other deck and **fuel**
for yours: it loads Tail-Cloaked Matriarch's targets. Turn it off in your head if the
Matriarch is not in the deck.

## What this deck does badly

- **No answer to a big Deflect wall.** Wind and Ghosts bounces it rather than killing it.
- **Attrition 16** is high for a deck that also wants runes up for Reaction cards. The
  Legend's hide discount is what makes it survivable; without it the list would not work.
- **Slow.** Nothing here wins before turn 6. Against real aggression you are relying on
  Gust and chump bodies.
