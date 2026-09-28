# Backlog

Everything deferred, considered, or half-finished, in one place. `PLAN.md` holds
the *roadmap and reasoning*; this holds the **list**.

Effort is rough: **S** = under an hour, **M** = a session, **L** = multi-session,
**XL** = a project. "Breaks checkpoints" means it changes the observation layout,
so `--init` will refuse to load older runs — batch those together.

---

## Do first — these protect the runs

| | what | effort | why now |
|---|---|---|---|
| ~~0~~ | ~~**`acting_seat` can name a seat with no legal actions**~~ — **DONE 2026-09-27** (`64395ee`). Root cause was not `acting_seat`: `state.priority` went **stale** when a Hard Bargain tax COUNTERED the Chain's last item. `chain.after_resolution` hands priority back per 340.2 but only runs where an item *resolved*; `chain.counter` pops one and no caller restored it. `actions._normalize_priority` now states the rule at the end of every `apply`. Named seed 859 runs first in `fuzz.main` | — | Stale priority lied in three places, not one: `obs` feeds `priority == seat` to the policy, `invariants.check_actions` reads it, and `_apply_one` took it as the seat ANNOUNCING a play — which is the crash, because the announcer indexes a hand |
| ~~1~~ | ~~**Truncation decided on points, not a draw**~~ — **DONE 2026-09-27**. **408.2.b answers it and it is not a draw:** "a player is declared the winner of the game if they have a point lead of two or more. If no player has a point lead of two or more, the game is a draw." So it stays in {-1, 0, +1} and the critic is still a literal win probability. `cfg.truncation_lead_to_win` | — | A losing player was *rewarded* for stalling: 0 beats the −1 they were heading for, and the turn cap is a house limit they can always reach |
| ~~2~~ | ~~**Sterile-loop detection**~~ — **DONE 2026-09-27**, in `env._check_sterile_loop`. An exact `state_hash` repeat with the same seat to move ends the episode. **Attribution only where it is honest:** >1 legal action means the seat chose the loop and takes the loss; exactly 1 means it was forced, and that falls back to 408.2.b. The 67us hash starts at `cfg.loop_watch_after = 700`, above the 529-decision ceiling measured at victory 8, so healthy games pay nothing. Reported as `loop=` in the training log | — | `ply` and `turn` are in the digest and only increase, so this only ever catches a loop INSIDE one turn — which is the gap `turn_cap` cannot see |
| 2b | **Three more crashes, all pre-existing, found clearing the above** — all fixed in `64395ee` | — | **(a)** an attached Equipment's granted Exhaust ability: 721.2 makes the Attached card's own abilities Inactive so `activatable` numbered the row without them and `_activate` numbered it with them, off by one — it activated a `[Play]` trigger. Real-deck seed 95, *in the training distribution*. **(b)** `env.play` spun forever on a truncation: it looped on `r.obs is not None` and a truncation leaves the next observation in place. **(c)** `invariants.check_actions` read Undying Loyalty's PRINTED cost and called a legal play illegal — its trash-tag discount reaches 0 Energy and the 1 Power left is paid by RECYCLING a rune, which needs no ready one. v1 spell seed 661 **at victory 8**, which is the argument for fuzzing the curriculum's destination and not only its current rung |
| 3 | **Commit the working tree** | S | 18 files uncommitted. Every checkpoint says `1dc45e4-dirty`, which is honest but not reproducible |
| 4 | **Victory 8 curriculum** | M | **Unblocked and set up: `rl/docs/V8_SETUP.md` holds the launch command and the measurements behind it.** Cold start, NOT `--init` — every older checkpoint is dead (`GLOBAL_DIM` 135 -> 145) and v6 was trained against a wrong combat model and an unplayable champion anyway. The one non-obvious knob is `--rollout 12288`: the reward is terminal-only so the signal unit is the EPISODE, and victory-8 episodes are ~6x longer, which at the default rollout is 15 outcomes per update against v6's 92. All three fuzz modes are clean at victory 8; the 471.1.b final-point gate is measured live (58 denials in 400 games). Remaining gate is the project owner's own pre-training judge-call audit |
| ~~5~~ | ~~**Expose damage assignment to the policy**~~ — **DONE 2026-09-25**, see `state.pend_dmg` and test_combat `[D1]`. The player now chooses whenever `assignment_is_a_choice`; `Config.with_solved_damage()` pins the old behaviour for the scenario suites. Greedy answers via `combat.dmg_solver_choice` so the baseline did not weaken. Residual gap: *which* units this seat has already doomed is invisible (a per-row flag would widen `row_dim`) | — | **This is a training-signal bug, not a missing feature.** `cfg.engine_solves_damage_assignment=True` makes `combat.solve_kills` decide for *both* players, including the learner. It maximizes summed Might with a more-bodies tiebreak and has **no ability awareness at all** -- so it never snipes the unit that actually matters. Sequencing attacks separately pays off precisely *because* a real defender kills your best unit when you batch; the engine's defender does not, so batching is never punished and the policy has no gradient toward sequencing. **Measured: the v5 policy commits 2+ combats in 10% of combat-turns, versus 12% for random play** -- it has not learned this at all. `combat.assignment_is_a_choice()` already detects the only case where a decision exists (the pool cannot cover every target) and the docstring says to gate exposure on exactly that, so the scaffolding is built |

