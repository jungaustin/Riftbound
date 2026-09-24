# Annie - Dark Child — full pool rating (Chaos+Fury, 252 main-deck cards + 64 battlefields)

Rated 2026-08-20 against a stated plan. Scores measure a card **in isolation**;
the built deck deliberately departs from the ranking (see README).

**THE PLAN, one sentence:** Strip their hand and take their units while cheap
Fury removal keeps their bodies off battlefields, then score 8 by turn 9-11 with
a small number of Deflect/lock bodies — funded by Annie readying 2 runes every
end of turn so a Reaction is live on *their* turn, every turn.

**Banned and excluded from all ratings** (`cli.py pool` does not filter bans):
Called Shot, Fight or Flight, Scrapheap, Draven - Vanquisher, Stealthy Pursuer,
and the battlefields Aspirant's Climb, Obelisk of Power, Reaver's Row,
The Arena's Greatest, The Dreaming Tree. All appear in the pool dump. Do not
re-add them on a later revision.

**Signature constraint (103.2.d.2):** with Annie as Legend, **Tibbers is the only
legal Signature card in the deck.** Death from Below (Pyke), Death Mark (Zed),
Super Mega Death Rocket! (Jinx) and Spinning Axe (Draven) are *illegal here*
despite being Chaos+Fury. This is the real price of choosing Annie.

---

## The rules facts that drove these numbers

1. **Runes to cast = max(energy, power)**, not the sum. Hextech Ray at
   `{1}{P1}` is a **one-rune** 3-damage spell; Falling Star at `{2}{P2}` is a
   **two-rune** double-3. This inflates a lot of Fury removal well past its
   printed look, and it is the single biggest driver of the removal scores below.
2. **Power is ongoing attrition.** A recycled rune is gone every following turn.
   Ratings for Power-heavy top-end (Mindsplitter `{7}{P2}`, Possession
   `{8}{P3}`) are marked down for what they cost the *next* three turns.
3. **A rune exhausted on your turn stays exhausted through theirs** (315.1.b).
   Annie hands 2 back at end of turn. Every Reaction-speed card below is rated
   assuming those 2 runes, and *only* those 2 — the deck cannot afford to hold
   up more than that.
4. **An empty battlefield is a lost battlefield** (190.4.c). Every bounce and
   self-bounce effect is rated against the fact that it can cost you control.
5. **Stun is tempo, not removal** (423.1.b-c). A stunned unit still blocks and
   still must be dealt its *full* Might to die.
6. **This deck persists, it does not swarm.** Its bodies are Deflect midrange
   units that stay put, so **hold triggers fire far more than conquer triggers**
   (471.2.b) — the opposite of the Lillia token decks in this repo. Battlefield
   ratings below follow from that and nothing else.

---

## Combo clusters (named, with what actually happens)

**C1 — The deny-the-board lock. `Vex - Apathetic` + cheap Fury removal.**
Vex stuns every unit an opponent plays while she is at a battlefield, and they
can't move it that turn. Stun is not removal — the unit still blocks and still
needs its full Might in damage (423.1.c) — so Vex alone is a tax, not a wall.
She becomes a lock only when paired with burn that finishes the stunned body
the same turn: Hextech Ray (1 rune, 3 damage) and Falling Star (2 runes, 3+3)
are the payoff halves. **3 pieces minimum: Vex on a battlefield, a removal spell
in hand, a rune up.** This is the deck's actual engine, more than the mill is.

**C2 — Steal, not strip. `Kharox` + `Conscription` + `Blind Fury`.**
Three different ways to win with the opponent's own cards: Kharox mills 3 and
plays a unit out of their trash free; Blind Fury banishes their top card and
plays it free; Conscription takes an enemy unit outright. None needs the others,
but together they are ~9 slots of "my threats are their threats," which means
the deck never has to draw its own top end. **Kharox is a two-turn commitment**
— 6 runes to cast, then `{6}{Chaos}{Chaos}` (6 runes + 2 recycled Chaos) to
Empower. Annie's 2 readied runes are what make the second half reachable.

**C3 — Annie's slack + Reaction-speed disruption.** Annie readies 2 at end of
turn; `Shakedown` (2 runes, deal 6 or they let you draw 2), `Gust` (1 rune),
`Existential Dread` (1 rune) and `Heedless Resurrection` (3 runes) are all live
on the opponent's turn for free. This is not a combo so much as the reason the
Legend was picked: without it these cards are dead weight in a deck that also
wants to cast 6-drops.

**C4 — `Bone Skewer` from Hidden.** Hidden grants Reaction speed to a card whose
printed speed is Neutral, for {0}. It reveals their hand (information for every
later strip), then forces a unit *out of it* onto a battlefield **stunned**.
Combined with C1's removal that is a hard one-for-one plus tempo. **Facedown cap
applies: 1 Hidden per battlefield, 2 battlefields in 1v1, so 2 is the real
ceiling on board at once** — but copies still cycle, so 3 is not a misplay.

**C5 — `Annie - Fiery` + every damage spell.** +1 Bonus Damage to all spells and
abilities turns Hextech Ray into 4-for-1-rune, Falling Star into 4+4-for-2, and
Tibbers into a 4-to-all-battlefields wipe. 715.4 gates it: if no damage was
dealt, no bonus applies, so it does nothing for the strip half of the deck.

---

## Traps — cards that look right for this deck and are not

- **Invert Timelines** (45). "Each player discards their hand, then draws 4"
  reads as hand attack and is the opposite: it *refills* the hand you spent six
  cards emptying, and hands them 4 fresh answers. Symmetric card-neutral resets
  help whoever has fewer resources — after you strip them, that is them.
- **Walking Roost** (52). A 6-Might Deflect body for 5 runes looks like a great
  hold — but it *gives the opponent a 1-Might Deflect Bird*, and per 190.4.a a
  Bird is a body, and a body holds a battlefield. You are handing the enemy the
  exact resource this deck is built to deny them.
- **Downwell / Possession / Baron Nashor** (55 / 60 / 55). All three are "I win
  if I reach turn 12." This deck's disruption has a shelf life — once their hand
  refills, stripping stops mattering. Rating a symmetric reset highly assumes a
  long game that the plan does not want.
