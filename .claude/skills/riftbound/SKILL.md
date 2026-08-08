---
name: riftbound
description: Build or review a Riftbound deck. Use when the user names a Riftbound Legend or champion and wants a decklist built, or pastes a decklist and wants it analyzed, improved, or checked for legality. Handles the card pool, deck legality, and the meta toggle.
---

# Riftbound deckbuilder

The card pool, legality rules, and statistics live in this repo as Python. You
do the reasoning; the tools do the counting. Never count cards yourself — the
validator is authoritative and you will get it wrong.

Run everything from the repo root.

## Before anything else

**1. Required reading — BEFORE looking at any cards.** Every deck build or
review starts by reading, in full, every `.txt` file in `reference/`. As of
this writing that is:

- `reference/riftbound-deckbuilding-tips.txt` — the compiled deckbuilding
  doctrine (deck ratios, rune-base method, battlefield selection, copy counts).
- `reference/riftbound_temporary_interactions.txt` — verified rulings on
  Temporary / Hidden / reaction timing. Lines that depend on these rulings must
  follow this file, not intuition.

New reference files may appear in `reference/` — read whatever is there, not
just the two above.

**Play-rate data lives in `data/staples/`** (`inclusion_all_types.csv` — domain,
card, type, inclusion %, avg copies). Consult it during the step-3 rating pass:
it is evidence where you would otherwise be guessing about what is generically
strong. Read `data/staples/README.md` first — the numbers are rune-normalised
and the raw column must not be used directly. Treat it as **a column in the
rating, never a filter that runs before it**: it records what people play, which
is a good proxy for strong and a poor proxy for correct in an unusual shell.
A card at 25% inclusion and 3 copies is a build-around; 25% at 1 copy is a flex
slot. Current format only, small sample — do not cite it as a matchup or meta
claim (that still requires `--meta` and `data/archetypes.md`). The Core Rules PDF also lives in `reference/`; its
extracted text is `data/rules.txt` (regenerate with
`pdftotext -layout reference/Riftbound-Core-Rules-*.pdf data/rules.txt`
whenever a newer PDF is dropped in — compare the `Last Updated:` date in the
txt header against the PDF filename). Skim the rules sections relevant to the
deck's mechanics via `python3 cli.py rules -s "<keyword>"` before building
around a mechanic.

Do not open the card pool, run `shortlist`, or rate a single card until this
reading is done. The reference files change how cards are evaluated; reading
them after the pool pass silently invalidates the ratings.

**2. Check the database is current:**

```bash
python3 cli.py sets
```

If `fetched_at` is more than a few days old, or a set the user mentions is
missing, refresh it (~30s):

```bash
python3 cli.py sync
```

## Deciding on the meta toggle

Every prompt-producing command takes `--meta`. It is **off by default** and you
must not turn it on silently.

- **Meta OFF** (default): you may not make any claim about matchups, tier
  placement, or what is popular. Evaluate only what card text and the computed
  statistics prove. This is the honest default, because `data/archetypes.md` is
  hand-maintained and may be empty.
- **Meta ON** (`--meta`): matchup analysis and tech-card suggestions are allowed,
  grounded *only* in the archetypes in `data/archetypes.md`. Every claim must
  name an archetype from that file. If a relevant archetype is missing, say so.

Turn it on when the user asks about matchups, "what beats this", tech cards, or
says the word meta. If they ask a matchup question and the file is empty, tell
them the file needs filling in and offer to help write entries — do not guess.

## Building a deck

1. Find the Legend — this is the primary input and what the user will normally
   give you. Names are exact; search first:
   ```bash
   python3 cli.py legends --search jinx
   ```
   Then pick the Chosen Champion from the legal options with `--champion`.

   As a fallback, if the user names only a champion unit, passing it in the
   Legend position resolves to the Legend sharing its tag and locks it in as the
   Chosen Champion. If several Legends match, the error lists them — ask the
   user which they want rather than picking one.
2. See the scale of the pool and the legal champions:
   ```bash
   python3 cli.py pool "Jinx - Loose Cannon" --champions
   ```
