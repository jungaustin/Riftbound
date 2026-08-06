"""Prompt assembly.

These functions only build text. Nothing here calls an LLM, so the same prompts
work whether you paste them into a Claude Code session or send them to the API.
"""

from __future__ import annotations

from .analyze import DeckStats
from .copies import at_least_one, cards_seen_by_turn
from .copies import doctrine as copy_doctrine
from .db import LegalPool
from .decklist import Deck
from .meta import MetaContext
from .model import Card, render_pool
from .rules import constitution
from .validate import MIN_MAIN_DECK, Report

def at_least_one_pct(copies: int) -> float:
    return at_least_one(copies, cards_seen_by_turn(5), MIN_MAIN_DECK) * 100


DECK_SIZE_DOCTRINE = f"""\
## Deck size doctrine
Build exactly {MIN_MAIN_DECK} main-deck cards (including the Chosen Champion).
{MIN_MAIN_DECK} is the legal minimum and the correct default: the smaller the
deck, the more often you draw your best cards. If you end up above {MIN_MAIN_DECK},
you must state explicitly, in a section titled "Why this deck runs more than
{MIN_MAIN_DECK}", what the extra cards buy and why that outweighs the loss of
consistency. Never go over {MIN_MAIN_DECK} silently or by accident.
"""

OUTPUT_FORMAT = """\
## Output format
Return two things, in this order.

1. A fenced code block containing the decklist and nothing else:

```
Legend:
1 <exact printed name>

Champion:
1 <exact printed name>

MainDeck:
3 <exact printed name>
...

Battlefields:
1 <exact printed name>
...

Rune Pool:
6 <Domain> Rune
...

Sideboard:
2 <exact printed name>
...
```

Use exact printed card names from the pool given to you. Do not invent cards.
Do not abbreviate. The Chosen Champion is listed once under `Champion:` and that
copy counts toward the 40 (add `2 X` under MainDeck for three total copies).
The Sideboard section is 0 to 10 cards (omit it for best-of-one). Copy limits
span MainDeck + Sideboard combined; domain identity applies to sideboard cards
too, and battlefields are legal sideboard entries.

2. Prose reasoning, using these headings:
- Game plan (3-4 sentences: how this deck wins, and by roughly what turn)
- Core engine (the 3-6 cards the deck is actually built around, and the
  specific interactions between them)
- Card-by-card justification for every non-obvious inclusion, and the count
  chosen (why 3 and not 2)
- Legend check: how many copies in your final list does the Legend's ability
  actually apply to, and is that enough to justify the slot
- Cuts considered (3-5 cards you nearly ran, and what lost them the slot)
- Weaknesses (what this build structurally cannot do)
"""


def _pool_section(pool: LegalPool) -> str:
    parts = [
        f"## Legend\n{pool.legend.compact()}",
        f"\nDomain identity: {'+'.join(sorted(pool.identity)) or 'none'}",
        f"\n## Legal Chosen Champion options ({len(pool.champion_options)})",
        render_pool(pool.champion_options),
        f"\n## Legal main-deck pool ({len(pool.main_deck)} cards)",
        render_pool(pool.main_deck),
        f"\n## Legal battlefields ({len(pool.battlefields)})",
        render_pool(pool.battlefields),
        f"\n## Available runes\n"
        + ", ".join(sorted({c.name for c in pool.runes})),
    ]
    return "\n".join(parts)


