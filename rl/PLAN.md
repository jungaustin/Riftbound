# Riftbound Deep RL — Expanded Build Plan

**Status:** rules model settled with the project owner; engine build underway.
Built and tested so far:

| File | What it does |
|---|---|
| `rl/config.py` | Every v1 scope knob; curriculum victory score |
| `rl/engine/cardtable.py` | Frozen card table, 929 cards -> 44-dim features, v1-legality |
| `rl/engine/state.py` | Array-backed state, ~99k clones/sec, runes as counts |
| `rl/engine/invariants.py` | Phase 0 checks incl. both movement rules |
| `rl/engine/phases.py` | Awaken -> Ending, Temporary expiry, 190.4.c control cleanup |
| `rl/engine/combat.py` | Move declaration, Showdown, Combat, Conquer, Control (445-470) |
| `rl/engine/actions.py` | Engine API: factored `legal_actions`/`apply`, rune payment |
| `rl/engine/game.py` | Setup, driver loop, random agent |
| `rl/engine/mirror.py` | Seat relabelling; every slot classified, asserted complete |
| `rl/agents/greedy.py` | Heuristic baseline built around attacker Recall |
| `rl/viewer.py` | Text replay viewer — **and the spec for what a policy may see** |
| `rl/obs.py` | Observation encoder: canonical, attribute-based, leak-tested |
| `rl/env.py` | `RiftboundEnv` — AEC-shaped, index actions, per-seat rewards |
| `rl/vec.py` | Synchronous vector env with auto-reset; observation batching |
| `rl/nets.py` | DeepSets trunk, candidate-scoring action head, asymmetric critic |
| `rl/ppo.py` | Self-play PPO; per-seat GAE; complete-episode harvesting |
| `rl/eval.py` | Seat-swapped duels against the Phase 2 baselines |
| `rl/tests/` | 20 combat assertions; `fuzz.py` (M1 gate); `test_env.py` (Phase 3); `test_ppo.py` (Phase 4) |

**Build order (v0 = units only, no spells):** phase machine (done) -> move
declaration / Showdown / Combat (done) -> Conquer + Hold scoring (done) -> random
agent (done) -> 100k fuzz (M1 gate, **passed**) -> greedy baseline + replay viewer
(done) -> gym (done) -> PPO (done, **Phase 4 exit met**) -> **effect DSL + Reactions
(next)**. The effect DSL comes *after* combat, so its hooks are derived from what
combat actually needs rather than guessed. Keywords are flag checks, not DSL (§3).

**The agent now plays a game that is missing its interactive layer.** v0 is
units-only, so there are no `[Reaction]` windows, no `[Hidden]` plays, and
`combat.run_combat` never yields priority. Phases 5-7 (recurrence, belief,
bluffing) all measure things that only exist once those land — a belief head has
nothing to infer when the Facedown Zone is always empty. So the effect DSL is
the next real work, not more training.

**Phase 1/2/3 gates, all green.** M1: 100k random games at victory 8, invariants
on — 0 exceptions, 0 truncations, bit-identical replay under seed, 82 games/s,
first player 53.7%. Phase 2: random mirror 50.0%, greedy vs random 90.0%, greedy
mirror 50.0% (seat-swapped on paired seeds). Phase 3: the env reproduces the
engine hash for hash, and canonicalization survives two deliberately-broken
encoders as a negative control.

**One gap recorded rather than papered over.** `combat.run_combat` resolves
Combat without yielding priority, so v0 has no Showdown decision window at all.
Auto-pass is therefore untested through gameplay and is tested as a predicate
instead; `actions.apply` now raises `NotImplementedError` on the mutual-pass
resolution path rather than letting two players pass forever. Splitting
`run_combat` into a resumable state machine is the first thing Reactions need.

**Payment correction — a card needs max(energy, power) runes, not the sum.**
A Basic Rune's two abilities are independent (164.2), and Recycle carries **no
ready requirement**, so a rune already exhausted for Energy can still be recycled
for Power in the same payment. `sim/engine/actions.py:93` removes recycled runes
from the ready pool before checking Energy and therefore overcounts; it is on the
"do not copy" list. Power's real cost is **attrition** — the rune goes to the
bottom of the Rune Deck (416.1.b), so `rune_deck` is a **ring buffer**, not a
one-way stack, and a Power-heavy turn shows up as a smaller rune board two turns
later rather than as a missed cast.

Next: greedy baseline and a replay viewer, then the gym wrapper.

Supersedes the handover brief where they conflict. The brief's ML sections
(algorithm choice, state/action encoding, belief modelling, bluffing) are sound
and mostly carried forward verbatim in intent. Its **premises about the codebase
and its build order are wrong**, and that changes the plan materially.

---

## 0. Corrections to the brief's premises

Checked against the repo before planning. Four things the brief gets wrong:

**"Status: design phase, no code written yet" — false.**
`sim/engine/` is ~950 lines of a working, rules-cited referee:

| File | What it already does |
|---|---|
| `state.py` | Full zone model, the four-state calculator (Neutral/Showdown × Open/Closed, rules 308–310), phases, victory check |
| `actions.py` | Legal action enumeration with timing **and** cost filters; rune payment planner (energy generic, power domain-bound) |
| `turn.py` | Phase machine — awaken, hold-scoring, channel, draw, ending |
| `cards.py` | Card DB loader, normalization, timing-tier derivation |
| `render.py` | Per-seat views that strip the other seat's private zones |

But it was written **before deep learning was a goal**, for LLM pilots reading
prose. Its rules knowledge is valuable; its data structures are wrong for RL.

**Decision: mine it, do not build on it.** See §2.2 for the line-by-line verdict.
Treat `sim/engine/` as a rules specification that happens to be written in
Python — read it while writing the new engine, and leave it in place as the
LLM-referee tool it was built to be.

**"Do not write a card database by hand… check apitcg" — already done.**
`data/cards.json` holds 929 cards with structured `energy / power / might / type /
domains / tags / text`. The card DB problem is solved locally. Skip the repo
survey for card data. `deckgym-core` is still worth reading as an architecture
reference; `rift-sim` and `tcg-engines` are now redundant with what you have.

**"Cut the most text-heavy cards" for v1 — there is nowhere to cut to.**
Measured across all 929 cards:

- **8 cards** have zero rules text. Eight. There is no vanilla subset.
- Median text length is 75 characters *after* stripping reminder text.
- 30 bracketed keywords carry most of the mechanical load:

```
Reaction 110   Action 91   Empowered 49   Equip 49   Hidden 46
Deflect 43     Empower 39  Ganking 35     Accelerate 27  Temporary 26
Tank 25        Deathknell 24  Repeat 24   Flow 17    Assault 16
Shield 15      Stun 14     Ambush 14      Weaponmaster 12  Legion 10
Vision 10      Mighty 10   Hunt 6         Predict 4  Backline 4
```

**Consequence:** the effect system is not deferrable to v2. But the shape of the
work is better than it looks — implementing ~15 keywords plus a dozen
parameterized primitives covers most cards' *entire* text. The v1 pool selection
criterion is therefore **"text is fully expressible in the DSL"**, not "low text".

**The engine's actual gap is much narrower than "build an engine".**
What is missing, in priority order:

1. **Combat / showdown resolution — entirely absent.** `state.showdown` is a bool
   that nothing ever sets. No attack action, no showdown sub-state machine.
2. **Chain resolution — absent.** `state.chain` exists and `render.py` displays
   it; nothing ever pushes or pops it.
3. **Card effects — absent.** No resolution of anything.
4. **Conquer scoring — absent.** Only Hold is implemented (`turn.py:38`). Per your
   own notes, conquer-vs-hold is a live strategic axis; an agent trained without
   Conquer is learning a different game.
5. **Spell/ability targeting** — spells are enumerated with no target choice.

That is the 90%. But it is a *known, bounded* 90% with the scaffolding around it
already correct.

---

## 1. How to make the idea better

Nine changes, ordered by how much they improve the project.

### 1.1 Reframe: this is a deck evaluator, not a game bot

You have a deck-building toolkit — 10 deck folders, ratings, archetypes, a meta
module, a legality checker. An agent that plays one mirror match well is a
science project you'll abandon. An agent that **pilots arbitrary decks well
enough to produce matchup win-rates** is a tool you use every week, and it plugs
directly into `cli.py`.

This changes one design decision: **the deck must be an input, never baked into
the network.** The brief's "card embeddings from attributes, not one-hot IDs"
already sets this up — this reframe is what makes it load-bearing rather than
nice-to-have.

It also gives you value *before the agent is good*. Two equally mediocre agents
still produce meaningful **relative** matchup numbers, because the badness
cancels. You get a usable deliverable at Phase 4 instead of Phase 8.

### 1.2 The critic is the deck evaluator — get it for free

Set `gamma = 1.0` with terminal-only ±1 reward. The value head then learns
literal **win probability from this state**. That gives you, at no extra cost:

- a win-probability curve to plot over any replay (an incredible debugging tool),
- a state evaluator you can query for "how good is this opening hand",
- the matchup oracle from §1.1.

This is why terminal-only reward is worth the slower learning: the critic becomes
a product, not just a variance-reduction trick.

### 1.3 Shrink the victory score for early training

`VICTORY_SCORE = 8` is already a constant (`state.py:20`). Train at **3 points**
first, then 5, then 8.

- Episodes get ~3× shorter → ~3× more games/hour on the same compute.
- Credit assignment over 40 decisions is far easier than over 150.
- The strategic skeleton (contest battlefields, hold them, tempo) is preserved.

Anneal it as a curriculum. This is the single cheapest speedup available and it
costs about four lines of config.

### 1.4 Measure exploitability, not just Elo

Self-play Elo hides cycling — a rock-paper-scissors league shows flat, healthy
looking Elo while the policy spins. The honest metric:

> Freeze checkpoint C. Train a **fresh best-response agent** against frozen C for
> a fixed budget. Report the BR's win-rate.

~55% means C is near-unexploitable at that budget. ~90% means C is a rock waiting
for paper. Run this every N checkpoints. **It is the only evidence that would
justify the bluffing claim**, and without it §8 of the brief is unfalsifiable.

### 1.5 The belief head needs a baseline or it proves nothing

Before building the neural belief head, build the **card-counting baseline**:
uniform distribution over cards not yet observed, given the known decklist,
constrained by hand size. In a mirror match with fixed decks this baseline is
strong and exactly computable.

The network's belief head must **beat that baseline in log-loss**. If it only
matches it, the head learned card counting and *zero behavioral inference* — the
entire hidden-information thesis has failed, silently. Build the baseline first
so you can never fool yourself.