3. **Rate the whole pool. Every card, no exceptions.** This is the pass that
   keeps quality up, and it is not optional on a first build.
   ```bash
   python3 cli.py shortlist "Jinx - Loose Cannon" [--champion "Jinx - Demolitionist"] [--meta] --out /tmp/shortlist.md
   ```
   Despite the command name, this is **not** a filter — it prints a rating
   prompt. Do the work yourself and write your answer to `/tmp/shortlist.txt`,
   structured as:

   - **A 1-100 rating and a reason for EVERY card in the legal pool**, including
     the ones you are rejecting. A card you never mention is a card the user
     cannot overrule, so the reasoning is the deliverable. Use the range — a
     100-point scale is pointless if everything lands between 60 and 80.
     Roughly: 85+ core, 70-84 strong, 55-69 conditional, 35-54 fringe, under 35
     unplayable here.

     Depth scales with the score, but nothing is omitted:
     - **55 and up** — full treatment. Say what it does in THIS deck, what it
       competes with for the slot, and what running it costs.
     - **The 55-69 band matters most and is the easiest to get lazy about.**
       These are the cards with a narrow but real application. Name the
       specific scenario that makes the card good, don't just mark it
       situational. A 55 that is excellent in one identifiable spot is more
       useful to the user than an 80 they already knew about.
     - **Under ~50** — one line each is fine. Rate it, say why not, move on.
       Don't spend paragraphs burying cards.

   **The rating is for consideration, not selection. It produces the pile for
   the sieve in step 4, nothing more. Never build the deck by
   taking the top 40 scores.** A score measures a card in isolation; a deck
   needs curve, role balance, copy counts, and combo pieces that each rate
   mediocre alone and are essential together. Expect the final 40 to include
   cards rated in the 50s and to exclude cards rated in the 80s. When the built
   deck departs from the ranking — and it should — say where and why.
   - **Combo clusters**, named: which cards work together, what actually happens
     when they meet, and how many pieces the interaction needs. Group these
     explicitly rather than listing cards in isolation.
   - **Traps** — cards that look right for the deck and are not, with the reason
     (symmetric effects that help the opponent more, keyword mismatches, payoffs
     whose enabler is not in the identity).
   - Then the roles: payoffs, enablers, interaction, value, curve fillers,
     battlefields.

   **Never substitute `grep` for this pass.** Keyword searching over card text
   finds the cards that name a mechanic and silently misses the ones that
   matter — battlefields, generically strong bodies, and cards whose synergy is
   structural rather than lexical. Dump the whole pool and read it.

   Battlefields get the same treatment as main-deck cards — rate every legal
   one. There are far more legal ones than the pool listing makes obvious,
   because the battlefield pool is colorless and unrestricted: this is the one
   step of deckbuilding where Domain Identity does not narrow anything. Which
   three you then present is its own decision with its own rules — see
   **Choosing the three battlefields** below, and do that step deliberately
   rather than grabbing the three highest ratings.

   On **iteration** this full pass is not required — but re-run it for the
   affected slice whenever a new set is added, or whenever a change moves the
   deck's plan (a new win condition, a swapped Champion, a different scoring
   route).
