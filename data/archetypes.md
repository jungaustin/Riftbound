# Riftbound meta archetypes

This file is the ONLY source of matchup information in the whole pipeline. Card
data says what cards do; it has no idea what people are playing. If an archetype
is not written down here, the tools will not claim anything about it — that is
deliberate, and it is what stops the model from inventing a meta that sounds
plausible and is fiction.

as_of: 2026-08-06

**Reader context (2026-07-31).** The user is a new player and does not have a
local field to report. Every list in `decks/meta/` is a deck found online that
did well in a tournament — not something the user has actually sat across from.
Treat this whole file as "what wins tournaments somewhere", not "what the user
will face", until real games get recorded. There are now THREE data grades in
this file, best to worst: the four `VEN` entries (real event, real lists), the
six pre-Vendetta entries plus the four `LIST` entries (real lists, no event
data), and the `HEARSAY` entries at the bottom (named threats from two
content-creator guide transcripts, no lists). Never let a HEARSAY entry
outvote a VEN entry.

**New batch added 2026-08-06 — the four `LIST` entries.** The user pasted
seven decklists. Three of them (Azir Calm/Order, Kai'Sa Fury/Mind, Master Yi
Body/Calm) were **byte-identical to the existing VEN top-4 lists** and were
not duplicated; the other four — Ezreal Chaos/Mind, Irelia Calm/Chaos, Rek'Sai
Fury/Order, Viktor Mind/Order — are new and are saved in `decks/meta/` with no
`ven-` prefix. **No source, event, or finish was recorded for any of them.**
That three of the seven are exact copies of the Vendetta top 4 is suggestive of
a shared origin, but suggestive is not evidence: until provenance is supplied,
these four carry list-grade confidence (plan, curve, and rune math are solid,
read straight off the cards) and ZERO matchup or prevalence confidence. Their
`strong_vs`/`weak_to` lines are labelled STRUCTURAL INFERENCE for that reason.
All four validate as legal 40/12/3 under the current banlist.

