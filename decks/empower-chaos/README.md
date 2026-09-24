# Empower / Chaos — three builds

Goal set by the user (2026-09-10): **cheat expensive Empower costs as often as
possible.** Tornado Warrior is the seed, not the whole plan — Sanction, Profiteer,
flicker effects and bounce-to-rehide all count.

Current versions: `calm-chaos-v1.txt`, `mind-chaos-v1.txt`, `body-chaos-v1.txt`.
All three `check` LEGAL. None has been played yet.

---

## The rule that governs every card choice here

**441.1.b — an Empowered object cannot be Empowered.** So a "When I become
Empowered" trigger fires *once per game* unless something removes the status.
Tornado Warrior and Sanction both carry "Disempower it at end of turn", and that
reset is what turns a one-shot into a per-turn engine.

**The corollary, which decides what is and isn't a legal target** (user caught
this on 2026-09-10, and it invalidated two cards already in the Calm build):

| Payoff shape | Free Empower? | Why |
|---|---|---|
| `When I become [Empowered], <effect>` | **YES** | Fires on the transition; the effect already resolved and does not un-happen |
| `[Empowered][>] I have +X Might`, used on YOUR turn | Partial | A one-turn combat trick, nothing more |
| `[Empowered][>] <Deflect / Shield / defensive>` | **NO** | You need it on the OPPONENT'S turn; end-of-turn disempower strips it first |
| `I can be [Empowered] up to three times` (Kayle, Justified) | **NO** | 442.1 removes the status; it never accumulates. Kayle wants HARD-CAST Empowers |

Cut from the Calm build for the third row: Serene Ascetic, Frostcoat Mother.
Never considered for the fourth: Kayle, Justified.

## Every free-Empower source in the game

Verified by scanning all 929 cards, not by grep on "Empower".

| Card | Domain | Notes |
|---|---|---|
| **Tornado Warrior** `{3}` 3M | Chaos | Must be played **from face down**. Empowers anything *here*. Resets EOT |
| **Sanction** `{3}{P1}` | Calm | **[Reaction]**, from hand, no Hidden needed. BOTH modes are a free Empower |
| **Profiteer** `{4}` 4M | Body | Transfers: disempower something → empower something else. Needs a prior Empower |
| **Hextech Formula** `{2}` gear | Mind | Repeatable free Empower, **gear only** |
| **Wild Claw** `{7}{P1}` | Body | Cheat a unit into play AND Empower it |

Legends that self-empower: Mel - Soul's Reflection, Ambessa - Matriarch of War,
Yordle Kennen, Zed.

## The three re-triggerable payoffs are all Chaos

This is why the engine core is identical in all three builds.

- **Kharox** `{6}` 5M — Empower cost `{6}{Chaos}{Chaos}`. Opponent **Burns 3**, then
  you play a unit **from their trash, free**. The biggest cost cheated in the format.
- **Tail-Cloaked Matriarch** `{4}` 4M — Empower `{2}{Chaos}`. Play a unit from **your**
  trash (≤`{3}`/`{P1}`) free.
- **Mel, Defiant Soul** `{5}` 4M — Empower cost is **"Discard a spell."** **Banish** an
  enemy unit ≤3 Might. Banish beats trash. Also a legal Chosen Champion for Mel.

---

## Build 1 — Calm/Chaos (recommended): cheat the biggest costs

`calm-chaos-v1.txt` · Irelia - Blade Dancer / Irelia, Fervent · 7 Calm / 5 Chaos
avg 2.98 runes · **attrition 8** (lowest of the three) · curve 1:6 2:11 3:14 4:4 5:1 6:2 8:2

**Plan:** six free-Empower spells (3 Tornado Warrior + 3 Sanction) cheat an `{8}`
Empower onto Nasus, then score two points per scoring event behind Deflect 2.

Why it's first: it has the most free Empowers **for units** (6, vs 3 in the others),
and Calm owns the two most expensive targets in the game — **Nasus, Ascended**
(Empower `{8}`) and **Steel Paws** (`{1}` for a 0-Might body, Empower `{7}` → +7 Might).
Sanction is the single best support card in the archetype because it needs **no
facedown slot at all**, which is the engine's hard bottleneck.

**The centrepiece combo — Reckoner's Arena + Nasus + Sanction:**
Nasus Empowered reads "When I conquer, you score 1 point." Reckoner's Arena reads
"When you **hold** here, activate the conquer effects of units here." Per rules-fact 9
a persistent body like Nasus **holds** every turn and conquers almost never — so the
Arena converts his once-only conquer trigger into a per-turn hold trigger.
Sanction is a **[Reaction]**, so you empower Nasus *during your Beginning Phase in
response to the hold trigger*, after the previous turn's disempower has already
happened. See `patterns.md` — the sequencing is exact and easy to get wrong.