4. **Build by sieve — additively, then cut.** Source:
   `reference/Deck building youtube video.txt`. Do not assemble 39 cards by
   picking winners; assemble a large pile and remove from it. Cutting is a
   *comparative* decision ("which of these two loses this slot") and rating is an
   *absolute* one; the comparison is where the real choices get made, and a deck
   built by picking never has to make it.

   **Sieve step 1 — state the game plan before you look at a single card.**
   One sentence: how this deck scores and by roughly what turn. Everything
   downstream is judged against it. If you cannot write it, you are not ready to
   build.

   **Sieve step 2 — the pile.** Go down the whole legal pool once and add every
   card meeting *either* criterion:
   - it is generically strong for the identity, or
   - it serves the stated game plan.

   Default every entry to **3 copies** as a placeholder; drop to 1-2 only where
   it is already obvious. Do not agonise here — a card you are unsure about goes
   IN, because the cut phase is where it gets judged. Expect **80-120 cards**.
   A pile under ~60 means you filtered while scanning and have pre-cut the
   interesting decisions; a pile over ~150 means the first half of your cutting
   is wasted effort.

   The 55+ band of the step-3 ratings is the natural pile. Use it directly.

   **Sieve step 3 — group by type, sort by energy.** You cannot compare cards
   for a slot until they are next to each other.

   **Sieve step 4 — lock, in this order:**
   1. **The two-drops: aim for 7-9.** This is the one hard number the reference
      gives, and it exists so you reliably have a turn-1 play. Count by **total
      cost (energy + power)**, not printed energy — that is what the rune curve
      actually charges you (`stats` prints the curve by total cost).
   2. **The game-plan core** — the cards the one-sentence plan does not work
      without.
   3. **The identity's best cards** — the ones that are strong regardless of
      plan.

   **Sieve step 5 — fill the remainder.** Every remaining slot must do one of
   exactly two jobs:
   - **fill the curve** — a cost bracket with nothing in it, or
   - **fill a capability gap** — no combat tricks, no unit removal, no gear
     removal, no card draw.

   Name which of the two each filler is doing. A card that is neither is not a
   filler, it is a leak.

   **Sieve step 6 — cut in multiple passes, getting stricter each pass.** Do not
   try to go 100 → 39 in one sweep. Take it to ~60, then ~45, then 39. The
   early passes are nearly free; spend your judgement on the last ten cuts,
   which are the deck. Say out loud what each late cut cost you.

   **Target: 39 main-deck cards + the Chosen Champion = 40.**

   **What the sieve does NOT do, and you must impose separately:** nothing in
   "remove the worst card" pushes toward curve, rune consistency, or completing
   a combo. Left alone it converges on a pile of individually strong cards — the
   exact good-stuff failure the rating pass already warns about. Cut against
   **role quotas** (N sprite sources, N answers, N cards under 3 runes), not
   against card strength.

   **Then stop.** The reference is emphatic and it is right: testing beats
   theory. Do not keep polishing a list that has never been played. Ship the
   first build, name what you are unsure about in the README's open questions,
   and let reps decide it.

   Now emit it:
   ```bash
   python3 cli.py build "Jinx - Loose Cannon" --shortlist /tmp/shortlist.txt [--champion ...] [--notes "..."] [--meta]
   ```
   Follow the prompt's output format exactly.

   **Every deck is a folder: `decks/<deck-name>/`.** One folder per deck, with
   versions inside it — never a bare `.txt` at the top of `decks/`, and never a
   new folder for a new version of an existing deck.

   ```
   decks/<deck-name>/
     README.md      index: legend/champion, the plan in one sentence,
                    which version is current, version history with WHY each
                    change was made, the BATTLEFIELD SELECTION write-up
                    (mandatory — see below), and known open questions
     v1.txt v2.txt  decklists, one per version. Keep numbering stable even if
                    versions get deleted — leave the gap and note it.
     ratings.md     the full 1-100 pool evaluation from step 3
     playstyle.md   mulligan, early/mid/late, showdown priority, and the
                    BATTLEFIELD USAGE write-up (mandatory — see below)
     patterns.md    verified rulings and sequencing rules this deck relies on,
                    with rule numbers, so they are never re-derived
   ```

   **The battlefields get written down twice, and this is not optional.** A
   deck's three battlefields are three of its 55 cards and they are the ones
   most often chosen by score and then never thought about again. Every build
   ships both halves:

   - **`README.md` — selection.** Name each of the three and its **role**
     (go-first / go-second / neutral game-1 presentation) per *Choosing the
     three battlefields* below. Answer Riot's question 2 explicitly for each —
     *what happens if the opponent has this?* — naming the specific opposing
     deck if there is one. Then list the **bench**: the next 3-6 battlefields
     considered, in preference order, with the condition that would promote
     each; and the **never-picks** for this deck, with the reason.
   - **`playstyle.md` — usage.** A "which to present, and how to play each"
     section: the Bo3 presentation order (game 1 / on the play / on the draw),
     any matchup override that changes it, and for **each** battlefield the
     concrete in-game lines — what to sequence, what it costs, and the mistake
     to avoid. "Dusk Rose Lab draws a card" is not usable; "resolve the Lab
     trigger before the Temporary trigger, and never Lab-kill your only unit
     there before the replacement is in" is.

   If the deck's three change, both write-ups change with them.

   Write the step 3 ratings to `ratings.md` **as a file**, not into the chat —
   a full pool is 300+ cards. Summarise the 55+ band and the combo clusters in
   the reply and point at the file.

   `decks/meta/` is not a deck — it holds opponent archetype lists. Leave it.

   **Deck file format (user-mandated, 2026-07-31).** Write every decklist file
   in exactly this layout — section headers on their own line, counts with no
   `x`, exact printed names, and a Sideboard section whenever one exists:

   ```
   Legend:
   1 <name>

   Champion:
   1 <name>

   MainDeck:
   3 <name>
   ...

   Battlefields:
   1 <name>

   Rune Pool:
   7 <Domain> Rune
   5 <Domain> Rune

   Sideboard:
   2 <name>
   ...
   ```

   The `Champion:` copy counts toward the 40; list only surplus copies under
   `MainDeck:`. Sideboard: 0-10 cards, domain identity applies, and the 3-copy
   limit spans MainDeck + Sideboard combined — the validator now checks all of
   this, so run `check` after any sideboard change. Build a sideboard for every
   deck intended for best-of-three (state the boarding plan per matchup in the
   README, preferring a going-first plan and a going-second plan over silver
   bullets); omit it only for pure best-of-one lists.