### 1.6 Define bluffing operationally, up front

**The brief modelled the wrong channel — or rather, only one of two.** It assumes
the tell is *open runes*. The `[Hidden]` keyword (44 cards, present in **all ten**
of your decks) says otherwise. Reminder text, quoted from the cards:

> **`[Hidden]`** — *"Hide now for {any rune} to react with later for {0 energy}."*

So there are **two independent threat channels**:

| Channel | Threat is | Visible as |
|---|---|---|
| Runes open | A `[Reaction]` paid from hand | Ready rune count |
| Facedown card | A `[Reaction]` costing **{0 energy}** | A public object at a battlefield (107.3.f) |

A facedown card threatens interaction **with no runes open at all**. An agent that
reads only rune count will systematically misread the board, and so would a human
opponent model built on the brief's assumption.

**Hidden is also the cleanest bluffing substrate imaginable**, and it is native to
the game rather than something we hope emerges:

- Hiding is a **discrete, publicly visible commitment** — the opponent sees you
  spend a rune and place a card, but not which card.
- The bluff is *constructible*: hide something you will never usefully play,
  purely to represent a threat. It costs exactly one rune.
- Ground truth is perfect in self-play — we know what was hidden and whether it
  was ever used.

That is a far better-posed emergent-bluffing experiment than "did they keep runes
open", and it is why Phase 6 targets the Facedown Zone first.

**Metrics, fixed in advance. Log all of these from the first PPO run:**

- **Hide-bluff rate** — P(a hidden card is never played before it is lost).
- **Hide-respect rate** — P(opponent declines a might-favourable Move into a
  battlefield | a facedown card is present there).
- **Rune-bluff rate** — P(end turn holding >=2 ready runes | zero affordable
  `[Reaction]` in hand). The brief's original metric; keep it, it is the second
  channel.
- **Signal strength** — mutual information between each channel (facedown present;
  ready rune count) and the opponent's move-in decision. This is the one that
  actually matters: nonzero only if the signal genuinely informs behaviour.

Watching the two respect rates diverge is also how you will detect the agent
learning one channel and ignoring the other.

### 1.7 Build the vertical slice before the complete engine

The brief says engine-complete, then ML. But its own M5 warns that a failure to
beat random is almost always a masking or encoding bug. You want to discover
those in week 2, not month 5.

So: get a **deliberately crippled but end-to-end-complete** game running into PPO
first — no chain, no spells, units and combat only. Then thicken the engine
underneath a pipeline you already trust. The order is *vertical slice first,
horizontal completeness second*.

### 1.8 Python first; Rust at Phase 8, with Python as the oracle

The brief says Rust/C++ now, TypeScript as a correctness oracle. Invert it:

- The rules model is not settled in your head yet — the open questions in §10
  (showdown vs combat, forced vs declared attacks) are proof. You will
  restructure state three or four times. Each restructure costs ~4× more in Rust.
- The throughput requirement is real but binds at **scale-up**, not at v1. With
  victory score 3 and a 20-card pool, Python gets you to "beats greedy".

Keep the **new** Python engine forever as the differential-test oracle once Rust
lands. (`sim/engine/` cannot serve as the oracle — it has no combat, no chain and
no effects. It is a spec source, not a reference implementation.)

**Write the Python engine in a Rust-shaped way from line one** — fixed-size
arrays, integer IDs, no Python objects in the hot loop, explicit `clone()`. There
is no legacy to preserve, so the eventual port becomes a transliteration rather
than a redesign. This costs almost nothing now and saves weeks later.

**Port trigger, decided now so it isn't argued later:** port to Rust when
profiling shows the engine is >60% of wall-clock at your target batch size, *or*
when a run you want to do would take >48h. Not before.

### 1.9 Source the prior from your local corpus

Section 7 of the brief says "scrape decklists" for P(card | color, archetype).
riftdecks is Cloudflare-blocked — you already know this. Use instead:
`data/staples/`, `data/archetypes.md`, `riftbound/meta.py`, and the saved pages
you parse locally. Same feature, no scraping problem.

---

## 2. Project structure

There are two halves to this project — a **deck creator** (built, LLM-assisted,
runs on the Claude Code plan) and an **RL agent** (new) — plus a third thing that
only exists if they share a repo: the **bridge**, where a trained agent scores
decks and feeds results back into the deck creator.

### 2.1 One repo. Not submodules, not a second repo.

| Option | Verdict |
|---|---|
| **Git submodules** | **No.** Submodules are for dependencies with an independent release cadence and outside consumers. What's actually shared here is data plus two small loaders. You'd buy detached-HEAD pain and stale-pointer bugs for nothing. |
| **Two repos** | **No.** `sync.py` refreshes card data, so you'd get two copies of `cards.json` drifting apart. And the bridge would straddle a repo boundary. |
| **One repo, `rl/` as a sibling** | **Yes.** |

The real concern behind "separate repos" is dependency weight — the deck creator
shouldn't need torch. That's solved by optional dependency groups, not by
splitting repos:

```toml
[project.optional-dependencies]
rl = ["torch", "numpy", "tensorboard"]
```

`pip install -e .` for deck work, `pip install -e ".[rl]"` for training.

**Do not restructure the deck creator now.** `cli.py`, `data/rules.txt`,
`data/banlist.json` and the `decks/` layout are referenced by the `riftbound`
skill, by CLAUDE.md, and by saved memory. Moving them breaks all three to
accommodate a project that does not exist yet.

Target layout — additive only:

```
Riftbound/
├── cli.py, riftbound/         # deck creator — UNCHANGED
├── data/, decks/, reference/  # shared content — UNCHANGED
├── sim/                       # LLM-referee tool — UNCHANGED, now a spec source
└── rl/                        # new
    ├── PLAN.md
    ├── config.py              # every knob from the §3 table
    ├── engine/                # new, DL-first, Rust-shaped
    ├── env/                   # gym wrapper
    ├── nets/
    ├── train/
    └── eval/
```

**Extract a shared `core/` at the moment of second use, not before.** The RL side
needs exactly two things from the existing code: the card table
(`sim/engine/cards.py`) and decklist parsing (`riftbound/decklist.py`). Import
them directly at first. When a third consumer appears, extract then.

The one condition that would justify splitting: if the engine becomes a
standalone thing other people use. That is not this year's problem.

### 2.3 Where an LLM fits, and where it must not

**The agent never reads card text.** This is the thing that makes a TCG tractable
for RL, and it is worth stating plainly because the intuition runs the other way.

- The **engine** executes what a card does, deterministically, from its DSL entry.
- The **agent** only ever picks an index into the legal action list the engine
  hands it. It does not decide *how* a card works; it decides *whether and when* to
  use one.
- A card with "many things you have to do" is not one complicated action — it is
  **several small sequential decision points**, each with its own small legal set
  (§1.3.a, brief §6). "Play card -> choose target -> choose battlefield" is three
  cheap choices, not one hard one.
- The **network** sees each card as a 44-dimension attribute vector from
  `rl/engine/cardtable.py` — cost, might, type, domains, keyword bits — never as
  English. It learns what a card is *worth* from the reward signal.

**An LLM in the training loop would break the project three ways:**

| | Why it fails |
|---|---|
| **Throughput** | Target is thousands of games/sec. An LLM call is ~100ms+. That is roughly six orders of magnitude too slow; training would never start. |
| **No learning** | An LLM is a fixed policy. It does not improve from self-play outcomes, which is the entire mechanism here. |
| **Non-determinism** | The engine must replay bit-identically under a seed. LLM sampling does not. |

**Where an LLM genuinely belongs — offline, never in the loop:**

- **Authoring the DSL entries.** Translating 929 cards of English into effect-DSL
  data is a one-time, offline, text-understanding job, and it is the single
  largest chunk of manual work in the project. This is the right use, it is a
  Claude Code job rather than an API-billed one, and it is what makes the Phase 8
  open-pool scale-up affordable.
- **Qualitative review.** The existing `sim/` LLM-referee is good for eyeballing
  whether a trained agent's line makes sense — the "is the agent playing badly or
  is the engine wrong" question that the replay viewer exists to answer.

### 2.2 What to take from `sim/engine/`

Of ~950 lines, roughly 250–300 lines of genuine rules knowledge transfer and
essentially none of the data structures.

| Piece | Verdict |
|---|---|
| Four-state calculator (`is_open` / `is_neutral` / `playable_timings`) | **Take the logic.** Correct, rules-cited, hard-won |
| `plan_payment` rules — energy generic, power domain-bound, recycled runes leave play | **Take the logic.** Real rules knowledge |
| Phase machine (`turn.py`) | **Port ~as-is.** Small and cheap |
| Timing tiers (plain ⊂ action ⊂ reaction) | **Take.** |
| `_unique()` duplicate collapse | **Take.** Good action-space idea |
| Rules citations in comments | **Take.** Genuinely the most valuable thing in the file |
| String IDs from a module-global `itertools.count` | **Drop.** Not resettable — breaks per-episode determinism |
| `location: str` = `"bf:0"`, parsed in the hot loop | **Drop.** Int enums |
| `Card` objects held by reference in zones; no `clone()` | **Drop.** `u16` indices into a static card table |
| `Action` dataclasses carrying `description` strings | **Drop.** String formatting per action, per step |
| `render.py`, `setup.py`, `make_brief.py`, `briefs/`, `REFEREE.md` | **Leave in place.** That's the LLM-referee tool, and it's good at that |

`sim/engine/cards.py` is the exception — it is deck-creator work (name
normalization, icon expansion, fuzzy lookup), not engine work. The RL engine
consumes a **frozen, compiled card table** derived from it at startup, never the
lookup logic at runtime.

---

## 3. Scope freeze for v1

Freeze these before writing any code. Re-opening scope mid-build is the main way
projects like this die.

| Dimension | v1 |
|---|---|
| Matchup | **Mirror**, one deck both seats — removes the matchup confound entirely |
| Victory score | **3** (anneal to 8 later) |
| Card pool | ≤20 uniques, every card fully expressible in the effect DSL |
| Battlefields | 2, fixed, no battlefield abilities |
| Legends/Champions | One pair, abilities disabled in v1 |
| Turn cap | 30 turns → truncate, reward 0 |
| Card text allowed | Tier-1 keywords only — see below |

**Tier-1 keyword set for v1:** `Action`, `Reaction`, `Tank`, `Shield`, `Assault`,
`Legion`, `Mighty`, `Deflect`, `Temporary`, `Backline`, **`Hidden`**,
**`Deathknell`**.

The last two are promoted deliberately, against the "keep v1 simple" instinct:

- **`Hidden` (46 cards) appears in every one of your ten decks.** There is no
  realistic deck without it, and it is the facedown-zone mechanic that Phase 6's
  entire belief experiment now rests on. Cutting it would cut the point of the
  project. It is also mechanically cheap — place a card facedown at a battlefield
  you control, reveal on a condition.
- **`Deathknell` (24 cards)** is a plain on-death trigger — one DSL hook, and it
  is common enough that excluding it distorts the card pool.

**Tier-1 keyword semantics**, extracted from the cards' own reminder text — this
is the actual v1 implementation surface, not a guess:

| Keyword | n | Reminder text | Engine work |
|---|---|---|---|
| `[Tank]` | 25 | "I must be assigned combat damage first." | Assignment ordering (1.3.b) |
| `[Backline]` | 4 | "I must be assigned combat damage last." | Assignment ordering (1.3.b) |
| `[Assault]` | 15 | "+1 Might while I'm an attacker." | Needs attacker/defender roles |
| `[Shield]` | 14 | "+1 Might while I'm a defender." | Needs attacker/defender roles |
| `[Deflect]` | 38 | "Opponents must pay {any rune} to choose me with a spell or ability." | Targeting tax |
| `[Temporary]` | 23 | "Kill it at the start of its controller's Beginning Phase, **before scoring**." | Lifecycle hook |
| `[Hidden]` | 44 | "Hide now for {any rune} to react with later for {0 energy}." | Facedown Zone (§Phase 6) |
| `[Ambush]` | 14 | "You may play me as a `[Reaction]` to a battlefield where you have units." | Reaction-speed unit play |
| `[Accelerate]` | 26 | "Pay {1 energy}{Fury rune} as an additional cost to have me enter ready." | Alternate cost |
| `[Ganking]` | 34 | "I can move from battlefield to battlefield." | Movement permission |
| `[Deathknell]` | 24 | (no reminder — on-death trigger) | Trigger hook |

Two things fall out of this table that were not obvious before reading it:

- **`[Assault]` and `[Shield]` require an attacker/defender distinction** even
  though there is no attack action. The mover is the attacker. Carry the role
  explicitly through the Showdown.
- **`[Temporary]` kills the unit *before* scoring**, at the controller's Beginning
  Phase. Combined with 190.4.c (no units = no control), a board made of Temporary
  tokens **evaporates immediately before Hold would score**. This is the
  interaction your `riftbound-conquer-vs-hold-trigger-inversion` note is about, and
  it is a trap for v1 deck choice — see below.

**Deck construction — measured, not guessed.** I scored every deck's latest
version by text complexity (unique cards, mean rules-text length with reminder text
stripped, and share of cards using a keyword outside Tier-1 or exceeding 90
characters):

| Deck | uniq | avg text | hard | hard keywords |
|---|---|---|---|---|
| lillia-sprite-fortress v1 | 19 | 68 | 21% | Deathknell, Hidden |
| lillia-protector v1 | 21 | 66 | 29% | Buff, Deathknell, Hidden, Repeat |
| ornn-swain v1 | 20 | 65 | 30% | Add, Hidden, Vision |
| diana-swain v1 | 20 | 68 | 30% | Add, Hidden, Predict, Repeat, Vision |
| lillia-sprite-conquest v2 | 19 | 70 | 32% | Accelerate, Deathknell, Hidden, Stun |
| meta ven-4-kennen | 26 | 67 | 35% | Add, Equip, Flow, Ganking, Hidden, Predict |
| lillia-fae-fawn v7 | 21 | 83 | 43% | Accelerate, Deathknell, Ganking, Hidden |
| lillia-fae-fawn-blind v5 | 28 | 85 | 43% | Accelerate, Deathknell, Hidden |
| diana-scorn-mind-chaos v2 | 20 | 90 | 55% | Add, Hidden, Predict, Vision |
| ambessa-empower v1 | 19 | 84 | 63% | Deathknell, Empower, Empowered, Flow, Ganking |

**`[Hidden]` appears in all ten decks** — further confirmation it belongs in Tier-1
rather than being cut.

**Decision: base v1 on `ornn-swain v1`.** Measured with the real compiler
(`rl/engine/cardtable.py`, which flags a card v1-legal iff every keyword is Tier-1
and its reminder-stripped text is <=90 chars):

| Deck | uniq | v1-legal | `[Temporary]` cards | substitutions needed |
|---|---|---|---|---|
| **ornn-swain v1** | 16 | 11 (68%) | **0** | **3** (+ Legend/Champion, abilities off) |
| diana-swain v1 | 16 | 11 (68%) | 0 | 3 (+ Legend/Champion) |
| lillia-protector v1 | 17 | 11 (64%) | 5 | 4 (+ Legend/Champion) |
| lillia-sprite-fortress v1 | 15 | 11 (73%) | 7 | 2 (+ Legend/Champion) |

`ornn-swain` and `diana-swain` are the only two candidates with **zero
`[Temporary]` cards**, which removes the token-evaporation trap entirely. Since v1
disables Legend and Champion abilities anyway, `ornn-swain` needs only **three**
main-deck substitutions: Crescent Strike (112 chars), Seal of Insight (`[Add]`) and
Swain, Visionary (`[Vision]`).

For context, **426 of the 929 cards in the pool are v1-legal**, so there is no
shortage of same-cost/same-might stand-ins to substitute in.

Earlier drafts recommended `lillia-protector` and then `lillia-sprite-fortress`; despite fortress scoring best on raw complexity.
Fortress is a `[Temporary]` token deck whose entire engine depends on drawing
LeBlanc ("Your `[Temporary]` effects at my battlefield don't trigger") to stop the
tokens dying at Beginning Phase before they score. That makes game outcomes hinge
on a single draw, which is terrible for v1: the agent would mostly be learning
"did I draw LeBlanc", and the win-rate signal would be swamped by variance. It also
inflates unit counts, which enlarges the 2^N move-declaration subset space (1.3.a).

`lillia-fae-fawn-blind v5` — the deck open in your editor — is mid-table at 43%
hard and 28 uniques, so it needs the most substitution work of the Lillia line.

Whichever base you pick, substitute the remaining text-heavy cards with
same-cost/same-might stand-ins whose text is fully expressible in the DSL. This
preserves a realistic curve and battlefield-contest dynamic; a synthetic
all-vanilla deck would teach the agent a game whose tempo does not resemble
Riftbound.

**Battlefields — selection is IN scope, and it is smaller than I claimed.**
Each player brings 3 and chooses one of their own (2 in play); in Bo3 a chosen
battlefield is burned for the rest of the match. I previously argued for hardcoding
2 on sparse-signal grounds. That objection was wrong, because the selection space
is tiny:

> Across a Bo3 you use each of your three battlefields **exactly once**. So a
> selection strategy is an **ordering of three battlefields** — 3 choices in game
> 1, 2 in game 2, and game 3 is forced. **Six orderings**, or a small conditional
> policy if you adapt to what the opponent has revealed.

That is not a credit-assignment problem. It is small enough to **solve exactly**
rather than learn, which is both cheaper and more useful than a policy head:

**How to do it (Phase 7.5, after the game policy is strong):**

1. **Randomize battlefield pairings during Phase 4–7 training** so the in-game
   policy generalizes across all 3x3 matchups instead of overfitting one board.
   This is the only change selection forces on earlier phases — do it from the
   start, it is free.
2. **Freeze the game policy** and simulate every (my battlefield, their
   battlefield) pairing to convergence. That is a **3x3 win-probability matrix**,
   maybe 9 x 2000 games. Cheap.
3. **Solve the Bo3 selection game by backward induction** over that matrix, with
   the burn constraint shrinking the available set each game. Game 3 is forced;
   game 2 is a 2x2; game 1 is a 3x3. If selections are simultaneous and hidden it
   is a small matrix game — solve for the Nash mixture directly, no RL needed.

**Why this is the better deliverable.** It does not just produce a policy — it
produces a **readable table** of which battlefield wants which slot, which is
precisely the go-first / go-second / neutral role question in your
`riftbound-builds-for-bo3` notes. That plugs straight into the deck-evaluator
reframe (§1.1): you get "battlefield X is your go-second pick against Fury" as an
output you can act on while deckbuilding, not just as network weights.

**Open detail:** are the two selections simultaneous-and-hidden, or does one
player reveal first? Simultaneous makes game 1 a genuine 3x3 matrix game with a
possibly-mixed solution; sequential makes it trivial. Either is easy; they just
need different solvers.

---

## 4. Phase-by-phase build

Each phase has an exit criterion. Do not start the next phase before it passes.

### Phase 0 — Scope freeze and harness (1–2 days)

1. Write `rl/config.py` holding every knob from the §3 table. Nothing hardcoded.
2. Add `sim/engine/invariants.py` — a `check(state)` asserting: points ≥ 0, no
   card in two zones, permanent locations valid, rune counts conserved, chain
   empty whenever `is_open`, and **no `move` action offered to a non-active seat**
   (Phase 1.4). Run it after **every** mutation under a debug flag.
3. Add `state_hash(state)` — a stable hash for determinism testing.

**Exit:** invariant checker runs clean over the existing `run_demo.py` flow.

### Phase 1 — Engine core (the real work, 3–6 weeks)

Order matters — each step is testable before the next.

**1.1 Effect DSL.** Cards become data, not code. An effect is an enum/dataclass
with parameters, never a closure — so it stays serializable, clonable, and
fuzzable:

```python
@dataclass(frozen=True)
class Effect:
    op: str          # "deal_damage" | "draw" | "gain_points" | "stun" | ...
    amount: int = 0
    target: str = "chosen_unit"     # selector name
    condition: str | None = None

@dataclass(frozen=True)
class Ability:
    trigger: str     # "on_play" | "on_death" | "on_conquer" | "activated" | "static"
    cost: Cost | None
    effects: tuple[Effect, ...]
```

Escape hatch: `op="native"` dispatching to a named Python function, for the tail
of cards that don't fit. Target <10% native.

**1.2 Chain.** Push spells/abilities, pass priority both ways, resolve top-down.
The four-state calculator in `state.py` already gates timing correctly — wire it
to a real chain.

**1.3 Showdown and combat.** The biggest single piece. **Rules model confirmed by
the project owner:**

