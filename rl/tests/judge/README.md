# The judge-scenario suite

`python3 rl/tests/test_judge.py`

Each case replays one community judge call from app.riftjudge.com inside the
RL engine and checks the engine answers the way the judge did. Unlike the
other suites this one does not stop at the first failure -- it prints one line
per scenario and a `N pass / N fail / N skip` tally, because an audit is a
report. A scenario whose cards are not scripted yet is a SKIP, never a pass.

- `riftjudge_scenarios.json` / `.md` -- the scraped questions and rulings, kept
  verbatim so a case can be re-read against its source. The `.json` holds an
  entry for **every ruling any case cites** (2036 of them), so the suite needs
  nothing outside the repo to be audited; the `.md` is the first batch's prose
  and was not grown with it. The re-runnable artifact is
  `rl/tests/test_judge.py`.
- Every case is titled with the RiftJudge question id, so `#12586` in the
  output is <https://app.riftjudge.com/questions/12586>.

Every engine bug these scenarios have found is in the tables below -- 62 of
them as of 2026-09-24 -- each fixed in the engine rather than papered over in
the test. Count the rows rather than trusting a number in this sentence; some
rows bundle several ruling ids behind one fix. The first eight (batch 1,
2026-09-15):

| # | what was wrong | fix |
|---|---|---|
| 12586 | a Might floor ignored an attached gear's bonus | `combat.set_might_mod` |
| 12560 | `[Action]` cards were playable in a Closed State (309.1.a) | `chain.speed_ok` |
| 12565 | Patched Porobot's second printed type was dropped, so a Unit Gear was never a gear (178.1) | `CardTable.type_mask` |
| 12573 | taking control of a unit and readying it fired no "when you ready me" | `resolve.OP_TAKE_CONTROL` |
| 12570 | `[Temporary]` expired silently instead of as a trigger with a response window (816) | `TR_TEMPORARY`, `phases.start_turn` |
| 12424 | a borrowed ability carried the donor's "only while I'm at a battlefield" clause | `actions.activatable` |
| 12564 | a Combat ran past a queued trigger, so "when I attack" resolved after the damage, and a unit that joined an ongoing Combat was never designated (323.2.a) | `combat.window_is_live`, `state.desig` |
| 12563 | a printed `[Flow]` cost hid a cheaper granted one (829.1.c.3) | `cost.base_flow` |

Batch 2 (2026-09-16, questions 12000-12619, 54 more cases):

