# Lillia - Fae Fawn — full pool evaluation (clean-room build, 2026-07-31)

> ## CORRECTIONS — read before trusting any score below (added 2026-08-04)
>
> The ratings below were written for the **v1 plan** (cluster Sprites around
> LeBlanc / Petal Pixie and hold with them) and under a **wrong rune model**
> (energy + power instead of `max(energy, power)`). Both changed. The scores
> that moved most, with the reason:
>
> | card | was | now | why it moved |
> |---|---|---|---|
> | Defy | 68 | **90** | 99.5% inclusion, 2.96 copies — the most-played Calm card. 1 rune, not 2. |
> | Discipline | 65 | **88** | 97.5% / 2.95. Turns a trade into a conquest at Reaction speed AND cantrips. |
> | Charm | 62 | **85** | 91.1% / 2.38. Sidesteps combat entirely; also forces combat by dragging base-sitters out (450/452) — the deck's only reach into a base. |
> | En Garde | 28 | **70** | Rated for a clustering plan that no longer exists. Single Sprites conquer alone now, so it is +2 for 1 rune. |
> | Heart of Dark Ice | 55 | **74** | Activation costs **no runes** (only Exhaust), so it pumps without touching the live-rune budget; rule 381 makes it a your-turn tool, complementary to tricks rather than competing. |
> | Scuttle Crab | 58 | **72** | 76.3% / 2.7 copies in Calm. |
> | Unchecked Power | 42 | **60** | Hits units *at battlefields only* — your base survives. 27.4% / 1.39 copies: a real 1-of. |
> | Zilean - Time Mage | 70 | **76** | 5 runes (turn 3), not 6; doubling is FREE where Heimerdinger charged 4 runes per extra Sprite; 5 Might survives the cheap-removal band. |
> | Sprite Call | 80 | **74** | Still good, but its headline Hidden-save mode existed to preserve a *hold*, which this deck no longer does. |
> | Keeper of Masks | 64 | **38** | Its three bodies enter **exhausted** and die at your next Beginning Phase — they only ever block once. Standalone it is a card spent to save one rune. |
> | Heimerdinger - Inventor | 78 | **52** | Enters exhausted (dead turn), 3 Might, and each copied activation still costs full price. |
> | Sprite Mother | 74 | **56** | 5 runes for a body that enters exhausted. |
> | LeBlanc - Everywhere At Once | 84 | **58** | Sprite Fountain forces its Sprite **to base** and Fae Fawn's spawns where she *left*, so two of four Sprite sources cannot feed her; Sprites under her are anchored forever. |
> | Soul Shepherd | 66 | **58** | The +1 breakpoint is matchup-specific (dodges 3-damage burn; useless against "-3 to a minimum of 1"). A 5-rune matchup card. |
> | Trevor Snoozebottom | 76 | **74** | Still strong, but his Sprite is created "here" and can never leave (144.4) — an anchor, not a two-point engine. |
>
> ### Battlefield corrections (added 2026-08-05)
>
> The battlefield section below was written under a **fourth** systematic error:
> its header assumed **Duel/Bo1** ("one of your three is randomly live"), so
> every battlefield was scored as a standalone lottery ticket. In **Match/Bo3**
> you *choose* one per game and burn it (486.5) — all three are presented, each
> is a deliberate slot, and the set needs three *roles*, not three high scores.
> Re-scored under the Match assumption:
>
> | battlefield | was | now | why it moved |
> |---|---|---|---|
> | Black Flame Altar | 62 | **75** | Near-zero value to opponents (nobody else fields Temporary), no trigger, no cost. Makes every Sprite a 4-Might defender, which is what makes Trevor's field unbreakable — and it is the only *one-sided* go-second pick. |
> | Ravenbloom Conservatory | 40 | **68** | Rated against a **v1** creature-heavy list. v5 is 21 spells in 40 (**52.5%**), so "when you defend here" is better than a coin flip to draw a free card — and it is the only battlefield that fires *only* when you're under attack. Recycle is bottom-of-deck, not a discard (416.1). |
> | Threshold of the Gray | 30 | **64** | Added energy survives to end of turn (167), and the answer layer is Stupefy {1} / En Garde {1} / Discipline {2} — so it is a free trick in every combat without touching the live-rune budget. Drop to **40 in a Kai'Sa field**: it funds their burn too. |
> | The Dreaming Tree | 38 | **BANNED** | Would have been ~55 for v5. Banned in Constructed 2026-07-24. |
> | Obelisk of Power | 50 | **BANNED** | Banned in Constructed 2026-07-24. Previously described here as "the neutral pick if avoiding all texture" — do not use it. |
> | Reaver's Row | 30 | **BANNED** | Banned in Constructed 2026-07-24. |
>
> **The banlist is bigger than this file assumed.** It is **10 cards**, five of
> them battlefields — not "three, of which two are battlefields." Full list in
> `data/banlist.json`; `python3 cli.py check` now enforces it across main deck,
> sideboard, battlefields, runes and Legend. Battlefields are over-represented
> on it, so **check the banlist before rating battlefields, not after.**
> | Targon's Peak | 55 | **70** | Conquer → ready 2 runes at end of turn. Under the tapping-out doctrine this is the deck's live-rune budget handed to it for free, and 190.4.c means we conquer constantly. |
> | Emperor's Dais | 64 | **58** | Still the only permanence the deck has, but it is a second conquer-trigger (role duplication) and it hands VEN Azir a free Sand Soldier with [Weaponmaster] (821) plus an ETB rebuy — a question-2 failure. |
> | Grove of the God-Willow | 58 | **50** | Hold triggers fire *less* often than conquer triggers for this deck specifically: 190.4.c means our Sprites' deaths cost us control every turn. The usual "holds beat conquers" heuristic is inverted here. |
> | Dusk Rose Lab | 72 | **72** | Unchanged, and confirmed as the correct blind game-1 pick: turn-order independent, and 190.6.a gates its ability to whoever has a body there. |
> | Hall of Legends | 66 | **66** | Unchanged. Checked against every meta legend's exhaust ability — Yi and Annie are passives (readying does nothing), Kai'Sa and Diana get one resource. Ours gets a ready 3-Might body. |
>
> **The rule that drives all of it:** 190.4.c — a player with no units at a
> battlefield loses control in the following cleanup. Our Temporary bodies die
> every Beginning Phase, so we lose fields and retake them constantly. Conquer
> triggers are worth *more* to this deck than to a normal one, hold triggers
> worth *less*. See `patterns.md`.
>
> **The three systematic errors that caused most of this**, all now in the
> skill's rules-facts section: (1) runes to cast is `max(energy, power)`, so
> every Power card was rated a turn slower than it is; (2) tokens enter
> exhausted and Temporary ones die before your Main Phase, so "makes bodies"
> was over-credited and "makes *ready* bodies in base" under-credited;
> (3) tapping out costs you the opponent's turn, so cheap interaction is worth
> far more, and cards that enter exhausted are worth less, than raw rate says.
>
> Play-rate figures come from `data/staples/` (rune-normalised inclusion, ≥20%
> threshold, current format only). Absence from that list means <20% inclusion,
> not "bad" — it is domain-wide across all Legends, not Lillia-specific.


Legend: **Lillia - Bashful Bloom** (Calm+Mind) — `{4}, Exhaust: play a READY 3M
Sprite token with [Temporary]; costs {1} less per friendly unit with [Temporary].`
Chosen Champion: **Lillia - Fae Fawn** (Mind, E3 M3, Accelerate) — `When I move
from a location, play a 3M Sprite token with [Temporary] there.`

Built without reading any existing Lillia deck in this repo (user instruction).
Meta layer ON (data/archetypes.md, as_of 2026-07-28 — the four VEN entries are
the current signal). Rules facts verified against RUP4 (2026-07-16) extraction.

## Rules facts every rating below leans on