> **Showdown** is the interactive decision window — playing cards and abilities.
> **Combat** is the might/damage calculation that resolves at the *end* of a
> contested Showdown. Combat is a step *of* a Showdown, not an alternative to it.
>
> **There is no "attack" action.** The atomic action is **Move** — exhaust an
> awake unit to travel to a Battlefield. **All movement is declared first**, and
> as long as the units share a destination you may move **any number of them at
> once**. One declaration produces **exactly one Showdown**. If the destination
> holds an opposing unit, the battlefield becomes Contested and the Showdown is
> initiated automatically.
>
> A turn may contain **multiple Showdowns at the same battlefield** — move one
> unit, resolve combat, then move another unit in and resolve again. That is a
> *choice*, not a requirement.
>
> **Damage:** each side **sums the Might of all its units in the Showdown into a
> single damage pool**, then deals it out among the opposing units however they
> see fit. Assignment happens **at the end** — after all Actions and Reactions,
> at the moment units are about to die — and both sides' damage is dealt
> **simultaneously**, with no priority window to kill an attacker first to save a
> defender. A unit is destroyed when marked damage >= its **current** Might. A
> **combat cleanup** step then fully heals every surviving unit **board-wide** and
> clears marked damage. Units heal again at end of turn.

Full sub-state machine:

```
MOVE DECLARATION              your turn only
   pick a destination battlefield
   pick ANY SUBSET of your awake units to send there   <- factored, see 1.3.a
   commit
 -> all declared units arrive together, exhausted
 -> battlefield becomes Contested
 -> SHOWDOWN begins                     exactly one, for the whole declared group
      priority loop, [Action]/[Reaction] timing only
      -- playable_timings() in state.py already gates this correctly --
    both players pass in succession
 -> DAMAGE ASSIGNMENT                   each side spends a POOL, see 1.3.b
 -> DAMAGE DEALT SIMULTANEOUSLY         no priority window here
 -> LETHAL CHECK                        marked damage >= CURRENT might
 -> COMBAT CLEANUP                      heal ALL units board-wide, clear damage
 -> Control resolved                    (190.4)
 -> SHOWDOWN ends
 -> ATTACKERS RECALLED if any defender survived   <- 466.1.a.2, see 1.3.e
 -> back to Main; you may declare ANOTHER move, same battlefield or elsewhere
```

**1.3.e Two rules found while implementing this, both missing from the drafts
above. Read these before touching `combat.py`.**

**(1) Attackers are Recalled if any Defender survives — rule 466.1.a.2.** The
Combat Cleanup inserts *"3d. Recall Attackers present at the Battlefield if
Defenders are still present."* So you cannot take a Battlefield by surviving
alongside its garrison: if one defender lives, **every attacking unit walks home
to base**, and since 466.1.a.1 has already healed the board, a failed attack
leaves literally no trace. There is no partial progress and no chip-away plan.
This is the single rule that most shapes the strategic layer, and it strengthens
§1.3.c rather than replacing it — the garrison question is now *"can I wipe them
outright, and does what survives hold through their turn?"*, with no middle
ground.

**(2) Vanilla combat is always decisive — and `[Stun]` is the designed escape
hatch from that.** With plain bodies, both sides surviving requires the attacker
pool to be too small to kill any defender *and* the defender pool to be too small
to kill every attacker — `SA < SD` and `SD < SA` simultaneously, where `S` is
summed Might. That is a contradiction, and `[Tank]`/`[Backline]` ordering does not
rescue it. Verified empirically: 3,000 randomized combats over the real card
table, **zero** left both sides alive.

**`[Stun]` (rule 423) is what breaks the symmetry, and it is why the Recall
exists.** A Stunned unit contributes nothing to its pool (423.1.b) but still needs
its **full** Might in damage to die (423.1.c) — so it decouples `SA` from `SD` in
exactly the way the algebra forbids. Project owner's example, now a test:

> Attack a 9-Might unit with a 5-Might unit and Stun the defender. Your 5 is not
> lethal, their 0 kills nothing, both live — and because a Defender survived,
> your attacker is Recalled and the Conquer fails.

Three details that are easy to get backwards:

- `might_for_pool()` and `might()` are **different numbers** for a Stunned unit.
  Stun stops a unit hitting back; it never makes it easier to kill.
- Stun clears at the end-of-turn cleanup (423.1.a.2), which runs at the end of
  **every** turn — so it is a one-turn combat trick, not a lasting debuff.
- A Stunned unit cannot be Stunned again (423.1.a.1), and the redundant attempt
  must not fire "when you stun" triggers. `GameState.stun()` returns that bit.

Consequences, in order of importance:

- **The Recall path is unreachable with vanilla bodies** and until effects exist
  is exercised only by a directly constructed test. Do not delete it as dead
  code — Stun makes it live.
- **Combat outcome in v0 is a closed-form function of summed Might**, so the
  policy has nothing to learn *inside* a fight. Everything worth learning is in
  the decisions *around* it: how much to commit, what garrison survives the
  reply, which battlefield, and tempo. Still a fine M1 target, but do not read
  early self-play strength as evidence the combat model works.
- **`[Stun]` is now the highest-priority entry in the first effect-DSL batch**,
  ahead of `[Shield]` and `[Ambush]`. 29 cards reference it; six are `[Action]`
  speed and therefore playable inside a Showdown. Two of those — **Back Off** and
  **Facebreaker** — are `[Hidden]` + `[Action]` + Stun, i.e. hide a card, hold it,
  and blank the biggest attacker mid-combat. That single card shape is
  simultaneously the game's canonical combat trick *and* the cleanest bluffing
  substrate available (§1.6, Phase 6), which makes it the highest-leverage effect
  in the entire pool for this project.

**(2b) Damage assignment is only a decision when you are losing.** Project owner:
*"if your might is greater than [the] enemies', you can wipe all their units and
[there is] no need to think about damage calculations. Only when losing does it
really matter to decide who to kill."* When the pool covers every target, "kill
everything" is optimal and the assignment is forced. `assignment_is_a_choice()`
detects the partial case; gate any future action-space exposure on **that**, not
on being in combat, or the action space fills with forced decisions. This also
means engine-solving it in v1 costs less than §5.3 gotcha 8 assumed — the
heuristic only ever fires in the minority of combats that are already going
badly.

**(3) Scoring is capped at once per Battlefield per turn — rules 469, 470.** Both
Hold and Conquer are gated on *"a Battlefield they did not yet Score this turn"*.
Tracked as `state.bf_scored[seat, bf]`, reset at the start of every turn. Losing
and retaking the same Battlefield within one turn is worth zero points — worth
doing for the board, never for the scoreboard.

**1.3.a Move declaration is a subset choice — factor it.**
Correcting an earlier draft of this plan: the absence of an attack step does *not*
remove the "which of my units commit" combinatorial choice. It **relocates** it
onto Move. With N awake units the raw space is 2^N per destination.

Factor it sequentially; never enumerate subsets:

```
choose destination battlefield  ->  [bf:0, bf:1, ..., CANCEL]
add a unit to the group         ->  [unit_a, unit_b, ..., COMMIT]   (repeat)
COMMIT                          ->  declaration resolves, showdown staged
```

Each step is a small legal set with its own policy call. This is exactly brief §6's
"play card -> choose target -> choose battlefield" factoring, applied to movement.

**1.3.b Damage is a pool, and healing collapses the decision to "who dies".**
Each side sums the Might of all its units in the Showdown into **one damage pool**
and spends it across the opposing units. It is not a per-unit assignment.

Naively that is an integer partition of P points across K targets. Combine it with
the board-wide heal at cleanup (1.3.d) and it collapses:

> **Damage that does not kill is worth exactly zero.** It heals away at cleanup.
> So the only rational spends are **exact-lethal** allocations.

The decision reduces to: **which subset of enemy units do I kill, subject to
sum(their current Might) <= my pool?**

**But the subset is constrained, not free.** Two Tier-1 keywords are pure
assignment-order rules (reminder text quoted from the cards):

- **`[Tank]`** (25 cards) — *"I must be assigned combat damage first."*
- **`[Backline]`** (4 cards) — *"I must be assigned combat damage last."*

So Tank units cannot be skipped to snipe something behind them, and Backline units
cannot be reached until everything else is satisfied. This is what makes Tank a
real defensive keyword, and it means the enumeration is an **ordered** knapsack:

```
resolve assignment order:  [all Tank] -> [unconstrained] -> [all Backline]
choose next unit to kill within the current tier, or STOP
```

**Implement the general pool assignment in the engine** for correctness, but
**enumerate only order-legal exact-lethal subsets** in the action list for v1,
behind a config flag. Per §5.3 gotcha 8, in v1 you can go further and let the
engine *solve* this rather than exposing it to the policy at all.

**1.3.c The real axis is the garrison, not the fight.**
Two earlier drafts of this got this wrong — first as "mass vs piecemeal", then as
"commit exactly enough". Both optimised the *current* Showdown. The project owner's
correction: winning the fight is not the objective. **Holding the battlefield
through the opponent's entire turn is**, because Hold only scores at the Beginning
Phase of *your* turn. Lose it in between and you get nothing.

So what matters is the force that **survives** your Showdown — your garrison — and
whether it outlasts everything the opponent can throw at it next turn.

Reconquest threat vectors, all of which must be modelled before this dynamic is
real:

| Vector | What it actually is (reminder text from the cards) |
|---|---|
| Units walking in | From their base — the only vector present in a vanilla v1 |
| **`[Ganking]`** (34) | *"I can move from battlefield to battlefield."* Lateral reinforcement |
| **`[Ambush]`** (14) | *"You may play me as a `[Reaction]` to a battlefield where you have units."* |
| **`[Accelerate]`** (26) | *"Pay {1 energy}{Fury rune} as an additional cost to have me enter ready."* |

**Correction — `[Ambush]` is not a facedown reveal.** An earlier draft had this
wrong. Ambush is *playing a unit from hand at Reaction speed* into a battlefield
where you already have units. It reinforces; it cannot open a new front.

**This overturns "the defender cannot join a Showdown".** That holds for
*movement* — you still cannot choose to move on the opponent's turn — but Ambush
lets a defender **play** a unit into an ongoing Showdown, adding its Might to the
damage pool mid-combat. That is a live combat trick and it is exactly the thing
open runes are supposed to threaten.

**Confirmed: ordinary movement is base <-> battlefield ONLY.** Lateral
battlefield-to-battlefield movement requires `[Ganking]`. `actions.py:113` offers
every ready unit every destination and is therefore too permissive — do not carry
that over.

This is a bigger strategic constraint than it looks, and it makes the garrison
decision (1.3.c) much weightier:

- **Commitment is sticky.** A unit at battlefield A cannot reinforce battlefield B
  at all without routing through base — two turns, and it is exposed at base in
  between. You cannot shuffle defenders laterally to meet a threat.
- **Retreat costs a full redeploy cycle**, not just the Hold.
- **The action space shrinks substantially.** Legal destinations are
  `base -> {bf_0, bf_1}` and `bf_i -> base` only. That is 2 destinations for base
  units and 1 for deployed units, versus the 3 the current enumerator offers.
