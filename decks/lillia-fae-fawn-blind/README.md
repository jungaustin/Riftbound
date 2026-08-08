# Lillia Fae Fawn — Sprite Tempo (clean-room build, meta-corrected)

**Legend:** Lillia - Bashful Bloom (Calm+Mind)
**Chosen Champion:** Lillia - Fae Fawn
**Current version: v6** (`v6.txt`)

**The plan in one sentence (v6):** manufacture **two ready Sprites in your base**
on the same turn and conquer **both** battlefields, using a dense layer of cheap
interaction to win combats a 3-Might Sprite would otherwise only trade — and
close at 8 with a double conquest rather than a hold.

**The v5 plan, for contrast:** make a cheap ready Sprite nearly every turn
(Legend activation, Sprite Fountain, Sprite Call, Fae Fawn's move), conquer
with it, and use a dense layer of 1-rune interaction — Stupefy, Defy, En
Garde, Charm — to win the combats a 3-Might Sprite would otherwise only trade,
while holding runes live on the opponent's turn; break a stalled board with
Riptide Rex, Thousand-Tailed Watcher, or the single Unchecked Power.

**Failure point:** the deck loses if 3-Might Sprites can't profitably attack
into blockers. Ten 1-rune interaction cards, Heart of Dark Ice's free +3, and
the three bombs all exist to answer that one problem.

Built **2026-07-31** as a clean-room build (no existing Lillia deck in this
repo was opened — hence the separate folder from `decks/lillia-fae-fawn/`).
v3-v5 then incorporated two established lists the user supplied, the user's own
playtest results, and several rules corrections they caught. Meta layer ON —
see `data/archetypes.md`. Play-rate figures below are from `data/staples/`.

## Version history

- **v1** — first 40 from the pool ratings. 1x Zilean, 2x Meditation; Trevor /
  Soul Shepherd / Protector of Dreams at 2 each.
- **v2** — critique flagged three engine pieces at 2 copies; cut Zilean and
  Meditation to take them to 3.
- **v3** — after studying the two supplied meta lists: imported 3x Sprite
  Fountain and 2x Riptide Rex; cut Keeper of Masks and Shadow Watcher.
- **v4** — cut the Heimerdinger + Keeper engine and LeBlanc entirely; added
  Scuttle Crab, Defy and Janna main, Heart of Dark Ice, and 2x Thousand-Tailed
  Watcher. Full reasoning retained below under "v4 changes".
- **v5** — the staples data (`data/staples/`) showed the deck was
  missing the format's most-played cards. See below.
- **v6 (current)** — dropped the hold plan and committed to the double conquest;
  added Seals for the rune bleed and a draw battlefield. See above.

### v6 changes and why (current)

Driven by the user's play experience and four corrections they were right about.
**Two decisions define this version: the deck stops trying to hold and commits to
the double conquest, and it stops trying to win the Might-trick war.**

**The structural finding behind it.** A Standard Move costs **zero runes**
(144.4) and **only the Turn Player readies** (315.1.b) — so an attacker declares
combat with a full pool while the defender holds only what they chose not to
spend last turn. This deck is on the wrong side of that in *both* directions: it
must spend 2-4 runes manufacturing an attacker before it can even move, and it
defends on leftovers. So Discipline/En Garde arms races are structurally
unfavourable and were trimmed, not expanded.

**The answer is pre-paid interaction.** Hidden cards are bought on your turn (when
you have runes) and flip for **{0}** on theirs (when you don't) — and hiding costs
**1 Power**, which a Seal produces free at Reaction speed. Seal → hide → free
answer on their turn, every turn cycle, for no runes and no attrition.

| out | in | why |
|---|---|---|
| 2 Riptide Rex | 2 Wages of Pain | {6}{P2} recycles 2 runes and you channel 2 a turn — Rex costs a **whole turn of channelling** on top of its cast. Wages is {3} **P0**, kills the 3-Might baseline *before* combat starts, is hideable, and its Gold token is a stored Power pip. |
| 1 Discipline (3→2), 1 En Garde (2→1) | 1 Back Off | Pump loses the mirror-trick war. Stun doesn't: their unit deals no damage (423.1.b), so your Sprite survives. {3} P0, hideable. |
| 1 Retreat | 1 Consult the Past | Retreat saved the card but not the field. Consult hides for 1 rune, bluffs as a threat, and cashes for Draw 2 at their end step — you never lose it, because Hidden grants Reaction (811.6). |
| 1 Lilting Lullaby (3→2) | 1 Seal of Focus | Lullaby was 6 of the deck's 24 attrition. Kept at 2 for the spell lockout — and it is the **only Signature card legal here** (103.2.d.2). |
| 1 Trevor Snoozebottom (3→2) | 1 Seal of Insight | Trevor gets you *to* 7 and can't get you *through* it. He stays at 2 for a second reason: see the Hidden constraint below. |
| 1 Smoke and Mirrors (2→1) | 1 Sprite Call (2→3) | Facedown slots are the scarce resource, and ready-Sprites-in-base is the plan. |
| Emperor's Dais | Ravenbloom Conservatory | The Dais made permanent bodies to *hold* — the plan the deck just abandoned. |
| 1 En Garde (1→0) | 1 Seal of Focus (1→2) | A 1-of situational trick is 22% to be found by turn 5, and it is spent on the Might arms race the deck loses. 0 or 3, never 1. |
| 1 Back Off (1→0) | 1 Seal of Insight (1→2) | The weakest of the Hidden package — stun that they can simply pump through — and the eighth card competing for two facedown slots. |
| 1 Unchecked Power (1→0) | 1 Smoke and Mirrors (1→2) | **Reason expired.** Unchecked Power exhausts all friendly units, so you sweep and then *cannot take the empty battlefields* — it actively fights the double-conquer plan it was kept for. |
| Runes 7 Mind / 5 Calm | **7 Calm / 5 Mind** | The split inverted. Calm now carries 9 hard pips (Defy, Charm, Dark Ice, Seal of Focus) and they are the cheap cards you want live every turn; Mind's 7 are Sprite Fountain plus the late Watcher, and by turn 6 you have all 12 runes anyway. |

**Seals to 2+2, not 3+3.** Chance of having drawn at least one, 40-card deck:
1+1 is 40% by turn 5, 2+2 is 66%, 3+3 is 81%. The jump from 1+1 to 2+2 costs two
slots for 26 points; 3+3 costs *four* slots for 15 more, and the ceiling is capped
anyway — a busy turn only spends 2-3 Power pips, so a third Seal of a domain is a
dead draw. **Cost of the change: gear is now 9 of 40**, which is a lot of surface
for Turn to Dust and Disarming Rake.

**Smoke and Mirrors stayed at 2 on the user's call, correctly.** Swapping Fae Fawn
is a *move*, so she leaves a Sprite at the battlefield she vacated while the base
Sprite arrives there — two bodies at the contested field, Lillia safe at base, and
a card drawn, for 2 runes and **zero attrition**. Nothing else in the deck does
four things at once, and P0 is the whole theme of this version.

**Charm was considered for the cut and kept.** Its sorcery speed spends runes on
*your* turn, which is exactly when you have them — the deficit is on the
opponent's turn, so Charm never competes for the scarce resource. And it is the
only card that takes a battlefield with **no combat happening**, which is the
direct answer to the mirror-trick problem.

Petal Pixie went **back to 2**: the turn-1 requirement outranks the synergy
argument for cutting her. Non-spell turn-1 plays are now **7 bodies** (2 Pixie,
2 Scuttle Crab, 3 Sprite Fountain) plus the 2 Seals.

**The Hidden constraint — this decides Trevor's floor.** 811.1.b lets you hide
only **at a battlefield you control**, and **107.3.d removes your facedown cards
when you lose control of it**. Your Sprites die at your Beginning Phase, so you
lose the battlefield (190.4.c) and the hidden card goes with it. A hidden card in
a pure-Sprite deck therefore gets **exactly one opponent turn** — which is enough,
since Reaction speed lets you always cash it before it expires, but it means
**Trevor's battlefield is the only place a facedown card persists.** Do not cut
him below 2 without replacing that.

**The double-conquer line, cheaper than it looks:**

```
1. Sprite Fountain  {2}{P1}  = 2 runes  -> ready Sprite #1 in BASE
2. Legend activation now {3}  = 3 runes  -> ready Sprite #2 in BASE
                                            (Fountain's Sprite supplies the discount)
3. Sprite #1 -> battlefield A -> conquer
4. Sprite #2 -> battlefield B -> conquer
                              5 runes, 1 recycled - live from turn 3
```

**Stats:** average **2.30** runes (v5 was 2.58), curve 1:12 / 2:13 / 3:12 / 4:1 /
7:2, **attrition 24 → 20** before the Seals refund up to 2 per turn. Top end is
now just the two Watchers — this is a lean tempo deck with no reset button.

**Not taken: Singularity** over Riptide Rex. It is the better card for the plan —
two targets, no battlefield restriction — but it is *also* {6}{P2}, so it does
nothing about the attrition complaint that removed Rex in the first place.
It is the 1-of to add if the deck wants a top-end sweeper back.

**Sideboard note:** with Rex out of the main deck, the single sideboard copy is
now the *only* copy, not a third. It is still the Vex - Apathetic plan; consider a
second if that matchup stays common.

### v5 changes and why

**In: 3 Discipline, 2 Charm, 2 En Garde, 1 Unchecked Power.** The play-rate
data made these impossible to justify leaving out:

| card | runes | inclusion | avg copies |
|---|---|---|---|
| Defy | 1 | **99.5%** (Calm) | 2.96 |
| Discipline | 2 | **97.5%** (Calm) | 2.95 |
| Charm | 1 | **91.1%** (Calm) | 2.38 |
| En Garde | 1 | 73.8% (Calm) | 2.20 |
| Unchecked Power | 7 | 27.4% (Mind) | 1.39 |

- **Discipline** solves the deck's central problem at Reaction speed for 2
  runes and replaces itself: a 3M Sprite becomes 5M, kills a 3M blocker, and
  *survives at 5 Might to hold*. Trade becomes conquest, card-neutral.
- **Charm** doesn't play the combat game at all — 1 rune, move the blocker to
  their base, walk in with no combat. It also **forces combat**: moving an
  enemy unit from their base onto a battlefield you control makes it Contested
  (450) and causes combat (452), so it is 1-rune removal for anything hiding at
  home — a range this deck otherwise cannot reach.
- **En Garde** was rated 28 in `ratings.md` on the grounds that this deck
  clusters tokens. That stopped being true in v4 (LeBlanc gone, single Sprites
  conquer alone), so the rating had expired. Alone is now the normal case, so
  it is +2 Might for 1 rune.
- **Unchecked Power** at 1 copy is the "I cannot beat this board" button. It
  hits units **at battlefields only** — your base units survive — and your
  board is free tokens while theirs cost cards.

**Out: Soul Shepherd (3), Janna - Savior (2, → sideboard), 1 Petal Pixie,
1 Scuttle Crab, 1 Sprite Call.**

- **Soul Shepherd** cut entirely at the user's call. Its +1 Might breakpoint is
  narrower than it looks: 4-Might Sprites dodge Hextech Ray and Falling Star
  (the Kai'Sa Burn matchup), but against Thousand-Tailed Watcher's "-3 to a
  minimum of 1" a 3M and a 4M Sprite both end at 1. A 5-rune matchup card that
  costs a full turn of rune posture.
- **Janna** is a 3-rune reaction — holding her up *is* the entire live-rune
  budget under the 2-3-runes-live posture, and ten 1-rune answers do her
  defensive work more cheaply. Moved to the sideboard where she belongs as an
  anti-aggro card.

**Kept against my recommendation, correctly (user's calls):**

- **Heart of Dark Ice.** I argued Discipline replaced it. Wrong twice: rule
  **381** means activated abilities only work on *your* turn, so Dark Ice and
  the combat tricks occupy different windows and are complementary, not
  competing; and its activation cost is `Exhaust:` with **no rune component**,
  so after the 3-rune install it gives +3 Might every turn for **zero runes** —
  the one pump that never touches the live-rune budget.
- **Sprite Call.** I proposed cutting it for En Garde. It is Action speed, so
  from hand it can add a ready 3-Might body *during a showdown*, and it is the
  only Sprite source needing no permanent already on board. Cutting it would
  have walked away from the deck's identity for generic efficiency.

**Runes 6/6 → 7 Mind / 5 Calm**: computed 11 Mind and 7 Calm hard pips
(1.6 and 1.4 per rune).

## The three battlefields — selection, re-derived

The original three were picked in v1 by taking the top three raw scores out of
`ratings.md` (Dusk Rose Lab 72, Hall of Legends 66, Emperor's Dais 64), under a
header that read *"one of your three is randomly live (485.5); each must stand
alone."* **That header assumed Duel (Bo1), and it is the wrong default.** In
Match (Bo3) you *choose* which of your three to present each game and the used
ones are burned (486.5), so all three get presented across a match and each is a
deliberate slot, not a lottery ticket. Re-derived below under the Match
assumption.

### Why the deck conquers far more than a normal deck (this drives everything)

**190.4.c: a player with no units at a battlefield loses control of it in the
following cleanup.** This deck's units at a battlefield are usually Temporary
Sprites, and they die at the start of your Beginning Phase — so you lose the
battlefield and have to *retake* it. Where a normal deck conquers a field once
and then holds it for six turns, this deck conquers the same field over and
over. **Conquer-triggered battlefields therefore fire several times a game for
us and roughly once a game for most opponents** (471.2.a). That is a real,
verified asymmetry and it is what makes the two conquer battlefields good here.

### The role assignment

| battlefield | trigger | role | works when |
|---|---|---|---|
| Dusk Rose Lab | your Beginning Phase, unit here | **neutral (game 1)** | always, either seat, ahead or behind |
| Hall of Legends | on conquer | **go-first / proactive closer** | you are ahead on board |
| **Ravenbloom Conservatory** | on defend | **go-second / reactive** | you are behind, or being attacked |

*(v5 ran **Emperor's Dais** in the third slot — a second conquer-trigger, so the
set had no card that was good from behind. Replaced in v6; the analysis that
chose the replacement is kept below.)*

**Dusk Rose Lab — the neutral, blind game-1 pick.** It converts the deck's
built-in liability into a resource: the Sprite is dying regardless, so killing
it for a card is pure profit, every turn, from turn 2. Turn-order independent —
it does not care who is on the play, which is the requirement for the pick you
make before turn order is even determined (rule 115 happens *after* battlefield
setup, 113). Riot's question 2 — *disastrous if they controlled it?* — answers
itself: to use it they would have to kill a real card to draw one card. It is
also control-gated in our favour (190.6.a: the battlefield's controller controls
its ability), and we are the deck that has a body there.

**Hall of Legends — the go-first pick, and the answer to the 8th-point problem.**
Every meta legend's exhaust ability was checked against readying it:
Kai'Sa (add 1 rune for a spell), Diana (1 showdown energy), Azir (a second Sand
Soldier, and only if they played an Equipment), Master Yi and Annie (passives —
readying does literally nothing). Ours plays a **ready 3-Might body**. This is
the clearest question-3 answer in the pool: the same text is worth several times
more to us than to anyone we expect to face. It is go-first because it is
conquer-gated, and going first is what gets you the first body down and the
first conquer.

**Emperor's Dais — kept, but it is the weakest of the three and the set's
structural gap.** What it does for us is genuinely unique: conquer, pay 1,
return the Sprite (a token, so it ceases to exist — 186) and get a **permanent**
2-Might Sand Soldier that stays. That is the deck's only way to turn token tempo
into a body that survives its own Beginning Phase, which is the deck's central
weakness. Two counts against it:

- **Role duplication.** It is the second conquer-trigger. The set has no card
  that is good *from behind*, and the skill is explicit that three picks should
  cover three game shapes.
- **It fails Riot's question 2 against one specific deck.** Azir's legend reads
  "Your Sand Soldiers have [Weaponmaster]" (821 — a play effect that attaches an
  Equipment). Emperor's Dais hands a VEN Azir Equipment player a free Sand
  Soldier that attaches gear on arrival, *and* rebuys one of their ETB units.
  Never present this one against Azir.

### The change, applied in v6: Emperor's Dais → Ravenbloom Conservatory

Ravenbloom won the slot over Black Flame Altar once the deck committed to the
double conquest, because it answers **two** problems at once. Under that plan you
take battlefields on your turn and your Sprites survive through *theirs* — so the
opponent must attack to get them back, and "when you defend here" fires. With
**21 spells in 40 (52.5%)** it is better than a coin flip for a free card every
time they contest you, and cards — not runes — are the binding constraint once
Seals are covering the Power pips.

The Black Flame Altar case, kept because it is still the pick if the deck goes
back to holding:

"Units here with [Temporary] have [Shield]" (+1 Might while defending) is the
most one-sided text in the battlefield pool *for this deck specifically*, because
essentially no opposing deck fields Temporary units — it is close to a blank card
in their hands. It needs no trigger, no conquer, and no energy. What it buys:

- Every Sprite defends at **4 Might**, so it beats the format's 3-Might bodies
  and *survives*. Your free token kills their real card.
- It is what makes **Trevor's battlefield unbreakable** — Trevor (3, 4 defending
  with his own Shield) plus one 4-Might escort Sprite is 8 Might of defence, and
  Trevor holding is where this deck's repeatable points actually come from.
- It is good precisely when you are behind and have nothing left but free
  tokens, which is the go-second requirement.
- Under the Vex - Apathetic lock it is at its best: stunned Sprites still soak
  full lethal damage (423.1.c), and the Altar makes each one cost 4.

Honest cost of the swap: the Altar generates no cards and no points, and Shield
is defenders-only, so it does **not** address the deck's stated failure point
(3-Might Sprites can't profitably attack). It buys survival, not conversion.
Emperor's Dais is the stronger card in a vacuum; Black Flame Altar is the better
third *slot*. In **Bo1 (Duel)** the current three are fine as-is — with a random
selection you want three high-floor standalone picks and role coverage is
meaningless.

### The go-second candidates, ranked (Bo3 — user builds for Match by default)

All four fire while you are being attacked or under pressure, cost nothing, and
compete for zero runes — which matters, because the go-second seat is the one
where you most need your runes live.

**1. Black Flame Altar** — "Units here with [Temporary] have [Shield]."
The only *one-sided* option: no opposing deck fields Temporary units, so it is
close to a blank in their hands. Changes combat math rather than generating
resources — a 4-Might Sprite beats the format's 3-Might bodies and survives.
Best when the problem is "I keep losing the battlefield." Does nothing on
offence (Shield is defenders-only) and draws no cards.

**2. Ravenbloom Conservatory** — "When you defend here, reveal the top card of
your Main Deck. If it's a spell, put it in your hand. Otherwise, recycle it."
The purest go-second card in the pool: it fires *only* when the opponent attacks
you. v5 is **21 spells in 40 = 52.5%**, so it is better than a coin flip to draw
a free card every time they contest you — and it patches the deck's named hole
(draw is thin: Stupefy, Discipline, Scuttle Crab, the Lab). Recycle is
bottom-of-deck, not a discard (416.1), so the miss costs nothing permanent —
but bottoming a Riptide Rex or a Trevor on the turn you needed it is a real
cost 47.5% of the time. Was rated 40 on a *v1* creature-heavy list; that rating
expired when v5 went spell-dense. **→ 68.**

**3. Threshold of the Gray** — "When combat starts here, the attacker and
defender each [Add] {1 energy}."
The highest raw value for this deck and the only one that helps you *retake* a
field. Added energy survives to end of turn (167), and the deck's whole answer
layer is 1-2 energy — Stupefy {1}, Charm {1}{P1}, Discipline {2} — so this is
effectively a free trick in every fight, in either seat, without touching the
live-rune budget. **It fails Riot's question 2 against the worst matchup:** it
hands VEN Kai'Sa Burn free energy for a burn spell every combat, on top of a
legend that already adds runes for spells. Was 30. **→ 64, or 40 in a Kai'Sa
field.**

*(A fourth candidate, **The Dreaming Tree**, was evaluated and then struck: it
is **BANNED** in Constructed as of 2026-07-24. So is **Obelisk of Power**, which
this file previously called "the neutral pick if avoiding all texture." Five of
the ten Constructed bans are battlefields — the full list is `data/banlist.json`
and `python3 cli.py check` now enforces it.)*

**Resolved in v6: Ravenbloom Conservatory.** The Altar fixes the reason you lose
battlefields; Ravenbloom fixes the reason you run out of answers. The double
conquest doesn't try to keep battlefields, so the second problem is the live one.
**Black Flame Altar is the first swap back** if the deck drifts toward holding.

### Battlefield bench (in preference order)

- **Black Flame Altar** — the go-second pick if the deck ever returns to holding.
- **Targon's Peak** — "on conquer, ready 2 runes at the end of this turn." Under
  the rune-posture doctrine this is the best economy battlefield in the pool for
  us: we conquer nearly every turn, and 2 readied runes at end of turn is
  precisely the live-rune budget the deck fights for. Underrated at 55; it is
  the swap for Hall of Legends if the 8th-point line stops mattering.
- **Grove of the God-Willow** — hold → draw 1. Hold triggers fire every turn you
  keep the field, which is more often than conquer triggers for a *normal* deck —
  but not for this one (190.4.c). It gets better as the deck adds permanents.
- **Windswept Hillock** — Ganking. The biggest structural upgrade available
  (it un-breaks the double-conquest line and lets Sprites redeploy), but fully
  symmetric and it hands VEN Kennen Movement their whole deck.
- **Forbidding Waste** — sideboard battlefield: lone defenders get -2 Might,
  which blanks Master Yi's legend entirely. Costs us when we hold with one Sprite.
- **Rockfall Path** — sideboard battlefield: units can't be played here. Hoses
  Annie Ambush and Azir; our tokens go to base anyway.

**Never pick:** Mystic Vortex (taxes Reactions in showdowns here — we are the
most reaction-dependent deck in the room), Sigil of the Storm (forced rune
recycle on every conquer, and we conquer constantly), Vaults of Helia (holding
taxes our own unit plays).

**Banned battlefields (2026-07-24), do not consider:** Aspirant's Climb,
Obelisk of Power, Reaver's Row, The Arena's Greatest, The Dreaming Tree.
Full list in `data/banlist.json`; `cli.py check` enforces it across main deck,
sideboard, battlefields, runes and Legend.

## Critique false-positives (do not "fix" these)

- **Smoke and Mirrors at 2, flagged "run 3".** One Hidden card per battlefield,
  two battlefields in 1v1, and Sprite Call competes for those slots. 2 is right.
- **Charm / En Garde / Heart of Dark Ice flagged as synergy orphans.** All three
  are standalone by design; the tool only finds lexical synergy.

## Sideboard (10, validated; run 0 in Bo1)

- 2 Disarming Rake — gear removal **on a body**, so hand disruption can't strip
  it like a spell. VEN Azir Equipment (16 gear), Kennen.
- 2 Akali, Silent — confirmed in the user's own games: a 6-Might attacker that
  can't be chosen by enemy spells outside combat. Great vs hold and vs removal.
- 2 Janna - Savior — anti-aggro: a reaction-speed body that heals and bounces
  an attacker home mid-combat.
- 2 Crescent Strike — 4 damage plus 1 splash at Action speed; cheapest real
  creature removal in the identity.
- 1 Riptide Rex — **the only copy since v6 cut it from the main deck.** The
  Vex-Apathetic dial; user's play data says Rex was what beat the Diana/Vex deck.
- 1 Turn to Dust — cheap extra gear hate.

**Boarding plans** (no silver bullets; keep a going-first and going-second plan):

- **vs VEN Kai'Sa Burn:** in 2 Akali, 2 Crescent Strike; out 2 Smoke and
  Mirrors, 1 Petal Pixie, 1 En Garde. Make threats free (Sprites) or
  unanswerable (Akali).
- **vs VEN Azir Equipment:** in 2 Disarming Rake, 1 Turn to Dust; out 2 Smoke
  and Mirrors, 1 Unchecked Power.
- **vs aggro (VEN Master Yi and similar):** in 2 Janna, 2 Crescent Strike; out
  2 Thousand-Tailed Watcher (too slow), 1 Unchecked Power, 1 Charm.
- **vs Vex-Apathetic / Diana (user play data):** in 1 Riptide Rex, 2 Crescent
  Strike; out 2 Scuttle Crab, 1 En Garde. Rex kills Vex on entry.

## Open questions

- **Legend relevance is trending down: 21 → 15 → 11 of 40 copies** across
  v2/v4/v5. Still above the ~8 threshold, but every revision has traded
  sprite-generation for interaction. If it drops below 8, the Legend has been
  outgrown and the deck should be rebuilt around what it is actually doing.
- ~~Sprite Call at 2~~ — **resolved in v6**: back to 3. The double conquest
  needs ready Sprites in base, and Sprite Call from hand is one of only three
  sources (with the Legend and Sprite Fountain).
- **The 8th point — now the deck's declared plan, and it needs a judge check.**
  Re-read 2026-08-05: **469.1 makes the Conquer itself the Score**, and 471.1
  says the player "Gains **up to one** Point" — so at 7 you conquer A (Score A,
  draw a card instead of the point), then conquer B (Score B; every battlefield
  is now Scored, so the Final Point lands and you win). An earlier note here
  called this unsafe; that was too pessimistic. It is still the one ruling worth
  confirming with a judge before an event, because the whole plan rests on it.
  Requires **two ready Sprites in your BASE** — a Standard Move can't go
  Battlefield → Battlefield without Ganking (144.4). See `patterns.md`.
- **Consistency of two 1-of Seals.** A 1-of is seen by turn 5 about 20% of the
  time. If the Seals feel absent, consolidate to 2x Seal of Insight — Mind
  carries 12 of the 20 hard pips against Calm's 8.
- **Rune attrition still prints as 24**, but the tool cannot see the Seals
  repaying their own pip and then producing one free per turn. Real figure is
  ~22 one-time, minus 2 per turn once both Seals are down. Fixing `analyze.py`
  to model Add-abilities is a real to-do.
- **Riptide Rex at 2 is on notice.** {6}{P2} recycles 2 runes and you channel 2
  per turn, so it costs a full turn of channelling on top of its cast. The
  Watcher does the double-conquer job better for 1 pip. Rex stays for now as the
  Vex - Apathetic answer; cut it to 1 if the rune bleed still bites.
- **Ahri - Alluring** ("When I hold, score 1 point") still needs a judge check
  against rule 470 before being built around.
- **Charm's forced combat** — worth a judge check on who counts as attacker vs
  defender when your effect moves *their* unit into your battlefield.
- Battlefield bench: Black Flame Altar (Shield for Temporary units),
  Windswept Hillock (Ganking — the biggest structural upgrade available, but
  symmetric and it upgrades VEN Kennen Movement), Targon's Peak.
- High-inclusion Calm cards never seriously tried: **Zhonya's Hourglass
  (64.9%)**, **Not So Fast (63.3%)**. Zhonya's turns the death of Trevor or a
  bomb into a recall.

### v4 changes and why (retained)

Cut the **Heimerdinger + Keeper of Masks** engine entirely — they were a
package and both halves were weaker than v1-v3 assumed:

- The Legend's discount **never carries between turns**: Temporary units die in
  your Beginning Step (315.2.a), *before* your Main Phase, so you start every
  turn with zero. Two activations really cost 4+3=7.
- Keeper's three bodies enter **exhausted** (185.2.d) and die at your next
  Beginning Phase — they never attack, conquer or hold. They block once.
- The Legend gets discounted for **free** by sequencing: move Fae Fawn first
  (her move costs nothing and leaves a Temporary Sprite).

Cut **LeBlanc - Everywhere At Once**: two of the four Sprite sources
structurally cannot feed her — Sprite Fountain forces its Sprite **to your
base**, and Fae Fawn's spawns where she moved *from*. Sprites parked under her
are anchored, since moving one off her battlefield means it dies next turn.