5. **Always validate**, and repair until clean:
   ```bash
   python3 cli.py check decks/<name>.txt
   ```
   Fix only what the errors name, then re-check. Do not hand the user a deck you
   have not run through `check`.
6. **Iterate before showing it.** A first draft is a draft:
   ```bash
   python3 cli.py critique decks/<name>.txt
   ```
   Answer every `!` flag. The two that matter most:
   - **Legend relevance** — if the Legend's ability applies to fewer than ~8
     copies, it is probably left over from an earlier version of the plan. This
     is the single most common way a deck quietly gets worse: the list improves
     card by card while the Legend's original justification expires and nobody
     re-checks it.
   - **Key piece at 1-2 copies** — if a card interacts with several others, it is
     an engine piece and wants 3.

   For a full revision pass, `python3 cli.py iterate decks/<name>.txt` emits the
   stats, combos, audit, and the step-by-step revision protocol.
7. Show the user the final list and your reasoning, including the interactions
   the deck is built to assemble and what the build costs.

Skip step 3 only for a narrow pool (under ~120 cards) or when the user asks for
something quick — then run `build` without `--shortlist`.

## Choosing the three battlefields

### The rules this rests on (verified against RUP4, 2026-07-16)

**There are two sanctioned 1v1 modes and they pick battlefields differently.**
This is the distinction the rest of the section turns on:

| | mode | how the battlefield is picked |
|---|---|---|
| **Duel** (485) | Best of 1 | Each player selects one of their three **at random** (485.5). The other two are removed. |
| **Match** (486) | Best of 3 | Each player **chooses** one (486.5). Both are placed simultaneously. |

In Match, after a game **someone won**, the two battlefields used are removed
from the match and each player must present one of their remaining two (486.5).
If a game ends with **no winner**, the battlefields presented may be re-used
(486.5.a). Best-of-five variant (486.6.a): once a player has presented all three
at least once, they may present one a second time — never a third.

So a battlefield is only "one in three, decided by luck" in Duel. Assume Match
unless the user says best-of-one: there, all three get presented across the
match, each is chosen deliberately, and each is a real slot.

**You commit the battlefield before you know turn order and before you see your
hand.** Setup runs 110-118 in this order: Legend to the Legend Zone (111) →
Chosen Champion to the Champion Zone (112) → battlefields handled per mode
(113) → shuffle (114) → **turn order determined by a fair random method (115)**
→ draw 4 (116) → mulligan up to 2 (117) → first player begins (118). Two
consequences that drive the whole selection framework:

- Game 1's presentation is **blind to turn order**. A battlefield whose value
  depends on being on the play is a coin flip in game 1.
- The presentation can never be tuned to a keepable hand — it is locked before
  the draw.

**The one mechanical asymmetry between the seats:** the player going second
channels an extra rune during their first Channel Phase (485.7, 486.7). Going
first buys tempo — first body down, first to contest. Going second buys a rune
of slack, which compounds with the tapping-out fact in the rules section below.

### Assign each of the three a role

Do not pick three battlefields; pick a **set** covering three different games.
State which is which in the deck README.

1. **Go-first / proactive.** Rewards already having a body down and contesting
   early; converts a tempo lead into points. Its floor is bad when you are
   behind, which is acceptable because you only present it knowing you are on
   the play.
2. **Go-second / reactive.** Stabilises, accelerates resources, or rewards
   catching up — it should pair with the extra rune the second player channels.
   This is the one that has to be good from behind.
3. **Neutral — the game-1 presentation.** The pick made blind. It should lean on
   your deck's structural synergy (something a generic opposing deck cannot
   exploit) while offering the opponent as little as possible, and it must not
   care who is on the play. "Blank for them, quietly good for me" beats "very
   strong for whoever is ahead."

Presentation sequence in a Bo3: neutral in game 1, then the go-first or
go-second one in games 2-3 to match the seat you are in — assuming you know the
seat by then, which is the convention flagged below.

### Two claims that are NOT in the rules — do not state them as rules

Both are widely repeated and both are plausible tournament policy or table
convention, but neither appears in RUP4:

- **"Battlefields are placed face down, then revealed simultaneously."** The
  rules say only that the selected battlefields are "placed simultaneously in
  the Battlefield Zone" (485.5, 486.5). Face-down-then-flip is how a table
  *implements* simultaneity, not printed procedure.