- **Temporary units die at the start of YOUR Beginning Phase, BEFORE scoring**
  (816.1.b, 315.2.a-b). A Sprite alone can NEVER hold for a point — unless the
  death trigger is responded to (Hidden Sprite Call replacement — see
  `reference/riftbound_temporary_interactions.txt`) or switched off
  (**LeBlanc - Everywhere At Once**). Sprites DO hold the fort through the
  opponent's whole turn, defend (even exhausted — defender designation is
  presence-based, 464.2.c.3), and conquer just fine.
- **Ready vs exhausted**: tokens enter exhausted by default (185.2.d). The
  Legend's, Sprite Call's, Sprite Fountain's, Sprite Burst's and Trevor's
  Sprites are printed READY — those conquer the turn they appear. Fae Fawn's
  move-spawn is NOT ready — it is a blocker/holder, not an attacker.
- **Units are played to base OR a battlefield you control** (355.2.a). Ready
  Sprites must MOVE to conquer a new battlefield; they can be played straight
  onto a held one to reinforce.
- **Standard move cannot go battlefield→battlefield** — that needs [Ganking]
  (810) or an effect. Fae Fawn hopping BF→BF (leaving a Sprite holding the old
  one) requires Windswept Hillock or similar.
- Legend discount counts friendly **units** with Temporary — Sprite Fountain
  (gear) does not feed it; Keeper of Masks + its two Reflections feed it 3.
- 1v1: Victory Score 8; each player brings 3 battlefields, ONE random is used
  (485.4-485.5) — every battlefield slot must stand alone.