| ~~0b~~ | ~~**The Deflect surcharge is offered against the PRINTED cost and paid against the real one**~~ — **DONE 2026-09-27.** `actions.play_cost_reservation` is now the ONE answer to "what will this play recycle", and every offer site uses it: the target slot, the paid-optional variant, the granted-[Repeat] variant and `chain.flow_playable`. Consistency is the load-bearing part — being strict in one place only turns the crash into a deadlock. Named seed: real-deck **5097** at victory 8 (a granted [Repeat] on Bellows Breath). It killed the first victory-8 run at iteration 19 and needed 5,000 real-deck games to reach by random play |

---

## Engine gaps — rules fidelity

| | what | effort | notes |
|---|---|---|---|
| ~~5~~ | ~~**108.3.d — play the Chosen Champion from the Champion Zone**~~ — **DONE 2026-09-25** (`d29e1a4`). `A_PLAY` arg `CHAMPION_SRC`, routed through the ordinary unit path; `state.champion` is occupancy and `champion_reg` the permanent public identity. Tests in test_env `[4f]` | — | **The biggest gap.** Every deck is understated by one guaranteed threat, and a human notices in the first game. Every play path takes a hand index, so this is a second source zone; `_play_from_hidden` and `_resolve_play_from_look` are the precedents |
| 6 | **718.3 — Equipment ability text** | L | 136.2/718.3 append an attached card's Effect Text to its top-most card's rules text. Right now Equipment attaches, grants its Might, and silently drops the clause that made it worth playing ("When I hold, score 1 point") |
| 7 | **Work down `PARTIAL_TRANSCRIPTIONS`** | M–L | Cards whose text is only partly scripted. Each one is a card the policy sees a lie about |
| 7b | **"Name a tag" is restricted to what is already on the board** | M, + an action-space decision | **Found by the project owner 2026-09-25.** The List reads *"As you play this, name a tag"* with the examples as illustration and **no visibility restriction** -- naming preemptively against a deck you know is a real play. `resolve.py:2651` instead builds the options from the opponent's live units plus their trash. Three layers, worst last: (a) the option set is too narrow; (b) `state.name_opts` holds **8** entries while the pool has **127** tags, and `opts[:shape[0]]` truncates silently; (c) with an empty enemy board and empty trash it **fizzles outright** -- verified: a turn-1 The List (it costs {1 energy}) names nothing and its ability can never target anything, so it is a permanently dead gear in exactly the situation the preemptive play is for. **The reason this is not a one-line fix:** 127 options collide with `cfg.max_actions = 64`, and `max_actions` is the action-row dimension of every observation, so widening it inflates the whole tensor. Options worth weighing: raise the cap; or restrict to tags legitimately knowable (own decklist + public zones + the opponent's list when `deck_known`), which is leak-safe, far smaller, and makes the play *learnable* off the deck-conditioning work -- but is not a superset of what a human may name from meta knowledge. Same code path serves NAME_SPELL (Fallen Feline), which reads the opponent's trash and has the same shape |
| 8 | **More judge rulings** | M each | 2017 verified across 80 case files, 62 engine bugs found, 16 rejections. Community calls are biased toward *confusing* interactions, which is exactly the coverage worth buying. Add a batch, fix what it finds, record contradictions in `judge/rejected.json` with the rule number |
| 9 | **`A_SHORTCUT` for productive combos** | L | The table rule: do it 2–3 times, then declare infinite. Detect a cycle returning to the same state *except* counters strictly increased, then apply the delta N times bounded by deck/points/cap. Turns "found an infinite" into "won with it" instead of a truncated episode. Riftbound has no loop rule, so this is a documented house rule — it belongs in `config.py` |
| 10 | **`state.victory_score` is redundant** | S | Set in `new_game` but `check_winner` is called with `cfg.victory_score`. Equal today, a trap the day something mutates one |
| 11 | **`coverage` excludes battlefields** | S | A deck at `coverage == 1.0` can still have 3 battlefields doing nothing. Report `bf_coverage` alongside it everywhere, not just in the loader |