- **Rhasa the Sunderer** (48) and **Shadowblade Lurker** (46). Both are
  self-mill payoffs: `{10}` minus 1 per card in your trash, `{5}` minus 2 per
  copy of itself in trash. In a deck with zero self-mill they are a 10-drop and
  a 5-rune 5/5. They belong to the *other* archetype (see README rejected list).
- **Blade Twirler** (58). Rated entirely on the 4-Might-for-4-runes body. Its
  Burn 1 is the headline text and it is worth approximately nothing: 40 cards at
  1/turn, and the payoff at the end is 1 point of 8 plus their trash reshuffling
  back into their deck (431.2.b-c).
- **Minefield / Shadow Temple** battlefields (28 / 25). Both Burn *your own*
  deck. In this deck that is pure downside — it accelerates you toward giving
  the opponent a free point.
- **Draven - Audacious** (74, but read the second line). Scores a point per turn
  on winning combat, and **hands them a point when it dies in combat**. Against
  a deck with a bigger body it is a point swing against you.

---

# SPELLS

## 85+ — core

**Hextech Ray** `{1}{P1}` — **86.** One rune for 3 damage, at Action speed. The
rune-count fact does all the work here: `max(1,1)=1`. Kills most 2- and 3-drops
on curve, and with Annie - Fiery it is 4 damage for one rune, which covers the
entire 4-Might midrange band. Competes with nothing — it is the cheapest
interaction in the identity and the deck runs 3 without discussion. Cost of
running it: the Power pip is Fury, pushing the rune base off a 6/6 split.

## 70-84 — strong

**Bone Skewer** `{2}{P1}` (Hidden) — **84.** The plan's best card. Hidden makes
it Reaction speed for {0}, it reveals their hand (which is what makes every
later Mindsplitter/Insightful Investigator a targeted strike instead of a
guess), and it drags a unit out of their hand onto a battlefield **stunned**.
Competes with nothing for its slot. Costs: it must be pre-committed a turn
early, it is Neutral speed and near-useless from hand, and it hands the opponent
a body on the board — so it is only correct when you can kill that body, which
ties it to the removal count. Capped at 2 face-down at once in 1v1.

**Void Seeker** `{3}{P1}` — **81.** Three runes for 4 damage **and** draw 1.
Fury and Chaos are both listed as weak at card draw, so a removal spell that
replaces itself is doing two jobs. This is the "when in doubt" removal slot.

**Falling Star** `{2}{P2}` — **78.** Two runes, two separate 3-damage hits, so
it is a genuine two-for-one against any board of 3-Might-or-less. `max(2,2)=2`
makes it look far worse than it is. With Annie - Fiery it is 4+4 for two runes.
Costs 2 recycled runes of ongoing attrition, which is the real reason it is not
higher.

**Smite** `{2}{P1}` — **77.** Deal 3, and **banish** it if it would die. Banish
dodges every recursion effect in the format, and Chaos/Shadow Isles decks are
full of them. Two runes. The narrow reason to pick this over Hextech Ray is a
known reanimator opponent.

**Wind and Ghosts** `{3}{P1}` — **76.** Three runes, and it answers *anything*:
banish if 3 Might or less, bounce it otherwise. The flexibility is the point —
this deck has no other clean answer to a 6-Might Deflect body, and bouncing one
costs them the whole re-cast. Competes with Rebuke for the bounce slot and wins
on the banish mode.

**Conscription** `{5}{P2}` — **76.** Five runes to take an enemy unit of 3 Might
or less permanently; spend 5 XP instead and it takes **any** enemy unit at a
battlefield. Steal is the plan and this is the cleanest expression of it: it is
simultaneously removal and a threat, which is the two-jobs test. The XP mode
needs a real XP source in the build or the card is capped at small units.

**Blind Fury** `{4}{P2}` — **74.** Four runes: banish their top card and play it
free. Card advantage, a permanent card off their deck, and a body/spell you did
not have to draw. Rated below Conscription because it is **random** — you may
banish and be handed a rune-hungry card you cannot use, and the Power cost is 2
recycled runes. It is also the only card in the deck that literally reduces
their library and never gives it back (banish, not trash — so a Burn Out never
returns it).

**Piercing Light** `{2}{P1}` — **74.** Two runes for 2 + 2 to a second unit,
with Repeat to scale late. The reach against two small bodies is what a
board-denial deck wants; the 2s are the problem, and Annie - Fiery fixing them
to 3s is a real argument for that champion.

**Gust** `{1}` — **73.** One rune, **Reaction speed**, bounce a ≤3 Might unit at
a battlefield. This is the card Annie's two readied runes exist to hold up. The
specific scenario that makes it excellent: they move a lone body onto an empty
battlefield in their Beginning Phase to hold; you bounce it in response and they
score nothing (190.4.c). That line wins games and costs one rune.

**Existential Dread** `{1}{P1}` — **72.** One rune: stun an attacking enemy, and
if it is *already* stunned, bounce it instead. The second clause is the Vex -
Apathetic payoff — Vex stuns their unit on play, this bounces it on their attack.
Repeat for {2} scales. Cheap combat blowouts are the correct interaction profile
for a deck that must hold runes back.

**Shakedown** `{2}{P1}` — **72.** Reaction speed, two runes: 6 damage to an enemy
unit **unless they let you draw 2**. Both halves are fine for you, which makes
it the rare card that is never dead. It is the best use of Annie's held-up runes
on a turn where nothing else needs answering.

**Rebuke** `{2}{P2}` — **70.** Two runes, bounce any unit at a battlefield, no
Might cap. Straight tempo and a scoring denial. Loses the slot to Wind and
Ghosts when both are in hand; runs alongside it because two runes beats three.

## 55-69 — conditional (the band that matters)

**Hard Bargain** `{2}` — **67.** Reaction, counter unless they pay {2}. Two runes
is exactly what Annie hands back, so this is castable on their turn without ever
skipping a development turn — which is the only reason a counterspell is
playable in a deck this expensive. The specific spot: they tap low to deploy a
threat, and the {2} tax is unpayable. Against an untapped opponent it is a
2-rune Cantrip-less blank, which is why it is not higher.