**The plan in one sentence:** print free ready Sprites every turn (Legend +
Heimerdinger + Sprite spells), conquer with them, make the token stream
permanent where it matters (LeBlanc, Emperor's Dais) and let token payoffs
(Petal Pixie, Soul Shepherd, Protector of Dreams) turn disposable bodies into
board dominance, with reaction-speed interaction backing the showdowns.

Scale: 85+ core · 70-84 strong · 55-69 conditional (the band that matters) ·
35-54 fringe · <35 unplayable here.

---

## Gear (36)

- **Seal of Focus — 30.** Rune fixing for Calm Power; this deck's hard Calm pips are near zero. A card spent smoothing a problem the rune base already solves.
- **Seal of Insight — 35.** Same card for Mind. We do have Mind pips (Sprite Mother, Heimerdinger, Zilean) but an 8/4 rune skew covers them without spending cards.
- **Chemtech Cask — 40.** We do play spells on opponents' turns (Lullaby, flipped Hidden cards), but a Gold trickle is a slow payoff for a card and a permission it needs every turn.
- **Cloth Armor — 25.** Vanilla equipment; no Weaponmaster/equip payoffs in this deck.
- **Doran's Shield — 22.** Same.
- **Experimental Hexplate — 22.** Same.
- **Orb of Regret — 38.** Free repeatable -1M each turn is real in Sprite-mirror math (3M vs 3M), but -1 once a turn is too small to spend a deck slot on.
- **Poro Snax — 45.** Draw 1 now, draw 1 later for 1E+P1 total investment — honest value, but Calm P1 and it never affects the board.
- **Soul Sword — 22.** Vanilla equipment.
- **Brutalizer — 22.** Vanilla equipment.
- **Forgotten Signpost — 58.** The specific line: exhaust a doomed Sprite at a battlefield + exhaust Signpost → MOVE Fae Fawn there without using her standard move — she spawns a Sprite at her origin, every single turn, for free. An extra Sprite per turn from a 2-cost gear. Costs: needs two units positioned right, does nothing turn it lands, and Fae Fawn must be alive. Worth testing in a later version; loses to the simpler "just run more token cards" v1 logic.
- **Frigid Jewel — 42.** We draw twice on many turns (Stupefy/Meditation/Lab), but +2M once a turn from a gear that had to be drawn and paid for is filler.
- **Garbage Grabber — 45.** Repeatable draw at 1E/turn — but its food is 3 trash cards per activation and this deck fills its trash slowly (tokens aren't cards).
- **Guardian Angel — 22.** Vanilla equipment.
- **Hand Hammer — 22.** Vanilla equipment.
- **Hextech Formula — 20.** No Empower-gear payoffs here.
- **Honeyfruit — 45.** A rune's worth of Power per turn from turn 3. It pays Lullaby/Sprite Mother pips, but we are energy-hungry, not power-hungry — the Legend eats {4} energy, and Honeyfruit doesn't feed that until Level 6 we'll never reach.
- **Mask of Foresight — 25.** Alone-payoff in a deck that exists to go wide.
- **Mushroom Pouch — 58.** With 8 Hidden cards (Sprite Call, Smoke and Mirrors, Keeper of Masks) this draws every turn you keep a card facedown. The named tension: the Pouch pays you NOT to flip the trick, and the Sprite Call flip is often the play. Best in a heavier-Hidden version; competes with Meditation for the draw slot.
- **Spirit's Refuge — 50.** Deflect on buffed friendlies taxes Kai'Sa Burn's targeted removal (the deck most likely to shoot Petal Pixie/LeBlanc), but only the one buffed unit is protected without more buff sources. Calm P1.
- **Sprite Fountain — 72.** 2E+P1 → a ready Sprite now AND (via its own Temporary death + Deathknell) another ready Sprite next turn — the second one spawns after the Temporary check so it survives a full turn cycle. Two conquest-capable bodies from one gear the opponent's unit removal cannot touch. That gear-resilience matters specifically vs Kai'Sa Burn, which kills every unit we play but has little gear hate. Doesn't feed the Legend discount (gear, not unit). First flex swap into the maindeck.
- **Sumpworks Map — 40.** Draws when the opponent scores, dies to its own Temporary after ~1-2 triggers. Cute, low impact.
- **Zhonya's Hourglass — 62.** Hidden (= reaction-speed) death-replacement: saves Fae Fawn or a payoff from removal or a lost combat for 2E, at the cost of recalling it exhausted. The named spot: hide it turn 2 at your held battlefield; Kai'Sa's Singularity or a losing showdown becomes a recall instead of a death. Competes with Lullaby/Twilight Shroud in the protection role; loses points because our units are mostly free tokens not worth saving.
- **Energy Conduit — 44.** +1 energy per turn starting next turn, for a card and 3E — the Legend loves energy but this repays too slowly (break-even turn 3 after landing).
- **Heart of Dark Ice — 55.** Free +3M every turn once installed. The named spot: parked at home, it turns one defending 3M Sprite into 6M every combat — the opponent can never math a battlefield assault cleanly. Costs Calm P1 and a proactive turn-2 slot that usually belongs to bodies.
- **Hextech Anomaly — 30.** Converts Power (recycling runes — shrinking your rune board) into energy. We can't afford the rune attrition.
- **Questionable Tome — 35.** Draw 1 every other turn with exhaust gymnastics; too slow.
- **Solari Shrine — 32.** We stun occasionally but rarely kill the stunned unit the same window.
- **Sterak's Gage — 25.** Equipment, P2 Calm.
- **Svellsongur — 60.** The named line: attach to Fae Fawn → the Equipment's effect text copies her text → her move-trigger exists twice → every move spawns TWO Sprites. Also doubles Trevor's hold-Sprite. Real doubling, but the full bill is 3E+P1 + equip (1E + Calm rune) on a 3M unit that every opponent already wants dead — a two-card, ~6-resource setup that folds to one removal spell. Deliberately excluded from v1; the fun version of this deck runs it.
- **Temporal Portal — 48.** 1 rune/turn to double a spell: Sprite Burst → 4 Sprites is the dream, Stupefy doubling is the reality. Needs the deck to hold spells back; ours wants energy for the Legend.
- **The Zero Drive — 20.** No banish engine.
- **World Atlas — 22.** Vanilla equipment.
- **Gutter Palace — 30.** "Exactly 4 in hand and exactly 4 at battlefields" is nearly uncontrollable when your board dies every Beginning Phase by design.
- **Helm of Suppression — 42.** A real tax vs Kai'Sa Burn/Lux-style spell decks, but 4E+P1 of non-board in an energy-tight deck.
- **Bottled Constellation — 55.** The named spot: grindy board stalls (Mageseeker Warden locks, Tianna, decks that just won't let tokens conquer) — kill 3 doomed Sprites at Main Phase start, score 1, every turn, no combat required. The Legend + Fae Fawn feed it for free. Costs: 10E+P2 (turn 5-6 with the Legend idle a turn), wins slowly, and is a dead card in every fast game. One-of finisher material for a control meta, not for v1.

## Spells (66)

- **Bellows Breath — 45.** Repeatable 1-damage spray; kills Birds/Recruits, not 2M Sand Soldiers in one go. Kai'Sa does this better than we ever will; wrong deck for it.
- **Charm — 62.** 1E+P1: yank the lone blocker off a battlefield and a ready Sprite conquers behind it, or pull a key defender out before your attack. The catch that keeps it from 70+: NO speed keyword — Neutral only, sorcery speed, never in showdowns. Pure proactive tempo. Competes with Skyward Strike (same effect +2E, stun rider we can't level).
- **Combat Experience — 30.** +1M without an XP engine.
- **Crumbling Sands — 45.** Counter-if-they-double-spelled: live vs Kai'Sa Burn strings and Diana, dead vs curve-out decks. Sideboard-shaped.
- **Decree of Focus — 45.** Anti-Fury hoser: +4M vs Kai'Sa Burn (Fury+Mind) and Annie. Blank elsewhere — sideboard.
- **Decree of Insight — 45.** Anti-Body hoser: -5M kills Master Yi's Rengar mid-combat, ignores Deflect. Blank vs half the field — sideboard.
- **Defy — 68.** 1E+P1 counter for ≤4E/≤1P spells: hits Punch First, Hextech Ray, Falling Star, Sabotage, Arise!, most of the field's cheap interaction. The premium cheap answer after Lullaby's 3 slots are spent. Calm P1 is nearly our only hard Calm cost — running it is what keeps 4 Calm runes honest.
- **En Garde — 28.** Alone-payoff; we go wide.
- **Friendship — 15.** No menagerie tags.
- **Mesmerize — 52.** Modal: save Fae Fawn from removal (rebuying her cost hurts) or -2M a combat. Flexible but half-strength in both modes.
- **Retreat — 50.** Save-your-champion + channel a rune (real rune ramp). The named spot: Fae Fawn about to eat Singularity → 1E saves her AND banks a rune; replay + Accelerate later. Costs tempo every time you use it.
- **Stupefy — 75.** 1E reaction: -1M and DRAW. In a format of 2-3M bodies fighting over battlefields, -1M at instant speed flips combats, and it cantrips. The glue interaction of the deck; never bad, always castable off the Legend's leftovers.
- **Twilight Shroud — 60.** 1E: untargetable + [Flow 2] rebuy. The named spot: protect Petal Pixie/LeBlanc the turn they matter against Kai'Sa's point removal — twice per copy thanks to Flow. Costs: sorcery-ish (no speed keyword — Neutral), so it protects proactively, not reactively.
- **Block — 52.** Shield 3 + Tank from Hidden at reaction speed makes a defending Sprite a 6M wall that must be hit first. From hand it's only Action speed. Real trick, but our Hidden slots are contested by Sprite Call.
- **Convergent Mutation — 40.** Copy a big friendly's Might onto a token — needs the big friendly we don't reliably have.
- **Desert's Call — 35.** Off-plan tokens; Sprites are better and free.
- **Discipline — 65.** +2M and draw at reaction speed. Same argument as Stupefy from the other side; the second-best glue trick. Calm-printed but zero Power — castable off any runes.
- **Double Trouble — 48.** Digs for payoff units (LeBlanc/Pixie); misses spells entirely. Repeat is unaffordable alongside the Legend.
- **Downstage Dramatics — 45.** Instant-speed draw filler; Meditation does it better here.
- **Dredge Up — 42.** Two cards over two casts, sorcery speed, no board impact.
- **Emperor's Divide — 40.** Mass self-retreat dodges Unchecked Power — a named but narrow insurance policy; usually a dead Hidden slot.
- **Feral Strength — 40.** Discipline without the draw.
- **Frigid Touch — 50.** -2M repeatable; fine rate, loses the slot to Stupefy (draws) and Smoke Screen (bigger).
- **Lilting Lullaby — 88. SIGNATURE, 3 max.** Counter + "can't play spells this turn" at 2E+P2 (hybrid — either rune color). In a showdown this is checkmate: their trick dies AND every follow-up trick is locked out, so our 3M-token walls win the combat math they were about to lose. The single best defensive card available to this Legend; the signature doctrine (run 3) applies with no reservations.
- **Meditation — 66.** Reaction draw 2 by exhausting a friendly — and this deck ALWAYS has a spent or doomed Sprite whose exhaustion is free. Card advantage stapled to the token engine. The cost: it's the card you cut when the interaction count needs to rise.
- **Not So Fast — 58.** Counters spells AND abilities that choose your stuff. The named spot: Kai'Sa's Singularity/Hextech Ray pointed at Soul Shepherd or LeBlanc — the two units whose death actually hurts. Misses anything that doesn't target (sweepers, Punch First on their unit). Calm P1.
- **Premonition — 40.** Draw 3 for P3 Mind — recycling three runes is a full turn of future resources; the deck cannot pay it.
- **Resonating Strike — 64.** Printed REACTION move: flash Fae Fawn from base into a defended battlefield (+2M) mid-showdown — and her move-trigger drops a Sprite at base behind her. Surprise defender + token, or a reactive conquest after they empty a battlefield. Hidden as a bonus. Calm P1 and needs her alive; the best trick v1 doesn't run — first candidate when Meditation feels too greedy.
- **Rune Prison — 60.** Action-speed stun: the attacker deals no combat damage, our Sprites eat the battlefield anyway. Two-turn tempo vs big single attackers (Rengar, TTW). Calm P1.
- **Skyward Strike — 48.** Charm for 2E with a Level-6 rider we never reach, Neutral speed.
- **Smoke Screen — 58.** -4M at reaction speed: a defending Sprite beats a 6M attacker outright. The bigger, non-drawing Stupefy; the two compete for the same slots and Stupefy's cantrip usually wins, but this one actually KILLS things in combat.
- **Smoke and Mirrors — 70.** Swap two of your units if one is Temporary, draw 1, Hidden. Every mode is on-plan: swap a fresh ready Sprite INTO a battlefield and the doomed one home; swap Fae Fawn out (her swap-move spawns ANOTHER Sprite — swap is a move) — and it cantrips. From Hidden it's the reaction that saves a battlefield when the Temporary trigger is on the chain (flip, swap fresh body in, let the old one die).
- **Temporal Breach — 55.** The named line: banish your Sprite Mother → she replays free → second ready Sprite, 2E+P1. Also resets damage mid-combat. Costs: the replayed unit re-enters exhausted, so never aim it at a ready attacker.
- **Thwonk! — 55.** Repeatable attacker-stun at Action speed. The named spot: they alpha-strike your held battlefield with two big units — stun one, your 3M wall kills the other, repeat if you have 4 energy. Loses to Rune Prison on speed flexibility, wins on Repeat.
- **Turn to Dust — 58.** Delayed kill-any-gear. The meta file says the field is gear-heavy: Azir Equipment (16 gear — this kills B.F. Sword/Eye of the Herald), Kennen's Treasure Hunter output, Zhonya's in both Yi lists. Sorcery speed, one-turn delay. Maindeck cost: ~blank vs Kai'Sa Burn. Sideboard staple, fringe maindeck.
- **Back Off — 63.** Stun + draw from hand (Action), or a FREE reaction stun from Hidden. The flexible interaction card: early it cycles while stopping an attack, late the Hidden copy ambushes an alpha strike. Competes directly with Rune Prison (cheaper, Power) and loses only on energy cost.
- **Crescent Strike — 62.** Real removal in Mind: 4 to a target + 1 spray at a battlefield, Action speed. Kills LeBlanc-hunters, Vanguard Captains, 4M champions; the spray clips 1M tokens. Our only clean way to actually KILL a mid-size threat. P1.
- **Eclipse — 58.** Reaction -4M + Predict. Kills via combat, not directly; the Predict smooths draws. Solid second interaction suite card; loses main slots to Smoke Screen only on curve grounds.
- **Find Your Center — 42.** Draw + channel when behind; the discount clause reads nice but rewards losing.
- **Last Stand — 45.** Double Might + give Temporary: a 12M Petal Pixie swing, and at LeBlanc's battlefield the Temporary never triggers so the unit even survives. Win-more — it doubles a board that was already winning.
- **Party Favors — 30.** 1v1 politics: the opponent always picks what hurts you.
- **Portal Rescue — 45.** Blink to BASE (exhausted): saves a unit, re-triggers Sprite Mother; worse Temporal Breach for our uses.
- **Sanction — 25.** No Empower theme.
- **Shock Blast — 48.** Deal 4 at Action speed, but the discount needs an Empowered permanent we don't make; full price loses to Crescent Strike.
- **Sprite Call — 80.** The engine's Swiss knife, and the card the reference file's whole reaction doctrine is written around. From hand: 3E ready Sprite (a point, or a wall). From Hidden: a 0-cost REACTION — respond to the Temporary death trigger and the replacement token keeps the battlefield and scores the hold (riftbound_temporary_interactions.txt §3). Also the thing Mushroom Pouch/Ava want facedown. Three copies, no debate.
- **Stand United — 40.** Buff payoff without a buff theme.
- **Wages of Pain — 55.** Deal 3 + Gold token, Hidden. The named spot: hidden at a contested battlefield it's reaction-speed removal for a 3M attacker plus a rune next turn. Competes with Crescent Strike (bigger, surer) and Sprite Call (better Hidden).
- **Wind Wall — 52.** Unconditional counter at 3E+P2 Calm — the pips fight our skew; Lullaby occupies the counter throne and Defy the budget seat.
- **Consult the Past — 58.** Reaction draw 2; hide it early and it's a 1-rune investment that flips for free mid-showdown. The pure-draw competitor to Meditation; loses because Meditation costs 2 less over the game, wins when the Hidden slots are free.
- **Deadly Flourish — 40.** Sorcery 3-damage for 4E; overpriced here.
- **Flurry of Feathers — 48.** Counter OR four Bird bodies — flexibility is real but P2 Calm at 4E collides with the Legend's energy appetite on exactly the turns it matters.
- **Iterative Design — 48.** A 3M token that can actually HOLD (no Temporary) plus a Flow rebuy. Soul Shepherd pumps it. Loses out because 4E sorcery for one exhausted body is the tempo the deck can't spare.
- **Mystic Reversal — 35.** P3 Calm; unpayable.
- **Production Surge — 38.** Mech shell card.
- **Rocket Barrage — 42.** Hits Renata/backline units in base and gear; niche, P1, Repeat unaffordable.
- **Tricksy Tentacles — 58.** Move ≤8 total Might of enemy units to ONE location. The named spot: turn 4-5, strip both defenders off their held battlefield onto a useless one → conquer with two Sprites the same turn; or pile their attackers onto your Tank'd kill zone. Sorcery, P1, and the 8-Might cap misses late boards.
- **Falling Comet — 55.** Deal 6, Action, no Power: the clean answer to Rengar/TTW/Rhasa-sized threats that Mind otherwise shrinks but never kills. The named spot: their one giant conquers a battlefield — Comet it on your turn, take the field back with a Sprite. 5E is the whole turn.
- **Promising Future — 32.** Symmetric free-play; their card pool is bigger than our token deck's.
- **Reinforce — 40.** -5E cheat on a deck whose units cost 2-5; math doesn't pay.
- **Sprite Burst — 68.** Two ready Sprites = two conquests or 6M of walls, 5E, no Power. With Zilean at a battlefield it's four. Slot-efficient burst scoring for the mid game; v1 leaves it out only because the unit engines already saturate the token stream — first card in when a Zilean build wants more fuel.
- **Progress Day — 48.** Draw 4 is the refuel this colour pair is famous for; 6E+P1 is two Legend activations. A control build runs it; the tempo build can't.
- **Singularity — 45.** 6/6 split removal, P2; strong card, wrong energy bracket for us.
- **Clairvoyance — 38.** 7E filtering; too rich.
- **Moonlight Affliction — 35.** -10M reaction for 7E; answers one giant, costs one turn.
- **Unchecked Power — 42.** The named spot: board reset vs Azir go-wide — our board is free tokens, theirs cost cards. But exhausting all friendlies + 12 to ALL units kills our payoffs too, and 7E+P2 is turn 4+ with everything else off. Sideboard consideration at best.
- **Time Warp — 35.** Extra turn = extra Legend activation + extra scoring step — but E10+P4 without ramp is a fantasy here.

## Units (148)

- **Steel Paws — 52.** 0-Might units CAN conquer and hold (Scuttle's reminder text states the general rule) — so this is a 1E Deflect body that claims an empty battlefield turn 1 and taxes removal. Dies to any 1-damage sweep; Empower 7 is a real late mana sink. The cheapest possible point-grabber; loses to Scuttle Crab (draws a card doing the same job).
- **Apprentice Smith — 30.** Gear-reveal body in a near-gearless deck.
- **Blastcone Fae — 52.** Hidden 2-drop: flip = reaction-speed -2M + a surprise defender. Real trick; the Hidden slot competition (Sprite Call) is what keeps it out.
- **Clockwork Keeper — 50.** 2E 2M cantrip-for-a-pip; honest filler that loses to Petal Pixie/Keeper of Masks on plan relevance.
- **Forecaster — 20.** No Mechs.
- **Icevale Archer — 40.** Micro-pinger; too small.
- **Keeper of Masks — 64.** Three bodies for 2E (itself + two Reflection copies), ALL with Temporary → the Legend's activation drops to {1} next turn. Chump wall, Dusk Rose Lab fodder, and from HIDDEN it's a reaction: flip during their attack for three surprise defenders. Costs: 1M bodies are air in combat, and all three evaporate at your next Beginning Phase — this is a rhythm card (discount + defense), not board.
- **Lonely Poro — 35.** Died-alone clause anti-synergizes with a token swarm.
- **Mournful Witness — 42.** Grows to 4M after a combat; fine, plain.
- **Mutated Mouser — 40.** Speedbump; no draw, no tokens.
- **Ol' Poro — 45.** 4M for 2E with a turns-1-3 lockout; curve filler for slower builds.
- **Otterpus — 30. TRAP** — see traps section. WE are the deck scoring on turns 1-2 (Legend Sprite conquers turn 2); this converts OUR early points into cards for the opponent's benefit as much as ours.
- **Patched Porobot — 35.** Dual-type curiosity without a gear count to feed it.
- **Petal Pixie — 74.** The aggro payoff: +1M per friendly Temporary AT her battlefield — two Sprites alongside = 4M attacker on turn 3, and the Legend keeps feeding her. Dies to everything (2E body), but she costs 2 and threatens 5+. The caveat the rating already prices in: she counts Temporaries at HER location only, so she attacks with the swarm or she's vanilla.
- **Plundering Poro — 48.** Conquer→Gold on a 2-drop: we conquer constantly; still just a rune per few turns.
- **Ravenbloom Student — 42.** Spell-count payoff in a unit-heavy list.
- **Scuttle Crab — 58.** ETB draw + 0M holds battlefields + Deathknell shows their hand AND their facedown cards (real info vs Hidden mirrors) + perfect Dusk Rose Lab fodder (it already cantripped; the Lab kill is pure profit). The named spot: turn 1-2, claim the empty battlefield, replace itself, die profitably. Loses maindeck slots to Keeper/Pixie on engine relevance only.
- **Stalwart Poro — 35.** Vanilla defender.
- **Teemo - Strategist — 45.** Needs Hidden density ~10+ to deal real damage; ours is ~8 and his reveal averages ~1.5 damage. Fun, not good enough.
- **Watchful Sentry — 55.** 2E 1M, Deathknell: draw. The named spot: it blocks or feeds Dusk Rose Lab and always replaces itself — the cheapest card-neutral speedbump vs aggro. Loses to Scuttle (draws NOW, holds).
- **Wuju Apprentice — 35.** XP shell absent.
- **Affectionate Poro — 40.** Draw-if-undamaged is combat-shy in a deck that blocks with everything.
- **Ahri, Inquisitive — 58.** -2M an enemy every combat she's in: a 3-drop that wins 3M-vs-3M mirrors on rate. Solid interactive body squeezed out by engine density; P1.
- **Allay, Eager Admirer — 56.** Deflect for herself AND every other unit at her battlefield: a rune tax on every Kai'Sa burn spell aimed at the swarm. The named spot: parked with LeBlanc + Sprites, the whole pile costs +1 rune per target — burn decks run out of runes before we run out of tokens. Costs: 3M body, no offense.
- **Apprentice Mage — 38.** Small Empower value.
- **Aspiring Engineer — 25.** No gear loop.
- **Bubble Bot — 20.** No Mechs.
- **Caitlyn - Patrolling — 62.** Damage-last + exhaust: snipe for her Might at a battlefield — a repeating removal turret while she stands on a held field. The named spot: parked at LeBlanc's battlefield picking off 3M attackers before combat every turn. Calm P1; competes with Shadow Watcher at 4E-adjacent value and loses v1 slots to engine pieces.
- **Card Sharp — 32.** Symmetric Gold; helps them.
- **Chakram Dancer — 60.** AMBUSH (reaction-speed body) + Shield for others here: flip into a defended battlefield mid-attack and every Sprite defends at 4M. The named spot: they commit to breaking your held field; Dancer turns the math upside down for 3E. Loses slots to Janna (bounces the attacker outright) and engine density.
- **Covert Informant — 40.** Draw-on-move behind a 3E Empower toll.
- **Diana - Lunari — 48.** Showdown Predict-draw; fine value, off-plan.
- **Disarming Rake — 55.** Gear kill on a body. Meta-justified: Azir Equipment (16 gear), Kennen's gear output, Zhonya's everywhere. Maindeck cost: 2M understatted body, near-blank vs Kai'Sa. Sideboard 2x.
- **Eager Apprentice — 42.** Spell discount aura for a unit deck.
- **Enthusiastic Promoter — 44.** Hold→buff-all engine; slow but real in stall mirrors.
- **Frostcoat Cub — 50.** 3E 3M with optional -2M rider; honest tempo filler, no engine text.
- **Frostcoat Mother — 35.** Late-game vanilla Empower.
- **Gemcraft Seer — 54.** ALL friendly units get Vision — including every token: each Legend Sprite = a Predict, every turn, filtering the deck for free. The named spot: the long game, where the token stream doubles as a card-selection engine. Costs: P1, 3M body with no immediate impact — the value is invisible the turn it lands.
- **Gustwalker — 48.** Hunt 2 self-levels to Ganking by ~2 scores; a BF→BF mover without Windswept. Interesting, off the core plan.
- **Heimerdinger - Inventor — 78.** "I have all Exhaust abilities of all friendly legends" — he casts the LEGEND'S Sprite ability, discount included. Two ready Sprites per turn (Legend + Heimer) at 3E M3 P1 is a second engine core; with two Temporaries out he prints for {2}. The costs the rating prices in: he must survive a turn (summoning-sick exhaust ability — he enters exhausted and the ability needs Exhaust… he enters exhausted, so it's NEXT turn's engine), he's a lightning rod, and using him for Sprites means he never attacks.
- **Janna - Savior — 66.** REACTION unit: flash into a battlefield you control mid-showdown, heal your units, and BOUNCE an attacking enemy to its base — the combat just ends wrong for them. Premium defensive trick on a 3M body. Calm P1. First unit in when the meta turns aggressive; v1's engine density squeezed her out and that is a real cost.
- **Lecturing Yordle — 52.** Tank + ETB draw: a cantrip speedbump. Fine glue; loses to on-plan 2-3 drops.
- **Legion Quartermaster — 25.** No gear to bounce.
- **Lillia - Fae Fawn — 90. CHOSEN.** Runs at 3 total copies (zone + 2 main): the engine's mobile half, and the redundancy is insurance on the deck's namesake — she eats removal on sight. Accelerate (1E+Mind) → enter ready → conquer turn 2-3 while leaving a Sprite home. Every move is a token; with Windswept Hillock she double-dips (hold + attack). Extra copies also just re-deploy after death.
- **Mosstomper — 45.** Gustwalker's Deflect cousin.
- **Nami - Headstrong — 58.** Optional-Calm stun ETB + hold→ready-and-buff. The named spot: stun their blocker on your conquest turn, then her hold makes your next Sprite READY. Real, but P-hungry across colors and competing at a stacked 3-slot.
- **Pickpocket — 35.** Narrow gear conversion.
- **Pit Crew — 25.** No gear.
- **Poro Herder — 25.** No Poros.
- **Ribbon Dancer — 45.** Move→pump filler; the trigger is small and needs another body there.
- **Riven, Shattered — 25.** No Equipment.
- **Royal Entourage — 66.** ETB: ready OR exhaust a legend. Both modes matter: ready OURS = second Sprite activation this turn (with discounts, often 1-2E); exhaust THEIRS = Darius/Annie legends skip a beat. 4M body, Calm P1. Left out of v1 for engine density — it is the first 4-drop in when Hall of Legends isn't the battlefield.
- **Serene Ascetic — 42.** Mana-sink defender.
- **Solari Shieldbearer — 50.** ETB stun at sorcery speed; softens a defender pre-attack. Fine filler.
- **Sunlit Guardian — 45.** Shield+Tank honest wall.
- **Trevor Snoozebottom — 76.** Shield 3-drop whose HOLD makes a READY Sprite AT the battlefield — a self-reinforcing scoring engine: every turn he holds, you gain the point AND a fresh body that can defend or peel off to conquer the other field. The realistic cost: he must survive the opponent's turn on 3M(4 defending) — he holds best behind other Sprites or after their attackers are spent.
- **Wielder of Water — 25.** Alone-payoff.
- **Yuumi - Magical Cat — 50.** +3M/Tank to a Sprite every combat from a 1M body that dies to a stiff breeze; great text, wrong body.
- **Adaptatron — 35.** Conquer-kill-gear rider; niche.
- **Akali, Silent — 62.** Untargetable outside combat + +2M on move = a 6M conquering attacker Kai'Sa Burn literally cannot answer outside combat. The named spot: THE unit to board in vs point-removal decks; maindeck she competes with LeBlanc/Sprite Mother at 4E and loses on plan relevance. Calm P1.
- **Aphelios - Exalted — 25.** Equipment triggers, no Equipment.
- **Applied Researchers — 35.** Spell discount for a unit deck.
- **Bard - Mercurial — 40.** His good mode exhausts the Legend — the engine's whole turn. Unpaid he's vanilla. Anti-synergy priced in.
- **Blue Sentinel — 55.** Hold effects at his battlefield trigger TWICE. The named stack: Trevor + Sentinel at Grove of the God-Willow = two Sprites and two draws per held turn. Real but multi-card; his own rune-add rider is honest. P1.
- **Dramatic Visionary — 38.** Deathknell Predict 2; filler.
- **Dropboarder — 28.** Gear count absent.
- **Ezreal - Dashing — 48.** Snipe-on-combat + self-bounce; a removal pinger that never brawls. Cute, energy-awkward.
- **Field Musicians — 40.** One-shot +3M on a 3M body.
- **Frisky Hunter — 45.** Two bodies (one Deflect Bird that can HOLD — not Temporary); fringe.
- **Grumpy Rockbear — 35.** Late Empower sink.
- **Herald of Spring — 35.** XP without payoffs.
- **Jayce, Man of Progress — 25.** Gear cheat, no gear.
- **Jhin - Meticulous Killer — 40.** The 4E-spell condition rarely fires here.
- **LeBlanc - Everywhere At Once — 84.** The one card in the pool that switches off Temporary at her battlefield: Sprites there STOP DYING → they hold for points, accumulate, feed Petal Pixie permanently, and the Legend's discount clause reads them forever (activations tend toward {1}). Backline keeps her out of first-strike range. The whole hold-scoring half of the deck runs through her; removal answers her but the Sprites lost were free. Core 3x.
- **Malzahar - Fanatic — 60.** Sacrifice a DOOMED Sprite → 2 runes, at Action speed, every turn. The named spot: turn 4+, a Sprite that already conquered pays for the next Legend activation before it would die anyway. Cost: he exhausts to do it (no blocking) and 3M at 4E is under rate. The resource-engine version of this deck starts here.
- **Mel, Newly Awakened — 52.** ETB draw on a 4M body, Empower protection rider later. Good honest card, no plan text.
- **Navori Scout — 40.** Deflect vanilla.
- **Prize of Progress — 25.** Gear-ability payoff.
- **Shadow Watcher — 72.** "Enters ready if a friendly unit died during your Beginning Phase" — in this deck that clause is simply TRUE from turn 3 on (a Sprite dies every Beginning Phase by design). A 4E 5M body that enters READY and conquers immediately, every time. Efficient pressure that the engine turns on automatically. Calm P1 ×2 copies is most of our hard Calm.
- **Sky Cruiser — 25.** Discard-a-gear cost, no gear.
- **Sona, Harmonious — 58.** Ready 4 runes at end of turn while she's at a battlefield = a full extra Lullaby/Sprite Call flip of resources on THEIR turn, every turn she lives. The named spot: the control mirror, where she funds double reactions. Fragile P1 4-drop; keep her behind the wall.
- **Sprite Mother — 74.** 4E: 3M body + a READY Sprite at her location. Played to a held battlefield: instant reinforcement + the Sprite can still peel off to conquer. The Temporal Breach blink target. Third engine card; P1 ×3 defines the Mind skew.
- **Stellacorn Herder — 56.** Move→draw on a 3M body: she conquers and cantrips every turn she swings. The named spot: the grind game, where she is a card per turn attached to a scorer. Loses v1 slots to Shadow Watcher (bigger, ready) — the closest cut.
- **Taric - Protector — 50.** Shield/Tank anchor granting Shield to the battlefield; honest hold-defense, no engine.
- **Tomb-Raider Barbara — 40.** Conditional gear kill at 7 runes.
- **Viktor, Innovator — 50.** Recruit token (NOT Temporary — it holds!) every time you play a card on their turn: with 11 reaction/Hidden cards he drips permanent bodies. Cute engine, 3M P1 body, one token per turn realistic.
- **Wizened Elder — 28.** Buff payoff, no buffs.
- **Ahri - Alluring — 62.** "When I hold, score 1 point" — a held battlefield with her = 2 points per turn cycle, which halves the clock to 8. The honesty tax: she's a P1 Calm 4M 5-drop that every removal spell kills on sight, and the double-score reading survives rule 470 only because her trigger is an effect gain, not a second Hold — flagged as needing a judge check before a tournament. High ceiling, high variance.
- **Ava Achiever — 52.** Attack → pay Mind → play a Hidden card from HAND free: a 5E body that cheats Sprite Call/Consult into play mid-swing. Needs board + hand + attack all at once.
- **Blitzcrank - Impassive — 45.** Drag-in + self-bounce control; rebuy cost every loop.
- **Ekko - Recurrent — 48.** Accelerate body + rune refund Deathknell; generically fine, no plan text.
- **Esteemed Hierophant — 45.** Anti-spell-damage wall at 7 runes; sideboard-shaped vs Kai'Sa, slow.
- **Fate Weaver — 30.** Digs for big spells we don't run.
- **Gearhead — 22.** Equipment payoff.
- **Hwei - Brooding Painter — 55.** Move→loot with escalators: a value champion whose every conquest draws. The named spot: the long game as a second Stellacorn with upside. 5E P1 is the engine-turn conflict; cut on curve.
- **Irelia, Fervent — 40.** Protect-the-queen shell card in a swarm deck.
- **Ivern - Nurturer — 48.** ETB/hold unit-dig; menagerie rider mostly dead. Decent value 5-drop, off-plan.
- **Jax - Unmatched — 25.** Equipment.
- **Jeweled Colossus — 40.** Stats + Vision; plain.
- **Lee Sin - Ascetic — 40.** Solo buff stacker; slow.
- **Lillia - Protector of Dreams — 68.** The other Lillia: your tokens get TANK (Sprites soak damage before Pixie/LeBlanc/Trevor can be touched in combat) and she grows +1 per token play — with the Legend + Fae Fawn feeding her she attacks at 5-7M. Champion unit but NOT the chosen one — perfectly legal as a normal 3-copy card (103.2.a rules text; we run 2). The named spot: she turns every combat over a held battlefield into "kill three free tokens first."
- **Master Yi - Meditative — 35.** 8-rune vanilla.
- **Nasus, Guardian of Knowledge — 45.** Big body + channel trickle; fine, plain.
- **Ornn - Blacksmith — 25.** Gear dig.
- **Pakaa Protector — 45.** Move-value cat; Stellacorn is cheaper and draws surely.
- **Playful Phantom — 32.** Vanilla.
- **Renata Glasc - Mastermind — 50.** The draw mode (1E+Mind/turn at a battlefield) is a real engine; the score mode's P4 Mind is a fantasy against a 12-rune board. Control-build card.
- **Rumble - Scrapper — 28.** Mechs.
- **Shen, Scourge of Shadows — 48.** Hold-draw wants EXACTLY one other unit — fights the swarm's nature.
- **Simian Ancestor — 30.** Buff engine absent.
- **Soul Shepherd — 66.** ALL token units +1M: Sprites hit 4M — over Hextech Ray's 3 damage, surviving Thousand-Tailed Watcher's -3, beating Sand Soldiers and every 3M mirror body. A one-card answer to the meta's token-sweeper math (VEN Kai'Sa Burn breakpoints, VEN Azir mirrors). Cost: a 5E 3M body that dies to the removal it's taxing; it protects the swarm, nothing protects it.
- **Vex - Mocking — 40.** Stun-rider without a stun package.
- **Zilean - Time Mage — 70.** Once per turn, a token you play while he's at a battlefield doubles. Doubles the Legend's Sprite, Sprite Mother's, Sprite Call's, Trevor's. Two ready Sprites a turn is two points of pressure. Priced down from core because he needs to both SURVIVE and STAND at a battlefield, and the doubling is win-more when the engine is already running — the 1-of finisher slot is his.
- **Alpha Wildclaw — 45.** Tank umbrella; P2 Calm heavy.
- **Azir - Ascendant — 45.** Swap-mover; his move makes no Sprites (only Fae Fawn's does).
- **Cloud Drake — 38.** 6E cantrip body.
- **Guardian of the Passage — 42.** Hold→regrow; slow value.
- **Jayce, Brilliant Inventor — 25.** Gear engine.
- **Kai'Sa - Evolutionary — 52.** Ganking conquest + spell rebuy scaling with points: a fine top-end scorer; 6E collides with the Legend every turn.
- **Leona - Zealot — 38.** Comeback clause + stun synergy we lack.
- **Lux - Illuminated — 28.** 5E-spell trigger; we cast cheap.
- **Mageseeker Warden — 55.** Opponents play units ONLY TO BASE and can't ready enemies: blanks Ambush (Annie's whole deck per meta file), Azir's token placement tricks, every flash-defender. The named spot: sideboard lock vs Annie/Azir; 6E maindeck is too slow.
- **Monch — 38.** Stun-conditional discount.
- **Ornn - Forge God — 25.** Gear count.
- **Riptide Rex — 50.** ETB deal 6 on a 6M body — real removal + threat; P2 Mind is 2 recycled runes on the turn the Legend also wants 4E. Curve casualty.
- **Ruined Rex — 42.** Deathknell 4; fine.
- **Sandstone Chimera — 25. TRAP** — halving channel hits US harder: the Legend needs energy every single turn.
- **Spectral Centaur — 38.** Death-pump is sporadic mid-combat.
- **Swain, Visionary — 40.** Unit+gear+spell condition; we skip gear most games.
- **Wraith of Echoes — 64.** "First friendly unit dies each turn → draw 1" — a Sprite dies at YOUR Beginning Phase every turn by design, and chump blocks trigger it on THEIR turn: realistically 1-2 cards per turn cycle. The named spot: the attrition matchup (Kai'Sa kills a token per spell — every kill now cantrips for us). Cost: 6E P1 5M, the engine-turn conflict again; the grind build's flagship.
- **Yasuo - Remorseful — 45.** Attack-snipe on a big body; P2 Calm heavy.
- **Zephyr Sage — 30.** Vanilla Shield.
- **Astral Heron — 40.** Discount engine at 7E arrives after the game is decided.
- **Eclipse Herald — 32.** Stun package rider.
- **Iascylla — 35.** Hold-drag kill zone; slow.
- **Mega-Mech — 30.** Vanilla.
- **Sprite Queen — 58.** A second never-exhausting Legend: ready Sprite on ETB and EVERY Beginning Phase. The named spot: the long game anchor — landing her turn 4-5 (10 runes) makes the token stream unstoppable. 7E means she and everything else can't share a turn; the control build's top end, v1's cut.
- **Tasty Faefolk — 38.** Accelerate + death-ramp; midrange filler.
- **Thousand-Tailed Watcher — 60.** Accelerate 7M + ETB -3M to ALL enemies: swings entire board states, and the meta file crowns it (VEN Kai'Sa's finisher). For us: the sideboard answer to Azir go-wide and mirror swarms. 7E; two Legend turns.
- **Tianna Crownguard — 55.** "Opponents can't score while I'm at a battlefield" — a clock-stopper that converts our incremental scoring into inevitability. The named spot: turn 5+, land her at the battlefield they must break; Deflect taxes the answer. P2 Calm, 4M body — she dies to committed attacks, and 7E is the whole turn.
- **Breakneck Mech — 25.** Mechs.
- **Dr. Mundo - Expert — 30.** Trash count we don't build.
- **Nasus, Ascended — 38.** 8E + 8E Empower across two turns; wrong deck.
- **Vilemaw — 45.** Ambush blowout; P2 Calm 8E.
- **Whiteflame Protector — 35.** +8M one-shot at 8E.
- **Needlessly Large Yordle — 30.** Needs multi-hold turns to discount; clunky.
- **Plaza Guardian — 25.** Gear discount.
- **Master Yi - Unstoppable — 20.** XP levels we never gain.

## Battlefields (64)

> **Scores below were written under the Bo1 assumption** — "one of your three is
> randomly live (485.5), so each must stand alone." That is only true in Duel.
> In Match (Bo3) you choose one per game and burn it (486.5), so the three want
> three *roles* (go-first / go-second / neutral). See the battlefield corrections
> at the top of this file and the selection write-up in `README.md`.

- **Abandoned Hall — 35.** Symmetric micro-pump.
- **Altar of Blood — 30.** Death-save tax; our deaths are free tokens.
- **Altar to Unity — 40.** Hold→Recruit at base; mild, ours more often.
- **Amateur Recital — 48.** Hold→evict any unit at a battlefield to its base: repeatable tempo denial while we hold. Sleeper; symmetric.
- **Aspirant's Climb — BANNED** (Constructed banlist, 2026-07-24). Never legal.
- **Back-Alley Bar — 35.** Move-pump; small.
- **Bandle Tree — 52.** TWO Hidden cards at one battlefield: Sprite Call + Smoke and Mirrors stacked = layered reactions at the field you must keep. Symmetric only vs Hidden decks (rare); the Hidden-heavy build's pick.
- **Black Flame Altar — 75.** Temporary units have Shield: every Sprite defends at 4M, near-one-sided (opponents almost never run Temporary). Turns the token wall into real defense. Loses to the top three only because it generates no cards/points itself.
- **Dragon Roost — 15.** No Dragons.
- **Dusk Rose Lab — 72.** The documented engine (reference file §6, RiftJudge FAQ #9231): at your Beginning Phase, kill the doomed Sprite BEFORE its Temporary trigger resolves → draw 1, every turn, from a body that was already dead. One-sided in practice, verified-legal sequencing, and it works from turn 2. Best battlefield in the pool for this deck.
- **Emperor's Dais — 64.** Conquer→pay 1, return the conquering unit to hand→2M Sand Soldier HERE. For us: the returned unit is a TOKEN — it evaporates — and the permanent Sand Soldier keeps the battlefield and holds next turn. Every Sprite conquest here converts a dying token into a lasting point engine. The named cost: 1 energy per trigger, symmetric text (but opponents returning real cards pay more than we do returning free tokens).
- **Forbidding Waste — 45.** Lone-defender -2M: meta tech that blanks Master Yi's whole legend, near-neutral for our swarm. Sideboard-battlefield thinking; main three are better.
- **Forge of the Fluft — 15.** Equipment.
- **Forgotten Library — 25.** 4E-spell Predicts; we cast cheap.
- **Forgotten Monument — 25.** Delays OUR turn-2 scoring; anti-plan.
- **Fortified Position — 40.** Defend-Shield; honest, small.
- **Frozen Fortress — 30.** Kills our Reflections and Birds, spares 3M Sprites; net negative with Keeper of Masks in the 40.
- **Gardens of Becoming — 20.** XP without payoffs.
- **Grove of the God-Willow — 58.** Hold→draw: we hold with Trevor/LeBlanc-Sprites/Fae Fawn from turn 2-3 on. Fully symmetric, but we're the deck built to hold more often. The fourth-best option and the swap-in if the user prefers draw over Dais's board.
- **Hall of Legends — 66.** Conquer→pay 1→ready your Legend: we conquer EVERY turn, and a readied Legend is a second discounted Sprite activation — the battlefield literally doubles the engine. Symmetric text, but no meta legend (Yi/Kai'Sa/Azir/Kennen) exhausts for anything close to our value.
- **Hallowed Tomb — 40.** Champion insurance; nice-to-have, low ceiling.
- **Heisho — 25.** Deflect-ignore niche.
- **Kinkou Temple — 35.** Needs Protector of Dreams on table first (tokens gain Tank) — two-card battlefield.
- **Marai Spire — 25.** Repeat discount; barely used.
- **Minefield — 20.** Self-mill for nothing.
- **Monastery of Hirana — 22.** Buff economy absent.
- **Mystic Vortex — 18. TRAP** — taxes REACTIONS during showdowns here: our Hidden flips, Lullaby, Sprite Call — we are the most reaction-dependent deck in the room. Never pick.
- **Navori Fighting Pit — 45.** Hold→buff: Trevor grows each turn; fine, small.
- **Obelisk of Power — BANNED** (Constructed banlist, 2026-07-24). Never legal. (Was rated 50 as "the neutral pick if avoiding all texture" — that recommendation was wrong to make.)
- **Ornn's Forge — 18** / **Piltovan Forge — 18.** Gear.
- **Power Nexus — 40.** Hold→4 runes→EXTRA point: a real late mana sink but 4 runes is two turns of channeling.
- **Protective Sands — 38.** Early-only draw.
- **Ravenbloom Conservatory — 68.** "When you defend here, reveal the top card; if it's a spell, take it, else recycle it." v5 is 21 spells in 40 (52.5%), so better than a coin flip for a free card, and it is the only battlefield gated on *being attacked* — the go-second slot. Recycle is bottom-of-deck (416.1), not a discard. (Was 40 on v1's creature-heavy list; that rating expired.)
- **Reaver's Row — BANNED** (Constructed banlist, 2026-07-24). Never legal.
- **Reckoner's Arena — 28.** Few conquer effects (Plundering Poro only).
- **Ripper's Bay — 25.** Bounce economy we don't run.
- **Risen Altar — 20.** Empower discount.
- **Rockfall Path — 40.** Meta tech (blanks Annie Ambush per the archetype file; hurts Azir). Costs us Keeper/Chakram flips at that field; our tokens play to base anyway. Sideboard-battlefield.
- **Sandswept Tomb — 25.** Friendly-target discount niche.
- **Seat of Power — 45.** In 1v1's two-battlefield board: conquer while holding the other = draw 1. Decent, conditional.
- **Shadow Temple — 15.** Milling OURSELVES toward Burn Out.
- **Sigil of the Storm — 8. TRAP** — forced rune recycle on every conquer, and we conquer constantly: the battlefield eats our rune board.
- **Star Spring — 30.** Micro-utility.
- **Startipped Peak — 52.** Hold→channel: ramp that compounds with our hold plan; simple, symmetric, good.
- **Sunken Temple — 35.** Mighty-conquer condition (5M+); occasional.
- **Targon's Peak — 70.** Conquer→ready 2 runes at end of turn: our every-turn conquests bank fuel for Lullaby/flips on THEIR turn. The reaction-deck's economy battlefield; just behind the top three.
- **The Academy — 40.** Hold→Repeat rider; our repeat targets are thin.
- **The Arena's Greatest — BANNED** (Constructed banlist, 2026-07-24). Never legal.
- **The Candlelit Sanctum — 45.** Conquer→scry-2: constant for us, tiny.
- **The Dreaming Tree — BANNED** (Constructed banlist, 2026-07-24). Never legal. Would have been ~55 for v5's spell density.
- **The Grand Plaza — 25.** 7 units at one field is fantasy outside Zilean dreams.
- **The Papertree — 42.** Symmetric hold-ramp; fine.
- **Threshold of the Gray — 64** (40 in a Kai'Sa field). Added energy survives to end of turn (167) and the answer layer is Stupefy {1} / En Garde {1} / Discipline {2} — a free trick every combat, both seats, without touching the live-rune budget. Symmetric, so it funds opposing burn too.
- **Trapping Grounds — 28.** Excess-damage conquest; our tokens hit for exactly enough.
- **Treasure Hoard — 48.** Conquer→pay 1→Gold: steady ramp off the thing we do anyway. Just behind Targon's Peak in the same genre.
- **Trifarian War Camp — 45.** +1M everyone here including attackers: the swarm likes it, so does theirs.
- **Valley of Idols — 25.** Units played AT battlefields — rare for us (tokens go to base).
- **Vaults of Helia — 10. TRAP** — holding taxes our own unit plays.
- **Veiled Temple — 20.** Gear ready.
- **Vilemaw's Lair — 22.** Trap-in-place oddity.
- **Void Gate — 20.** Amplifies BURN — hands Kai'Sa a better sweep against our own tokens.
- **Windswept Hillock — 58.** Ganking for units here: Fae Fawn attacks battlefield-to-battlefield, leaving a Sprite holding the old one — the double-dip line the standard move forbids. Ready Sprites redeploy across fields. The named cost: fully symmetric, and vs VEN Kennen Movement it upgrades THEIR whole deck; picked third anyway when the field isn't movement-based.
- **Zaun Warrens — 42.** Conquer-loot; card-neutral filtering.

---

## Combo clusters (named)

1. **The Sprite Press** — Legend + Heimerdinger + Keeper of Masks. Keeper (turn 2)
   puts 3 Temporary units out → Legend's activation costs {1}; Heimerdinger
   copies the Legend's exhaust ability at the same discount. From turn 4:
   TWO ready Sprites per turn for ~2-3 total energy, zero cards. 2-3 pieces;
   degrades gracefully (Legend alone is the 1-piece version).
2. **The Dream Garden** — LeBlanc + any Sprite source (+ Petal Pixie / Soul
   Shepherd). Sprites at LeBlanc's battlefield never die → they hold for points
   every turn, stack into a wall, and Pixie's count only rises. 2 pieces to
   function, 3 to threaten lethal math. The deck's hold-scoring win line.
3. **The Documented Save** (reference file §3-6, verified) — Temporary trigger
   on the chain + Hidden Sprite Call at that battlefield (+ Dusk Rose Lab).
   Respond to the death trigger: flip Sprite Call (free, Reaction), new ready
   Sprite lands, old token dies, battlefield held → hold point scores; with
   the Lab, feed the OLD token to the Lab first and draw 1 too. 2 pieces
   (battlefield counts as one). Sequencing is mandatory: flip BEFORE the
   trigger resolves (§3), Lab kill before Temporary resolves (§6).
4. **The Toll Booth** — Soul Shepherd + token stream vs the meta's breakpoints.
   4M Sprites survive Hextech Ray (3), TTW (-3), and beat Sand Soldiers (2M)
   and every 3M mirror body. 1 piece + the engine; matchup math, not a trick.
5. **The Revolving Door** — Fae Fawn + Windswept Hillock (or Smoke and Mirrors /
   Resonating Strike). Her move IS the token: BF→BF attacks leave a holder
   behind; reaction-speed moves make surprise defenders + a token. 2 pieces.
6. **The Second Shift** — Hall of Legends (or Royal Entourage) + Legend.
   Conquer→1E→ready Legend→second discounted activation. 2 pieces, one is a
   battlefield slot.
7. **The Blink Nursery** — Temporal Breach + Sprite Mother: 2E+P1 for a second
   ready Sprite and a reset body. 2 pieces; not in v1, listed for iteration.

## Traps (look right, are not)

- **Otterpus** — reads as anti-aggro tech; actually neutralizes OUR turn-1-2
  Legend-Sprite conquests. The mirror-image of our early plan.
- **Sandstone Chimera** — big stats + symmetric channel-halving strangles the
  4-energy-per-turn Legend engine first.
- **Mystic Vortex** — taxes reactions in showdowns; we are the reaction deck.
- **Sigil of the Storm** — forced rune recycle on conquer × a deck that
  conquers every turn = self-mill of the rune board.
- **Vaults of Helia / Void Gate** — hold/burn riders that each punish exactly
  our texture (unit plays after holding; +1 damage onto our own 3M tokens).
- **Unchecked Power** — looks like the token deck's sweeper; exhausts OUR
  board and kills OUR payoffs too. Kai'Sa casts it better than we do.
- **Bard - Mercurial** — mass repositioning looks on-plan; the cost is
  exhausting the Legend, i.e. the engine.
- **Last Stand / Svellsongur** — flashy Sprite-math cards that are win-more
  (Last Stand) or a two-card 6-resource setup that folds to one removal spell
  (Svellsongur).
- **Frozen Fortress** — "kills small tokens" reads anti-Azir; it mainly kills
  our own Reflections and Birds while 2M Sand Soldiers survive.

## Roles

- **Payoffs:** Petal Pixie, Soul Shepherd, Lillia - Protector of Dreams,
  LeBlanc (persistence), Zilean (multiplication).
- **Engines/enablers:** Legend, Fae Fawn, Heimerdinger, Sprite Mother, Sprite
  Call, Trevor, Keeper of Masks, Sprite Fountain, Sprite Queen (unbuilt).
- **Interaction:** Lilting Lullaby, Stupefy, Defy, Janna, Rune Prison/Back Off,
  Crescent Strike, Smoke Screen, Falling Comet (unbuilt tiers listed in order
  of preference).
- **Value/draw:** Meditation, Smoke and Mirrors, Scuttle Crab, Watchful Sentry,
  Wraith of Echoes, Stellacorn Herder, Dusk Rose Lab (battlefield).
- **Curve fillers (avoid unless short):** Frostcoat Cub, Lecturing Yordle,
  Clockwork Keeper, Sunlit Guardian.
- **Battlefields:** Dusk Rose Lab, Hall of Legends, Emperor's Dais (picked);
  Black Flame Altar, Windswept Hillock, Grove of the God-Willow, Targon's
  Peak, Startipped Peak (bench, in order).