## Build 2 — Mind/Chaos: the flicker loop

`mind-chaos-v1.txt` · Mel - Soul's Reflection / **Mel, Defiant Soul** · 8 Mind / 4 Chaos
avg 2.92 runes · attrition 18 · curve 1:5 2:11 3:13 4:6 5:3 6:2

**Plan:** Empower Mel, Defiant Soul every turn to banish an enemy unit; the Legend
turns each Empower into a −2 Might that makes the *next* unit banishable.

The tightest build of the three because **the Legend and the Chosen Champion are
both Empower cards**. Legend: "when you empower something else, empower me…
Disempower me, Exhaust: give a unit −2 Might." Champion: "when I become Empowered,
banish an enemy unit ≤3 Might." The −2 drags a 5-Might unit into banish range, and
**Mel, Newly Awakened** in the main deck adds another −1 on top (6-Might units die).

Mind also owns the flicker the user asked about — **Temporal Breach** `{2}{P1}` and
**Portal Rescue** `{3}{P1}` banish-and-replay a unit **ignoring its cost**, which both
resets the Empowered status *and* re-buys the body. And Mind has the cheapest
returns for re-hiding Tornado Warrior: **Gust** `{1}`, **Retreat** `{1}`.

Highest attrition of the three (18) — 15 Mind pips forced the 8/4 skew.

## Build 3 — Body/Chaos: Empowered beatdown

`body-chaos-v1.txt` · Miss Fortune - Bounty Hunter / Miss Fortune - Captain · 6/6
avg 3.48 runes · attrition 7 · curve 1:3 2:8 3:7 4:13 5:7 6:2

**Plan:** hard-cast a *cheap* Empower, then use **Profiteer** to move it onto an
expensive one. Profiteer converts Legion Marauder's `{1}` Empower into Kharox's
`{6}{Chaos}{Chaos}` for the price of a 4-Might body.

Body has the most Empower cards (18 in pool) and by far the biggest bodies, but the
weakest *free* Empower count — Profiteer is a transfer, so it needs a prior Empower
to move. **Renekton, Brute** self-empowers permanently once his Might hits 10
(Guttural Roar + his own `{1}`: +1 Might), and that Empower has no disempower
attached — the one card here that genuinely accumulates.

Clunkiest curve of the three (13 cards at 4 runes, avg 3.48).

---

## Battlefield selection

Bans checked first (`data/banlist.json`, 2026-07-24): **5 of the 10 Constructed bans
are battlefields.** None of the picks below is on it.

**All three builds share Risen Altar and Seat of Power.**

- **Risen Altar** — *neutral, game-1 presentation.* "[Empower] costs of your units
  here cost `{1 energy}` or `{any rune}` less." Question 2 (*what if the opponent has
  it?*): near-blank. It only reads Empower costs, and Empower is a narrow mechanic —
  most decks in the field run zero. This is the strongest form of Riot's question 3:
  a text the opponent structurally cannot use. It also patches the archetype's real
  weakness, which is that the hard-cast Empower costs are the expensive fallback when
  the free Empowers don't show up.
- **Seat of Power** — *go-first.* "When you conquer here, draw 1 for each other
  battlefield you or allies control." Conquer the other battlefield first, then this
  one the same turn, for a real draw. Question 2: genuinely dangerous in an
  opponent's hands, which is why it is the on-the-play pick only — you want to be the
  one setting the pace.

Third slot, per build:

- **Calm/Chaos → Reckoner's Arena** *(go-second / grind).* "When you hold here,
  activate the conquer effects of units here." Built for Nasus, above. Question 2:
  bad for you against any deck with strong conquer triggers of its own — check the
  opponent's list before presenting.
- **Mind/Chaos → Minefield** *(go-first).* "When you conquer here, put the top 2
  cards of your Main Deck into your trash." Self-mill is a **cost** for almost every
  other deck and **fuel** for yours — Tail-Cloaked Matriarch plays a unit out of your
  trash. Question 3 in its cleanest form.
- **Body/Chaos → Sunken Temple** *(go-first).* "When you conquer here with one or
  more [Mighty] units, you may pay `{1}` to draw 1." **707/708: a unit is Mighty at
  5+ Might.** Body is the only one of the three builds that reliably fields those —
  Dame the Despoiler, Miss Fortune - Captain, Kharox, Renekton.