| # | what was wrong | fix |
|---|---|---|
| 12477 | Eclipse's -4 carried a "minimum 1" the card does not print | `effects.SPECS["Eclipse"]` |
| 12071 | a second Ki Barrier overwrote the first instead of adding a second Prevent (437.5.a) | `resolve.OP_DAMAGE_SHIELD`, `state.block_next_ply` |
| 12381 | Soraka dying in the same lethal check as a smaller ally did not save it (370.4) | `combat._soraka_guards(batch)` |
| 12217 | an unattached gear left at a battlefield was never recalled (323.7 / 457.1) | `combat.recall_stray_gear` |
| 12008 | a kill replaced by Soraka still counted as "the killed unit", so Baited Hook played off the top | `resolve.OP_KILL` |
| 12421 | a swap ignored "can't move to base" (Zed at Vilemaw's Lair) | `resolve.OP_SWAP_LOC` |
| 12025, 12538, 12337, 12418, 12580 | "when you play" triggers fired at finalization; 419.4.a fires them once the play is completed by resolution, and never for a countered spell | `chain.spell_resolved`, `state.cards_completed`, `C_PLAY_SPELL`/`C_SPENT_E` |
| 12102 | Elder Dragon did not kill an enemy already carrying your damage, and a Cleanup skipped its lethal sweep in a Closed State (323.4-323.5 are not gated) | `state.foe_dmg`, `combat.enforce_lethal`, `chain.fire_play_unit`, `combat.cleanup` |
| 12143, 12198 | a [Repeat] reused the first execution's targets; 820.2.a gives it its own choices, and Deflect is owed per choice | `effects.repeated_spec`, `resolve.legal_targets`, `chain.resolve_top` |
| 12449 | `TargetSpec.in_showdown` was declared but never read, so Akali - Rogue Assassin could move a unit that was in no showdown | `resolve._matches` |

The 419.4.a change moved three existing tests with it: Abandoned Hall now
offers its +1 after the spell resolves (`test_battlefields`), Jhin - Virtuoso
banishes the resolved spell out of the trash instead of countering it
(`test_legends`), and a repeated Hard Bargain chooses its second target
(`test_triggers`).

Two more came out of the spell fuzz while checking these fixes: a kill cost
interrupted by an Altar of Blood offer was charged a second time (seed 250,
`actions._advance_pending`), and a deferred [Repeat] pass that stopped for a
decision still had triggers placed on top of it, stalling the game once
419.4.a queued Abandoned Hall at resolution (seed 420, `actions._settle`).

Austin's own judge calls (2026-09-16), cases `A1`-`A3`:

| case | what was wrong | fix |
|---|---|---|
| A1 | a Sprite played from a hidden Sprite Call in answer to the old Sprite's [Temporary] trigger was killed too, so the Hold was lost -- a leftover sweep killed every Temporary permanent after the triggers had resolved, though 816.1.c only expires what was there when the Beginning Phase started | `phases.resume_turn` sweeps only in v0 |
| A2 | (passed) Dusk Rose Lab kills a Sprite for the draw when ordered ahead of its Temporary trigger | -- |
| A3 | "disempower it at end of turn" ran AFTER the end-of-turn heal, so a Tornado-Warrior-empowered Steel Paws with 2 Shuriken Flip damage survived; 317.1 puts it in the Ending Step, before 317.2.b's heal | `phases.fire_end_of_turn` applies the reversals and checks lethal |

Batch 3 (2026-09-16, questions 11000-11999, 55 more cases):

| # | what was wrong | fix |
|---|---|---|
| 11124 | Deathgrip gave its +Might even when Tactical Retreat replaced the kill ("If you do") | `effects.SPECS["Deathgrip"]` kills first and gates the buff; `resolve` reads the killed unit's recorded Might |
| 11411 | "They deal damage equal to their Mights to each other" was spell damage, so Unyielding Spirit stopped Challenge; 417.6.b.3 makes the units the only source (Challenge, Rampage, Marching Orders, Gentlemen's Duel, Dragon's Rage, Clash of Giants, Carnivorous Snapvine) | `combat.mark_damage(unit_source=True)`, `resolve.OP_FIGHT` |
| 11553 | Imperial Decree ignored combat damage, so a defender left with non-lethal damage survived | `combat._assign` |
| 11983 | a spell that lost every target was countered outright; 359.3.e.1 resolves it and skips only the instructions on the lost targets, so Discipline still draws | `resolve.resolve` (and `test_effects` [4]) |
| 11895 | [Assault]/[Shield] applied in a Non-Combat Showdown; 807.1.d gives designations only during Combat | `combat.combat_role_bonus` |

Known approximations left standing: a moded spell's [Repeat] still shares one
set of choices (its slot 0 is the mode), and Emperor's Divide's "any number"
is four target slots.

One scenario is reported here rather than asserted: RiftJudge #12573 notes in
passing that Hostile Takeover also gives Irelia, Fervent a "+1 for being
chosen". The engine gives only the readied +1, because at the moment she is
chosen the opponent still controls her, and 191.4.a reads "when YOU choose me"
from her controller -- the same reasoning the ruling itself uses for FAQ #236.
The case asserts the readied half.

A ninth, found by the real-deck fuzz while these were being written: a Deflect
surcharge was planned against the card's printed cost, so a paid `[Repeat]`
could recycle the rune the surcharge had reserved (`cost.plan_surcharge`).

Batches 20-33 (2026-09-20 to 09-22, questions 9166-10292; suite at 1006 pass):

| # | what was wrong | fix |
|---|---|---|
| 10256 | Call to Battle / Shadow Dash could "move" a unit to the battlefield it was already on (355.4.a) | `resolve` TK_BATTLEFIELD slots honour `move_dest_of` |
| 10252 | a kill paid as a spell's additional cost was not "killing with a spell" (428.1.a.1), so Immortal Phoenix never saw Sacrifice | `actions._choose_cost_kill_target` sets `combat.KILLER` |
| 10266 | an ignored optional additional cost was never paid, so Bone Skewer's Clockwork Keeper drew nothing (356.4.f.1) | `combat.record_effect_play(free_costs=True)` |
| 10273 | a target whose relation slot was lost at resolution became illegal too; 359.3.e.2 re-reads only its own requirements (Facebreaker) | `resolve._matches(lost_ok=True)` |
| 10271, 10272 | a printed optional cost and a granted [Repeat] could not both be paid (The Academy); the repeat re-used the paid clause | new action **A_PLAY_BOTH** (C_REPEAT 3); second pass runs with `resolving_paid = 0`; a paid "ignore this spell's cost" still owes the Repeat |
| 10215 | Atakhan bounced before his attack trigger: "here" decayed to "anywhere" | OP_EACH_KILLS_OWN fizzles on a lost location |
| 10254 | a showdown-begins trigger was placed ABOVE attack triggers (seat order only); 464.2.b precedes 464.2.e | `state.trig` step stamp (col 6) + `chain.new_step` |
| 10174 | Fizz offered a spell whose REQUIRED kill cost had no legal payment -> assert in `legal_actions` | `resolve._can_play_from_trash` uses `can_play_with_cost_kill` |
| 10154 | two Zileans made one extra token, not two | `actions._resolve_double` re-offers for each unused Zilean |
| 9962 | Reckoner's Arena re-ran Yone's "conquer an OPEN battlefield" on a hold | OP_ACTIVATE_CONQUERS stamps `bf_prev_ctrl` |
| 9940 | Alpha Strike's split could land on Baron Nashor ("can't be chosen") | `actions.split_candidates` |
| 9780 | Undying Loyalty was only offered when its UNdiscounted cost was affordable | `chain.tag_discount_targets` gates the offer and the slot |
| 9685 | "move ... to this battlefield" sent units to base once the source had been pushed home | OP_MOVE_TO with T_HERE requires a battlefield |
| 9616 | Sun Disc's [Legion] counted Sun Disc itself | COND_PLAYED_CARD_THIS_TURN needs 2 for a permanent that arrived this turn |
| 9374 | a card ENTERING the trash never saw its own trash trigger (383.2.c.1: Phoenix killed by your spell) | `combat._destroy` checks the arriving card |
| 9374 | lethal-damage deaths held to the end of a resolution lost their killer, so "when you kill a unit with a spell" never fired via the Chain | `combat.HELD_KILLER` |
| 9241 | The Dreaming Tree's "first time each turn" was not enforced for battlefields | `combat._queue_bf_trigger` stamps `bf_first_use` |

Rejected against rules.txt this round (see `rejected.json`): #10211 (477.3.e
layer order), #10147 (464.2.b vs #10254), #9818 (419.4.a vs #10217), #9264
(no attack into an empty battlefield), #9227 (419.4.a). #10274 is asserted in
the form 465.2.c.4.a states (its worked example IS Lotus Trap).