**Incinerate** `{2}` — **66.** Two runes, 2 damage, no Power pip. The no-Power
part is the argument (Section 6: zero-Power cards smooth the curve and let you
skew the rune base hard). Strictly worse than Hextech Ray on rate; runs as
copies 4-6 of the cheap-removal effect.

**Star-Crossed** `{3}{P1}` — **64.** Reaction, bounce one of yours and one of
theirs. The symmetric clause is usually a cost, but here it is sometimes the
point: bouncing your own "when you play me" unit (Insightful Investigator,
Bewitching Spirit) rebuys the strip trigger. Three runes at Reaction speed is
one more than Annie gives back, which is what caps it.

**Abandon** `{2}` — **62.** Counter a spell, return it to **hand** rather than
trash, plus Predict. Returning it to hand is a real downside against a deck that
can just re-cast — you have bought a turn, not a card. The Predict is small. Its
one clear application: countering a removal spell aimed at Vex - Apathetic, where
one turn is enough.

**Firestorm** `{6}{P1}` — **62.** Six runes, 3 to all enemy units at *one*
battlefield. The sweeper this deck wants exists at 8 runes (Tibbers); this is
the affordable version but 6 runes is a whole turn with no board added. With
Annie - Fiery it becomes 4-to-all, which clears the entire 4-Might band and is
the specific case that makes it playable.

**Isolate** `{2}` — **60.** Move an enemy unit from a battlefield to base, draw 1
if that leaves an enemy alone there. Scoring denial for two runes with a
conditional cantrip. Loses to Gust on speed (Neutral vs Reaction) and that is
usually decisive.

**Disintegrate** `{4}` — **58.** Four runes, 3 damage, draw if it kills. No Power
pip. Too expensive for the effect in a deck already straining on runes; it is
the cut when the curve gets counted.

**Sky Splitter** `{8}{P1}` — **56.** Cost reduced by the highest Might you
control, so with a 6-Might body it is a 2-rune 5-damage spell. The specific
scenario: you have Draven - Audacious or Beast Below down and need to answer
their finisher immediately. Real, but it is dead in every hand where the board is
empty — which is exactly the hand where you need removal.

**Downwell** `{8}{P2}` — **55.** Return all units and gear to hand. A genuine
reset button, but symmetric and 8 runes, and it undoes your own board. Its one
use is unwinding a board you have already lost, at which point you have spent a
turn to go back to parity with no cards gained.

**Ruthless Strike** `{3}` — **55.** 3 damage, or 5 if you discard a card. Three
runes, no Power. The discard is a real cost in a deck with no trash payoffs; the
5-damage mode is the reason to consider it over Void Seeker, which draws instead.

**Thermo Beam** `{5}{P2}` — **55 main / 78 sideboard.** Kill all gear. Dead in
most matchups, devastating against an Equipment or Gold-token deck. This is the
textbook sideboard profile (Section 9) and it should never start.

**Whirlwind** `{3}{P1}` — **55.** Starting with the next player, each player may
bounce a unit. Giving the opponent the choice first is a serious downside;
politically it is a one-for-one where they pick the better trade.

**The Harrowing** `{6}{P2}` — **55.** Six runes to play a unit from your trash
free. The deck has no self-mill, so the trash fills only from removal trades and
Annie's own dead bodies. It is a fine "rebuy Mindsplitter" card in the late game
and nothing at all before turn 8.

**Heedless Resurrection** `{2}{P1}` — **57.** Reaction, kill a friendly unit as
an additional cost, play a unit from your trash of no greater cost, free. Three
runes at Reaction speed. The specific spot that makes it good: your unit is about
to die in combat anyway, so you convert a dying body into a fresh one at
instant speed and keep the battlefield (190.4.c). Needs a populated trash, which
this deck fills slowly.

**Possession** `{8}{P3}` — **60.** Take any enemy unit at a battlefield and
recall it. Strictly the effect the deck wants, at a cost the deck cannot pay —
8 runes and 3 recycled. Conscription does 80% of it for 5. Rated here only
because "steal their best unit" is genuinely a win condition, not just value.

**Fading Memories** `{4}{P1}` — **58.** Give a unit or gear Temporary — it dies
at the start of its controller's Beginning Phase, before scoring. Four runes to
kill anything, with a full turn of delay, and it kills *before* the Scoring Step
so it does deny the point. The delay is the problem: they get a full turn of
attacks out of it first.

**Up from the Deep** `{3}` — **56.** Two 1-Might Tentacle tokens, with Flow to
rebuy from the trash. Bodies are this deck's structural weakness and this is the
cheapest way to buy two of them. **They enter exhausted (185.2.d — no "ready"
in the text), so they are two blocks, not two attackers,** and they cannot
conquer the turn they arrive.

**Get Excited!** `{2}{P1}` — **55.** Discard a card, deal its Energy cost as
damage. Two runes and it scales with the expensive cards you were not going to
cast anyway (discard Mindsplitter, deal 7). The specific case: you are flooded on
top-end and short on answers, which happens often in this build.

**Stacked Deck** `{1}` — **58.** One rune, look at top 3, keep 1, recycle the
rest. Pure selection, no card advantage — but a deck with a two-card combo (Vex +
removal) and expensive one-ofs wants to find its half. Cheap enough to cast on a
turn where the runes would otherwise sit idle.

**Right of Conquest** `{3}{P1}` — **57.** Draw 1, plus 1 per battlefield you
control. In 1v1 with two battlefields the realistic mode is draw 2 for three
runes, which is fine and unexciting; draw 3 requires the board this deck
struggles to build.

**Lunar Boon** `{3}` — **55.** Reaction, discard 1 then draw 2. Real card
advantage at instant speed, but three runes is one more than Annie hands back,
so casting it on their turn means skipping development on yours.

## Under 55 — one line each