def shortlist_prompt(pool: LegalPool, champion: Card | None, meta: MetaContext) -> str:
    """Stage 1: rate the whole legal pool, card by card, before any building.

    Deliberately NOT a filter. An earlier version asked for a 70-90 card
    shortlist; that hid the rejected cards, and a card the user never sees is
    one they cannot overrule. The rating pass is the artefact — the build reads
    from it, but the user reads it too, and disagreeing with a number is much
    easier than noticing an absence.
    """
    focus = f"\nThe Chosen Champion is fixed as: {champion.compact()}" if champion else ""
    return f"""\
You are rating the entire card pool for a Riftbound deck.

{constitution()}

{_pool_section(pool)}
{focus}

{meta.block()}

## Task
Rate EVERY card in the legal pool above from 1-100 for a deck built around this
Legend{' and Champion' if champion else ''}. Every card gets a number and a
reason, including the ones you are rejecting. Do not omit a card because it is
obviously bad — say so and score it. Do not build a deck yet.

Use the full range. A 100-point scale is worthless if everything lands between
60 and 80:

- **85-100** Core. The deck is materially worse without it.
- **70-84**  Strong. Wants a slot; competing only against other good cards.
- **55-69**  Conditional. Narrow but real application.
- **35-54**  Fringe. Playable in some build, not obviously this one.
- **1-34**   Unplayable here. Wrong identity fit, wrong speed, or anti-synergy.

Depth scales with the score, but nothing is skipped:

- **55 and up** — full treatment. What it does in THIS deck, what it competes
  with for the slot, and what running it costs.
- **The 55-69 band gets the most care.** It is the easiest band to be lazy in
  and the most useful to get right. Name the SPECIFIC scenario that makes the
  card good — "situational" is not an evaluation. A 55 that is excellent in one
  identifiable spot is worth more to the reader than an 80 they already knew.
- **Under 50** — one line each. Rate it, say why not, move on. Do not spend
  paragraphs burying cards.

Then, after the ratings:

- **Combo clusters.** Named groups of cards that work together: what actually
  happens when they meet, and how many pieces the interaction needs before it
  does anything. Group them explicitly; do not leave synergies implied by two
  cards sitting near each other in a list.
- **Traps.** Cards that look right for this deck and are not, with the reason —
  symmetric effects that help the opponent as much as you, keyword mismatches,
  payoffs whose enabler is not in this identity.
- **Roles.** Payoffs, enablers, interaction, value, curve fillers.

Battlefields are rated on the same scale as main-deck cards, not as an
afterthought. The pool is colorless and unrestricted, so it is larger than it
looks. Only one battlefield per player is live in a game, and it is presented
alone — so each is judged standalone, and one that is only good alongside
another battlefield you run is worth nothing.

Rate two things separately: raw strength, and **who it favours**. Battlefield
effects are symmetric, so score down anything the opponent uses at least as well
as you, however well it fits your plan. Then note, per battlefield, whether it
wants you on the play, on the draw, or is turn-order neutral: in a Bo3 (Match,
rule 486) you choose which of your three to present each game, so the set should
cover a go-first, a go-second, and a neutral game-1 presentation. In a Bo1
(Duel, rule 485.5) the one used is random, so all three must be independently
playable.

## The rating is for consideration, not selection
Whoever builds from this list must NOT simply take the top 40 scores. A score
measures a card in isolation; a deck needs curve, role balance, copy counts, and
combo pieces that each rate mediocre alone and are essential together. A good
final 40 will include cards rated in the 50s and exclude cards rated in the 80s.
"""