**BANLIST WARNING (added 2026-08-05).** Six of the eleven lists in `decks/meta/`
are **pre-ban and now illegal** — all six on their battlefield line:
`annie-chaos-fury`, `darius-fury-order`, `lillia-galewinds-unleashed`,
`masteryi-body-calm` (The Arena's Greatest); `lux-mind-order`,
`sivir-body-chaos` (Aspirant's Climb). The four `VEN` lists and
`diana-chaos-mind` / `lillia-sprite-tempo-netdeck` are clean. Run
`python3 cli.py check <list>` before copying any slot out of a reference deck;
`data/banlist.json` is the source and the checker enforces it. This is another
reason the pre-Vendetta entries are a lower data grade — those decks were tuned
in a format that no longer exists.

**Provenance and its limits.** Six lists supplied by the user, sourced from
riftools.app tier list and riftdecks.com tournament results. All six validate as
legal 40/12/3 *for the format they were played in* (see the banlist warning). The `plan`, `identity`, `speed` and `key_cards` fields are read
off the lists and their computed statistics — those are solid. The `strong_vs`,
`weak_to` and `tech_against` fields are **structural inferences from comparing
these six decks against each other**, not observed win rates. They say "this
deck's answers do not line up with that deck's threats," which is real analysis,
but it is not the same as knowing a matchup is 60/40. Replace them with observed
results when you have them.

**`prevalence` is UNKNOWN for every entry.** The user did not record field share
or ordering. Fill this in — it is the field that most changes deckbuilding advice,
and right now every entry is guessing that they are equally common.

**Two data vintages in this file.** The first six entries are pre-Vendetta
(riftools tier list + riftdecks tournaments, which only ran through Unleashed).
The four `VEN` entries are post-Vendetta, from a single 100-player event, and
are the better data — larger field, current card pool. Where they disagree,
trust the VEN entries. The pre-Vendetta six may no longer reflect the field at
all; treat them as historical until re-confirmed.

**Placements within the VEN top 4 were not recorded**, so all four carry the
same prevalence note. If you learn the ordering, put it in.

## How to maintain this

- One `## Heading` per archetype. Everything under it is `key: value`.
- Recognised keys: legend, identity, speed, prevalence, plan, key_cards,
  strong_vs, weak_to, tech_against, updated. Extra keys pass through.
- Update `as_of` when you revise. The tools warn if it predates the newest set.
- Delete archetypes that rotate out. A stale entry is worse than a missing one.

## Field-wide observations

These come from comparing all six sideboards, and are the most trustworthy
meta signal in the file, because a sideboard is a direct statement of what a
pilot expects to face. **Scope note (2026-08-06):** every count below is over
the ORIGINAL SIX pre-Vendetta lists only. `decks/meta/` now holds sixteen
lists, so "four of six" and "all six" here are not field-wide totals any more.
Two of the numbers are already superseded: the rune-load claim below names
only Sivir (3.3 Body) and Darius (3.0 Order) as stretched, but VEN Kai'Sa
(4.2 Mind), VEN Kennen (2.9 Chaos) and LIST Viktor (2.9 Order) are all in or
past that range. Re-derive these observations across all sixteen before
quoting them.

- **Four of six sideboards carry gear hate**: Thermo Beam (Annie, Darius),
  Factory Recall (Annie, Sivir), Disarming Rake (Master Yi), plus Acceptable
  Losses maindeck in Diana. The field expects gear-based decks — which matches
  Sivir running 10 gear and Lux running 5.
- **Hand disruption is widespread**: Sabotage, Mindsplitter, Ashe - Focused.
  Consistent with a field that expects at least one slow controlling deck.
- **"Can't be chosen by enemy spells" is a sideboard theme**: Ruin Runner
  (Master Yi), Baron Nashor (Sivir). That is answer-to-removal, aimed at
  spell-heavy decks like Lux and Diana.
- **Rune requirements are much lighter than card colours suggest.** Across all
  six decks, 18-31 of 40 main-deck copies have no Power cost at all and are
  castable off any runes. Only Sivir (Body, 3.3 pips per rune) and Darius
  (Order, 3.0) are meaningfully stretched. Judge rune decks by Power pips, never
  by how many cards are printed in a colour.
- **Gust (return a unit with 3 Might or less) appears in two maindecks.** It is
  the single best line for reading the field: it is excellent against Master Yi
  and Darius (both full of 2-Might bodies and 1-Might tokens) and blank against
  Sivir's Elder Dragon and Annie's Ferrous Forerunner.

## Lux Control

legend: Lux - Lady of Luminosity
identity: Mind+Order
speed: slow control; wants the game past turn 6
prevalence: unknown
plan: Trade off early, draw an overwhelming number of cards, and win late. The
  Legend draws on every 5+ energy spell, which turns Progress Day (Draw 4) and
  Promising Future into two-for-ones. Sacrifice and Shadow's Call convert its own
  units into cards, and cheap Deathknell bodies (Watchful Sentry, Soaring Scout)
  mean even its blockers replace themselves. The Ruination is a one-sided reset
  once ahead on cards. Renata Glasc offers an alternate win that scores a point
  directly without combat.
key_cards: Progress Day, Sacrifice, Shadow's Call, The Ruination, Renata Glasc -
  Mastermind, Ekko - Recurrent
notes: Both non-neutral battlefields actively slow the game — Aspirant's Climb
  raises the points needed to win, Forgotten Monument blocks scoring until turn
  three. This is a deliberate clock-extension package, and it is the clearest
  statement of intent in any of the six lists.
strong_vs: go-wide boards (The Ruination, Cull the Weak sweep Darius's Recruit
  tokens and Vanguard Captain); any deck that runs out of cards trying to break
  through
weak_to: fast starts, because the payoff cards cost 5-9 and 10 of 40 cards cost
  5+; hand disruption (Mindsplitter, Sabotage, Ashe) strips the one expensive
  card it is holding; the deck has only 15 units and can be raced before Progress
  Day comes online
tech_against: gear removal answers Forge of the Future and Sumpworks Map;
  pressure that closes before turn 6 is the real answer
strength_computed: the least Power-dependent deck in the field. 31 of 40 copies
  have no Power cost at all, and it needs only 11 hard pips total (Mind 7,
  Order 4) against a 6/6 split. Its expensive spells are expensive in Energy,
  not in runes, so the 6/6 rune deck is not a compromise — it genuinely does not
  care which half it draws.
confidence: high on plan, medium on matchups
updated: 2026-07-27

## Diana Showdown Tempo

legend: Diana - Scorn of the Moon
identity: Mind+Chaos
speed: interactive midrange; operates on the opponent's turn
plan: Win showdowns with cheap reactions rather than with bigger units. The
  Legend adds energy that can only be spent during showdowns, which is a direct
  subsidy on holding up tricks. Ravenbloom Student grows with each spell,
  Hwei - Brooding Painter converts movement into cards, and Fizz - Trickster
  replays a spell from the trash. Moonfall (3x signature) both repositions an
  enemy unit and shrinks the whole battlefield.
key_cards: Moonfall, Stupefy, Star-Crossed, Hwei - Brooding Painter,
  Ravenbloom Student, Ride The Wind
strong_vs: decks that commit units to battlefields and expect combat to resolve
  as drawn — Star-Crossed, Gust, and Moonfall all undo attacks after they are
  declared; Ambush decks, because Rockfall Path shuts off unit plays entirely at
  one battlefield
weak_to: units it cannot bounce or shrink — Gust caps at 3 Might, Eclipse at -4,
  so Ferrous Forerunner (6), Rengar - Trophy Hunter (6) and Elder Dragon (10)
  all sit above the answer band; also weak to its own inconsistency, see below
tech_against: resilient single large threats; "can't be chosen" units (Ruin
  Runner, Baron Nashor) blank most of this deck's interaction
weakness_computed: 9 singletons in 40 cards. Each is seen by turn 5 about 20% of
  the time, so a meaningful part of this list is not showing up in most games.
  The 3-ofs are the real deck.
confidence: high on plan, medium on matchups
updated: 2026-07-27

## Annie Ambush Aggro

legend: Annie - Dark Child
identity: Fury+Chaos
speed: fast; wants the game decided by turn 5
plan: Apply pressure with units that arrive at instant speed and hit above their
  cost. Inferna and Grim Apothecary have Ambush, Rengar - Pouncing can be played
  directly to a battlefield you are attacking, and Cleave, Long Sword and
  Star-Crossed convert a surprise body into a won combat. The Legend readies 2
  runes at end of turn, which pays for holding reactions up. Kai'Sa - Survivor
  draws on conquer, giving the aggro plan a card-advantage tail.
key_cards: Inferna, Rengar - Pouncing, Kai'Sa - Survivor, Flash, Long Sword,
  Ferrous Forerunner
strong_vs: slow decks that need to untap and cast something expensive — Lux and
  Sivir both spend early turns doing nothing this deck cannot punish
weak_to: Vex - Apathetic (stuns units an opponent plays at its battlefield,
  which is precisely what Ambush does) and Rockfall Path (units cannot be played
  there at all); also weak to sweepers once committed, and Flurry of Blades
  cleanly answers a 1-Might Inferna
tech_against: anti-Ambush effects are the specific answer, not generic removal;
  Vex - Apathetic and Rockfall Path both appear in the Diana list already
confidence: high on plan, medium on matchups
updated: 2026-07-27

## Master Yi Solo Aggro

legend: Master Yi - Wuju Bladesman
identity: Body+Calm
speed: fastest deck in this group; average cost 2.35 with twelve 1-drops
plan: Attack with a single unit and make that unit unprofitable to block. The
  Legend gives +2 Might to a friendly unit defending alone, and the deck stacks
  effects that reward being solo: En Garde, Lonely Poro's Deathknell, Punch First
  (+5 Might). Defy and Not So Fast protect the threat with counterspells rather
  than by adding bodies. Master Yi - Tempered accrues XP through Hunt 2 and turns
  on Deflect and Ganking at Level 6.
key_cards: Punch First, Discipline, Rengar - Trophy Hunter, Irelia - Fervent,
  Master Yi - Tempered, Zhonya's Hourglass
strong_vs: decks relying on targeted removal to answer a single threat — Defy,
  Not So Fast and Zhonya's Hourglass all protect the one unit that matters, which
  is awkward for Lux and Diana
weak_to: Gust and Stupefy line up almost perfectly against this deck's 2-Might
  bodies; Flurry of Blades (deal 1 to all units at battlefields) kills Scuttle
  Crab outright at 0 Might; anything that goes wide makes the "defends alone"
  bonus and Lonely Poro stop working
tech_against: mass damage and cheap bounce; forcing multiple blockers turns off
  the Legend
strength_computed: rune base is well tuned. Only 18 Power pips across the whole
  deck (Body 11, Calm 7) against a 7/5 rune split — 1.6 and 1.4 pips per rune.
  25 of 40 copies have no Power cost at all. This deck is close to always able
  to cast what it draws, which is what lets it curve out so aggressively.
confidence: high on plan and rune math, medium on matchups
updated: 2026-07-27

## Sivir Ramp

legend: Sivir - Battle Mistress
identity: Body+Chaos
speed: slowest deck here; average cost 3.62 with six top-end cards at 9-12 energy
plan: Channel extra runes with Catalyst of Aeons, Mobilize and Treasure Trove,
  then deploy something the opponent cannot answer. Dazzling Aurora (3x, 9 energy)
  puts a free unit into play at the end of every turn; Elder Dragon (3x, 12
  energy) kills any enemy unit with any amount of damage. The Legend converts
  rune recycling into Gold gear and readies whenever an enemy unit dies.
key_cards: Dazzling Aurora, Elder Dragon, Catalyst of Aeons, Treasure Trove,
  Mobilize, Mindsplitter
strong_vs: attrition and grind — nothing else in this group produces a threat at
  Elder Dragon's scale, and Flurry of Blades sweeps the token-and-2-Might boards
  that Darius and Master Yi rely on
weak_to: pressure before the ramp arrives. Only 6 units in the entire main deck,
  so the early turns are close to defenceless; gear hate is unusually punishing
  here because 10 gear is part of the mana engine, not just value — Thermo Beam
  (kill all gear) is close to a blowout
tech_against: Thermo Beam, Acceptable Losses, Factory Recall, Disarming Rake —
  all already present in this field's sideboards, which suggests this deck is
  being actively prepared for
weakness_computed: the heaviest Power requirement in the field — Body needs 20
  hard pips against only 6 Body runes (3.3 per rune). Almost all of it is the
  top end: Dazzling Aurora (P2 x3) and Elder Dragon (P4 x3) alone account for 18
  of those 20 pips. The ramp package is not just about reaching 9-12 Energy, it
  has to assemble Body power at the same time, and that is a second failure
  point the Energy curve alone does not show.
confidence: high on plan, medium-high on the gear vulnerability, medium on
  matchups
updated: 2026-07-27

## Darius Legion

legend: Darius - Hand of Noxus
identity: Fury+Order
speed: midrange; wants two cards a turn from turn 2
plan: Play a second card every turn to switch on [Legion]. Noxus Hopeful costs 2
  less, Trifarian Gloryseeker buffs itself, Vanguard Captain adds two Recruit
  tokens, and Darius - Trifarian readies and grows on the second card played.
  The Legend itself adds energy under Legion, which is what makes double-spelling
  affordable. Backed by the most removal of any deck here — Hidden Blade, Falling
  Star, Imperial Decree, Vi - Peacekeeper.
key_cards: Noxus Hopeful, Vanguard Captain, Trifarian Gloryseeker, Hidden Blade,
  Vi - Peacekeeper, Darius - Trifarian
notes: Twenty of forty cards cost exactly 2 energy. That is not an accident; it
  is what makes the two-cards-per-turn Legion plan reliable.
strong_vs: single-threat decks, because it has the deepest removal suite here and
  Vi - Peacekeeper stuns on attack — Master Yi's solo plan runs directly into it
weak_to: sweepers and mass damage. The Ruination and Cull the Weak (Lux) and
  Flurry of Blades (Sivir) all punish a wide board of 1-Might Recruit tokens and
  2-Might bodies; Gust bounces most of the curve
tech_against: any effect that hits multiple small units at once
weakness_computed: the second-most Power-hungry deck here. Order demands 21
  hard pips against 7 Order runes (3.0 per rune) while Fury needs only 7 against
  5 (1.4). The 5/7 split is directionally right but Order is still stretched;
  Hidden Blade, Vanguard Captain, Vi - Peacekeeper and Imperial Decree all want
  Order power in the same turns Legion wants a second card played.
confidence: high on plan and rune math, medium on matchups
updated: 2026-07-27

## VEN — Azir Equipment Soldiers

legend: Azir - Emperor of the Sands
identity: Calm+Order
speed: fast; average cost 2.33, twenty-eight cards at 1-2 energy
prevalence: top 4 of a 100-player Vendetta event (placement not recorded)
plan: The board is made of tokens, not cards. Only TWO units are in the main
  deck; everything else is Equipment and cheap spells. The Legend plays a 2 Might
  Sand Soldier for 1 energy on any turn you played an Equipment, and Arise!
  (3x signature) plays a Sand Soldier FOR EACH Equipment you control and readies
  two of them. With 16 gear in the deck that is a board out of nowhere. Azir -
  Sovereign then moves every token to whichever battlefield he attacks.
key_cards: Arise!, Azir - Sovereign, B.F. Sword, Eye of the Herald, Hidden Blade,
  Deathgrip
strong_vs: decks that answer units one at a time — the tokens arrive in a batch
  and cost no cards
weak_to: mass damage and board sweepers; the tokens are 2 Might, so anything
  dealing 2 or giving -2 Might clears the whole board at once
tech_against: sweepers, and gear removal (16 gear is the deck's engine, not just
  value — Brittle Steel and Thermo Beam are close to blowouts)
notes: Deathgrip turns a token into damage on a real unit and draws. Hidden Blade
  is unconditional instant-speed removal at 2 energy. This deck is not a durdly
  token deck; it interacts.
confidence: high on plan, medium on matchups
updated: 2026-07-28

## VEN — Kai'Sa Burn Control

legend: Kai'Sa - Daughter of the Void
identity: Fury+Mind
speed: slowest in the field; average cost 3.58, twelve cards at 6+ energy
prevalence: top 4 of a 100-player Vendetta event (placement not recorded)
plan: Point damage at everything until the board is empty, then win with the
  biggest threats in the format. The Legend adds a rune usable only on spells,
  which subsidizes a deck that is 20 spells deep. Thousand-Tailed Watcher (3x,
  7 energy, 7 Might) gives ALL enemy units -3 Might on arrival, which is a
  one-sided sweeper against small boards. Time Warp (2x) takes an extra turn.
key_cards: Hextech Ray, Falling Star, Thousand-Tailed Watcher, Singularity,
  Unchecked Power, Time Warp
strong_vs: any deck whose board is made of small units or tokens. This is the
  single most punishing deck in the field for cheap bodies — see the damage
  breakpoints below
weak_to: fast pressure before the expensive half comes online; only 7 cards cost
  1, and the deck wants to reach 6-10 energy
tech_against: units that cannot be chosen by spells (Ruin Runner, Pouty Poro's
  Deflect); pressure that ends the game before turn 6
damage_breakpoints: Hextech Ray 3 damage for 1 energy. Falling Star 3 twice for
  2. Bellows Breath 1 to three units, repeatable. Thousand-Tailed Watcher -3
  Might to all enemies. Singularity 6 to two units. Unchecked Power 12 to ALL
  units at battlefields. Void Gate battlefield adds +1 bonus damage to spells
  affecting units there. Any board of 3-Might-or-less units is in range of
  almost every card in this deck.
confidence: high on plan and breakpoints, medium on matchups
updated: 2026-07-28

## VEN — Master Yi Solo Aggro (Vendetta build)

legend: Master Yi - Wuju Bladesman
identity: Body+Calm
speed: fastest deck in the field; average cost 2.17, sixteen 1-drops
prevalence: top 4 of a 100-player Vendetta event (placement not recorded)
plan: Unchanged from the pre-Vendetta list — attack with one unit and make it
  unprofitable to block, protected by counterspells rather than by extra bodies.
  The Vendetta build adds 3x Sabotage (strip a non-unit card from their hand)
  and moves Ruin Runner to the maindeck.
key_cards: Punch First, Rengar - Trophy Hunter, Ruin Runner, Sabotage, Defy,
  Zhonya's Hourglass
strong_vs: decks relying on targeted removal — Defy, Twilight Shroud, Zhonya's
  Hourglass and Ruin Runner all protect the single threat
weak_to: going wide. The Legend only grants +2 Might while a unit "defends
  alone", and free chump blockers blank the whole plan
tech_against: cheap disposable bodies; anything that forces multiple blockers
changes_from_pre_vendetta: 3x Sabotage main (was 1x), 2x Ruin Runner main (was
  sideboard), Seat of Power replaces The Arena's Greatest, Rampage added.
confidence: high on plan, medium on matchups
updated: 2026-07-28

## VEN — Kennen Movement Value

legend: Yordle, Kennen - Heart of the Tempest
identity: Order+Chaos
speed: midrange; average cost 2.65
prevalence: top 4 of a 100-player Vendetta event (placement not recorded)
plan: Every unit is paid for movement — Traveling Merchant draws, Treasure Hunter
  makes gear, Shadow Order Disciple grows — and Ride the Wind (3x) both moves and
  readies. The Legend empowers whenever you play a card from anywhere other than
  hand, which the deck does constantly via [Flow] and Fizz - Trickster. Filling
  the trash is a resource: Rhasa the Sunderer costs 1 less per card in the trash
  and routinely lands far below its printed 10.
key_cards: Ride The Wind, Traveling Merchant, Treasure Hunter, Fizz - Trickster,
  Nocturne - Horrifying, Rhasa the Sunderer, Lightning Rush
strong_vs: grindy decks — it generates value every turn without spending cards,
  and recurs spells from the trash
weak_to: pressure while it sets up; the payoff cards are 3-4 energy and the
  finisher needs a full trash
tech_against: trash hate; forcing it to act before turn 4
notes: 9 Chaos / 3 Order is the most lopsided rune split in the field, which
  works because Order appears almost entirely on hybrid or Power-free cards.
  Gust (2x), Star-Crossed (2x) and Rebuke give it six bounce effects — relevant
  against small and token boards.
confidence: high on plan, medium on matchups
updated: 2026-07-28

## Lillia Sprite Tempo

legend: Lillia - Bashful Bloom
identity: Calm+Mind
speed: fast tempo; conquers nearly every turn, does not hold
prevalence: unknown — but two independent tournament-adjacent lists exist
  (decks/meta/lillia-sprite-tempo-netdeck.txt, Vendetta-era, and
  decks/meta/lillia-galewinds-unleashed.txt, the Unleashed Vancouver list it
  descends from; the latter still runs the now-banned The Arena's Greatest)
plan: Print ready 3-Might Temporary Sprites (Legend ability, Sprite Fountain,
  Sprite Burst) and conquer with them every turn, supported by 15+ cheap
  tricks (Stupefy, Discipline, Defy, En Garde). Tokens are spread one per
  battlefield, so alone-payoffs (En Garde, Mask of Foresight) are live. Heart
  of Dark Ice makes one token a 6M problem each combat. Finishes by racing to
  6 points then double-conquering with Sprite Burst (which satisfies the
  final-point conquer restriction by scoring every battlefield in one turn).
key_cards: Sprite Fountain, Sprite Burst, Ravenbloom Student, Defy,
  Mask of Foresight, Riptide Rex, Smoke and Mirrors
strong_vs: slow spell decks with little action-speed interaction — per the two
  Lillia guides, Pyke/Jhin-style shells — the token stream outpaces reactive
  removal because every dead token is a card the opponent spent on nothing
weak_to: established holds it cannot crack (big Tank/Deflect holders); Vex -
  Apathetic specifically (see HEARSAY entry — stuns every unit its opponent
  plays, and the deck's whole plan is playing ready tokens); sweepers are
  survivable card-economically but stop the point clock
tech_against: kill the payoff gear (Sprite Fountain, Heart of Dark Ice);
  settle a fat holder early and make every conquest a bad combat
notes: Gale Winds (the archetype's defining pilot) runs ZERO copies of the
  signature Lilting Lullaby — the race shell cannot afford holding 2E+2 runes
  reactively. Sideboard doctrine from the same guide: no silver bullets, keep
  a going-first plan (extra cheap unit) and a going-second plan (extra Smoke
  and Mirrors).
confidence: high on plan (two real lists + pilot interview), none on matchups
updated: 2026-07-31

## LIST — Ezreal Spell Velocity

legend: Ezreal - Prodigal Explorer
identity: Chaos+Mind
speed: midrange control; average cost 2.70, 26 of 40 copies are spells
prevalence: unknown — list supplied 2026-08-06, no event or finish recorded
plan: Make spells cheap, then cast several a turn and get paid for each one.
  The Legend exhausts for a [Reaction] Draw 1, usable only if you have chosen
  enemy units and/or gear TWICE this turn with spells or abilities — so the
  deck is built from cheap targeted spells (Stupefy {1}, Frigid Touch, Bellows
  Breath, Wages of Pain) specifically to turn the Legend on every turn.
  Applied Researchers (3x) Empowers for {3} and then makes every spell cost
  {1 energy}{any rune} less; Ezreal - Prodigy discounts optional additional
  costs ([Repeat], [Flow], [Accelerate], [Equip]) by {1 energy} or {any rune}.
  Card flow is 10 draw effects plus 12 recursion effects — Dredge Up and Up
  from the Deep both have [Flow] and get cast twice, and Fizz - Trickster
  replays a spell of Energy cost {3} or less out of the trash.
key_cards: Applied Researchers, Ezreal - Prodigy, Fizz - Trickster, Dredge Up,
  Up from the Deep, Wages of Pain, Vex - Apathetic
battlefields: Void Gate (spells/abilities affecting units here deal +1 bonus
  damage — turns Bellows Breath into 2-to-three-units and Wages of Pain into
  4), Sigil of the Storm (conquer here, recycle a rune), Frozen Fortress
  (1 damage to every unit here each Beginning Phase)
strong_vs: STRUCTURAL INFERENCE, not observed. Boards of 1-2 Might bodies —
  Bellows Breath at Void Gate deals 2 to three units for {1}{P1}, and 2x Vex -
  Apathetic maindeck stuns every unit an opponent plays while she stands at a
  battlefield
weak_to: STRUCTURAL INFERENCE. Only 14 units, three of them 1-of; the deck
  answers threats but does not pressure, so a resilient board that ignores
  small damage outruns it. Its own Tentacle tokens (1 Might, from Up from the
  Deep) die to its own Frozen Fortress
tech_against: gear (Turn to Dust main + sideboard, 3x Pickpocket sideboard);
  hand disruption in the board (Mindsplitter)
notes: This is the FIRST recorded list running Vex - Apathetic maindeck. The
  HEARSAY entry below calls Vex the worst enemy of Lillia Sprite Tempo; a real
  list now plays two. Read those two entries together.
confidence: high on plan (list + verified card text), NONE on matchups or
  prevalence
updated: 2026-08-06

## LIST — Irelia Ready-and-Move Tempo

legend: Irelia - Blade Dancer
identity: Calm+Chaos
speed: fast tempo; average cost 2.27, 27 of 40 copies at 1-2 runes
plan: Untap the same unit over and over. The Legend reads "when you choose a
  friendly unit, you may exhaust me and pay {any rune} to ready it," and
  "when you conquer, you may pay {1 energy} to ready me" — so every cheap
  buff that CHOOSES your own unit (Discipline, En Garde, Defiant Dance) is
  also a free ready, and conquering refunds the Legend for the next one.
  Irelia - Fervent closes the loop: [Deflect], and "when you choose or ready
  me, give me +1 Might this turn," so each activation grows her twice over.
  The movement half — Stellacorn Herder (draw on move), Ride the Wind (move
  and ready), Tideturner (swap two friendly units' locations) — repositions
  the single threat to wherever the point is.
key_cards: Irelia - Fervent, Defiant Dance, Discipline, Ride The Wind,
  Tideturner, Stellacorn Herder, Zhonya's Hourglass
prevalence: unknown — list supplied 2026-08-06, no event or finish recorded
battlefields: Targon's Peak (conquer here, ready 2 runes at end of turn — this
  is the deck's fuel line, because every Legend activation costs {any rune});
  Sunken Temple (conquer with a 5+ Might unit, pay {1} to draw 1 — Fervent
  gets there after two buffs); Abandoned Hall (playing a spell may give a unit
  here +1 Might — symmetric, but this deck casts 23 spells)
strong_vs: STRUCTURAL INFERENCE. Decks that answer a threat by blocking it,
  since readying means the same unit defends after attacking
weak_to: STRUCTURAL INFERENCE. Same structural weakness the file already
  records for Master Yi — only 12 units, so going wide beats one big body.
  Also rune-starved: every Legend ready costs a rune on top of the spell, and
  the deck has no ramp beyond Find Your Center and Targon's Peak
tech_against: cheap disposable blockers; rune denial; sweepers hit its 12-unit
  board hard
data_gap: Boots of Swiftness (2x) and Guardian Angel (1x) have NO attached
  ability text in data/cards.json — only the [Equip] line is recorded. Do not
  claim what those two gear do until the card data is fixed.
confidence: high on plan, NONE on matchups or prevalence
updated: 2026-08-06

## LIST — Rek'Sai Assault Aggro

legend: Rek'sai - Void Burrower
identity: Fury+Order
speed: aggro; average cost 2.42, 25 of 40 copies castable at 2 runes
prevalence: unknown — list supplied 2026-08-06, no event or finish recorded
plan: Cheap bodies that hit far above their printed Might while attacking,
  refuelled by conquering. The Legend exhausts on conquer to reveal the top 2
  and play one; Void Rush (2x, the signature) does the same for {2}{P1} with a
  {2 energy} discount. Rek'Sai - Breacher is what makes that a tempo engine
  rather than card advantage: "friendly units played from anywhere other than
  a player's hand have [Accelerate]," so anything hit off a reveal enters
  READY. Undertitan is built for it — "as I'm revealed from your deck, [Add]
  {2 energy}." The buff package is all Assault (+Might only while attacking):
  Blood Rush (3x, [Repeat]), Cleave (2x), Daring Poro, Inferna, Breacher
  itself. 25 units is the most unit-dense list in this file.
key_cards: Rek'Sai - Breacher, Void Rush, Undertitan, Blood Rush, Inferna,
  Noxus Hopeful, Falling Star
battlefields: Forbidding Waste (a unit defending ALONE here has -2 Might),
  Hall of Legends (conquer here, pay {1} to ready your Legend — a second
  reveal in the same turn), Seat of Power (conquer, draw 1 per other
  battlefield you control)
strong_vs: STRUCTURAL INFERENCE, but a hard one: Forbidding Waste directly
  cancels the Master Yi Legend, which grants +2 Might to a friendly unit
  defending alone. -2 and +2 net to zero, and the whole Master Yi plan is one
  unit defending alone
weak_to: STRUCTURAL INFERENCE. Sweepers and mass -Might. Average Might at 2
  energy is 1.6, so the VEN Kai'Sa entry's damage breakpoints apply to
  essentially this entire board (Thousand-Tailed Watcher's -3 Might alone
  clears it). Assault buffs are also blank on defence
tech_against: anything that stops the conquer trigger, since both the Legend
  and two of three battlefields only pay out on conquer
confidence: high on plan, NONE on matchups or prevalence
updated: 2026-08-06

## LIST — Viktor Token Attrition

legend: Viktor - Herald of the Arcane
identity: Mind+Order
speed: slow control; average cost 2.62, 17 removal-flagged copies
prevalence: unknown — list supplied 2026-08-06, no event or finish recorded
plan: An endless supply of free bodies feeding an unusually deep removal suite.
  The Legend makes a 1 Might Recruit token for {1} and an exhaust EVERY turn;
  Viktor - Leader makes another whenever a non-Recruit unit you control dies.
  The deck then converts those bodies into cards and damage: Shadow's Call
  (give a friendly unit [Temporary], draw 2), Escaped Grayback ([Empower] by
  killing a friendly unit), Blood Money (kill a ≤2 Might unit; a FRIENDLY one
  makes two Gold tokens), Carrion Dredger ([Deathknell] leaves a 1 Might
  [Deflect] Bird). Sprite Fountain is two ready 3 Might Sprites per copy — it
  makes one on play and repeats on its own [Deathknell]. Xin Zhao - Vigilant
  enters ready whenever two other units are in base, which the token stream
  guarantees.
key_cards: Viktor - Leader, Sprite Fountain, Imperial Decree, Hidden Blade,
  Shadow's Call, Xin Zhao - Vigilant, Vi - Peacekeeper
combo: Imperial Decree (3x, {5}{P2}: "when any unit takes damage this turn,
  kill it") plus Bellows Breath (3x, 1 damage to up to three units at a
  location, [Repeat]) is a two-card unconditional wipe that ignores Might
  entirely. It is SYMMETRIC — it kills Viktor's own damaged units too, which
  is precisely why the deck wants replaceable tokens. Wages of Pain (3x) and
  Void Gate's +1 bonus damage feed the same line.
battlefields: Void Gate (+1 bonus damage from spells/abilities — Bellows
  Breath becomes a 2-damage sweep), Rockfall Path (units can't be played
  here at all), Forbidding Waste (-2 Might to a unit defending alone)
strong_vs: STRUCTURAL INFERENCE. Single-threat decks — 17 removal copies plus
  3x Vi - Peacekeeper stunning on attack, against a plan that has one body
weak_to: STRUCTURAL INFERENCE, though this one is arithmetic rather than a
  matchup guess. 20 hard Order pips across only 7 Order runes (2.9 per rune), 26
  runes leaving the pool if every copy is cast. That is the fourth-heaviest
  rune load in this file, just under Darius (3.0 Order). Only 17 of 40 copies
  are castable off any rune. It cannot deploy and hold up interaction in the
  same turn nearly as often as its card quality suggests
tech_against: rune denial and pressure that punishes a tapped-out turn; gear
  hate is nearly blank here (4 gear, one of them a 1-of)
confidence: high on plan and rune math, NONE on matchups or prevalence
updated: 2026-08-06

## HEARSAY — NA circuit threats named in the two Lillia guides

The entries below have NO lists behind them. Source: two guide transcripts
(one Vendetta-era video guide, one interview with Gale Winds about the
Vancouver/Pittsburgh circuit, recorded at the Unleashed/Vendetta boundary).
They are a watch-list, not matchup data. Card text cited below IS verified
against data/cards.json; everything else is what the guides said. None of
these appear in the recorded VEN event's top 4 — the scenes may simply
diverge. Do not base maindeck slots on these; sideboard consideration only.

### HEARSAY: Vex Apathetic hold shells

key_cards: Vex - Apathetic (verified text: Chaos champion, E4 M4, [Deflect];
  "When an opponent plays a unit while I'm at a battlefield, [Stun] it. They
  can't move it this turn.")
why_it_matters: the stun-and-root triggers on units PLAYED anywhere while Vex
  stands at any battlefield — every freshly played ready token loses its
  conquest turn. Both Lillia guides call this the archetype's worst enemy.
verified_outs_for_lillia: Riptide Rex (ETB deal 6 kills the 4M body through
  Deflect's 1-rune tax); units played directly to an already-controlled
  battlefield don't need to move (rule 355.2.a) so LeBlanc-field
  reinforcement still works; tokens played LAST turn move and conquer freely
  — Vex costs each token one turn, it is not a hard lock.
updated: 2026-07-31

### HEARSAY: Zed / Rhasa trash midrange

key_cards: Rhasa the Sunderer (verified: Chaos, E10 P1 M6, costs 1 less per
  card in your trash)
why_it_matters: Gale describes these as ordinary midrange decks that fill the
  trash and land a cheap Rhasa — structurally adjacent to the RECORDED
  VEN Kennen Movement entry, which runs the same finisher. If faced, the
  Kennen entry's analysis is the better guide.
updated: 2026-07-31

### HEARSAY: Kayle scaling threat decks

key_cards: Kayle, Justified (verified: Order champion, E3 M3, stacks Empower
  up to three times for +2M each; at three stacks gains [Deflect 3] and
  [Ganking])
why_it_matters: a single unit that outgrows the 3-4M token wall and moves
  battlefield-to-battlefield. Gale's answer was a third Charm (move it away
  from where it matters); displacement beats removal here since the deck
  can't profitably burn a 9M Deflect-3 body.
updated: 2026-07-31

### HEARSAY: other named-but-unverified shells

notes: "Pyke and Jhin spell decks" (called good matchups FOR Lillia tempo),
  "Draven aggro-hold", "Aurora decks" (Gale calls current Jayce "an Aurora
  bot"), and First Mate shells (verified card: Body, E3 M3, readies another
  unit on play — the reason the old list ran Stalwart Poro as a blocker).
  Nothing else is known. Recorded here only so the names are not lost.
updated: 2026-07-31