- **"The loser of the previous game decides who starts the next one."** Rule 115
  says turn order is determined by a fair random method agreed on by all
  players, and 486 specifies no game-2 exception. Nothing in the core rules
  grants the loser the choice.

Confirm both against the user's actual event document rather than asserting
them. The second one matters strategically: **if loser-chooses does not apply at
their event, every game is blind to turn order**, the go-first and go-second
picks become gambles rather than answers, and the neutral pick should probably
be two of the three.

### The selection questions

Riot's framework, in this order (see `reference/riftbound-deckbuilding-tips.txt`
§7, which is required reading anyway):

1. Which battlefields most support my strategy?
2. Which would be **disastrous for me if my opponent controlled them?**
3. Which are slightly better for me than for my opponent?

**Question 2 is the one people skip and it matters most.** Battlefield effects
are symmetric — they apply to both players. A battlefield that supercharges your
plan may supercharge theirs harder. Pick the ones you will *use better*, not the
ones you like.

Then, in the same pass:

- **Work out whether this deck triggers conquers or holds more, first.**
  190.4.c loses you a battlefield the moment nothing of yours is standing on
  it. A deck of persistent bodies takes a field once and holds it for six turns
  (hold triggers, 471.2.b, fire constantly; conquer triggers fire once). A deck
  of Temporary tokens or chump attackers loses the field every Beginning Phase
  and re-takes it (conquer triggers, 471.2.a, fire constantly; holds barely
  fire). Rating "when you hold here" and "when you conquer here" battlefields
  without settling this first gets the whole set wrong — and the intuitive
  answer is backwards for token decks. See rules-fact 9.
- **Prefer texts the opponent structurally cannot use.** Question 3 has a
  strongest form: a battlefield keyed to a mechanic only your deck fields
  (Temporary, Sand Soldiers, Mechs, Dragons, gear) is near-blank in their hands
  while being free value in yours. That beats a bigger symmetric effect.
- **Patch holes, don't only amplify strengths.** A draw or rune-channelling
  battlefield substitutes for main-deck slots you could not spare. Cross-check
  the deck's capability gaps from sieve step 5 — if neither of your domains
  draws cards, a draw battlefield is doing real work.
- **Cover different game shapes.** You must win with two different battlefields
  to win a match, so three near-identical picks throw away a slot.
- Battlefields are legal **sideboard** cards, and they count against both the
  10-card sideboard cap and the 3-copy limit.
- **Check the ban list BEFORE rating battlefields, not after.** Battlefields are
  wildly over-represented on it: **5 of the 10 Constructed bans (2026-07-24) are
  battlefields** — Aspirant's Climb, Obelisk of Power, Reaver's Row, The Arena's
  Greatest, The Dreaming Tree. The full list is `data/banlist.json` and
  `python3 cli.py check` enforces it across main deck, sideboard, battlefields,
  runes and Legend. Banned battlefields are the single easiest thing to leave in
  a copied list, because nobody re-reads the battlefield line. Note that
  `decks/meta/` contains pre-ban tournament lists — run `check` on any list you
  are learning from before you copy a slot out of it.

## Reviewing a decklist the user pastes

1. Save it verbatim to `decks/<name>.txt`.
2. ```bash
   python3 cli.py stats decks/<name>.txt
   ```
   If parsing fails, the error names the unresolvable lines. **Ask the user
   which card they meant** — never pick one yourself. A silently mis-resolved
   card invalidates the whole review.
3. ```bash
   python3 cli.py analyze decks/<name>.txt [--meta] [--question "..."]
   ```
   Answer the prompt it prints.

## Finding combos

```bash
python3 cli.py combos decks/<name>.txt              # interactions inside a deck
python3 cli.py combos --legend "Ornn - Fire Below the Mountain"   # across a pool
```

Run this during the shortlist step — it surfaces pairs worth building around that
are easy to miss in a 250-card list. It is a heuristic text matcher: it finds
candidates, not conclusions, so verify each against the card before you build
around it. The "Notable interactions" block at the top is the highest-value part;
it covers dual-type cards, non-token traps, and free-gear engines.

## Rules questions

The constitution in the prompts covers deck construction. For anything else —
keyword definitions, timing, combat — grep the full Core Rules:

```bash
python3 cli.py rules -s "Deflect"      # search
python3 cli.py rules 103               # a section and everything under it
```

Do not answer a rules question from memory. Look it up.

## Rules facts that change how cards are RATED

Learned the hard way (2026-07-31 Lillia build; the user caught every one of
these and was right every time). Each of them silently mis-rates whole
categories of card if you forget it. Check them against the card text of
anything you are about to score above 55.