def build_prompt(
    pool: LegalPool,
    champion: Card | None,
    meta: MetaContext,
    shortlist: str | None = None,
    notes: str = "",
) -> str:
    """Stage 2: build the actual list."""
    if shortlist:
        card_section = (
            f"## Legend\n{pool.legend.compact()}\n\n"
            f"Domain identity: {'+'.join(sorted(pool.identity)) or 'none'}\n\n"
            f"## Shortlisted candidates\n{shortlist}\n\n"
            f"## Available runes\n"
            + ", ".join(sorted({c.name for c in pool.runes}))
            + "\n\nYou may only use cards from the shortlist above."
        )
    else:
        card_section = _pool_section(pool)

    focus = f"\nThe Chosen Champion is fixed as: {champion.compact()}" if champion else ""
    extra = f"\n## Additional direction from the user\n{notes}\n" if notes else ""

    return f"""\
You are an expert Riftbound deckbuilder. Build one complete, legal, competitive
deck.

{constitution()}

{DECK_SIZE_DOCTRINE}

{copy_doctrine()}

{card_section}
{focus}
{extra}
{meta.block()}

## Build synergy first, then fill

Before you choose a single card, write down:

1. **The plan.** "This deck wins by ___." One sentence.
2. **Two or three named interactions** the deck is built to assemble — specific
   cards, and what happens when they meet. Not "token synergy": "card A makes a
   body every time card B moves, and card C makes those bodies survive scoring."
3. **The failure point.** The one thing that, if it does not happen, the deck
   loses. Then make sure at least a quarter of the list protects or enables it.

Only then pick cards, and pick them to serve those three answers.

Two things to hunt for deliberately, because they are easy to miss and are worth
more than raw card quality:

- **Cards that do two jobs at once.** If your payoff has several conditions, one
  card that satisfies two of them beats two cards that each satisfy one. Check
  the printed type line — a dual-type card counts as every type it prints, and a
  spell that plays a unit counts as both.
- **More copies of your best interaction, not more different interactions.** A
  deck with one line at 3+3 copies beats a deck with three lines at 2+2 each.

## How to think
- Pick a single coherent game plan first, then fill the list to serve it. A pile
  of individually strong cards loses to a deck that does one thing well.
- Every card must answer "what is this buying me in THIS list?" If the honest
  answer is "it was good in the version I started with," cut it. That applies to
  the Legend too: if its ability applies to fewer than about 8 copies in your
  final list, you probably picked it for a plan the deck has outgrown.
- Build the rune deck against POWER pips, not against card colours. Energy is
  generic; only a Power cost demands a specific rune. Counting "how many Fury
  cards do I have" is the classic mistake and will give you a rune deck that
  answers a question nobody asked.
- Redundancy beats power for combo pieces: if the deck needs a card to function,
  run 3 or run a functional replacement.
- Be honest about the curve. Say what your turn-by-turn sequence looks like.

{OUTPUT_FORMAT}
"""


def analyze_prompt(
    deck: Deck,
    stats: DeckStats,
    report: Report,
    meta: MetaContext,
    question: str = "",
) -> str:
    """Analyze an existing decklist."""
    card_text = "\n".join(
        f"{n}x {c.compact()}" for c, n in deck.main_cards()
    )
    bf = "\n".join(f"{n}x {deck.card(name).compact()}" for name, n in deck.battlefields.items())
    runes = ", ".join(f"{n}x {name}" for name, n in deck.runes.items())
    ask = f"\n## The user specifically asks\n{question}\n" if question else ""

    return f"""\
You are an expert Riftbound player reviewing a decklist.

{constitution()}

{DECK_SIZE_DOCTRINE}

{copy_doctrine()}

## The decklist: {deck.name}
Legend: {deck.legend.compact() if deck.legend else 'NONE DECLARED'}
Chosen Champion: {deck.champion.compact() if deck.champion else 'NONE DECLARED'}

Main deck:
{card_text}

Battlefields:
{bf or '(none)'}

Runes: {runes or '(none)'}

## Legality check (computed, authoritative — trust this over your own counting)
{report.render()}

## Computed statistics (authoritative)
{stats.render()}

{meta.block()}
{ask}

## Task
Write a review with these sections:

1. **What this deck is trying to do** — read the list and state its game plan in
   3-4 sentences. If the list looks like two competing plans stapled together,
   say so.
2. **What it does well** — be specific and cite cards. Ground every claim in the
   card text or the computed statistics above.
3. **Structural weaknesses** — what the deck cannot do, derived from the list
   itself: gaps in the curve, missing interaction, rune inconsistency, combo
   pieces without redundancy, dead cards in the opening hand.
4. **Matchups** — {'for each relevant archetype in the meta context, say favoured/even/unfavoured and give the reason. Name the archetype. If an important archetype is missing from the meta context, say that rather than guessing.' if meta.usable else 'SKIP THIS SECTION ENTIRELY. The meta layer is off, so you have no basis for matchup claims. Write only: "Matchup analysis unavailable: meta context disabled."'}
5. **Suggested changes** — a specific cut-for-add list, at most 6 swaps, each
   with a one-line reason. Keep the deck at exactly {MIN_MAIN_DECK} main-deck
   cards; if you propose more, justify it under the deck size doctrine above.
6. **What NOT to change** — the parts of the list that are already correct and
   that a less careful reviewer would meddle with.

Rules for this review:
- Do not recount the deck. The counts above are computed and correct.
- The role buckets in the statistics are substring heuristics. Verify against
  card text before relying on one.
- Do not praise a card without saying what it does in THIS deck.
"""