- `[Ganking]` becomes a genuinely premium keyword — it is the only way to convert a
  committed unit back into a flexible one.

Since taking a battlefield requires killing **every** unit you have there
(190.4.c — control is lost only when you have none), the garrison's strength is
**total Might at that battlefield**, and the opponent needs an achievable pool that
clears it.

That makes over-committing much less bad than the previous draft claimed: extra
bodies you send are extra bodies that *survive* into the garrison. The genuine
trade-off is global, not local:

- **Too few committed** — you lose the fight, or win it and hold a garrison too
  thin to survive the counterattack. Either way, zero points.
- **Too many committed** — more bodies exposed to their pool in the initial
  Showdown, *and* your base and other battlefields are stripped of defenders,
  which is exactly what lets them take something else.

This is a **multi-turn, multi-battlefield allocation problem**, and it is the
strategic core of Riftbound. It is also why the value head (§1.2) is worth having:
"did I leave enough behind" is precisely a win-probability question and is very
hard to express as a heuristic.

**What survives into v1:** with a vanilla pool and no card text, Ganking, Ambush
and enters-readied all disappear, leaving only *units walking in from their base*.
That is still enough for the garrison dynamic to be real and learnable — the agent
must still decide how much to leave behind. Add the other three vectors at Phase 8
and expect the learned policy to shift substantially when you do; they are what
make a garrison unsafe at a distance.

**Retreat is the other half of the decision.** A **readied** unit at a battlefield
may move back to your base on your turn. That gives up the Hold, but when you are
clearly outmatched it beats handing the opponent free kills. Two rules details make
this sharper than it first looks:

- **Committing locks you in for exactly one opponent turn.** Units arrive
  exhausted, so they cannot retreat until they ready at your next Awaken. The real
  cost of over-committing is not just exposure in the Showdown — it is that those
  bodies are unavailable everywhere else until your next turn.
- **You bank the Hold point *before* you get the chance to retreat.** Phase order
  is Awaken → Beginning → Channel → Draw → Main (`state.py:18`), and Hold scores in
  Beginning (`turn.py:33`). So retreating during Main costs you the *next* turn's
  point, never the one you just collected. Retreat is therefore cheaper than it
  intuitively feels, and an agent that never retreats is leaving value on the table.

Good news for the engine: retreat needs no new action type. `_unit_destinations`
already includes `base:{seat}` and the move enumeration already requires a ready
unit (`actions.py:161`), so retreat falls out of the existing move logic for free.

**Metric to log at Phase 4:** the rate at which a conquered battlefield is still
yours at your next Beginning Phase (call it *hold-through rate*). An agent that
conquers a lot but has a low hold-through rate has learned to win fights and lose
games — and that is a failure mode you want visible early, because the win-rate
alone will not tell you which half is broken.

**1.3.d Damage does not persist.**
`Permanent.damage` is **~always 0** outside an actively resolving combat. Keep the
feature — it matters at the moment it matters — but do not be surprised when it
contributes almost nothing to the learned representation.

`turn.py:78` already heals everything at end of turn, matching the second healing
rule. The combat-cleanup heal is new and is **board-wide**, not restricted to the
contested battlefield — an easy detail to get wrong.

`Permanent.remaining` (`might - damage`) is the right shape. Lethal is checked
against **current** Might, so buffs and debuffs must resolve through an
effective-might accessor rather than reading the printed value.

**Two consequences for the rest of the design:**

- **Move is the commitment action, and it is where the bluff pressure lives.**
  "Do I commit these units while they hold two runes open?" *is* the respect/bluff
  decision (§1.6), with clean ground truth in self-play.
- **Never auto-pass inside a Showdown when a `[Reaction]` is affordable.** That is
  the entire interactive layer of the game. See §5.3 gotcha 3.

Existing move enumeration (`actions.py:157`) has the right **filters** — ready
units only, own turn only, Neutral Open only — but the wrong **shape**: it emits
one action per (unit, destination) pair rather than a group declaration. Take the
filters, rebuild the interface.

**1.4 Conquer scoring.** Rule 194.1.b. **Rules model confirmed by the project
owner:**

> You Conquer a battlefield when a unit you control **enters and remains** on a
> **neutral or enemy-controlled** battlefield **after resolving a Showdown**, or
> when you **play a card onto an empty battlefield**. This can happen on your own
> turn *or during your opponent's turn*, via effects or movement cards.

Conquer is therefore an **event that scores immediately**, not a phase-based tick.
It is structurally different from Hold in three ways, all of which matter:

| | Hold | Conquer |
|---|---|---|
| When | Beginning Phase of your turn | Immediately, on the triggering event |
| Requires | You already control it | It is neutral or enemy-controlled |
| Whose turn | Yours only | **Either player's** |

**On the off-turn case — keep it in scope, but do not build strategy around it.**
Per the project owner it is genuinely niche: it requires a spell that specifically
moves a unit during the opponent's turn, *and* then winning the resulting combat
through a trick or an opponent's miscalculation. It is a real line, not a routine
one.

So the strategic weight of a priority window on the opponent's turn is what the
brief always said it was — **combat tricks**, not scoring. Two practical
consequences:

- **The engine must support it** (correctness), but expect it to be rare in
  logged games. If it shows up often in self-play, that is a signal the engine is
  wrong, not that the agent is clever.
- **Do not expect RL to find it.** Rare, high-leverage lines are exactly what
  sparse-reward policy gradient learns worst — the sample frequency is too low for
  the gradient to see. If the v1 pool contains no movement spells it cannot occur
  at all, which is fine; it belongs to the Phase 8 open-pool work, not v1.

Two entry paths must both be implemented:

1. **Move → Showdown → survive → Conquer** (the contested path, via Phase 1.3).
2. **Play a unit directly onto an empty battlefield → Conquer** (no Showdown).
   This path is *already enumerated* by `actions.py:143` as `play <unit> -> bf:N`.
   It just never scored.

Path 2 means even the crippled vertical slice (§1.7) has real scoring dynamics
before combat exists — a genuinely useful property for getting to Phase 4 early.

**Correction to note in the code:** `turn.py:31-37`'s comment ("taking one on your
own turn scores nothing until you have held it through the opponent's turn") is
correct *about Hold* but produces a wrong game overall, because Conquer was never
implemented. Taking a battlefield scores immediately **and** scores again at your
next Beginning Phase if you still hold it.

**Confirmed: you cannot *choose* to move on the opponent's turn.** Plain
discretionary movement is strictly your-turn-only, so the existing
`state.active == seat` gate (`actions.py:157`) is correct and should be kept
exactly as it is. The **only** way a unit moves on the opponent's turn is a card
effect that moves it.

That gives a hard engine invariant worth asserting, because it is the kind of
thing a refactor silently breaks:

> `legal_actions(state, seat)` must never contain a `move` action when
> `state.active != seat`.

Keep the restriction on the *discretionary action*, not on the movement
**primitive** the DSL calls — otherwise card-driven movement (and with it off-turn
Conquer) becomes unreachable. Two different layers.

**1.5 Burn-out.** Rule 194.1.d, including the +1 point award to the chosen player.

**1.6 Engine API.** Formalize:

```python
def legal_actions(state, seat) -> list[Action]   # exists
def apply(state, action) -> None                  # mutate in place
def clone(state) -> GameState                     # for search later
def is_terminal(state) -> bool
def outcome(state) -> tuple[float, float]         # per-seat, ±1 / 0
```

**1.7 Fuzz.** 100,000 random games. Assertions: no exceptions, all terminate
within the turn cap, invariants hold every step, same seed → same
`state_hash` trace. Log the truncation rate; anything above ~2% means a stall
loop worth investigating.

**1.8 Priority windows exist during ABCD — correcting the phase machine.**
The turn runs **ABCD**: Awaken, Beginning-of-turn effects, Channel, Draw. An
earlier draft of `phases.py` asserted that all four are forced and contain no
player choice. That is true **only while no trigger fires**, and it is the
assumption the Sprite package is built to break.

Rule 335 is precise: outside the Main Phase, if there are no Outstanding Tasks,
no pending Chain Items and no Showdown, you *"proceed to the next substep"* — no
priority. But 315.2.a.1 puts start-of-Beginning-Phase effects on the Chain, and
once a Chain Item is pending the turn is in a **Closed State**, which grants
priority to both players in turn order (312.2.c, 312.2.d). So:

> **Any trigger during ABCD opens a priority window, and `[Reaction]`-speed cards
> — which includes every live `[Hidden]` card — can be played in it.**