**1. Runes needed to CAST = max(energy, power). NOT energy + power.**
A Basic Rune has two independent abilities (164.2): `[E]: Add 1 Energy` and
`Recycle this: Add 1 Power`. Recycle's cost is *only* "Recycle this" — no
ready-state requirement, and Recycle (416) is just "put it on the bottom of
the Rune Deck". So a rune already exhausted for Energy can still be recycled
for Power the same turn. `{2}{P1}` is a **2-rune, turn-1** play; `{2}{P2}` is
2 runes, not 4.

**But a Power cost IS still more expensive than its Energy number suggests** —
the extra cost is *ongoing*, not a later cast turn. That recycled rune is gone
from every following turn until re-channelled at 2/turn, so a turn-1 `{2}{P1}`
leaves you 3 runes on turn 2, not 4. Hold both facts at once:

| | runes to cast | after |
|---|---|---|
| plain `{3}` | 3 | keep all 3 |
| `{2}{P1}` | 2 | down 1 rune, every turn |

So `{2}{P1}` is *easier to cast* than a plain `{3}` and *more expensive to have
cast*. Power front-loads access and back-loads cost: an asset to tempo decks, a
real drag on long-game decks. `stats` prints both the runes-needed curve and
total deck attrition — judge the curve on the first and the grind plan on the
second.

**1b. Castable is not the same as correct — tapping out has a price.**
Only the Turn Player readies, and only on their own turn (315.1.b, 415.3.a), so
**a rune you exhaust on your turn stays exhausted through your opponent's whole
turn.** Spending is a two-turn commitment. Consequences that change both
ratings and play:

- **Emptying your pool surrenders the opponent's turn.** Counterspells, combat
  tricks, Hidden flips and Ambush units are all blank with no runes up. A deck
  holding nine reaction cards that taps out every turn holds nine dead cards.
- **Cards that enter exhausted, or have no enter-the-board impact, cost
  double** — the runes, plus the defensive posture, and they return nothing
  until your next turn. A 5-rune exhausted body on turn 3 spends five of six
  runes to do nothing this turn and nothing on defence. Rate these BELOW their
  stat line, and never sell one to the user on "it's castable on turn 3" —
  that is a fact about the curve, not a recommendation.
- **A perfectly-filled curve is a trap.** Spending your exact rune count every
  turn maximises deployment and minimises defence. Build and play for SLACK:
  decide how many runes you want live on the opponent's turn (about the cost of
  your most important reaction, plus one), then spend the rest.
- A reaction-heavy deck therefore wants a **lower curve than its rune count
  allows** — that is the real reason cheap interaction (1-2 runes) outclasses
  expensive interaction well beyond the raw rate.
- The per-turn question is never "what is the biggest thing I can afford?" but
  "does this development beat the interaction I give up?" Both answers are
  right sometimes: you cannot contest battlefields without bodies, and a turn
  spent holding up a trick that never comes is wasted too. Say which one a
  given deck's plan wants, in the README and in playstyle.md.

**2. Phase order decides whether an effect ever "carries".**
Awaken → Beginning Phase (Beginning Step, then Scoring Step) → Channel → Draw
→ Main (315). Anything that dies in the Beginning Step is **gone before your
Main Phase**. Consequence: "costs 1 less per [Temporary] unit you control"
never carries between turns, because your Temporary units died minutes ago in
the Beginning Step. Discounts like that are same-turn-sequencing effects only.
Before rating any "per X you control" payoff, ask when X actually exists.

**3. Where a token ENTERS decides forever whether it can conquer.**
A Standard Move goes Base → Battlefield or Battlefield → Base, and *that is
all* (144.4). Battlefield → Battlefield needs **Ganking** (810). A token that
dies each turn can never make a two-turn journey, so:
- token created **in base**, printed **ready** → can move out and conquer.
- token created **"here"** at a battlefield → reinforcement only, forever.
- token created **not ready** → blocker only on the turn it arrives.
Read the token-creating text for BOTH the location word and the word "ready".
Two cards with identical stat lines can be a threat and a speed bump.

**4. Tokens enter exhausted by default (185.2.d).** Only text saying "ready"
overrides it. A card making three exhausted tokens that die next upkeep makes
three *blocks*, not three attackers.

**5. Combat damage is simultaneous and equal to Might.** Equal Might = both
die and NOBODY holds the battlefield. One more Might = you kill theirs, survive
at full Might, and hold. So a +1 Might anthem is not incremental, it converts
every trade into a conquest — rate anthems (and repeatable pumps like
"Exhaust: +3 Might") far higher in any token deck than their text suggests.