Known gaps, deliberately not asserted:
- #9667: a spell replayed from the trash by Fizz / Kai'Sa is never offered its [Repeat].
- #9762: two [Repeat] instances (printed + Temporal Portal) -- only one is modelled (820.1.c.2 allows both).
- #9352: Bellows Breath whose targets are split across locations by a response should let the caster pick the location; the engine anchors on the first target.

Batches 34-43 (2026-09-22, questions 8540-9163; suite at 1239 pass):

| # | what was wrong | fix |
|---|---|---|
| 8819, 8622 | 471.1.b denied the Final Point by Conquer and then **returned**, dropping every "when I conquer" trigger for the rest of that Combat -- so Trinity Force could not take the eighth point off a Conquer that scored nothing itself (471.1.a.1 exempts it) | `combat._establish_control` falls through to the trigger queue; `TR_OPPONENT_SCORES` still only fires when someone scored |
| 8692, 8693 | 809.1.c covers "spells **and abilities**", but the Deflect surcharge was charged at the card path only: Ahri, Inquisitive's attack trigger and Overzealous Fan's defend trigger chose a [Deflect] unit for free | `actions._finalize_pending` charges it for an ability too, and `_slot_options` drops targets it cannot pay for while another choice remains |
| 8705 | re-attaching an Equipment to the unit already wearing it restamped `P_ATTACH_TURN`, renewing Brutalizer's "attached this turn" +2 (434.1.g/h: nothing happens) | `state.attach` returns early; OP_ATTACH skips the equipped trigger |