This matters most at exactly the point the existing engine is most delicate.
`start_turn` runs `expire_temporary` -> `control_cleanup` -> `score_holds`, and
the whole conquer-vs-hold inversion lives in that ordering. **Sprite Queen** ("at
the start of your Beginning Phase, play a ready 3 Might Sprite token") and
**Trevor Snoozebottom** ("when I hold, play a ready Sprite token here") both fire
inside that window, and **Sprite Call** is `[Hidden]` + `[Action]` — a free
reaction that replaces a garrison mid-Beginning-Phase. So a Temporary board that
should evaporate before scoring can be re-garrisoned in response to its own
expiry trigger. Structure `start_turn` so a priority window is insertable between
every step, even though v0 never uses one.

**`[Hidden]` is a bigger mechanic than the drafts assumed (811.1.b).** Its full
functional text: *"While this card is in your hand or Champion Zone **on your
turn during an Open State**, you may pay {any rune} to hide this facedown at a
battlefield **you control** that doesn't already have a facedown card hidden
there, for as long as you control that battlefield. **Beginning on the next
turn**, this gains **`[Reaction]`** and you may play this, **ignoring its base
cost**."* Five consequences:

- Hiding costs exactly one rune of any domain, and is a Discretionary Action, not
  a Play — it does **not** open a chain (811.1.c.2). Playing *from* hidden does.
- It is **dead for a turn**. Hiding is a telegraphed, one-turn-delayed investment,
  which is what makes it a bluff rather than a trick.
- Once live it is **free and Reaction-speed**, so it is castable in any priority
  window on either player's turn — including the ABCD windows above.
- It is tied to a battlefield **you control**, and is discarded when you lose it
  (107.3.d, 466.5.c). Hiding is a bet on holding.
- **The locality rule is a per-target filter at finalization, not a gate on when
  the card may be played.** A live hidden card is a Reaction *everywhere* — the
  battlefield it sits at does not have to be the one under attack. Only its
  targets are constrained. Details below.

**Hidden locality, precisely (811.1.d–811.3).** Confirmed by the project owner
and pinned to the rulebook's own worked examples. Getting this wrong makes hidden
cards either unplayable or unrestricted, and both look plausible in a replay.

- **It binds targets, not playability.** A live hidden card can be played as a
  Reaction even when *a different* battlefield is the one being attacked. There
  is no requirement that its own battlefield be involved in anything.
- **The rule is applied per target slot, individually** (811.1.d.2.a) — not once
  per spell. One spell can have a local slot and a free slot.
- **A slot is free only when the card's own wording makes locality structurally
  impossible**, e.g. "at a different location", "at another location". A slot
  that merely *happens* to have nothing local right now is still a local slot —
  and then the card **cannot be played from hidden at all** (811.1.d).
- **Non-targeting instructions are unrestricted** (811.2), including the
  non-targeting half of a spell whose other half is local. *Stand United*
  ("Buff a friendly unit. Buffs give an additional +1 Might to friendly units
  this turn") must buff a local unit, but its global half hits everything.
- **If a hidden card plays a unit, that unit enters at that battlefield**
  (811.1.d.3).
- **Hidden is strictly optional upside** (811.3): the card can always be played
  from hand for full cost at normal timing with no targeting restriction.

The rulebook's own example is the one the project owner raised. *Smoke and
Mirrors* — "Choose a unit you control **and** another unit you control **at a
different location**. If at least one has `[Temporary]`, move each to the other's
location. Draw 1." Hidden at battlefield A while battlefield B is attacked:

| Slot | Wording | Locality | Result |
|---|---|---|---|
| 1 | "a unit you control" | compatible with A | **must** be your unit at A |
| 2 | "at a different location" | impossible at A | **free** — may be your unit at B |

So it swaps a unit out of the quiet battlefield into the contested one, played
from a battlefield nobody attacked. That is a reinforcement trick, and it is
reachable only because playability and target locality are separate questions.

**DSL consequence:** every target slot carries an authored `locality: local |
free` annotation. It **cannot** be derived from a runtime emptiness check —
"structurally impossible" and "currently empty" produce opposite outcomes (free
slot vs. unplayable card) and are indistinguishable at runtime. This is a second
concrete reason the DSL is a card-by-card authoring job with a review gate.

**Targeting — the spec the effect DSL must satisfy (rules 355, 359).**
Supplied by the project owner from the FAQ; this is the contract every DSL entry
has to honour, and the reason the DSL is a careful card-by-card job rather than a
text-parsing pass.

- **Targets are declared and locked at finalization** (355.8), all at once. **A
  spell with no legal target cannot be played at all** — so `legal_actions` must
  verify target availability *before* offering the play, not discover it after.
- **Reflexive triggers are the exception**: they choose targets on **resolution**,
  not at cast. Two different factorings; the DSL must distinguish them.
- **Targeting is implied, never marked.** "Kill a unit" and "Move a friendly unit"
  both target. Anything mentioned is a target unless one of six exceptions
  applies (355.10.a–f): it is in a non-public zone; it is only a location
  requirement for another target; it is part of a trigger condition, cost, or
  replacement effect; there is no real choice ("kill *all* units"); the set is
  chosen wholly or partly by other players; or the instruction uses **"must"**.
  When in doubt, it is a target. **No regex finds this** — it is why the LLM
  authoring pass needs a review gate.
- **Only words describing the target restrict it** (355.9.b). *"Kill a unit with 3
  Might or less"* can only target such a unit; *"Kill a unit **if** it has 3 Might
  or less"* targets **any** unit and checks the condition at resolution. The DSL
  needs `target_filter` and `condition` as separate fields, or half the card pool
  will be silently wrong.
- **An illegal target on resolution does not fizzle the spell** (359.3.e.5/6).
  The spell resolves; instructions tied to that target are skipped; information
  drawn from it is null and calculations using it are ignored (359.3.e.12); and
  later instructions *linked* to a skipped one are also skipped (359.3.e.14.a).
  So DSL instructions need explicit linkage, not just an ordered list.
- **`[Deflect]` couples targeting to payment.** Every enemy unit chosen is a legal
  target, so Deflect fires during finalization as a **mandatory additional cost**.
  You therefore cannot price a spell before choosing its targets: the action
  order must be *choose targets -> recompute cost -> pay*, never pay-then-target.

**Variable-arity targeting, and why it needs no new machinery.** *Alphabet
Strike* is the hard case: one friendly unit as a standard target, then **up to**
a number of enemy units equal to that unit's **current** Might — fewer is legal,
including zero. Every chosen unit is a real target, so each one's `[Deflect]`
adds cost at finalization. Damage is then distributed **at resolution**, minimum
1 per surviving target, from a pool equal to the friendly unit's Might *at that
moment* — so a buff or debuff in response rescales the pool, and a reduction
below the target count forces the subset to shrink.

That decomposes into two shapes the engine already has:

| Alphabet Strike step | Existing machinery |
|---|---|
| add an enemy target, or STOP | move declaration's add-unit/COMMIT loop (§1.3.a) |
| distribute a pool at resolution, min 1 each | damage assignment's ordered pool (§1.3.b) |

So target selection is the *same* sequential factoring as move declaration, and
resolution-time allocation is the *same* pool solve as combat damage. Build both
generically and the effect DSL inherits them. Do not write a third mechanism.

**Exit:** 100k random games, zero failures, bit-identical replays under seed.
**This is the brief's M1 gate and it is non-negotiable.**

### Phase 2 — Baselines and viewer (1 week)

1. **Random agent** — uniform over `legal_actions`.
2. **Greedy agent** — heuristic, in priority order: play a unit onto an **empty**
   battlefield (immediate Conquer, no Showdown risk); Move into a contested
   battlefield only when your might clearly wins; otherwise hold what you control
   and play the highest-might affordable unit; otherwise pass.

   The empty-battlefield line goes first deliberately — per Phase 1.4 it is free
   points, and a greedy agent that doesn't take free points is not a useful
   baseline.
3. **Replay viewer.** `render.py` already produces per-seat views; extend it to
   dump a full annotated game log to text. Text first — HTML only if text proves
   insufficient. Build it *now*, per the brief's M3.

**Exit:** random-vs-random is 50% ±2 in the mirror (seat-swapped, paired seeds);
greedy beats random ≥80%. If greedy doesn't crush random, the engine is wrong or
the heuristic is — find out here, not after training.

### Phase 3 — The gym (1 week) — see §5 for full detail — **DONE**

**Exit:** a random policy driving the env produces identical results to Phase 2's
random agent driving the engine directly. This equivalence test catches almost
every wrapper bug.

**Met, and extended.** `rl/tests/test_env.py` checks six things:

1. **Equivalence** — 200 seeds identical through the wrapper, including
   `state_hash`. The env's `_advance` deliberately mirrors `play_game`'s loop so
   any control-flow divergence surfaces here as a hash mismatch.
2. **Auto-pass** — a no-op with the flag on or off. See the gap noted at the top:
   v0 never reaches a pass-only window, so the rule is tested as a predicate.
3. **Canonicalization** — `encode(s, 0) == encode(mirror(s), 1)` byte for byte
   over 260 mid-game positions. Two deliberately-broken encoders (raw seat id in
   globals; battlefields mirrored along with seats) each fail 103/103, so the
   test is known to have teeth rather than merely passing.
4. **No leak** — rewriting the opponent's hand, deck order and facedown card
   moves not one bit of the policy observation, *and* the same perturbation does
   move `privileged`, *and* the seat's own facedown card is visible to it. The
   second and third are negative controls: without them the test would pass if
   the encoder simply dropped those zones.
5. **Mask hygiene** — prefix-shaped masks, zero padding, `A_max` holds with room
   (median 3 legal actions, max 10, cap 64).
6. **Vector env** — batched shapes agree with `Encoder.shapes()`, auto-reset does
   not leak between slots, and 12 replays match the single env exactly.

**The action space is much smaller than §5.3 gotcha 4 estimated** — median 3,
max 10 against a cap of 64. That is v0 being units-only with small hands; expect
it to grow when spells and target selection land, which is when the cap earns
its assertion.

### Phase 4 — PPO, no recurrence, no belief (2–3 weeks) — **EXIT MET**

Feed-forward only. Candidate-scoring action head. Beat random, then greedy.

**Exit:** ≥90% vs random, ≥65% vs greedy.

**Result — met at the full victory score, 582k parameters, ~1,400 transitions/sec
on one CPU core-set (M1 Max).** Trained at `victory_score=3` per the §1.3
curriculum, 205k transitions (100 iterations x 2048), ~4 minutes:

| Measured at | vs random | vs greedy |
|---|---|---|
| victory 3 (trained here) | 97.5% | 77.0% |
| victory 5 (zero-shot) | 98.0% | 79.0% |
| **victory 8 (zero-shot)** | **96.0%** | **74.5%** |

**The curriculum transferred with no retraining at all**, which was not
guaranteed and is worth recording as a design win rather than luck: `globals`
encodes points as `points / victory_score` and turn as `turn / turn_cap`, so
"I am two thirds of the way to winning" is the same input vector whether the
target is 3 or 8. Encoding a raw point count would have made the victory-3
policy actively wrong at victory 8 — it would have tried to close out games
five points early.

**Annealing to victory 8 bought nothing measurable.** A second run warm-started
from the victory-3 checkpoint and trained at victory 8 for 40k transitions was
then compared against it at 1,000 games per matchup:

| Checkpoint | vs random | vs greedy |
|---|---|---|
| trained at victory 3 only | 96.0% ± 1.2% | 76.3% ± 2.6% |
| annealed at victory 8 | 96.5% ± 1.1% | 77.6% ± 2.6% |

Both gaps sit well inside the 95% intervals, so the honest reading is that the
anneal is *not yet* demonstrated to help — not that it helped a little. Two
plausible explanations, and they need different responses: either the curriculum
really does transfer completely (in which case §1.3's 3 → 5 → 8 schedule is
unnecessary overhead for v0), or greedy is too weak to resolve the difference
(in which case the anneal may matter and this measurement simply cannot see it).
The second is more likely, and it is the same limitation as the caveat below —
which is why Phase 5's Elo ladder and the §1.4 exploitability probe, not more
baseline duels, are what should settle it. Do not delete the anneal step on this
evidence.

Training curve was healthy rather than lucky: normalized entropy fell smoothly
0.85 → 0.19, explained variance rose 0.00 → 0.61, KL held at 0.002–0.004 and
clip fraction at 2–4%. Policy collapse would look like entropy crashing to zero
with KL spiking; that did not happen. Victory-3 play saturates at ~97%/77% by
iteration 100, which is unsurprising — those games last **2.3 turns and 12
decisions**, so there is not much policy there to find.

### Phase 4 re-run with spells, the Chain and [Hidden] — **exit met, with two findings**

Retrained at `victory_score=3` with `units_only=False` (30% spell decks) against
a greedy baseline that now hides and uses combat tricks. 400 deals x 2 seats:

| Checkpoint | vs random | vs greedy |
|---|---|---|
| **iter 100 (best)** | **93.1% ± 1.8%** | **69.0% ± 3.2%** |
| iter 150 (last) | 92.8% ± 1.8% | 60.2% ± 3.4% |

**1. Late training made it measurably worse against greedy.** The per-checkpoint
sequence was 61.5 → 64.5 → 68.0 → 69.5 → 64.0 → 61.5, and the properly powered
comparison confirms it: best and last differ by 8.8 points with non-overlapping
intervals, while `vs_random` stayed flat. So this is not eval noise — the policy
co-adapted to its own current self and lost ground against a *fixed, different*
opponent. That is textbook self-play drift, and it is precisely what Phase 5's
PFSP opponent pool exists to prevent. Note also that picking "best" by periodic
eval is itself mild overfitting to the eval set; the honest headline is the 69%,
but it should not be treated as a stable capability until the opponent pool
lands.

**2. Going first is worth much more at victory 3 than the curriculum assumed.**
Self-play seat-0 win rate is **64.3% ± 5.4%** — the interval excludes 50%, so it
is real. It is not a seat-asymmetry bug: the same network plays both seats, so
any deviation is a property of the position. Random play shows 54.2% at victory
3 and 48.4% at victory 8, so a stronger policy *amplifies* a tempo edge that
only exists at the short victory score. Two consequences: the victory-3
curriculum is a more lopsided game than the real one, and seat-swapped paired
seeds (which `eval.duel` already does) are mandatory for every number reported
from it — an unpaired measurement here would be off by ~14 points.

### The Final Point changes the curriculum (471.1.b)

Taking the last point **by Conquer** requires having Scored every Battlefield
that turn; otherwise you draw a card instead. Non-Conquer sources (Hold, spells,
Burn Out) are exempt (471.1.a.1).

The restriction applies from *one point below* the Victory Score, so the
curriculum setting decides how much of the game it governs:

| Victory score | Restriction applies from | greedy vs random |
|---|---|---|
| 8 (real game) | 7 points — the last stretch | **97.2%** (was 90.5%) |
| 3 (old curriculum) | 2 points — most of the game | 77.3% |

At victory 8 the rule does what it is for: closing demands the whole board, and
skill matters *more* — greedy's edge over random grew by 7 points. At victory 3
it is not an endgame rule at all, it is a permanent tax, and the skill gap
compresses. **So the curriculum floor is now 5, not 3.** Anything measured at
victory 3 describes a game with a different rule shape from the real one, which
retroactively weakens the Phase 4 numbers taken there.

### Deck construction, measured rather than assumed

Read off the 29 decklists in `decks/`:

| Property | Value |
|---|---|
| Main deck size | **39**, every deck |
| Copies of any one card | **at most 3** |
| Spell fraction | 28% - 62%, **median 49%** |

An earlier `v1_deal` used 30-card decks and a 30% spell rate documented as
"well above what a real decklist would run". Both were wrong, and the second in
the opposite direction: 30% is near the *low* end. The project owner's Lillia
lists run 54% and one netdeck runs 62%.

**The implemented card pool, not the rate parameter, is what limits realism.**
With three spells in the DSL and a 3-copy limit, a deck tops out at 9 spells =
23% of 39 — below even the lowest real deck. Roughly seven more spells are
needed before a realistic density is reachable at all. `deal_stats()` reports
what the deal function actually produced versus what it was asked for, so this
gap stays visible instead of being assumed away.

**Phase 1-4 numbers describe a 30-card game.** `v0_deal` and `fuzz.make_game`
are deliberately left at 30 so the golden outcome and the gate suite stay
valid; that makes those results internally consistent but not a description of
the real game.

**Caveat to carry forward.** Greedy is a deliberately shallow baseline (three
rules, §Phase 2), so 74.5% against it is a floor on competence, not evidence of
strong play. The meaningful measurements are Phase 5's Elo against held-out
checkpoints and the §1.4 best-response exploitability probe — a policy can beat
greedy handily and still be trivially exploitable.

**One bug worth remembering, found by a test rather than by a bad run.** A
trailing minibatch of size 1 makes the advantage `std()` undefined; the NaN
reached every parameter through a single Adam step and the run kept printing
plausible numbers indefinitely. Minibatches are now even splits
(`torch.tensor_split`) and the loss is asserted finite before stepping. This is
the failure mode the §4 debug list cannot help with, because nothing looks
wrong.

**Debug order when it fails** — check in this sequence, every time:
1. Action mask alignment (is `legal_actions[i]` the same action the net scored at
   index `i`?)
2. Reward sign and seat attribution
3. Observation canonicalization (does seat 1 see a mirrored world?)
4. Advantage normalization
5. Learning rate

The bug is in 1–3 roughly 90% of the time.

### Phase 5 — Recurrence and opponent pool (2 weeks)

LSTM over the trajectory. Opponent pool with **PFSP** sampling (prioritize
opponents you beat ~50% of the time — AlphaStar's scheme), not uniform, not
latest-only. Add Elo/TrueSkill *and* the §1.4 best-response exploitability probe.

**Exit:** monotone Elo against a fixed held-out checkpoint set, and BR-exploitability
that is not getting worse.

### Phase 6 — Belief head (2 weeks)

1. Card-counting baseline (§1.5) — **first**.
2. **Start with the Facedown Zone, not the hand.** See below — it is a strictly
   better-posed problem and it is the one this game is actually built around.
3. Auxiliary head off the shared trunk. Hand target: multi-hot over the opponent's
   actual hand, masked to cards not publicly known. Loss: BCE per card type,
   weighted low (~0.1) so it shapes the trunk without dominating.
4. Calibration report: reliability diagram + Brier score + log-loss vs baseline.

**The Facedown Zone is the ideal first belief target.** It is the `[Hidden]`
mechanic (44 cards, in all ten of your decks): *"Hide now for {any rune} to react
with later for {0 energy}."* Confirmed from the rules (107.3, and already modelled
in `state.py:65`):

- **107.3.f** — Facedown Zones are **Public** zones, but the cards in them are
  **Private**. Presence is known; identity is not.
- **107.3.b** — maximum occupancy **one** card.
- **107.3.c** — you may only hide there if you **control** that battlefield.
- **107.3.d** — lose control of the battlefield and the facedown card is **removed
  at the next cleanup**.

That combination makes it far cleaner than the hand as a first experiment:

| | Opponent hand | Facedown Zone |
|---|---|---|
| Question | "which cards, how many" | **"which single card"** |
| Output shape | Variable-size multi-hot | **One categorical over the pool** |
| Presence known? | Only the count | **Yes, exactly** |
| Spatially anchored? | No | **Yes — to a battlefield** |
| Ground-truth reveals | Sporadic | **Structured** — 107.3.d forces resolution when control flips |

The spatial anchoring is what makes it strategically pointed: *they hid something
at the battlefield they are defending* is a concrete, learnable read, and it feeds
directly into the garrison decision in Phase 1.3.c. And because 107.3.c ties hiding
to control, the prior is heavily conditioned on public information the network
already sees.

**This also raises the stakes on the Ambush interaction.** A facedown card that can
be revealed as a reconquest threat (Phase 1.3.c) means "how big a garrison do I
leave" depends on a belief about a specific hidden card at a specific location.
That is the project's whole thesis in one decision, and it is measurable.

**Exit:** belief head beats the counting baseline in log-loss by a clear margin on
the Facedown Zone target. If it doesn't, stop and fix that before Phase 7 —
everything downstream depends on it.

### Phase 7 — Bluffing (2–4 weeks)

Track the §1.6 metrics. Escalate only as needed:
1. Entropy bonus, normalized (§6.3).
2. Larger, more diverse opponent pool.
3. **R-NaD / DeepNash-style regularization toward an anchor policy** — the
   intended destination if 1–2 plateau, and the closest published analogue to
   what this project wants.

**Exit:** nonzero, *stable* bluff rate and respect rate, and nonzero mutual
information between rune count and opponent behaviour.

### Phase 8 — Scale (open-ended)

Rust port (per the §1.8 trigger), full card pool, deck-as-input, multi-deck
training, then the deck-evaluator integration into `cli.py`.

---

## 5. Setting up the gym — concrete

### 5.1 Do not use Gymnasium directly

Gymnasium is single-agent. Riftbound is two-player with alternating priority, and
your action space is a variable-length candidate list that fits no standard
`Space`. Forcing it produces hacks you'll fight for months.

**Recommendation: a plain custom env class with a PettingZoo-AEC-shaped API.**
You get correct semantics now and can adopt PettingZoo later if you want its
ecosystem. Self-play with one shared network doesn't need multi-agent plumbing.

```python
class RiftboundEnv:
    def reset(self, seed: int, deck_a: Deck, deck_b: Deck) -> Obs: ...
    def step(self, action_index: int) -> StepResult: ...
    @property
    def to_move(self) -> int: ...
```

`action_index` indexes into the `legal_actions` list the env just returned. The
policy never names an action; it picks a slot. This is what makes the
variable-length action space tractable.

### 5.2 The observation

```python
@dataclass
class Obs:
    zones: dict[str, np.ndarray]   # {"hand": [N_max, D_card], "board": ..., ...}
    zone_mask: dict[str, np.ndarray]  # [N_max] bool per zone
    globals: np.ndarray            # [G] scalars
    legal_actions: np.ndarray      # [A_max, D_act] — one featurized row per action
    action_mask: np.ndarray        # [A_max] bool
    to_move: int
    privileged: np.ndarray | None  # critic-only, training-only
```

**Card features** (`D_card`), all available in `data/cards.json`:
energy, power, might, type one-hot (5), domain multi-hot (6), the 30 keyword
flags from §0, tag hashes, plus a zone tag concatenated on. No card-ID one-hots —
that is what lets unseen cards get sensible embeddings.

**Globals** (`G`): both scores, turn number, phase one-hot, priority holder,
ready/exhausted rune counts by domain for both seats, opponent hand *count*,
deck counts, battlefield control flags.

**Canonicalize.** Always encode from the acting seat's perspective so one network
serves both seats. Verify with an assertion: a mirrored state must produce a
byte-identical observation.

### 5.3 Eight gotchas that will bite

**1. Reward attribution across seats.** The classic self-play bug is crediting the
final actor. Keep **two separate trajectory buffers**, one per seat, tag each
transition with its seat, and write ±1 into both at game end.

**2. GAE must skip opponent steps.** Between two of your seat's decisions, the
opponent acted. Treat each seat's trajectory as its own episode with the opponent
folded into the environment dynamics. Bootstrap from *your* next decision, never
across the opponent's.

**3. Auto-pass — keep it, but only the trivial case.** `actions.py:184` already
has `only_pass()`, which cuts a game from 400+ decisions to ~200. That is a real
speedup and it is safe *only* when the legal set is literally `[pass]` — that's a
no-op, not a decision. **Never auto-pass when a `[Reaction]` is affordable**, or
you destroy exactly the decision points where bluffing lives.

**4. Cap `A_max` and assert.** Worst case ≈ 10 hand uniques × 3 locations + 6
units × 3 move destinations + pass ≈ 50. Set `A_max = 64`, assert on overflow,
log the distribution. Keep the existing `_unique()` duplicate collapse
(`actions.py:176`) — identical copies are interchangeable, so collapsing them is
both correct and a free action-space reduction.

**5. `plan_payment` is a hidden policy decision.** `actions.py:62` auto-picks the
cheapest rune assignment. Which domains you keep ready is a *real* strategic
choice and the agent currently can't make it. Fine as a v1 approximation —
**record it as a known bias**, and promote it to its own decision point when you
factor multi-part actions.

**6. Determinism.** Separate RNG streams for shuffle vs in-game randomness, both
seeded from the episode seed, so a replay is stable even if you change how many
random draws an effect makes. Test: same seed twice → identical `state_hash`
trace.

**7. Truncation.** Cap at 30 turns → reward 0. Track the truncation rate as a
first-class metric: a rising rate means the agent found a stalling strategy, and
you'll want to know before it eats a training run.

**8. Damage assignment is simultaneous but *separable* — mask it anyway, cheaply.**
Confirmed: you cannot see the opponent's allocation when choosing yours. But the
project owner's read is that it almost never matters, and the rules say why:
**damage is dealt simultaneously and every unit contributes its full Might whether
or not it dies.** So their allocation cannot shrink your pool, and yours cannot
shrink theirs. The two optimisations are independent.

That means it is a simultaneous move with **no strategic interaction** — there is
no mixing to learn, and an earlier draft of this plan was wrong to call it an
equilibrium canary.

Two things still follow:

- **Keep the masking.** "Almost never" is not "never", and the assertion is nearly
  free: the observation handed to the second assigner must be byte-identical
  whether or not the first has chosen. Revisit if **Deflect** or **Shield** turn
  out to make incoming damage conditional — those are the keywords that could
  couple the two allocations.
- **In v1, do not make it a policy decision at all.** Because the problem is
  separable and (per 1.3.b) reduces to an exact-lethal knapsack, **solve it in the
  engine** behind a config flag. That deletes a whole class of decision points,
  shortens episodes, and costs essentially nothing in play strength. Expose it as
  a real decision at Phase 8, when keywords make it interesting.

### 5.4 Vectorization

Python engine, so: **8 worker processes × 32 envs each**, batching inference
either per-worker with numpy or through a central inference server. Start
per-worker; it's simpler and the difference won't matter until Phase 7.

Use CleanRL's `ppo_lstm` single file as the base — ~400 lines you'll fully
understand. **Do not use RLlib**: the candidate-scoring action head is
non-standard and you'll spend more time fighting the abstraction than writing the
algorithm.

---

## 6. Network architecture

### 6.1 Trunk

```
per-zone: card features -> shared MLP -> attention pool (DeepSets or 1-layer transformer)
concat all zone summaries + globals -> trunk MLP -> h  [256]
Phase 5+: h -> LSTM -> h_t
```

### 6.2 Candidate-scoring action head (the core mechanism)

```python
# a: [A_max, D_act] featurized legal actions
# h: [H] trunk output
x = concat(broadcast(h, A_max), a)        # [A_max, H + D_act]
logits = mlp(x).squeeze(-1)               # [A_max]
logits = logits.masked_fill(~action_mask, -inf)
pi = softmax(logits)
```

Two hidden layers of 128 is plenty. This handles variable action counts natively
and scores unseen cards by their features rather than by an index.

### 6.3 Normalize the entropy bonus — non-obvious, matters

Entropy of a softmax over `n` legal actions is bounded by `log(n)`. Since `n`
swings from 2 to 64 across states, a fixed `ent_coef` systematically pushes the
policy toward high-branching states — it will learn to keep its options open for
reasons that have nothing to do with winning. Normalize:

```python
ent_bonus = entropy / math.log(max(n_legal, 2))
```

### 6.4 Heads

- **Policy** — sees only legitimate information (opponent hand as a *count* plus
  public knowledge).
- **Value** — may see full state during training (OpenAI Five asymmetric critic).
  Discarded at inference, so policy validity is preserved.
- **Belief** (Phase 6) — strictly on the policy side. See §4 Phase 6.

### 6.5 Starting hyperparameters

```
gamma            1.0        # terminal-only reward; critic = win probability
gae_lambda       0.95
lr               3e-4 -> cosine decay
n_envs           256
rollout_steps    128
minibatches      4
update_epochs    4
clip_coef        0.2
ent_coef         0.01       # applied to the NORMALIZED entropy (§6.3)
vf_coef          0.5
max_grad_norm    0.5
```

---

## 7. Evaluation methodology

**Always evaluate with paired seeds and seat swap.** Play each matchup twice from
the same seed, once in each seat, and average. Detecting a 2% edge on unpaired
games needs thousands of matches; pairing cuts the variance enormously and
controls for first-player advantage (which rule 485.7's extra rune only partly
offsets — measure the actual random-vs-random seat split and record it).

**Dashboard from day one of Phase 4:**

| Metric | Why |
|---|---|
| Win-rate vs random / greedy / pool | Progress |
| BR-exploitability (§1.4) | The honest one |
| Belief log-loss vs counting baseline (§1.5) | Falsifies the thesis |
| Bluff rate, respect rate, rune↔attack MI (§1.6) | The actual goal |
| Truncation rate | Stalling detector |
| Mean episode length, mean `n_legal` | Engine health |
| Value calibration (predicted vs actual win rate) | Critic sanity |

---

## 8. Known limitations to record now

**Self-play models itself.** The agent's read on "open runes" will be calibrated
to its own bluffing frequency, which may be nothing like a human's. The *policy*
transfers to humans reasonably; the *opponent model* largely will not. Recalibrating
needs human game logs. (Carried from the brief's §9 — still true, still worth
writing down before it's discovered as a surprise.)

**`plan_payment` bias** — see §5.3 gotcha 5.

**Multi-domain power costs** — `actions.py:30` documents a permissive reading that
may be wrong. It never blocks a legal play, so it's safe for training, but it
could let the agent learn a line that isn't legal in paper. Verify against card
images before trusting any result that hinges on it.

**Mirror-match overfit** — v1's mirror removes the matchup confound but produces
an agent that has never seen a different deck. §1.1's deck-as-input work is what
fixes this; don't be surprised when the v1 agent generalizes poorly.

---

## 9. What to do first — this week

1. **Read `data/rules.txt` §190 and the 300-series for showdown/combat.** This is
   the largest unknown and everything in Phase 1 depends on it. Do it before
   writing code.
2. **Write `rl/config.py` and `sim/engine/invariants.py`** (Phase 0). Small,
   mechanical, and they pay for themselves within a week.
3. **Design the effect DSL against 20 real candidate cards** — not in the
   abstract. Pick the 20 you want in the v1 pool, write out each card's text as
   DSL, and let the primitive set fall out of what those cards actually need. If
   more than 2 of the 20 require the `native` escape hatch, the pool is wrong,
   not the DSL.

Then Phase 1.

**Do not write the training loop yet.** The brief is right about that.

---

## 10. Open questions for you

The brief says to verify rules with you rather than infer from other TCGs.

### Resolved

**Combat and movement**

- ✅ **Showdown vs Combat** — Showdown is the interactive window; Combat is the
  might/damage resolution at its end, not an alternative to it. Phase 1.3.
- ✅ **No attack action.** Move is atomic; Combat is forced when a Move lands in an
  enemy-occupied battlefield.
- ✅ **Staging** — all movement declared first; any number of units sharing a
  destination move together and produce **exactly one** Showdown. Multiple
  Showdowns per turn at the same battlefield are legal, by choice.
- ✅ **Discretionary movement is your-turn-only.** Asserted invariant (Phase 0).
- ✅ **Defenders join via `[Ambush]`, not movement** — *"play me as a `[Reaction]`
  to a battlefield where you have units."* Reinforces only; cannot open a front.
- ✅ **Retreat** — a *readied* unit may return to base on your turn. Units arrive
  exhausted, so commitment locks them for one opponent turn; and Hold banks in
  Beginning before Main, so retreating costs the *next* point, not the current one.
- ✅ **Damage is a pool**, spent freely across opposing units, assigned at the end,
  simultaneous, lethal vs **current** Might — but **ordered by `[Tank]` /
  `[Backline]`**. Phase 1.3.b.
- ✅ **Assignment is hidden but separable.** Full Might is dealt regardless of
  deaths, so neither allocation affects the other. No mixing to learn; engine-solve
  it in v1. §5.3 gotcha 8.
- ✅ **Board-wide heal** at combat cleanup and again at end of turn. Phase 1.3.d.

**Scoring**

- ✅ **Conquer** — immediate and event-driven; **always 1 point**. Off-turn Conquer
  is real but niche; do not build strategy around it. Phase 1.4.
- ✅ **"Empty" battlefield** — resolved from rule **190.4.c**: no units means control
  is lost at the following cleanup, so "empty" and "uncontrolled" converge. My
  question assumed a state that cannot persist.
- ✅ **Battlefields** — each player brings 3 and chooses one of their own (2 in
  play); a used battlefield is burned for the rest of a Bo3. **v1 hardcodes both**
  and skips selection. §3.

- ✅ **Ordinary movement is base <-> battlefield only.** Lateral movement requires
  `[Ganking]`. Shrinks the action space and makes commitment sticky. Phase 1.3.
- ✅ **Battlefield selection is in training scope**, as an exactly-solvable Bo3
  ordering meta-game rather than a policy head. §3.

**Remaining, non-blocking**

1. **Are the two battlefield selections simultaneous-and-hidden, or does one player
   reveal first?** Changes only which solver Phase 7.5 uses. Not blocking.
2. **v1 deck base** — going with `lillia-protector v1` as the default per the
   measured table in §3, avoiding `lillia-sprite-fortress` because its
   `[Temporary]` engine hinges on drawing LeBlanc. Say the word if you'd rather
   start from `ornn-swain v1`.