**6. Cost is locked before resolution (403).** A token an ability is about to
create cannot discount that same ability.

**7. The final point has its own rule (471.1.b.1).** At 1 point from the
Victory Score, a **Conquer** only wins if you scored *every* battlefield that
turn — otherwise you just draw a card. **Hold is exempt** (471.1.a.1). So every
deck needs an explicit 8th-point plan: a real body that survives to hold, or a
same-turn double conquest. In 1v1 a double conquest needs two ready units in
**base**, since units at a battlefield cannot split up without Ganking. State
this plan in the README; a deck that scores 7 and stalls is a real failure mode.

**8. Recall the exhaust/attack asymmetry for holding:** exhausted units still
defend (defender designation is presence-based, 464.2.c.3) and still hold
(holding checks control, 469.2). Being exhausted only stops moving and
attacking.

**9. An empty battlefield is a LOST battlefield (190.4.c).** You keep control
"for as long as you have Units at that Battlefield" (190.4.a); with none there
you lose control at the following cleanup. This decides which battlefields a
deck wants:
- A deck whose bodies **persist** conquers a field once and holds it for many
  turns → **hold triggers (471.2.b) fire far more often than conquer triggers.**
- A deck whose bodies **die every turn** (Temporary tokens, chump attackers)
  loses the field every Beginning Phase and re-takes it → **conquer triggers
  (471.2.a) fire far more often than hold triggers.**
Work out which kind the deck is *before* scoring battlefields; the default
heuristic ("holds fire more") is backwards for token decks. And note that a
conquer trigger never fires while you keep the field — 469.1 requires *gaining*
control of one you haven't scored this turn.

**10. A battlefield's controller controls its abilities (190.6.a).** An
uncontrolled battlefield's abilities are run by the Turn Player (190.6.b). So
"At the start of your Beginning Phase, do X here" is only ever available to
whoever has a body standing there — which makes some symmetric-looking
battlefields effectively one-sided in a deck that always has a body there.

**11. Stun does not stop a unit from blocking.** A stunned unit contributes no
Might in the combat damage step (423.1.b), but must still be dealt damage equal
to its **full** Might to die (423.1.c), and loses the status in step 3d of the
end-of-turn cleanup (423.1.a.2). So stun effects are tempo, not removal — and
a "stun everything you play" lock (Vex - Apathetic) blanks *movement and
damage*, not the wall. Rate accordingly on both sides.

**11a. The corollary that bit this repo:** against a stun-on-play lock, a deck
whose bodies are all **Temporary** has no answer at all, because the stun wears
off at end of turn but the token dies at the start of the next Beginning Phase,
before the Main Phase — so it is never once able to move. There is no such
thing as "last turn's token." Permanent bodies eat the stun for one turn and
then act freely forever. Check this before calling any lock "a one-turn tax."

**12. Deflect costs POWER, and Power is priced by `max()`, so it is often free
in rune count.** 809.1.c: spells and abilities an opponent controls that choose
the permanent cost that much more Power *to play*, as a Mandatory Additional
Cost (356.2.a.2). A {3}{P1} spell aimed at a Deflect unit becomes {3}{P2} =
still **3 runes**; the tax lands entirely on attrition. Do not rate Deflect as
a rune-count tax. Open question worth flagging in any deck relying on it:
Deflect charges things you *play*, so whether it taxes a **triggered**
play-effect (e.g. "when you play me, deal 6") is unclear — judge check.

## NEVER enumerate candidate cards from raw `data/cards.json`

Every list of "cards worth considering" must come from the **legality-filtered
pool**, not from a direct read of the card file:

```bash
python3 cli.py pool "<Legend name>"          # the filtered pool
```
```python
from pathlib import Path
from riftbound.db import CardDB
pool = CardDB.load(Path("data")).legal_pool(legend)   # pool.main_deck, pool.battlefields
```

`legal_pool` (`riftbound/db.py`) already applies domain identity **and 103.2.d.2**.
An ad-hoc `json.load(open('data/cards.json'))` applies neither.

**Signature cards are the specific trap**, because a domain filter passes them
and the tag rule does not. 103.2.d.2: *all* Signature cards in a deck must carry
the Champion tag matching the deck's Legend — so an off-tag Signature card is
not merely unplayable, the decklist is **illegal**. In a Calm+Mind pool, five
Signature cards look legal by domain and are not: Fox-Fire (Ahri), Siphoning
Strike (Nasus), Forgefire Cape / Rabadon's Deathcrown / Shurelya's Requiem
(Ornn). Most Legends have exactly **one** legal Signature card.