- **Acceptable Losses** `{1}` — 40. Symmetric gear kill; this deck runs almost no gear, so it is nearly one-sided, but the effect is too small to matter.
- **Blood Rush** `{1}` — 38. Assault 2 with Repeat. Combat trick for an aggro deck; this is not one.
- **Cleave** `{1}` — 36. Assault 3 this turn. Same.
- **Decree of Discord** `{1}{P1}` — 48. Sideboard-only: bounces enemy Order units of total Might ≤5. Excellent against an Order swarm, blank otherwise. **62 as a sideboard card.**
- **Decree of Rage** `{1}{P1}` — 48. Uncounterable 4 damage to a **Calm** unit. Same profile. **64 as a sideboard card** — Calm is a real archetype.
- **Detonate** `{1}{P1}` — 30. Kill a gear, its controller draws 2. Giving them 2 cards is unacceptable in a deck built on card denial.
- **Factory Recall** `{1}` — 32. Bounce a gear. Sideboard filler at best.
- **Monster Harpoon** `{1}{P1}` — 52. One rune, 2 damage, 4 if you control a facedown card. With 3 Bone Skewers the condition is live more often than it looks — but "more often than it looks" is still under half the time.
- **Vault Breaker** `{1}{P1}` — 34. Assault 2 + Ganking. Aggro trick.
- **Against the Odds** `{2}` — 30. Defensive pump scaling with enemy units here. Wrong deck.
- **Angle Shot** `{2}` — 24. Equipment shuffling plus a cantrip. No Equipment.
- **Brittle Steel** `{2}{P1}` — 42. Kill a gear, with Flow. Sideboard tech.
- **Bushwhack** `{2}{P1}` — 40. Friendly units enter ready this turn + a Gold token. For a deck deploying multiple bodies a turn; this one deploys one.
- **Consuming Curse** `{2}` — 44. 2 damage, +1 per copy in your trash. Needs 3 copies and a long game to beat Incinerate. A self-mill card in disguise.
- **Dancing Grenade** `{2}{P1}` — 46. 2 damage, and its *controller* may replay it — the opponent gets the rebuy too. Reads better than it is.
- **Flash** `{2}` — 36. Move up to 2 friendly units to base. Retreat effect; abandoning a battlefield loses it.
- **Lotus Trap** `{2}` — 44. Double all damage to a unit this turn. A real removal multiplier at Reaction speed, but it does nothing on its own — a two-card combo where the other half is already sufficient.
- **Morbid Return** `{2}` — 42. Return a unit from your trash to hand. Slow value in a deck with a thin trash.
- **Ride The Wind** `{2}{P1}` — 40. Move a friendly unit and ready it. Tempo for a conquer deck.
- **Switcheroo** `{2}{P2}` — 46. Swap the Might of two units at a battlefield. Genuine blowout potential against one big body, but it needs your own unit there and does nothing to a lone enemy.
- **Temptation** `{2}` — 48. Move an enemy unit to a location with a friendly-to-them unit. Can force a bad combat; too cute for a slot here.
- **Twilight Step** `{2}{P1}` — 40. Move a ≤3 Might unit, with Flow. No self-mill to feed the Flow half.
- **Upstage Comedy** `{2}` — 34. Ready a unit, Repeat. Wrong deck.
- **Invert Timelines** `{3}{P1}` — 45. See Traps. Refills the hand you spent the whole game emptying.
- **Perfect Execution** `{3}{P1}` — 36. Ready + Assault 3, with Flow. Aggro.
- **Shadows of the Past** `{3}{P1}` — 42. Return up to 2 units from *trashes* (both players') to hand. The scoping is interesting — it can strand nothing of theirs usefully — but it is card-neutral value in a deck that wants tempo.
- **Sudden Storm** `{3}` — 50. Hidden, 2 damage, 4 to an attacker. Competes directly with Bone Skewer for the one-Hidden-per-battlefield slot and loses badly.
- **Square Up** `{4}` — 26. Assault 4, Repeat by discarding. Aggro.

---

# UNITS

## 85+ — core

**Vex - Apathetic** `{4}` 4 Might, Chaos, Champion unit (Vex tag — legal in the
**main deck**, not the Champion Zone) — **87.** Deflect, and *"when an opponent
plays a unit while I'm at a battlefield, stun it. They can't move it this turn."*
This is the deck's engine. It does not remove anything — a stunned unit still
blocks and still needs its full Might in damage (423.1.c) — but it denies them
the two things that score points: **damage and movement**. A unit played to
contest Vex's battlefield cannot attack into her that turn, and cannot leave.
Four runes for a 4-Might Deflect body is already fair rate; the lock is free.
Competes with nothing. What it costs: it only works where Vex is standing, so
the deck must be able to *keep* her there, which is what the removal suite is
for. Run 3.

## 70-84 — strong

**Insightful Investigator** `{3}` 3 Might, Chaos — **78.** Reveal their hand, pay
2 XP, take their best card. A 3-Might body on a 3-drop is exactly on rate, so
the strip is free — that is the two-jobs test passing. Two flaws: the XP cost
needs a real source in the build, and **they draw 1** afterwards, so it is a
quality swap rather than card advantage. Still the best strip effect per rune in
the pool, and unlike Mindsplitter it is castable on turn 2.

**Mindsplitter** `{7}{P2}` 7 Might, Chaos — **76.** Seven runes for a 7-Might
body plus a targeted hand strip. It is the *only* strip effect attached to a
body that can actually hold a battlefield by itself, which is why it survives
the curve objection. The 2 Power is 2 runes of ongoing attrition — casting this
on turn 7 leaves you at 10 runes on turn 8, not 12. One or two copies, never
three.

**Draven - Audacious** `{6}{P1}` 6 Might, Chaos — **74.** Deflect, 6 Might, and
**scores a point the first time it wins a combat each turn.** That is a genuine
win condition rather than a value engine, and this deck badly needs one. Read
the second line before running it: *"when I die in combat, choose an opponent.
They score 1 point."* Against a bigger body it is a 2-point swing. The specific
condition that makes it correct: you have removal up to clear the blocker first.

**Kharox** `{6}` 5 Might, Chaos — **72.** The flagship of the plan. Empower for
`{6}{Chaos}{Chaos}` → they Burn 3, and **you play a unit out of their trash for
free.** The mill is irrelevant; the steal is the card. Rated 72 not higher
because it is a **two-turn, twelve-rune commitment** (6 runes to cast, 6 more
plus 2 recycled Chaos to Empower) and Empowered is binary (441.1.b), so each
copy fires **once**. Annie's readied runes are what bring the second half into
range at all. Its floor is a 5-Might body for 6, which is poor.

**Brynhir Thundersong** `{6}` 5 Might, Fury — **70.** *"When you play me,
opponents can't play cards this turn."* Six runes for a 5-Might body and a
one-turn hard lock. The specific scenario that earns the slot: the turn you
Empower Kharox or swing for the final point, this guarantees no Reaction, no
counterspell, no Ambush blocker. It is protection for a combo deck that
otherwise has none. Costs a full turn's runes.

**Vex - Cheerless** `{5}{P1}` 5 Might, Chaos — **70.** While in combat, your
spells cost `{1}{any}` less and **enemy spells cost `{1}{any}` more.** A
two-sided tax that turns every showdown into a resource mismatch, on a 5-Might
body. The condition — "while I'm in combat" — is narrower than it reads: it does
nothing on your Main Phase deployments. Good in the exact games that go long.

## 55-69 — conditional (the band that matters)

**Minah Swiftfoot** `{6}{P1}` 6 Might, Chaos — **68.** *When I move to a
battlefield*, each player discards 1 **or** each player draws 1. The trigger is
on **move**, so it is repeatable — a recurring symmetric discard, and symmetric
discard favours whoever has fewer cards, which after six turns of stripping is
them. The draw mode matters more than it looks: it is the deck's only repeatable
card draw. Six runes and 1 Power caps it.

**Beast Below** `{7}{P2}` 8 Might, Chaos — **68.** Bounce a friendly and an enemy
unit, on an 8-Might body. The friendly bounce is upside here — it rebuys
Insightful Investigator or Bewitching Spirit. Seven runes; the biggest body in
the identity that is not a 10-drop.

**Kayn - Unleashed** `{6}{P1}` 6 Might, Chaos — **66.** Ganking, and takes **no
damage** if it has moved twice this turn. Battlefield→battlefield movement
without Ganking is illegal (810), so Kayn is the deck's only unit that can
contest two battlefields in a game, and the damage immunity makes it an unkillable
attacker on the turn it double-moves. The specific spot: their last blocker sits
on the battlefield you need for point 8.

**Bewitching Spirit** `{3}` 2 Might, Chaos — **62.** Random discard 1 on a 2-Might
body. Strictly worse than Insightful Investigator as a body and as a strip
(random vs targeted), but it needs no XP and it is a *3-drop that is never dead*.
Copies 4-6 of the strip effect.

**Syndra - Transcendent** `{6}{P1}` 6 Might, Chaos — **62.** While in a showdown,
your spells have Repeat `{2}{Chaos}`. Doubling Falling Star or Piercing Light mid-
combat is a genuine blowout; six runes for the body plus the Repeat cost on top
means you rarely have the runes to use it the turn it lands.

**Mel, Defiant Soul** `{5}` 4 Might, Chaos — **62.** Empower by discarding a
spell → **banish** an enemy unit of 3 Might or less. Banish, not kill, so it
beats recursion. The cost is a card, and this deck's cards are its plan.

**Zaunite Bouncer** `{4}{P2}` 2 Might, Chaos — **58.** Bounce a unit at a
battlefield stapled to a body. Four runes for 2 Might is a genuinely bad rate —
you are paying two extra runes over Rebuke for a body that cannot hold anything.
Its one real use: the bounce target is *another* unit, so it can rebuy your own
strip unit while adding a blocker.

**Blade Twirler** `{4}` 4 Might, Fury — **58.** See Traps. A fine 4-for-4 body;
the Burn 1 is decoration. Included in ratings at the body's value so a later
revision does not re-add it for the text.

**Walking Roost** `{5}` 6 Might, Chaos — **52.** See Traps — the Deflect Bird it
gives the opponent is a body, and a body holds a battlefield.

**Evelynn - Entrancing** `{2}` 2 Might, Chaos — **60.** Hidden, Backline, and when
played from face down on your turn it **drags an enemy unit from another location
to her battlefield.** That is forced repositioning at Reaction speed for {0} —
it can strip the last body off a battlefield they were about to score
(190.4.c). Competes with Bone Skewer for the Hidden slot and loses, but it is
the best two-drop in the identity for this plan.

**Undercover Agent** `{5}{P1}` 5 Might, Chaos — **58.** Deathknell: discard 2,
draw 2. A 5-Might body for 5 runes that replaces itself when it dies. Card
filtering, not advantage.

**Grim Apothecary** `{3}` 3 Might, Fury — **57.** Ambush (Reaction speed) and it
may bounce a friendly unit at a battlefield on arrival. The Ambush is the value:
a 3-Might blocker flashed in during their attack, off Annie's held runes. The
bounce clause rebuys a strip trigger.

**Jae Medarda** `{5}{P2}` 5 Might, Chaos — **56.** Draw 1 whenever you choose it
with a spell. In a deck with 12+ spells that is a real engine, but almost all of
this deck's spells choose *enemy* units. Wrong shell.

**Ravenbloom Prefect** `{3}` 3 Might, Chaos — **56.** Banish it to banish an
opposing gear as they play it. A 3-Might body with a free sideboard-grade answer
attached. **68 against a gear deck.**

**Sneaky Deckhand** `{3}` 2 Might, Chaos / **Sai Scout** `{6}` 5 Might, Chaos —
**58 / 56.** Both may be played to an **open** battlefield, which is otherwise
illegal (806.3 restricts you to base or a battlefield you control). That is the
deck's only way to claim new ground without spending a Move, and it matters for
the 8th-point problem (471.1.b.1). Sneaky Deckhand's 2 Might is the issue.

**Miss Fortune - Buccaneer** `{4}{P1}` 4 Might, Chaos — **64.** *"Friendly units
may be played to open battlefields"* — it grants the Sneaky Deckhand effect to
the **whole deck**, permanently. That directly answers the final-point rule:
with her out, a second body can be deployed straight onto an uncontested
battlefield for a same-turn double score. Four runes, 4 Might, on rate.

**Traveling Merchant** `{2}` 2 Might, Chaos — **55.** Loot on move. Cheap body,
smooths draws, fills the trash slightly for Heedless Resurrection.

**Tail-Cloaked Matriarch** `{4}` 4 Might, Chaos — **55.** Empower `{2}{Chaos}` →
play a cheap unit from your trash free. Fine rate, but the trash is thin here.

**Angler Beast** `{5}{P1}` 5 Might, Chaos — **58.** Bounce **all** units of 2
Might or less on arrival. A one-sided sweeper against token and swarm decks and
a blank against midrange. **72 against Order swarm.**

**Maddened Marauder** `{5}` 4 Might, Chaos — **56.** Tank, and moves a unit from
a battlefield to base on arrival. Scoring denial plus a body that soaks damage
first.

**Gust Monk** `{2}` 2 Might, Chaos — **55.** Two-drop that can banish a card from
**any** trash — including theirs. Anti-recursion tech on a body.

**Kog'Maw - Caustic** `{3}{P1}` 1 Might, Chaos — **57.** Deathknell: 4 damage to
**all** units at its battlefield. A 1-Might body that trades up into an entire
board when they kill it. The specific scenario: chump into a stacked battlefield
and wipe it.

## Under 55 — one line each

**Two-drops (Chaos):** Mister Root 48 (Accelerate, 2 XP on move — the XP source Insightful Investigator wants, but a 1-Might body). Mystic Poro 44 (Vision). Overzealous Fan 46 (kill it to send an attacker home — a free scoring denial, but it must be defending). Sinister Poro 42. Teemo - Scout 44. Tideturner 40. Treasure Hunter 46 (Gold on move = ramp). Void Hatchling 34. Windsinger 52 (Hidden + bounce a ≤3 Might unit on arrival — nearly a two-rune Gust with a body; loses the Hidden slot to Bone Skewer). Shadow Order Disciple 30 (self-Burn). Vi, Destructive 46 (Ganking on a 2-drop, but the pump costs trash cards).

**Two-drops (Fury):** Blast Corps Cadet 50 (2 damage stapled to a 2-Might body for 2 extra runes — the cheapest "removal on a body" in the deck). Chemtech Enforcer 38 (discard on play, no payoff). Forsaken Baccai 30. Gem Jammer 40. Inferna 46 (Ambush = a Reaction blocker off Annie's runes). Legion Rearguard 38. Mischievous Marai 52 (Hidden + 2 damage on arrival at a battlefield). Pouty Poro 48 (Deflect on a 2-drop is genuinely annoying to remove). Punching Poro 30. Shadow Fiend 34.

**Three-drops:** Akali, Deadly Weapon 46. Baccai Reaper 44. Black Market Broker 50 (Gold whenever you play from face down — real with 3 Bone Skewers, but 3 Might for 3 is all it does otherwise). Cemetery Attendant 44. Corrupt Enforcer 48. Dangerous Duo 40. Dune Surfer 38. Eager Drakehound 52 (enters ready for 3 runes — tempo). Evershade Stalker 46. Ezreal, Prodigy 54 (discard 1 draw 2 on a 3-Might body; the optional-cost discount is dead here). Fizz - Trickster 52 (replay a ≤3 spell from trash — the Chaos staple at 60% inclusion, but this deck's trash is thin early). Flame Chompers 34. Immortal Phoenix 48. Jinx, Demolitionist 40. Kennen, Storm of Shuriken 36 (self-mill). Loyal Pup 44. Lucian - Gunslinger 46. Mask Mother 32. Noxus Saboteur 50 (**shuts off their Hidden cards at its battlefield** — 66 against a Hidden deck). Prepared Neophyte 40. Pyke - Dockside Butcher 46. Pyke - Returned 50. Rek'Sai - Breacher 42. Rengar - Pouncing 52 (Reaction-speed body playable to a battlefield you are attacking). Scorchclaw 46. Sentinel Adept 26. Sharkling 40. Shipyard Skulker 30 (vanilla). Spiderling 34. Tornado Warrior 44. Twilight Reveler 42. Undying Legion 40. Void Drone 44.

**Four-drops:** Annie - Stubborn 60 (see Champions). Captain Farron 46. Crescent Guardian 50. Diana, No Longer Human 48. Ember Monk 46. Fae Porter 44. Harpoon Squad 40. Irelia - Graceful 44. Jhin - Murderous Artist 54 (Deflect + Ganking + adds a rune on move — genuine ramp on a body). Kai'Sa, Survivor 50. Kha'Zix - Mutating Horror 52 (Ambush + XP generation). Kinkou Lifeblade 44. Nocturne - Horrifying 46. Noxus Hopeful 48. Oasis Raider 36. Perched Grimwyrm 32. Raging Soul 34. Red Brambleback 50. Rell - Magnetic 38. Rengar - Unseen 54 (Accelerate + Assault 2 + Deflect + Ganking on one 4-drop). Rumble - Hotheaded 32. Sivir - Mercenary 46. Twisted Fate - Gambler 48. Vayne - Hunter 46. Vi - Hotheaded 50. Zed, From the Shadows 34.

**Five-drops:** Ancient Warmonger 42. Annie - Fiery 72 (see Champions). Arena Kingpin 50 (enters ready, repeatable +3 Might). Battering Ram 44. Blazing Scorcher 40. Darius - Trifarian 48. Draven, Showboat 38. Jinx - Rebel 34. Katarina - Reckless 50. Lord Broadmane 46. Minotaur Reckoner 44 (**units can't move to base** — locks their retreats, and yours). Morgana, Vindictive 52 (Ambush, doubles marked damage — a finisher for a removal deck). Scrapyard Champion 40. Shadow Assassin 40. Shadowblade Lurker 46 (self-mill payoff). Stargazer 34 (self-mill payoff). Vicious Snapjaws 40. Xerath - Freed 54 (repeatable 3 damage for one Fury rune, but only while at a battlefield). Yasuo - Windrider 44. Zed, Without a Sound 36.

**Six-drops:** Armed Assailant 42. Baccai Sandspinner 40. Brazen Buccaneer 38. Ferrous Forerunner 48. Illaoi 46. Master Bingwen 30. Megatusk 40. Raging Firebrand 50. Renekton, Rage Fueled 44. Towering Pairofant 40. Yeti Brawler 42.

**Seven-plus:** Dunebreaker 48. Maduli the Gatekeeper 52 (moves itself onto an enemy battlefield if it outsizes them — reaches ground nothing else can). Revna the Lorekeeper 46. Tryndamere - Barbarian 44. Eclipse Dragon 40. Inviolus Vox 42. Magma Wurm 46. Ocean Drake 50. Soulgorger 44. Kadregrin the Infernal 34. Baron Nashor 55 (12 Might, uncounterable-by-them, +2 Might to your team — 10 runes is the whole objection). Rhasa the Sunderer 48 (self-mill payoff). Volibear - Furious 50.

---

# GEAR

**Seal of Discord / Seal of Rage** `{0}{P1}` — **62 / 58.** One rune each, and
they add a Chaos/Fury Power at Reaction speed. Kharox's Empower needs
`{Chaos}{Chaos}` and Annie's whole design is holding runes up — a Seal is Power
you did not have to recycle a rune for. **But see the demand rule in the skill:
count Power pips AFTER the cuts, not before.** This deck's Chaos Power demand is
modest, so 1-2 Seals maximum, and only if the final list keeps Kharox.

**Scryer's Bloom** `{1}` — **56.** One rune: kill it, `{1}`, exhaust → Predict 2,
draw 1, **gain 1 XP.** It is the cheapest XP source in the identity, and
Insightful Investigator and Conscription both want XP. Two jobs on a 1-drop.

**The List** `{1}` — **54.** Name a tag, then repeatedly give units with that tag
-2 Might. Against a tribal deck (Poro, Mech, Dragon, Yordle) it is a repeatable
removal enabler for one rune; against a mixed deck it names one card. **70 in
the sideboard.**

**Iron Ballista** `{3}` — **55.** Enters exhausted, then repeatable 2 damage to a
unit at a battlefield. Rules-fact 1b applies hard: it costs 3 runes and does
nothing the turn it lands. But from turn 4 on it is free removal every turn,
which is exactly what a deck holding runes for Reactions wants.

**Blast Cone** `{4}{P1}` — **54.** Move an enemy unit on arrival; exhaust to stun
one whenever you move an enemy unit. Combos with Isolate/Temptation/Evelynn.
Four runes for a gear that needs a second card is too slow here.

**Treasure Trove** `{2}` — **52.** Draw 1 and channel a rune when it leaves;
`{Chaos}`, exhaust to kill it on your own terms. Ramp plus a cantrip for two
runes, at instant-ish speed.

**Rage Amplifier** `{4}{P1}` — **50.** +1 Might to your units, +2 Empowered.
Anthems convert every trade into a conquest (combat damage is simultaneous and
equal to Might), but this deck fields 2-3 bodies, not 6.

**Fresh Beans** 44. **Spirit Wheel** 46. **Pack of Wonders** 48 (rebuys a Hidden
card or a strip trigger). **The Syren** 44. **Unlicensed Armory** 40. **Sun
Disc** 38. **Assembly Rig** 30. **Cursed Sarcophagus** 34. **Last Rites** 24.
**Ravenborn Tome** 42. **Endless Riches** 20 (self-mill build-around; wrong
deck entirely). **Forgotten Relic** 26 (self-Burn). **Boots of Swiftness /
Cull / Doran's Ring / Serrated Dirk / Recurve Bow / Pendulum Blade / Long Sword
/ Skyfall of Areion / Blighted Battleaxe / Edge of Night** — 18-30. Vanilla
Equipment with no Weaponmaster payoff in the build; Edge of Night reaches 34 for
the Hidden mode.

---

# CHAMPIONS (Champion Zone candidates — Annie tag only)

**Annie - Fiery** `{5}{P1}` 4 Might, Fury — **72. CHOSEN.** *"Your spells and
abilities deal 1 Bonus Damage."* Applied across a removal-dense deck for the
whole game this is the largest recurring effect available to Annie: Hextech Ray
becomes 4 damage for one rune, Falling Star 4+4 for two, Firestorm a 4-to-all
sweep, Tibbers a 4-to-all wipe. Because the Champion Zone copy is guaranteed
every game, the static is the most reliable card in the deck. Two real costs:
five runes for a 4-Might body with **no enter-the-board impact** is exactly the
profile rules-fact 1b says to rate *below* its stat line, and 715.4 gates the
bonus behind damage actually being dealt — it does nothing for the strip half.

**Annie - Stubborn** `{4}{P1}` 3 Might, Chaos — **60.** Cheaper by a rune,
matches the deck's Chaos weight, and returns a spell from your trash to hand —
rebuying Bone Skewer, Conscription or Blind Fury is real value. Passed over
because 3 Might for 4 runes is a body that holds nothing, and the effect is
once-per-cast rather than continuous. **This is the first thing to change if
the removal count drops in a later revision.**

**Tibbers** `{8}{P2}` 7 Might, Fury+Chaos, **Signature (Annie)** — **68.** The
only legal Signature card in the deck. Eight runes for a 7-Might body and 3
damage to **all** units at battlefields — including yours, so it is a sweeper you
build around rather than a free wipe. With Annie - Fiery it deals 4, clearing the
whole 4-Might midrange band. Section 4 says default to 3 copies of a Signature;
that advice does not survive an 8-rune card in a deck already top-heavy. One
copy, as a closer.

---

# BATTLEFIELDS (all 59 legal — 5 of the 64 in the pool dump are banned)

**Settled first, because it inverts half the ratings: this deck PERSISTS.** Its
bodies are 4-6 Might Deflect midrange units that take a battlefield and stand on
it. So **hold triggers (471.2.b) fire far more often than conquer triggers
(471.2.a)** — a conquer trigger never fires again while you keep the field
(469.1 requires *gaining* control of one you have not scored this turn). Every
"when you conquer here" battlefield is therefore rated down, and every "when you
hold here" rated up. This is the opposite of the token decks elsewhere in this
repo.

## 70+ — the real candidates

- **Grove of the God-Willow** — **82.** "When you hold here, draw 1." Both Fury and Chaos are named weak at card draw; this is the cleanest patch available and it triggers on the thing the deck already does. Q2: fully symmetric, and any holding deck draws — the weakest question-2 answer of the top picks.
- **Void Gate** — **80.** "Spells and abilities affecting units here each deal 1 Bonus Damage." Stacks with Annie - Fiery: Hextech Ray becomes **5 damage for one rune** at this battlefield. Q3 in its strongest form — this deck is removal-dense by construction and a generic midrange opponent is not.
- **Amateur Recital** — **78.** "When you hold here, you may move a unit at a battlefield to its base." Repeatable, every turn, and it can target *their* unit at the *other* battlefield — scoring denial as a permanent engine. **Q2 flags it hard:** in their hands it bounces your holder off, which is your own plan aimed at you. Bench, not a pick.
- **Power Nexus** — **76.** "When you hold here, you may pay 4 runes to score 1 point." Answers the deck's named failure point: at 7 points a Conquer only wins if you scored *every* battlefield that turn (471.1.b.1), and this deck holds with 2-3 bodies. **471.1.a.1 exempts non-Conquer point sources from that restriction**, so this is a clean 8th point. Q3: 4 runes is trivial for the deck whose Legend hands back 2 every turn and ruinous for a deck that spends its whole pool.
- **Altar to Unity** — **74.** "When you hold here, play a 1 Might Recruit unit token in your base." A free body every turn, in **base** and therefore able to move out and conquer later (rules-fact 3). Directly patches the body shortage and supplies the second ready body a same-turn double conquest needs.
- **Frozen Fortress** — **74.** 1 damage to each unit here at the start of *each* player's Beginning Phase. Asymmetric toward big bodies, and this deck's are 4-6 Might while swarm decks live at 1-2. Chips into range of Hextech Ray. Q2: genuinely bad for us against a deck that ignores it, and it kills our own 2-Might strip units.
- **The Academy** — **72.** "When you hold here, give your next spell this turn Repeat equal to its base cost." Doubling Falling Star or Piercing Light is a one-sided sweep. You still pay the cost twice, which is the cap.
- **Startipped Peak** — **72.** Channel a rune on hold. Ramp on the thing the deck does; redundant with Annie.
- **Navori Fighting Pit** — **70.** Buff a unit here on hold — a **permanent** accumulating +1 Might buff. Combat damage is simultaneous and equal to Might, so each stack converts another trade into a conquest.
- **Fortified Position** — **70.** Shield 2 on defence. This deck defends its held battlefields; it does not attack into theirs.
- **Ravenbloom Conservatory** — **70.** "When you defend here, reveal the top card of your Main Deck. If it's a spell, put it in your hand." Triggers on **defending** — i.e. exactly when you are behind — and this deck is spell-dense, so it hits far more often than half the time. The best genuinely *reactive* battlefield in the pool.

## 55-69

- **Hallowed Tomb** — **68.** Return your Chosen Champion from trash to the Champion Zone on hold. Annie - Fiery is a 5-rune static engine they will kill; buying it back for free matters.
- **Ripper's Bay** — **68.** "When a unit here is returned to a player's hand, that player may pay {1} to channel a rune." This deck bounces constantly (Gust, Rebuke, Wind and Ghosts, Beast Below) — ramp riding on the plan it already runs.
- **Forgotten Monument** — **66.** "Players can't score here until their third turn." A pure clock-slower, which is a one-sided gift to the slower deck. This is the slower deck.
- **Gardens of Becoming** — **64.** "Units here have 'Exhaust: Gain 1 XP.'" The XP source Insightful Investigator and Conscription's 5-XP mode both want.
- **Trifarian War Camp** — **62.** +1 Might to units here, symmetric. Rated down because this deck fields fewer bodies than most, so a symmetric anthem favours the wider board.
- **Bandle Tree** — **58.** Hide an additional card here — two Bone Skewers at one battlefield. Narrow but genuinely this deck's card.
- **Threshold of the Gray** — **58.** Both sides Add {1} when combat starts. Slightly ours: we hold Reactions.
- **Targon's Peak** — **58.** Ready 2 runes at end of turn on **conquer**. Doubles Annie, but it is a conquer trigger in a hold deck.
- **The Papertree** — **56.** Symmetric rune channel on hold.
- **Risen Altar** — **54.** Empower costs 1 less. Kharox, Mel and Tail-Cloaked Matriarch only.
- **Abandoned Hall** — **52.** +1 Might on playing a spell, symmetric; this deck plays the most spells.
- **Rockfall Path** — **50.** Units can't be played here. Denies deployment, but units may still *move* in, so it does not lock the field.
- **Marai Spire** — **50.** Repeat costs 1 less. Three cards care.

## Under 50 — one line each

Seat of Power 48 · Sunken Temple 48 · Windswept Hillock 48 · Vilemaw's Lair 46 · Valley of Idols 46 · Treasure Hoard 46 · Altar of Blood 46 · Forgotten Library 46 · Forbidding Waste 45 · Star Spring 44 · Zaun Warrens 44 · Trapping Grounds 44 · The Candlelit Sanctum 42 · Emperor's Dais 42 · Back-Alley Bar 40 · Vaults of Helia 40 (its hold trigger *taxes the holder* — a downside battlefield) · Sandswept Tomb 40 (discounts spells choosing your **own** units; this deck's spells choose theirs) · Reckoner's Arena 40 (this deck has almost no conquer effects) · Dusk Rose Lab 38 (wants disposable bodies; these are persistent) · Protective Sands 36 (rewards controlling ≤4 runes — anti-synergy with Annie) · Sigil of the Storm 36 · Veiled Temple 34 · Monastery of Hirana 32 · Hall of Legends 30 (Annie's ability is a static end-of-turn trigger — readying her does nothing) · Ornn's Forge 30 · Dragon Roost 30 · Piltovan Forge 28 · Kinkou Temple 28 · **Minefield 28** (Burns *your* deck) · **Shadow Temple 25** (Burns *your* deck, 3 at a time) · Forge of the Fluft 24 · Black Flame Altar 22 · The Grand Plaza 20 (needs 7 units at one battlefield).

## Never-pick for this deck, with the reason

- **Heisho, Shell of the World** — **25.** "Players ignore Deflect while paying for spells and abilities choosing something here." This deck's three most important bodies are Deflect (Vex - Apathetic, Vex - Cheerless, Draven - Audacious). It is a battlefield that specifically switches off your own defensive keyword.
- **Mystic Vortex** — **30.** Reaction cards cost {any rune} more here. Annie's entire design is holding runes for Reactions; this taxes the Legend's ability directly.
- **Shadow Temple / Minefield** — Burn your own deck. Every card burned moves you toward a Burn Out, which hands the **opponent** a point (431.2.c).