Rejected against rules.txt this round (see `rejected.json`): #8857 (316.8.b.1.a
/ 323.14 / 460.1 -- a Non-Combat Showdown DOES become a Combat Showdown),
#8607 (Defy reaches {any rune} of Power, and Rebuke costs two).

Two rulings contradict each other on [Legion] off Void Rush: #8943 says the
revealed unit gets it and #8836 says it does not. 419.4.b has [Legion] read
FINALIZATION, and Void Rush was finalized before it resolved, so #8943 is the
one asserted.

Known gaps added this round, deliberately not asserted:
- #8838, #8696, #8609: Arcane Shift's blink is `to_base=True`, so the unit it
  banishes always returns to base. The card says only "its owner plays it", so
  the owner should choose base or a battlefield they control -- which needs a
  destination decision during resolution, not a target slot.
- #8706: [Assault]/[Shield] read `showdown_bf`, which is already cleared when
  Establish Control queues the conquer triggers, so a conquer trigger that asks
  about Might (Sunken Temple) sees the base value. 323.2 removes the
  designations in a Cleanup, i.e. after 466.5.
- #8671: "units played from anywhere other than a player's hand have
  [Accelerate]" (Rek'Sai - Breacher) is not offered at the non-hand play paths.
- #8721: a Deflect surcharge for units chosen during RESOLUTION (Alpha Strike's
  split) is not charged; only choices made by finalization are.
- #8618: which of several simultaneous deaths a Zhonya's Hourglass replaces is
  picked by the engine, not offered to its controller. The count is asserted
  (#8617, #8809).
- #8845/#8577: Vanguard Armory's three Recruits all land at the base; the card
  lets you distribute them across legal locations. The tested half is that an
  uncontrolled battlefield is never one of them.


Batches 71-83 (2026-09-23 to 09-24, questions 6100-7101 plus a themed sweep of
the "lost target" family; suite at 2017 pass):

| # | what was wrong | fix |
|---|---|---|
| 7074 | Irelia - Graceful's discount applied once per target SLOT, so a `[Repeat]`ed spell that chose her got it twice (820.1.c.1 makes both clauses one payment) | `actions` counts distinct Irelias |
| 7056 | a **mandatory** additional cost was never paid on a free play out of a look (Baited Hook into Cruel Patron), so the unit arrived without killing anything | `state.rp_kill`, `actions._pay_rplay_cost_kill` |
| 6973 | a unit's own printed `[Accelerate]` was offered only from hand, never on a play out of a reveal | `actions._rplay_accel_ok` |
| 6756 | Temptation's `[Repeat]` could move a unit to a destination whose "where you have a unit" requirement its own first move had emptied (359.3.e.2) | `resolve` re-checks `dest_has_ally_of` at resolution |
| 6683 | a card PLAYED mid-resolution (Dazzling Aurora's reveal) was eligible for the events that resolution had already caused, so Karma - Channeler saw the recycle that revealed her; 354.3 holds her play until Aurora has finished | `actions.flush_player_events`, called before an effect plays a card |
| 6655 | Guerilla Warfare's second sentence ("you can hide cards ignoring costs this turn") was unimplemented while the card still counted as covered | new `OP_FREE_HIDE`, `state.free_hide_ply`, read by `chain.hideable` / `actions._hide_at` |
| 6498 | Pickpocket paid out its Gold token although the gear it chose had been spent in response and nothing was killed; `COND_SLOT_DIED` read "the row is dead" rather than "this resolution killed it" | `resolve` checks the resolution's own kill log (also tightens Adaptatron and Disintegrate) |
| 6364 | a unit that left a Combat's battlefield kept its designation, so walking back in never re-fired "when I attack/defend" (323.2.c strips it, 323.2.a hands it back) | `combat.cleanup` sweeps 323.2.c; new `state.desig_seat` keeps the battlefield's own "when you defend here" once per player |
| 6308 | the "becomes [Mighty]" scan looked for watchers among PERMANENTS only, so Fiora - Grand Duelist -- a legend -- never triggered at all, and case #8881 had been passing vacuously | `combat.scan_might_transitions` checks legends too |
| 9352, 11505, 11681 | a group requirement ("up to three units at the same location") anchored on whichever unit was chosen FIRST, so a Flash on that one made the spell hit the runaway and spare the two that stood still | `resolve` suspends and **asks** its controller which location the group settles at (355.11.b); `state.pend_group_loc`, `actions._finish_group_loc` |

Rejected against rules.txt this round (see `rejected.json`): #6896 (Baited
Hook's kill is the effect, not the cost -- 377.1/403.1.a), #6887
(Reinforce/[Legion] reads FINALIZATION, 812.1.c / 419.4.b), #6775 (a "you may"
trigger is decided as it goes on the Chain, 402.1), #6656 ("attack and defend
triggers only trigger the first time a unit gains the designation" is not a
rule the text has; 323.2.a/c say otherwise, and FAQ #6364 answers the same
question the opposite way -- that one is asserted instead).