The failure mode this prevents is recommending a card in prose. `cli.py check`
catches an illegal card only once it is in a decklist file — a card named in
chat is never validated. So: **if you are going to name a card to the user, it
must have come out of the pool, or be run through `check` in a scratch list
first.**

## Known `critique` false positives — do not "fix" these

The auditor is a text matcher. It cannot see:
- **Passive ability grants.** A card reading "I have all Exhaust abilities of
  friendly legends" is an engine, not an orphan.
- **Always-true conditional text.** "Enters ready if a friendly unit died
  during your Beginning Phase" is unconditional in a deck whose tokens die every
  Beginning Phase.
- **The facedown cap.** One Hidden card per battlefield, and 1v1 has two
  battlefields total — so Hidden cards legitimately cap at 2 copies even when
  the tool says "engine piece, run 3".
Record each one you hit in the deck README under a "critique false positives"
heading, so the next revision does not re-litigate it.

## How to iterate well

What produced the good revisions, in order:

1. **State the plan in one sentence.** If you cannot, the deck has no plan.
2. **Name the failure point** — the one thing that, if it does not happen, the
   deck loses — and count the cards that address it.
3. **Re-audit choices whose reason expired.** Decks improve card by card, and
   cards picked for the *original* plan stop earning their slot silently. Ask of
   the Legend, the Champion, and every engine card: what is this buying me right
   now? `critique` counts Legend relevance for you.
4. **Hunt for cards that do two jobs.** Dual-type cards count as every type they
   print; a spell that plays a unit counts as both. One card covering two
   requirements turns a three-card turn into a one-card turn.
5. **Add copies of the best line, not new lines.**
6. **State what each change costs.** A revision with no stated downside has not
   been thought through.

Verify claims about cards against the card, not against the database — the API
has been wrong at least twice (it flattens dual types and mislabels signatures).

**When the user contradicts you about a card, a cost, or a rule, go look it up
before defending your answer. They have been right every single time so far** —
including on the rune economy (max, not sum), on Battlefield → Battlefield
movement needing Ganking, and on which cards a combo actually needs. Treat a
contradiction as a signal that a load-bearing assumption is wrong, and re-check
what else depended on it: these errors propagate silently through ratings,
curve, and the written docs.

The user is a **new player** who is nevertheless playing real games. Their
playtest reports outrank theory — when they say a card felt clunky or a
sideboard card overperformed, that is the best data in the room. Ask what
happened in the game rather than re-arguing the card's text.

## Hard constraints

- **Never say what turn a card is playable without checking the rune curve.**
  You channel 2 runes a turn (3 on the second player's first turn), the Rune
  Deck is 12, and **runes needed = max(energy, power)** — see the rules-facts
  section below. `critique` prints the turn each cost bracket comes online —
  use it instead of estimating.
- 40 main-deck cards, always, unless you write a section justifying more. That
  is **39 listed + the Chosen Champion**.
- **7-9 cards needing 2 runes or fewer**, so a turn-1 play is reliable. Check it
  against `stats`, which prints the curve by runes-needed.
- **Build for rune slack, not for a filled curve.** Count the deck's
  opponent-turn cards (counterspells, reaction tricks, Hidden, Ambush) and name
  how many runes you intend to leave live on the opponent's turn. If that
  number plus your typical turn's spending exceeds the rune table, the curve is
  too high no matter how good each card is — see the tapping-out fact above.
- **Runes are a quick decision. Battlefields in a Bo3 are not.** Split the rune
  deck by where the Power pips actually are and move on. Battlefields are a
  quick decision only in **Duel** (Bo1), where the one used is picked at random
  from your three. In **Match** (Bo3) all three get presented over the match and
  each one is *chosen*, so each is a real slot with a job — assign the three
  roles per **Choosing the three battlefields**. Neither deserves the budget the
  last ten main-deck cuts get, but a trio of near-identical battlefields wastes
  the format.
- **Do not over-polish an untested list.** Per
  `reference/Deck building youtube video.txt`: testing beats theory. Once the
  deck is legal, curved, and has its capability gaps covered, ship it and put
  the remaining doubts in the README's open questions.
- Copy counts: default to 3. A 1-of needs a one-sentence reason (Unique, tutored,
  or a finisher you expect to draw into). See the copy-count doctrine in the
  prompts for the actual draw odds.
- Exact printed card names. If you are unsure a card exists, check:
  `python3 cli.py pool "<legend>" | grep -i "<name>"`.
- Never invent a card, a matchup, or a count.