**Bench** (promote if): *Hall of Legends* — if a build ever leans on repeated Legend
activations. *Protective Sands* — if the curve drops. *Sigil of the Storm* — if
attrition becomes the losing stat (Mind/Chaos is the candidate at 18).

**Never-picks for these decks:** *Heisho, Shell of the World* ("players ignore
[Deflect] while paying for spells and abilities choosing something here") — the Calm
build is built on Deflect bodies (Steel Paws, Allay, Navori Scout, Nasus at Deflect 2)
and this blanks all of them. *Monastery of Hirana* — pays off buffs; none of the three
builds runs a buff source. *Emperor's Dais* — the bounce looks like re-hide enablement
but it only reaches a unit **here**, and it costs you the conquer body.

## Critique false positives — do not "fix" these

- **body-chaos: "Legend interacts with nothing (0 of 40 copies)."** Miss Fortune -
  Bounty Hunter grants **Ganking**, which is the double-conquer enabler required by
  rules-fact 7 (the 8th point by Conquer needs every battlefield scored that turn, and
  144.4 forbids battlefield→battlefield movement without it). The matcher cannot see
  a keyword grant.
- **"Key piece at 2 copies: Kharox / Nasus, Ascended."** Both are 6-8 rune finishers.
  2 is deliberate; 3 would flood the top of the curve.

## Open questions — decide these with reps, not theory

1. **Does Nasus's extra point dodge the Final Point rule?** 471.1.a.1 exempts "points
   Gained from sources that are not Conquer" from the 471.1.b restrictions. Nasus's
   point is granted by his own ability, triggered *by* a conquer. Reading favours
   "yes, it can be your 8th point without scoring every battlefield" — but the
   wording is genuinely ambiguous and this is a **judge question**. Do not build the
   last point around it until confirmed.
2. **Is one free Empower per turn worth the setup?** The engine costs a card, a rune
   to hide, and a whole turn of delay. Untested.
3. **Does 442.1 Disempower strip ONE instance or ALL** of a multi-stacked Empowered
   status? Irrelevant to these three lists (none runs Kayle) but it decides whether
   Kayle is ever buildable.
4. Sideboards are not written yet — all three are 0-card, which is legal. They need
   building before any Bo3 event.

## 2026-09-10 — official errata applied pool-wide

`data/errata.json` now overlays Riot's official errata onto the card pool on every load
(see the memory note `riftbound-errata-overlay`). 51 of 63 errata'd cards had superseded
text in `cards.json`. Three land on decks in this folder:

- **Teemo - Strategist** — **MAJOR NERF.** The *"or I'm played from [Hidden]"* trigger is
  **gone**; he now fires only *"When I defend."* `teemo-hidden-v1.txt` was built on that
  clause and `teemo-hidden-explanations.md` argues for it explicitly. That deck's core
  premise no longer holds and it needs a rebuild, not a patch.
- **Pack of Wonders** — now reads *"facedown card"*, not *"[Hidden] card"*. A small
  **buff**: it bounces anything hidden at a battlefield regardless of the keyword.
- **Tornado Warrior / Sanction / Matriarch / Kharox / Nasus** — unchanged. The
  empower-chaos engine is unaffected.

## sanction-stack-v1 — 2026-09-10 change

- **−2 Mournful Witness, +2 Treasure Trove.** Trove pairs with Pack of Wonders (bounce to
  hand → `draw 1 + channel 1 rune`, repeatable for 2 energy) and is the deck's only ramp,
  which is what pays for the Fizz package's attrition. The Witness was a fine 2-drop
  attached to nothing, and a trap for the Tornado Warrior trigger (a `[Empowered][>]`
  static loses the buff to TW's end-of-turn disempower).
- **−3 Allay, Eager Admirer, +3 Fizz - Trickster.** Fizz is a legal Tail-Cloaked Matriarch
  target at the exact ceiling of both clauses (`{3}` energy, `{P1}` power), so a
  Reaction-speed Empower on Matriarch chains into Fizz into **Ride The Wind from the
  trash — on the opponent's turn**, laundering an [Action] through an instructed play
  (806.1.b). That is the deck's cleanest way to make Nasus actually conquer. Allay's
  Deflect is a 1-rune tax that only touches effects which *choose*.
- **Rune base 7/5 → 6/6 Calm/Chaos.** Fizz added 3 Chaos pips, taking Chaos to 8 pips on
  5 runes (1.6/rune). Calm only ever needs one pip at a time.
- Curve is unchanged: `1:6, 2:13, 3:14, 4:3, 6:2, 8:2`. Attrition 10 → 13, which is what
  Treasure Trove exists to offset.