`cases_83.py` is one batch on one rule: 359.3.e, "a target that is gone by
resolution". Every sub-rule has a case, because it is what the FAQ is asked
about most and the answer is always the same -- the spell resolves, the
instructions tied to the lost target are skipped, the rest happen, and it still
counts as played.

Known gaps added this round, deliberately not asserted:
- #7069: Hostile Takeover's end-of-turn hand-back is applied directly in the
  Ending Step rather than as a Chain trigger, so it cannot be responded to.
- #7089, #6698: Sett - The Boss's death replacement is unimplemented.
- #7080: Hallowed Tomb returns the champion to hand and `champion_only` accepts
  any champion rather than the Chosen one.
- #7034, #7018, #6990, #6997, #6960, #6920, #6929, #6889: the Icathian Rain /
  Falling Star reflexive-trigger family is modelled with cast-time targets. The
  rulings that ask about DECLARING both at once (#6403, #6378) are asserted;
  the ones that ask about re-aiming between instances are not.
- `OP_BLINK` plays its unit inline, so a blinked unit is never offered
  [Accelerate] and its owner never chooses base or a battlefield (#8838 family).
- #7059: which of several simultaneous deaths a Zhonya's replaces is still the
  engine's pick, not its controller's -- the same shape as the group-location
  question, which #9352 above now asks properly.

## Batch 84 (2026-09-27, questions 12602-12724)

**123 new rulings scraped, corpus 2036 -> 2159.** The range is contiguous and
12724 is the newest question the site has; 12725 and above 404. Four cases
written from it (`cases_84.py`), chosen to probe what changed in the engine this
week rather than to cover the batch evenly — **all four pass, so this batch found
no new engine bugs.**

| # | what it pins |
|---|---|
| 12648 | Deflect is charged **per choosing** (809.1.c), and 820.2.a makes each execution of a [Repeat] choose for itself: Bellows Breath repeated into a [Deflect 3] Kayle owes 6 Power, not 3. Asserted as the delta against a Kayle with no Deflect, so the number is the surcharge and not the spell's own cost baked into a constant |
| 12693 | an attack trigger fires once per combat (383.4.e) — a unit walking in mid-combat is not stunned again |
| 12716 | a Deathknell unit that arrives in the Beginning Step is there to Hold in the Scoring Step (315.2, 469.2), and 471.1.a.1 exempts a Hold, so it can be the **eighth** point |
| 12681 | two of one player's Rift Heralds dying together queue both Deathknells (383.3.d) |

Three things in the batch worth knowing that are **not** encoded as cases:

- **The rulings contradict each other on Astral Heron.** #12623 says the two
  discounts cannot be split; #12622, #12624, #12625 and #12631 all say they can,
  by playing a Reaction-speed card in the priority window between the two
  triggers resolving. The majority and the later answers permit the split
  (#12631 cites #12624), so #12623 reads as the outlier. Nothing is asserted
  either way until someone decides which the engine encodes.
- **#12648 flags its own conflict with an older FAQ** that claims Deflect is
  once per spell. The current wording and the bulk of rulings go per choosing,
  which is what the engine does and what the case above pins.
- **#12667 corrects older FAQs: the Victory Score is 8, not 7** — which is what
  `config.victory_score_full` already says.

Card names in the scraped `cards` field are as the pages rendered them, so
punctuation drifts ("Karthus Eternal" vs "Karthus, Eternal"). Normalize against
the legal pool before matching them to `cards.json`.