ITERATION_PROTOCOL = f"""\
## How to revise a deck

This protocol is written down because it is what actually produced good
revisions, in this order. Work through it in order. Each step ends in a
decision, not an observation.

**1. Restate the plan in one sentence.** "This deck wins by ___." If you cannot,
that is the finding — the deck has no plan and card changes will not fix it.

**2. Name the failure point.** The single thing that, if it does not happen, the
deck loses. Usually "the payoff card needs to survive / connect / resolve". Then
count how many cards in the list protect or enable it. If the answer is under
about a quarter of the deck, that is the revision, and everything else is noise.

**3. Re-audit the cards whose reason has expired.** This is the step people skip
and it is where the biggest wins are. A deck improves card by card, and choices
made for the *original* plan quietly stop earning their slot. For each of the
Legend, the Chosen Champion, and every card you would describe as "the engine",
answer: what is this buying me RIGHT NOW, in this version of the list? The
self-audit below counts Legend relevance for you — if it is flagged, take it
seriously rather than explaining it away.

**4. Hunt for cards that do two jobs at once.** If the payoff has several
conditions, a single card that satisfies two of them is worth more than two
cards that each satisfy one. This is where a three-card combo turn becomes a
one-card turn. The combo report below lists multi-role and dual-type cards.

**5. Run more copies of the best line, not more different lines.** If one
interaction is the deck's best, the improvement is usually a fourth and fifth
copy of an enabler, not a new package. Check the draw odds before deciding: a
2-of is seen {int(at_least_one_pct(2))}% of the time by turn 5, a 3-of {int(at_least_one_pct(3))}%.

**6. Pay for it honestly.** State what the change costs — rune consistency,
curve, a matchup — and whether the trade is worth it. A revision with no stated
cost has not been thought through.

**7. Re-check legality and the numbers.** Never hand over a list that has not
been validated. The counts in this prompt are computed and authoritative; do not
recount by hand.

Rules for this pass:
- Change what the audit and your own reading justify, and no more. Rewriting the
  whole list is not iteration.
- Every cut and every add gets one line of reasoning.
- If a flag in the audit is wrong, say why it is wrong. Do not ignore it.
- Keep the deck at exactly {MIN_MAIN_DECK} cards.
"""


def iterate_prompt(
    deck: Deck,
    stats: DeckStats,
    report: Report,
    combo_text: str,
    critique_text: str,
    meta: MetaContext,
    notes: str = "",
) -> str:
    focus = f"\n## What this pass should focus on\n{notes}\n" if notes else ""
    return f"""\
You are refining an existing Riftbound deck. It already works; your job is to
make it better without losing what it does well.

{constitution()}

{copy_doctrine()}

## Current list: {deck.name}
{deck.to_text()}

## Legality (computed, authoritative)
{report.render()}

## Statistics (computed, authoritative)
{stats.render()}

## Detected interactions
{combo_text}

## Self-audit
{critique_text}

{meta.block()}
{focus}
{ITERATION_PROTOCOL}

## Output
1. A short section per protocol step 1-3: the plan, the failure point with its
   count, and anything whose justification has expired.
2. A cut-for-add table, at most 6 swaps, one line of reasoning each.
3. The complete revised decklist in a fenced code block, same format as the
   input, at exactly {MIN_MAIN_DECK} main-deck cards.
4. "What this costs" — the honest downside of the changes.
"""