---

## Decisions the engine makes for the player

Audited 2026-09-25 after the damage-assignment finding, by searching for
"no choice" claims and for heuristics standing in for a decision. Ordered by how
much it matters. **The same failure mode applies to all of them:** whatever the
engine decides, the policy is trained against an opponent making that decision by
heuristic, so it never learns to punish a bad one or to exploit the choice itself.

| | what the engine decides | where | why it matters |
|---|---|---|---|
| D1 | **Which units combat damage kills** | `combat.solve_kills`, `cfg.engine_solves_damage_assignment` | **FIX — project owner: "this changes things drastically, and that's why things like Backline and Tank exist to protect your units in these kinds of scenarios."** That is the argument: 815.1.c.2 / 826.4.b exist *because* the assigner chooses, so an engine that chooses for them makes two whole keywords strategically inert. Max summed Might, tiebreak more bodies, **no ability awareness**. `assignment_is_a_choice()` already gates the only real case. See item 5 for the measured consequence |
| D2 | **Which of your three battlefields you present — in Bo3 only** | `ppo.deck_pool_deal` does `rng.integers(3)` | **Corrected 2026-09-25 by the project owner, and the rules agree.** 485.5 (Duel/Bo1): "Each player **randomly** selects one of their three Battlefields" -- so the current random pick is *exactly right* for Bo1 and nothing is wrong there. 486.5 (Match/Bo3): "Each player **selects** one" -- a real decision, with two more layers the engine has none of: the used battlefields are **removed for the rest of the match** if someone won that game (so the three want go-first / go-second / neutral roles), and 486.5.a lets them be reused if nobody won. There is no action kind for any of it. Needs a match-mode notion in `config.py` first, since the correct behaviour differs by format |
| D2b | **Sideboarding — the whole mechanic is missing** | nothing implements it; `decks.py` does not even parse it | **High priority, project owner's call.** 0 or up to 10 cards, raised from 8 on 2026-07-24; copy limits span deck **and** sideboard combined, and battlefields are legal sideboard cards. **The data is already in the repo and unread: 27 of 47 decklists carry a `Sideboard:` section, 17 of the 18 meta lists**, in the same `Nx Card Name` format `decks.py` already parses for every other section. This is the same shape as the Chosen Champion gap -- parsed by the corpus, ignored by the engine. Strategically it is deck adaptation, and it pairs directly with `deck_known`: in Bo3 games 2-3 you know their list *and* you get to change yours. **Verified against the Tournament Rules (`data/tournament_rules.txt`), not the stale secondary reference:** 10 or fewer cards (601.1.c.1), **only valid Main Deck cards so NOT battlefields** (601.1.c.2, and 403.4.b forbids changing Runes/Legend/Battlefields at all), exchanged **1-for-1** (403.4), never in game 1 (403.5), and no sideboarding after a draw (403.10). Bo1 is allowed at the head judge's option (406.1.g), where you sideboard knowing their Legend, the battlefields *and* who goes first. **A separate allowance worth modelling on its own: 403.4.a / 601.1.c.4 let you change the Chosen Champion to one from the sideboard OR the main deck** -- Akali decks swap red/green Akali between games. Because 103.2 counts the champion inside the 40, that is a re-designation within the registered list rather than a 41st card, which our 39-main + 1-champion split already represents |
| D3 | **Which domain's runes to recycle for Power** | `cost.plan_payment` — "recycle from the domain held most, keeping scarce domains available" | **I overstated this and the project owner corrected it.** A card with a *printed* Power cost gives no choice: 163.2 binds the Power to the card's own domains, so if there is one domain there is nothing to decide. The choice is real in three narrower places: **hiding a card** (the cost is any rune, so any domain can pay it -- the main one), a **multi-domain** card whose Power could come from either, and a **domainless unit paying [Accelerate]'s Power**, which 805.1.a.2 lets any domain cover. **And the project owner's reason is stronger than mine:** the decision is driven by what your *hand and deck* need LATER, not by what you hold now. Harrowing + Baron Nashor wants 4 Power of one colour; Falling Star wants 2 red. So with a majority-purple rune pool you may still want to exhaust yellow, precisely because your deck runs little yellow Power and the purple has to survive for the big cast. `plan_payment`'s "recycle from the domain held most" is not merely a neutral heuristic -- it optimizes the wrong thing, spending the abundant domain that the expensive cards actually need |
| D4 | **Unlicensed Armory's "you may pay {Fury rune}"** | `effects.py` OP_ARMORY — "paid automatically when it can be" | **FIX.** An explicit **may** resolved without asking. Project owner: "typically it is right. Can be wrong if it has things like Deathknell" -- i.e. saving a unit whose death you *want* is a loss, and the rune has a better use. Safe to expose, and cheap: one yes/no at a known moment |
| D5 | **Which location a scattered group requirement lands on (355.11.b)** | `resolve.py:1905` | **FIX.** Worked example: you cast Bellows Breath ("up to three units at the same location") naming enemies A, B, C at battlefield B1. The opponent responds by moving A and B away. On resolution your three chosen units are no longer in one place, so 355.11.b has you pick ONE of the locations they are *now* at -- what you chose there is hit, the rest are not (FAQ #11681 / #11505 / #11633). The engine picks the location holding the **most** of them, so it hits A and B. But C may be the one that matters -- the lethal target, or the only one that stops a Conquer -- and taking two irrelevant units instead is a real loss. Documented in the code as "the remaining half of gap #9352" |
| D6 | **Replacement-effect ordering is fixed, not offered (372)** | M | **The last known-bad from Austin's batch 1 (`cases_austin_01.py` AJ-02).** 372: "if more than one Replacement Effect applies to the same event being executed, the controller of the object being acted on determines the order." `combat._destroy` runs a FIXED ladder — attached Guardian Angel, then the self-shields/Soraka, then Smite's `banish_death_ply`, then Zhonya's `death_guard` — so Smite always pre-empts Zhonya's and the save is unreachable. Measured: the unit is banished and Zhonya's is never spent. **It cannot be hard-coded the other way either**: Zhonya's is a one-shot you may not want to spend on a 1 Might token, so both directions are live choices. **The machinery already exists** — `pend_altar` is a death-time decision belonging to the dying unit's controller, and `_destroy` suspends for it by simply RETURNING without killing, with a per-row ply stamp so a made choice sticks when the caller comes back round and kills for real. Plan: `pend_repl` + a per-row `repl_pick`/`repl_ply` pair, an `A_PICK` site with one option per applicable replacement, offered only when two or more apply. **Probably does not widen the observation** — the options ride the action rows, which are already encoded, so the new slots can sit in `obs.OBS_UNREAD` like `showdown_step` does, and checkpoints survive |

**Checked and correctly offered**, so the audit is two-sided: the Mulligan (117),
simultaneous trigger ordering (383.3.d, `pend_order`), all targeting (355.8),
"look at the top N" / `[Predict]` (suspend-and-ask), optional additional costs
(`A_PLAY_REPEAT` / `A_PLAY_BOTH`), `OP_PAY_ANY_AMOUNT` (`A_PICK`), and
`auto_pass` — which has a test proving it collapses only literal pass-only
windows and is otherwise a no-op.

**Which ready rune you exhaust for Energy** is not modelled as a choice either.
Energy is generic (163.1.a) so it usually cannot matter, and the project owner's
read is that it matters *sometimes* in situations neither of us can currently
name. Recorded as known-and-unmodelled rather than a task, because a fix with no
example to test against is a guess.

**Settled, and it is not a bug.** `cost.least_cost` minimizes this cast under
356.1's free ordering. The project owner confirms a one-shot discount **must** be
used on the next spell -- it cannot be banked -- so applying it automatically is
correct. What that makes real is **play ordering**: "sometimes it's better to play
the expensive one first", and choosing which spell to cast next is already in the
action space, so this is learnable rather than missing.

It only became learnable this session, though. `next_spell_discount` was one of
the 24 fields invisible to the policy until `_standing` landed -- the agent could
not previously see that a discount was pending at all, so ordering around it was
not a behaviour it could express.

Priority, set with the project owner: **D2b (sideboard) and D2 (Bo3 battlefield
choice) first, then D3, then D1.** D2b and D2 are both pre-game or between-game
decisions, so neither floods the action space, and both need the same missing
piece: **a match-mode notion in `config.py`** (Bo1 vs Bo3), since Bo1 is random
with no sideboarding and Bo3 is chosen with sideboarding between games. Build
that once and both become expressible.

**Default it to Bo3.** Project owner: "Bo1 are not rare, but most people play Bo3
much more often, so I want to train on this whenever possible." That also matches
`riftbound-builds-for-bo3` and makes `deck_known_prob` principled rather than a
coin flip -- knowing the opponent's list *is* the Bo3 games-2-3 condition, not a
free parameter.

D3 wants the `assignment_is_a_choice()` treatment -- offer it only where the
domains genuinely differ, which after the correction above is a much smaller set
of moments than "every cast".

**One rules conflict to settle before building D2b.** The project owner's read is
that Bo1 allows sideboarding *after seeing the enemy Legend* and Bo3 allows it
after each game but not before game 1. `reference/riftbound-deckbuilding-tips.txt`
Section 9 says the opposite for Bo1: "Sideboarding isn't permitted in best-of-one
at all, so the slots do nothing." `data/rules.txt` (RUP4) does not mention
sideboarding anywhere, so there is no rulebook arbiter -- it is a Constructed
*format* rule, and the reference is a secondary source that already admits it
tracks a moving target (it flags the 8->10 change most guides missed). Resolve
against the current Constructed format document before implementing, because the
two readings give completely different pre-game information games.

---

## Measurement — we still cannot tell how good it is

| | what | effort | notes |
|---|---|---|---|
| 12 | **Exploitability probe** | M | Train a fresh policy purely to beat a frozen one; how much it wins by is how exploitable you were. **The only measure that really answers "is it good."** Everything else is a proxy |
| 13 | **Per-deck greedy baseline** | S | The v4 per-deck spread (4% → 79%) conflates "agent is bad with Azir" and "Azir is bad against the field". Run greedy piloting each deck to separate them |
| 14 | **Deck-conditioning ablation** | M | Needs a flag to switch the `decks` zone off. Nobody has measured whether the zone we built actually *helps* — only that the policy can now express deck-aware play |
| 15 | **Raise per-deck `n`** | S | n=24 gives ±8–20% per deck. The spread is real; the ordering is not. 60+ before trusting any single deck's number |
| 15b | **Behavioural metrics, not just win rate** | S | Win rate cannot tell you *what* it learned. The first one: fraction of combat-turns with 2+ committed combats (random 12%, greedy 9%, v5 policy 10% — so sequencing is absent). Others worth having: how often it commits a combat it loses on raw Might (deliberate trades), and how often it declines a scoring line |
| 15c | **Greedy's ceiling is a measurement limit** | note | Greedy attacks **only when it wipes every defender**, so it can never swing one unit at a time, never make a deliberate losing trade, and never kill a specific unit to unlock a later play. `vs_greedy` therefore says nothing about whether the agent has learned any of that. A second, sequencing-aware baseline would give the number teeth |

---

## Replaying and studying positions

| | what | effort | notes |
|---|---|---|---|
| 16 | **Record games as `(seed, decks, [action indices])`** | S | The engine is deterministic given a seed, so a whole game replays from a few hundred bytes — no state serialization needed. ~5 lines in `play.py vs` |
| 17 | **`play.py review` mode** | M | Step through a recorded game and print `rank()` at each of *your* decisions: "you played X (4%, −0.31); it preferred Y (63%, −0.12)". `env.reset_from`, `viewer.view` and `play.rank` all exist already — this is glue |
| 18 | **Position builder for physical games** | L | Enter a board you played at a table. Different and harder than replay, because nothing generated it. The judge suite's staging code is the closest existing thing |
| 19 | **Counterfactual rollouts from a position** | M | "What happens if I take this line?" — play out N samples from a candidate and report the spread, not just the 1-ply value |

**Worth noting on 16–19:** the infrastructure is worth building before the policy is strong, because it costs little and `win_prob()` is already honest. But its *advice* is only as good as the policy — at ~54% vs a heuristic, its preferences are opinions.

---

## Training regime

| | what | effort | notes |
|---|---|---|---|
| 20 | **True specialist: pilot deck D vs the field** | M | Take gradient only from D's seat. `Trainer.learner_seat` and `collect`'s `mine` filter already do the credit-masking; what is missing is letting the deal tell the Trainer which seat it put D on (seeds are monotone, so `seed % 2` suffices). Deliberately not half-built — a subtle credit-assignment bug is the worst kind. A mirror match (`--decks one-name`) is available today but never faces another archetype |
| 21 | **Matchup-aware PFSP** | M | PFSP weights opponents by `(1 − winrate)^p` — strength only, deck sampled independently. It has no notion of "this *matchup* is hard for me". Prioritizing over the 900-cell matrix is the cheap version of a population |
| 22 | **Population diversity** | L | Several learners with different seeds/deck subsets/hyperparameters feeding one shared pool. This is the right axis for the "many agents" idea — the pool today is one lineage of past selves, which is why `pool_frac=0.5` did **not** stop the 7.5-point drift. Costs linearly in compute, so not yet |
| 23 | **Potential-based shaping, Φ = turns-to-win** | M | *Not* score difference — that asserts "a point is a point, linearly", which the parity structure says is false. PBRS provably cannot change the optimal policy, so it is safe; measure it as an ablation rather than assuming it helps. `cfg.potential_shaping` is currently a flag with **no implementation** |
| 24 | **Targeted fine-tunes on the weak decks** | M | Warm-start from the generalist on the 5 worst decks. Justified by the 75-point spread — but do 13 first, or you may be fine-tuning against a deck that is simply bad |

---

## Learning algorithm — `PLAN.md` Phases 5–8

| | what | effort | notes |
|---|---|---|---|
| 25 | **LSTM / recurrence** (Phase 5) | L | Partial observability across turns. Also pin a PFSP floor for random/greedy so the pool cannot forget them |
| 26 | **Belief head** (Phase 6) | L | Predict the opponent's hand as an auxiliary task. The hypergeometric counting posterior (cards left in deck given what is seen) is the cheap version and could be an **input feature** long before a learned head |
| 27 | **R-NaD / bluffing** (Phase 7) | XL | Anchor regularization for approximate equilibrium. The escape hatch if self-play drift proves unfixable by a pool |
| 28 | **Inference-time tactical solver** | L | Search only in subgames where hidden information provably does not bind: combat math, lethal detection, Final Point arithmetic. This is where "play perfectly" belongs — at inference, not in training |

---

## Hygiene

| | what | effort |
|---|---|---|
| 29 | **Rename runs `vs3-` / `vs5-` / `vs8-`** by victory score | S — `v3-deckcond` and `v4-standing` were *both* victory 3, which is confusing |
| 30 | **Audit the remaining stale docstrings** | S — `play.py` called a method that no longer existed, and `viewer.py` described a critic that is no longer the default. Both found by accident |
| 31 | **Prune `OBS_UNREAD` as fields get encoded** | ongoing — a stale exemption hides the next `victory_bonus`. The gate catches additions, not removals that should happen |
