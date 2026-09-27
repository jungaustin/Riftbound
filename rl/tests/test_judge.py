"""RiftJudge scenarios, replayed in the engine.

Run: python3 rl/tests/test_judge.py

Every case here is a community judge call scraped from app.riftjudge.com --
the questions and their rulings are kept verbatim in
`rl/tests/judge/riftjudge_scenarios.md`. This file asks the engine the same
question and checks it answers the way the judge did.

Unlike the other suites this one does NOT stop at the first failure: a judge
audit is a report, so every case runs and the failures are listed at the end.
A case whose cards are not scripted yet is reported as SKIP, not as a pass.
"""

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge import harness as _h


@case(12587, "marked damage counts toward lethal (Flurry 1 + 6 combat kills a 7)")
def _():
    need("Flurry of Blades")
    s = fresh()
    mine = body(s, 0, bf_loc(0), 6)
    theirs = body(s, 1, bf_loc(0), 7)
    rsv.resolve(s, T, V1, SPECS["Flurry of Blades"], 0, [], -1, True)
    assert int(s.perms[theirs, P_DMG]) == 1, "Flurry marks 1 on everything at a bf"
    s.showdown_bf = 0
    combat.damage_step(s, T, V1, 0)
    combat.enforce_lethal(s, T)
    assert s.perms[theirs, P_ALIVE] != 1, "1 marked + 6 combat is lethal on a 7"


@case(12588, "Vilemaw: a smaller attacker deals no combat damage, spell damage sticks")
def _():
    need("Vilemaw", "Flurry of Blades")
    s = fresh()
    vm = s.add_permanent(T.id_of("Vilemaw"), 1, bf_loc(0))     # 8 Might
    mine = body(s, 0, bf_loc(0), 7)
    rsv.resolve(s, T, V1, SPECS["Flurry of Blades"], 0, [], -1, True)
    assert int(s.perms[vm, P_DMG]) == 1, "spell damage is not combat damage"
    s.showdown_bf = 0
    combat.damage_step(s, T, V1, 0)
    combat.enforce_lethal(s, T)
    assert s.perms[vm, P_ALIVE] == 1, "a 7 into an 8 Vilemaw deals nothing"
    assert int(s.perms[vm, P_DMG]) == 1, "so only the Flurry damage is on it"


@case(12586, "Smoke Screen snapshots its -4 (min 1) against the gear-boosted Might")
def _():
    need("Smoke Screen", "Long Sword")
    s = fresh()
    u = body(s, 0, base_loc(0), 2)
    sw = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
    s.attach(sw, u)
    assert combat.might(s, T, u) == 4, "2 + the sword's +2"
    rsv.resolve(s, T, V1, SPECS["Smoke Screen"], 1, [u], -1, True)
    assert combat.might(s, T, u) == 1, f"floored at 1, got {combat.might(s, T, u)}"
    s.detach(sw)
    assert combat.might(s, T, u) == 0, (
        "the -3 it snapshotted stays when the gear leaves: 2 - 3, floored at 0")


@case(12585, "Fiora - Peerless checks 'one on one' when she becomes a defender")
def _():
    need("Fiora - Peerless")
    # 383.2.a.1 -- "one on one" is part of the trigger condition: two attackers
    # at designation means no trigger at all, whatever happens afterwards.
    s = fresh(seat=1)
    s.hand[0, 0], s.n_hand[0] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 0
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 0, bf_loc(0))
    a1 = body(s, 1, base_loc(1), 1, ready=True)
    a2 = body(s, 1, base_loc(1), 1, ready=True)
    attack(s, 1, 0, a1, a2)
    A._settle(s, T, V1)
    assert not any(T.names[int(s.chain[k, 0])] == "Fiora - Peerless"
                   for k in range(s.n_chain)), "two attackers: no trigger"
    combat.destroy(s, T, a2)                       # answer one afterwards
    A._settle(s, T, V1)
    assert combat.might(s, T, fi) == 3, "and removing one later does not create one"


@case(12560, "an [Action] in hand cannot answer a trigger on the chain")
def _():
    need("Emperor's Divide", "Smoke Screen", "Patched Porobot")
    s = fresh(hand=[T.id_of("Patched Porobot")])    # its play trigger opens a Chain
    for _ in range(3):                              # ...once its "if" is met
        s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
    s.hand[1, :2] = [T.id_of("Emperor's Divide"), T.id_of("Smoke Screen")]
    s.n_hand[1] = 2
    A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
    A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
    pass_priority_to(s, 1)
    assert s.n_chain > 0 and s.showdown_bf < 0, "the window under test is a Chain"
    offered = hand_plays(s, 1)
    assert "Smoke Screen" in offered, f"a [Reaction] answers it: {offered}"
    assert "Emperor's Divide" not in offered, (
        f"309.1.a -- a Closed State takes [Reaction] only: {offered}")


@case(12590, "Guards! is Main-only from hand, but playable from Hidden in a showdown")
def _():
    need("Guards!")
    g = T.id_of("Guards!")
    s = fresh(hand=[g], seat=1)
    s.bf_ctrl[0] = 1
    s.add_permanent(VANILLA, 1, bf_loc(0))
    s.add_permanent(VANILLA, 0, bf_loc(0))
    s.showdown_bf = 0
    s.priority = 1
    assert "Guards!" not in hand_plays(s, 1), "no [Action]/[Reaction] keyword"
    s2 = fresh(seat=1)
    s2.bf_ctrl[0] = 1
    _fd = list(fd_slots(0))[0]        # facedown SLOT, not battlefield
    s2.fd_owner[_fd], s2.fd_card[_fd], s2.fd_ply[_fd] = 1, g, -5
    s2.add_permanent(VANILLA, 1, bf_loc(0))
    s2.add_permanent(VANILLA, 0, bf_loc(0))
    s2.showdown_bf = 0
    s2.priority = 1
    assert 0 in chain_mod.hidden_playable(s2, T, V1, 1), (
        "811.6 gives a facedown card [Reaction], so it plays in the showdown")


@case(11777, "Brynhir's lock stops every play -- Ambush and Hidden included")
def _():
    need("Brynhir Thundersong", "Vi - Peacekeeper", "Smoke Screen")
    s = fresh()                                     # seat 0's turn
    s.hand[1, :2] = [T.id_of("Vi - Peacekeeper"), T.id_of("Smoke Screen")]
    s.n_hand[1] = 2
    s.bf_ctrl[0] = 1
    s.add_permanent(VANILLA, 1, bf_loc(0))
    _fd = list(fd_slots(0))[0]
    s.fd_owner[_fd], s.fd_card[_fd], s.fd_ply[_fd] = 1, T.id_of("Back Off"), -5
    bry = s.add_permanent(T.id_of("Brynhir Thundersong"), 0, base_loc(0))
    spec = abilities_for(T, T.id_of("Brynhir Thundersong"))[0]
    rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=bry)
    src = s.add_permanent(VANILLA, 0, bf_loc(0))
    chain_mod.queue(s, __import__("rl.engine.effects", fromlist=["x"]).TR_PLAY_ME,
                    src, bf_loc(0))
    A._settle(s, T, V1)
    pass_priority_to(s, 1)
    legal = A.legal_actions(s, T, V1, 1)
    assert not [a for a in legal if a.kind in (A.A_PLAY, A.A_PLAY_REPEAT)], (
        "no card at all -- not a [Reaction], not the [Ambush] unit")
    assert not [a for a in legal if a.kind == A.A_PLAY_HIDDEN], (
        "and not the facedown card either")


@case(12452, "a legend's activated ability can be answered with an Ambush unit")
def _():
    need("Lillia - Bashful Bloom", "Rengar, Trophy Hunter")
    s = fresh()                                     # seat 0's turn
    s.hand[1, 0] = T.id_of("Rengar, Trophy Hunter")
    s.n_hand[1] = 1
    s.legend[0], s.legend_ready[0] = T.id_of("Lillia - Bashful Bloom"), 1
    s.add_permanent(VANILLA, 0, bf_loc(0))          # enemy ground for Rengar
    act = next(a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE)
    A.apply(s, T, V1, act)
    assert s.n_chain == 1, "the legend ability is a Chain Item (377.3)"
    pass_priority_to(s, 1)
    assert A.ambush_playable(s, T, V1, 1), (
        "Trophy Hunter may Ambush onto enemy ground in that window")


@case(12572, "a triggered ability opens a Closed State the opponent may answer")
def _():
    need("Astral Heron", "Smoke Screen")
    s = fresh(hand=[VANILLA])
    s.hand[1, 0] = T.id_of("Smoke Screen")
    s.n_hand[1] = 1
    s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    s.add_permanent(VANILLA, 1, bf_loc(1))
    A.apply(s, T, V1, A.Action(A.A_PLAY, 0))        # first card this turn
    A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
    A._settle(s, T, V1)
    pass_priority_to(s, 1)
    assert s.n_chain >= 1, "Heron's trigger is on the chain"
    assert "Smoke Screen" in hand_plays(s, 1), "so the opponent gets a window"


@case(12582, "a BATTLEFIELD's trigger is a Chain Item and can be reacted to")
def _():
    need("Seat of Power", "Smoke Screen")
    s = fresh()
    s.hand[1, 0] = T.id_of("Smoke Screen")
    s.n_hand[1] = 1
    s.bf_card[0] = T.id_of("Seat of Power")
    s.add_permanent(VANILLA, 1, bf_loc(1))
    mover = s.add_permanent(VANILLA, 0, base_loc(0), ready=True)
    A.apply(s, T, V1, A.Action(A.A_DECLARE, bf_loc(0)))
    A.apply(s, T, V1, A.Action(A.A_ADD, mover))
    A.apply(s, T, V1, A.Action(A.A_COMMIT))
    for _ in range(8):                              # close the Showdown first
        if s.n_chain or s.n_trig:
            break
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who)
        nxt = next((a for a in legal if a.kind == A.A_PASS), None)
        if nxt is None:
            break
        A.apply(s, T, V1, nxt)
    A._settle(s, T, V1)
    pass_priority_to(s, 1)
    assert s.n_chain >= 1, "conquering fires the battlefield's own trigger"
    assert "Smoke Screen" in hand_plays(s, 1), "and it can be answered"


@case(12583, "Shen's 'when I hold' is a trigger, so it can be answered")
def _():
    need("Shen, Leader of the Kinkou Order", "Smoke Screen")
    s = fresh()
    s.hand[1, 0] = T.id_of("Smoke Screen")
    s.n_hand[1] = 1
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Shen, Leader of the Kinkou Order"), 0, bf_loc(0))
    s.add_permanent(VANILLA, 0, bf_loc(0))
    phases.score_holds(s, V1, T)
    A._settle(s, T, V1)
    pass_priority_to(s, 1)
    assert s.n_chain >= 1, "the hold trigger is on the chain"
    assert "Smoke Screen" in hand_plays(s, 1), "and the opponent may respond"


@case(12584, "a 'when you play me' trigger is answerable; the unit itself is not")
def _():
    need("Patched Porobot", "Lilting Lullaby")
    s = fresh(hand=[T.id_of("Patched Porobot")])
    s.hand[1, 0] = T.id_of("Lilting Lullaby")       # [Reaction] counter a spell
    s.n_hand[1] = 1
    A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
    A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
    assert any(int(s.perms[i, P_CARD]) == T.id_of("Patched Porobot")
               and s.perms[i, P_ALIVE] == 1 for i in range(s.n_perms)), (
        "337.2 -- the unit resolves immediately, it never sits on the Chain")
    A._settle(s, T, V1)
    counters = [a for a in A.legal_actions(s, T, V1, 1) if a.kind == A.A_PLAY]
    if s.n_chain:
        spec = SPECS["Lilting Lullaby"]
        assert not rsv.legal_targets(s, T, spec, 0, 1, [], -1), (
            "a triggered ability is not a spell, so 'counter a spell' misses it")


@case(11889, "Shuriken Flip's damage kills in Cleanup, BEFORE its move stages a combat")
def _():
    need("Shuriken Flip")
    s = fresh()
    s.bf_ctrl[0] = 1                                # theirs, one 2 Might body
    foe = body(s, 1, bf_loc(0), 2)
    mine = body(s, 0, base_loc(0), 3, ready=True)
    spec = SPECS["Shuriken Flip"]
    targets = [foe, bf_loc(0), mine]                # deal 2, then move me in
    rsv.resolve(s, T, V1, spec, 0, targets, -1, True)
    A._settle(s, T, V1)
    assert s.perms[foe, P_ALIVE] != 1, "2 damage on a 2 Might unit is lethal"
    assert int(s.perms[mine, P_LOC]) == bf_loc(0), "and my unit made the move"
    assert s.showdown_combat == 0, (
        "323.4-5 kills before 323.8-9 stages: no enemy is left to fight")
    assert int(s.bf_ctrl[0]) == 0, "so the move just conquers (348.2.a.1)"

    alive = fresh()                                 # the survivor case
    alive.bf_ctrl[0] = 1
    tough = body(alive, 1, bf_loc(0), 5)
    m2 = body(alive, 0, base_loc(0), 1, ready=True)
    rsv.resolve(alive, T, V1, spec, 0, [tough, bf_loc(0), m2], -1, True)
    assert alive.perms[tough, P_ALIVE] == 1, "5 Might survives 2 damage"
    A._settle(alive, T, V1)
    assert alive.perms[m2, P_ALIVE] != 1 and alive.perms[tough, P_ALIVE] == 1, (
        "so a Combat IS staged, and my 1 Might unit loses it")
    assert int(alive.bf_ctrl[0]) == 1, "the battlefield stays theirs"


@case(12450, "Shuriken Flip has no [Action]/[Reaction], so a showdown locks it out")
def _():
    need("Shuriken Flip", "Back Off")
    s = fresh(hand=[T.id_of("Shuriken Flip"), T.id_of("Back Off")])
    s.add_permanent(VANILLA, 0, bf_loc(0))
    s.add_permanent(VANILLA, 1, bf_loc(0))
    s.showdown_bf, s.showdown_combat, s.priority = 0, 1, 0
    offered = hand_plays(s, 0)
    assert "Back Off" in offered, "[Action] plays in a showdown"
    assert "Shuriken Flip" not in offered, (
        f"343.1.a -- [Flow] is not a speed keyword: {offered}")
    assert not [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_DECLARE], (
        "144.1.c -- and the unit at base cannot Standard Move back in either")

    main = fresh(hand=[T.id_of("Shuriken Flip")])    # it is a Main-phase card
    main.add_permanent(VANILLA, 0, base_loc(0), ready=True)
    main.add_permanent(VANILLA, 1, bf_loc(0))
    assert "Shuriken Flip" in hand_plays(main, 0), "outside a showdown it plays"


@case(12589, "Back Off resolving leaves the showdown open, so an [Action] may follow")
def _():
    need("Back Off", "Emperor's Divide")
    s = fresh(hand=[T.id_of("Emperor's Divide")])   # seat 0 attacks, holds an Action
    s.bf_ctrl[0] = 1
    s.add_permanent(VANILLA, 1, bf_loc(0))
    _fd = list(fd_slots(0))[0]
    s.fd_owner[_fd], s.fd_card[_fd], s.fd_ply[_fd] = 1, T.id_of("Back Off"), -5
    mover = s.add_permanent(VANILLA, 0, base_loc(0), ready=True)
    A.apply(s, T, V1, A.Action(A.A_DECLARE, bf_loc(0)))
    A.apply(s, T, V1, A.Action(A.A_ADD, mover))
    A.apply(s, T, V1, A.Action(A.A_COMMIT))
    pass_priority_to(s, 1)
    hid = [a for a in A.legal_actions(s, T, V1, 1) if a.kind == A.A_PLAY_HIDDEN]
    assert hid, "the facedown Back Off is a [Reaction] here (811.6)"
    A.apply(s, T, V1, hid[0])
    for _ in range(8):                              # resolve the chain it made
        if s.n_chain == 0 and not chain_mod.decision_open(s):
            break
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who)
        A.apply(s, T, V1, next((a for a in legal if a.kind == A.A_PASS), legal[0]))
    assert s.showdown_bf == 0, "347.1.b -- resolving it does not close the showdown"
    pass_priority_to(s, 0)
    assert "Emperor's Divide" in hand_plays(s, 0), (
        "focus comes back around and an [Action] is legal again")


@case(12591, "attacker/defender is fixed at the start; a late arrival inherits it")
def _():
    need("Glasc Mixologist")
    s = fresh(seat=1)                               # seat 1 attacks seat 0's bf
    s.hand[0, 0] = T.id_of("Smoke Screen")          # keeps the window open
    s.n_hand[0] = 1
    s.bf_ctrl[0] = 0
    mix = s.add_permanent(T.id_of("Glasc Mixologist"), 0, bf_loc(0))
    s.trash[0, 0], s.n_trash[0] = VANILLA, 1
    mover = body(s, 1, base_loc(1), 6, ready=True)
    A.apply(s, T, V1, A.Action(A.A_DECLARE, bf_loc(0)))
    A.apply(s, T, V1, A.Action(A.A_ADD, mover))
    A.apply(s, T, V1, A.Action(A.A_COMMIT))
    assert s.showdown_bf == 0 and int(s.attacker) == 1, "seat 1 applied Contested"
    combat.destroy(s, T, mix)                       # it dies mid-combat
    A._settle(s, T, V1)
    for _ in range(12):                             # take the Deathknell's offer
        if s.n_chain == 0 and not chain_mod.decision_open(s) \
                and s.pend_slot < 0 and s.pend_may < 0:
            break                                   # and let it resolve (FEPR)
        legal = A.legal_actions(s, T, V1, A.acting_seat(s))
        pick = next((a for a in legal if a.kind == A.A_TARGET
                     and a.arg == bf_loc(0)),
                    next((a for a in legal if a.kind == A.A_PASS), legal[0]))
        A.apply(s, T, V1, pick)
    new = [i for i in range(s.n_perms)
           if s.perms[i, P_ALIVE] == 1 and int(s.perms[i, P_CTRL]) == 0
           and int(s.perms[i, P_LOC]) == bf_loc(0)]
    assert new, "the Deathknell played a unit from the trash into the combat"
    assert int(s.perms[new[0], P_DMG]) == 0, "12569 -- it enters with no damage"
    assert s.showdown_bf == 0 and int(s.attacker) == 1, (
        "464.2.c -- the designation does not move to the newcomer's controller")
    assert combat.in_combat(s, new[0]), "it joins the fight as a defender"


@case(12562, "The Harrowing PLAYS from the trash -- it never banishes")
def _():
    need("The Harrowing")
    s = fresh(hand=[T.id_of("The Harrowing")])
    s.trash[0, 0], s.n_trash[0] = VANILLA, 1
    spec = SPECS["The Harrowing"]
    from rl.engine.effects import pack_trash
    assert rsv.legal_targets(s, T, spec, 0, 0, [], -1) == [pack_trash(0, VANILLA)], (
        "359.3.e -- it targets the card in the trash, so it can be answered")
    log = rsv.resolve(s, T, V1, spec, 0,
                      [pack_trash(0, VANILLA), base_loc(0)], -1, True)
    assert log.get("played_from_trash"), "the unit is PLAYED, not returned"
    assert int(s.n_trash[0]) == 0, "it left the trash"
    assert int(s.n_banished[0]) == 0, "and nothing was banished on the way"
    assert any(int(s.perms[i, P_CARD]) == VANILLA and s.perms[i, P_ALIVE] == 1
               for i in range(s.n_perms)), "it is a new object on the board"


@case(12565, "Patched Porobot is a Unit AND a Gear: killing it as gear is a unit death")
def _():
    need("Jayce, Man of Progress", "Viktor - Leader", "Patched Porobot")
    por = T.id_of("Patched Porobot")
    assert T.is_type(por, "Unit") and T.is_type(por, "Gear"), (
        "178.1 -- a dual-type card has the properties of both types")
    s = fresh(hand=[T.id_of("Jayce, Man of Progress")])
    p = s.add_permanent(por, 0, base_loc(0))
    s.add_permanent(T.id_of("Viktor - Leader"), 0, base_loc(0))
    A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
    A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
    A._settle(s, T, V1)
    for _ in range(14):                             # accept, then kill the Poro
        if s.n_chain == 0 and not chain_mod.decision_open(s) \
                and s.pend_slot < 0 and s.pend_may < 0:
            break
        legal = A.legal_actions(s, T, V1, A.acting_seat(s))
        pick = next((a for a in legal if a.kind == A.A_TARGET and a.arg == p),
                    next((a for a in legal if a.kind == A.A_PASS), legal[0]))
        A.apply(s, T, V1, pick)
    assert s.perms[p, P_ALIVE] != 1, "Jayce's 'kill a friendly gear' reached it"
    recruits = [i for i in range(s.n_perms) if s.perms[i, P_ALIVE] == 1
                and "Recruit" in T.names[int(s.perms[i, P_CARD])]]
    assert recruits, "so Viktor saw a non-Recruit unit of yours die"


@case(12566, "a Gold token is a gear, so killing it is not a unit's death")
def _():
    need("Bushwhack", "Viktor - Leader")
    s = fresh()
    s.add_permanent(T.id_of("Viktor - Leader"), 0, base_loc(0))
    rsv.resolve(s, T, V1, SPECS["Bushwhack"], 0, [], -1, True)
    gold = next(i for i in range(s.n_perms)
                if T.names[int(s.perms[i, P_CARD])].startswith("Gold"))
    assert s.has_flag(gold, F_NON_UNIT), "187.5 -- the Gold token is not a unit"
    s.perms[gold, P_READY] = 1                      # Bushwhack makes it exhausted
    for a in [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]:
        A.apply(s, T, V1, a)                        # "Kill this, Exhaust: Add"
    drain(s)
    assert s.perms[gold, P_ALIVE] != 1, "it killed itself as a cost"
    assert not [i for i in range(s.n_perms) if s.perms[i, P_ALIVE] == 1
                and "Recruit" in T.names[int(s.perms[i, P_CARD])]], (
        "Viktor's 'when another unit you control dies' must not see a gear")


@case(12567, "cashing a Gold token in adds Power -- it is not a Recycle")
def _():
    need("Bushwhack")
    s = fresh()
    rsv.resolve(s, T, V1, SPECS["Bushwhack"], 0, [], -1, True)
    gold = next(i for i in range(s.n_perms)
                if T.names[int(s.perms[i, P_CARD])].startswith("Gold"))
    s.perms[gold, P_READY] = 1
    before = int(s.recycled_n[0])
    for a in [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]:
        A.apply(s, T, V1, a)
    drain(s)
    assert int(s.pool_power[0].sum()) == 1, "416.1.b -- it adds one Power"
    assert int(s.recycled_n[0]) == before, (
        "and nothing was recycled, so a 'when you recycle a rune' never fires")


@case(12569, "a unit replayed by a Deathknell enters fresh, with no damage")
def _():
    need("Glasc Mixologist")
    s = fresh()
    hurt = body(s, 0, base_loc(0))
    s.perms[hurt, P_DMG] = 2
    combat.destroy(s, T, hurt)                      # it dies damaged...
    assert int(s.trash[0, int(s.n_trash[0]) - 1]) == VANILLA, "...into the trash"
    mix = s.add_permanent(T.id_of("Glasc Mixologist"), 0, base_loc(0))
    combat.destroy(s, T, mix)
    A._settle(s, T, V1)
    for _ in range(12):
        if s.n_chain == 0 and not chain_mod.decision_open(s) \
                and s.pend_slot < 0 and s.pend_may < 0:
            break
        legal = A.legal_actions(s, T, V1, A.acting_seat(s))
        A.apply(s, T, V1, next((a for a in legal if a.kind == A.A_PASS), legal[0]))
    back = [i for i in range(s.n_perms) if s.perms[i, P_ALIVE] == 1
            and int(s.perms[i, P_CARD]) == VANILLA]
    assert back, "the Deathknell played it back out of the trash"
    assert int(s.perms[back[0], P_DMG]) == 0, (
        "317 -- damage does not persist on a card in the trash")


@case(12570, "a Sprite's [Temporary] expiry is a trigger you may answer")
def _():
    need("Fading Memories", "Star-Crossed")
    s = fresh()
    s.hand[0, 0], s.n_hand[0] = T.id_of("Star-Crossed"), 1
    mine = body(s, 0, bf_loc(0))
    rsv.resolve(s, T, V1, SPECS["Fading Memories"], 0, [mine], -1, True)
    assert combat.perm_kw(s, T, mine, "Temporary"), "it now expires on my turn"
    body(s, 1, bf_loc(1))                           # Star-Crossed needs an enemy
    phases.start_turn(s, T, V1)
    A._settle(s, T, V1)
    assert s.n_chain >= 1, (
        "816 -- [Temporary] is a triggered ability, so it opens a Closed State")
    assert s.perms[mine, P_ALIVE] == 1, "and nothing has died yet"
    assert "Star-Crossed" in hand_plays(s, 0), (
        "so a [Reaction] can answer the expiry (FAQ #6571 / #5523)")
    drain(s)
    assert s.perms[mine, P_ALIVE] != 1, "then it resolves and the unit dies"

    lone = fresh()                                  # no enemy unit: no cast
    lone.hand[0, 0], lone.n_hand[0] = T.id_of("Star-Crossed"), 1
    solo = body(lone, 0, bf_loc(0))
    rsv.resolve(lone, T, V1, SPECS["Fading Memories"], 0, [solo], -1, True)
    phases.start_turn(lone, T, V1)
    A._settle(lone, T, V1)
    assert "Star-Crossed" not in hand_plays(lone, 0), (
        "355.8 -- it needs BOTH a friendly and an enemy unit to be played")


@case(12573, "Hostile Takeover readies the unit as its new controller")
def _():
    need("Hostile Takeover", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("Hostile Takeover")])
    s.bf_ctrl[0] = 1
    ire = s.add_permanent(T.id_of("Irelia, Fervent"), 1, bf_loc(0), ready=False)
    base = combat.might(s, T, ire)
    A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
    A.apply(s, T, V1, A.Action(A.A_TARGET, ire))
    drain(s)
    assert int(s.perms[ire, P_CTRL]) == 0 and int(s.perms[ire, P_READY]) == 1, (
        "control changes first, then she is readied")
    assert combat.might(s, T, ire) == base + 1, (
        f"191.4.a -- 'when you ready me' is read from her NEW controller "
        f"(got {combat.might(s, T, ire)}, base {base})")

    ready = fresh(hand=[T.id_of("Hostile Takeover")])
    ready.bf_ctrl[0] = 1
    i2 = ready.add_permanent(T.id_of("Irelia, Fervent"), 1, bf_loc(0), ready=True)
    b2 = combat.might(ready, T, i2)
    A.apply(ready, T, V1, A.Action(A.A_PLAY, 0))
    A.apply(ready, T, V1, A.Action(A.A_TARGET, i2))
    drain(ready)
    assert combat.might(ready, T, i2) == b2, (
        "415.1.c -- a unit that is already ready is not readied again")


@case(12424, "Heimerdinger's borrowed ability leaves the donor's restriction behind")
def _():
    need("Heimerdinger - Inventor", "Renata Glasc - Mastermind")
    s = fresh()
    h = s.add_permanent(T.id_of("Heimerdinger - Inventor"), 0, base_loc(0),
                        ready=True)
    r = s.add_permanent(T.id_of("Renata Glasc - Mastermind"), 0, base_loc(0),
                        ready=True)
    acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
    borrowed = [A.unpack_activate(a.arg) for a in acts]
    assert not [b for b in borrowed if b[0] == r], (
        "Renata herself is at a base, so her own text stops her")
    assert [b for b in borrowed if b[0] == h and b[1] == r], (
        "but Heimerdinger HAS the exhaust ability, and 'only while I'm at a "
        "battlefield' is Renata's clause, not part of what he copied")


@case(12579, "a token needs no card behind it, and leaves none when it dies")
def _():
    need("Zed, Without a Sound")
    s = fresh()
    zed = s.add_permanent(T.id_of("Zed, Without a Sound"), 0, bf_loc(0))
    spec = next(a for a in abilities_for(T, T.id_of("Zed, Without a Sound"))
                if a.trigger == __import__("rl.engine.effects",
                                           fromlist=["x"]).TR_CONQUER)
    rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=zed)
    tok = next(i for i in range(s.n_perms) if s.perms[i, P_ALIVE] == 1
               and "Shadow Clone" in T.names[int(s.perms[i, P_CARD])])
    assert T.is_token(int(s.perms[tok, P_CARD])), "185 -- a token is not a card"
    combat.destroy(s, T, zed)
    assert s.perms[tok, P_ALIVE] == 1, "it outlives the effect that made it"
    before = int(s.n_trash[0])
    combat.destroy(s, T, tok)
    assert int(s.n_trash[0]) == before, (
        "186.1 -- and it ceases to exist rather than reaching a zone")


@case(12564, "a unit played INTO a combat attacks: Kennen triggers twice")
def _():
    need("Kennen, Keeper of Balance", "Ava Achiever")
    ken = T.id_of("Kennen, Keeper of Balance")
    s = fresh(hand=[ken])                           # he has [Hidden], Ava's fuel
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 3)
    ava = s.add_permanent(T.id_of("Ava Achiever"), 0, base_loc(0), ready=True)
    A.apply(s, T, V1, A.Action(A.A_DECLARE, bf_loc(0)))
    A.apply(s, T, V1, A.Action(A.A_ADD, ava))
    A.apply(s, T, V1, A.Action(A.A_COMMIT))
    assert s.showdown_bf == 0, (
        "the Combat must still be open -- Ava's attack trigger is pending")
    offers = 0
    for _ in range(30):
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        if not legal:
            break
        item = chain_mod.oldest_pending(s)
        if item >= 0 and int(s.chain[item, __import__(
                "rl.engine.state", fromlist=["x"]).C_CARD]) == ken \
                and any(a.kind == A.A_ACCEPT for a in legal):
            offers += 1
        pick = next((a for a in legal if a.kind == A.A_ACCEPT),
                    next((a for a in legal if a.kind == A.A_TARGET and a.arg == foe),
                         next((a for a in legal if a.kind == A.A_PASS), legal[0])))
        A.apply(s, T, V1, pick)
        if s.showdown_bf < 0 and s.n_chain == 0:
            break
    assert any(int(s.perms[i, P_CARD]) == ken and s.perms[i, P_ALIVE] == 1
               for i in range(s.n_perms)), "Ava played him into her battlefield"
    assert offers == 2, (
        f"383.4 -- one instance for 'when you play me' and one for the "
        f"Attacker designation he inherits in the next Cleanup (323.2.a); "
        f"got {offers}")


@case(12563, "Kennen's granted [Flow] is a second, cheaper Flow cost")
def _():
    need("Kennen, Storm of Shuriken", "Brittle Steel", "Long Sword")
    from rl.engine.cost import base_flow
    ken, bs = T.id_of("Kennen, Storm of Shuriken"), T.id_of("Brittle Steel")
    assert (int(T.flow_energy[bs]), int(T.flow_power[bs])) == (4, 1), (
        "the printed [Flow] this case is about")
    s = fresh()
    s.runes_ready[:, :] = 3
    k = s.add_permanent(ken, 0, bf_loc(0))
    s.add_permanent(T.id_of("Long Sword"), 1, bf_loc(1))    # something to kill
    s.trash[0, 0], s.n_trash[0] = bs, 1
    assert base_flow(s, T, 0, bs) == (4, 1), "with no grant, the printed cost"
    spec = next(a for a in abilities_for(T, ken)
                if a.trigger == __import__("rl.engine.effects",
                                           fromlist=["x"]).TR_CONQUER)
    from rl.engine.effects import pack_trash
    rsv.resolve(s, T, V1, spec, 0, [pack_trash(0, bs)], -1, False, source=k)
    assert base_flow(s, T, 0, bs) == (int(T.energy[bs]), int(T.power[bs])), (
        "829.1.c.3 -- both instances exist and the controller takes the "
        "cheaper: Kennen's 'equal to its cost' beats the printed 4 Energy")
    play = next(a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_PLAY_FLOW)
    runes = int(s.runes_ready[0].sum())
    A.apply(s, T, V1, play)
    drain(s)
    assert int(s.n_banished[0]) == 1, "829.1.b -- a Flow play banishes the card"
    assert runes - int(s.runes_ready[0].sum()) == 3, (
        "2 Energy exhausted plus the 1 Power recycled, not the printed 4+1")
    assert int(s.flow_grant_card[0, 0]) == -1, "and the grant was spent"


@case(12543, "a unit killed during the showdown assigns no combat damage")
def _():
    s = fresh(seat=0)                               # seat 0 attacks
    s.hand[1, 0], s.n_hand[1] = T.id_of("Smoke Screen"), 1   # keeps it open
    s.bf_ctrl[0] = 1
    dfn = body(s, 1, bf_loc(0), 5)
    atk = body(s, 0, base_loc(0), 4, ready=True)
    A.apply(s, T, V1, A.Action(A.A_DECLARE, bf_loc(0)))
    A.apply(s, T, V1, A.Action(A.A_ADD, atk))
    A.apply(s, T, V1, A.Action(A.A_COMMIT))
    assert s.showdown_bf == 0 and s.perms[atk, P_DMG] == 0, (
        "the Showdown Step comes before any damage is assigned")
    combat.mark_damage(s, T, atk, 4, by_seat=1)     # as a Reaction would
    A._settle(s, T, V1)
    assert s.perms[atk, P_ALIVE] != 1, (
        "323.4 -- the Cleanup that follows the response kills it")
    drain(s)
    assert int(s.perms[dfn, P_DMG]) == 0 and s.perms[dfn, P_ALIVE] == 1, (
        "465.1 -- with no attacker left there is no Combat Damage Step at all")
    assert int(s.bf_ctrl[0]) == 1, "and the defender keeps the battlefield"


@case(12002, "Bellows Breath follows its lone target to base after a Flash")
def _():
    need("Bellows Breath", "Flash")
    s = fresh(hand=[T.id_of("Bellows Breath")])
    give(s, 1, "Flash")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 1)
    cast(s, 0, "Bellows Breath", u, -1, -1)
    cast(s, 1, "Flash", u, -1)
    drain(s)
    assert int(s.perms[u, P_LOC]) == base_loc(1) or not alive(s, u), "Flash moved it"
    assert not alive(s, u), (
        "'same location' is a cast-time restriction; one target is always "
        "at the same location as itself, so the 1 damage lands at base")


@case(12218, "Star-Crossed still returns the target that stayed legal")
def _():
    need("Star-Crossed", "Gust")
    s = fresh(hand=[T.id_of("Star-Crossed")])
    give(s, 1, "Gust")
    mine = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Star-Crossed", mine, theirs)
    cast(s, 1, "Gust", mine)
    drain(s)
    assert not alive(s, mine) and VANILLA in list(s.hand[0, :int(s.n_hand[0])]), (
        "Gust returned my unit")
    assert not alive(s, theirs), (
        "359.3.e.8 -- no fizzle: the enemy half of Star-Crossed still resolves")
    assert VANILLA in list(s.hand[1, :int(s.n_hand[1])]), "to its owner's hand"


@case(12203, "a countered Back Off does nothing -- not even its draw")
def _():
    need("Back Off", "Defy")
    s = fresh(hand=[T.id_of("Back Off")])
    give(s, 1, "Defy")
    foe = body(s, 1, bf_loc(0), 3)
    before = int(s.n_hand[0])
    cast(s, 0, "Back Off", foe)
    item = int(s.chain[s.n_chain - 1, __import__(
        "rl.engine.state", fromlist=["x"]).C_UID])
    cast(s, 1, "Defy", item)
    drain(s)
    assert not s.has_flag(foe, F_STUNNED), "the stun never happened"
    assert int(s.n_hand[0]) == before - 1, "and no card was drawn"
    assert T.id_of("Back Off") in list(s.trash[0, :int(s.n_trash[0])]), (
        "a countered spell goes to its owner's trash")


@case(12073, "Singularity's 6 then Stupefy's -1 kills a 7 Might unit")
def _():
    need("Singularity", "Stupefy")
    s = fresh()
    u = body(s, 1, bf_loc(0), 7)
    rsv.resolve(s, T, V1, SPECS["Singularity"], 0, [u, -1], -1, True)
    A._settle(s, T, V1)
    assert alive(s, u) and int(s.perms[u, P_DMG]) == 6, "6 on a 7 is not lethal"
    rsv.resolve(s, T, V1, SPECS["Stupefy"], 0, [u], -1, True)
    A._settle(s, T, V1)
    assert not alive(s, u), "143.2.a -- Might 6 now meets the 6 marked damage"


@case(12225, "Falling Star marks damage and leaves Might untouched")
def _():
    need("Falling Star")
    s = fresh()
    u = body(s, 1, base_loc(1), 6)
    rsv.resolve(s, T, V1, SPECS["Falling Star"], 0, [u, -1], -1, True)
    assert combat.might(s, T, u) == 6 and int(s.perms[u, P_DMG]) == 3


@case(12539, "Void Gate adds +1 to EACH instance: Falling Star twice is 8")
def _():
    need("Falling Star", "Void Gate")
    s = fresh()
    s.bf_card[0] = T.id_of("Void Gate")
    u = body(s, 1, bf_loc(0), 10)
    rsv.resolve(s, T, V1, SPECS["Falling Star"], 0, [u, u], -1, True)
    assert int(s.perms[u, P_DMG]) == 8, (
        f"715.2 -- 4 + 4, got {int(s.perms[u, P_DMG])}")
    away = fresh()
    away.bf_card[0] = T.id_of("Void Gate")
    v = body(away, 1, base_loc(1), 10)
    rsv.resolve(away, T, V1, SPECS["Falling Star"], 0, [v, v], -1, True)
    assert int(away.perms[v, P_DMG]) == 6, "not at the Gate: 3 + 3"


@case(12071, "two Ki Barriers are two Prevent pools: 14 prevented")
def _():
    need("Ki Barrier")
    s = fresh()
    u = body(s, 0, base_loc(0), 20)
    rsv.resolve(s, T, V1, SPECS["Ki Barrier"], 0, [u], -1, True)
    rsv.resolve(s, T, V1, SPECS["Ki Barrier"], 0, [u], -1, True)
    combat.mark_damage(s, T, u, 14, by_seat=1)
    assert int(s.perms[u, P_DMG]) == 0, (
        f"437.1.b.1 -- 7 + 7 prevented, got {int(s.perms[u, P_DMG])} through")
    combat.mark_damage(s, T, u, 1, by_seat=1)
    assert int(s.perms[u, P_DMG]) == 1, "and the 15th point gets through"


@case(12184, "a stunned unit chosen by Rampage still deals its Might")
def _():
    need("Rampage")
    s = fresh()
    mine = body(s, 0, bf_loc(0), 4)
    s.stun(mine)
    foe = body(s, 1, bf_loc(0), 6)
    rsv.resolve(s, T, V1, SPECS["Rampage"], 0, [mine, foe], -1, True)
    assert int(s.perms[foe, P_DMG]) == 4, (
        "423.1.b -- stun only stops COMBAT damage")
    assert int(s.perms[mine, P_DMG]) == 6 or not alive(s, mine)


@case(12201, "Flurry of Blades hits Baron Nashor -- it never chooses him")
def _():
    need("Flurry of Blades", "Baron Nashor")
    s = fresh()
    baron = s.add_permanent(T.id_of("Baron Nashor"), 1, bf_loc(0))
    rsv.resolve(s, T, V1, SPECS["Flurry of Blades"], 0, [], -1, True)
    assert int(s.perms[baron, P_DMG]) == 1, "352.10.d -- 'each' is not a choice"


@case(12274, "Stupefy in answer to Frozen Fortress kills a 2 Might unit")
def _():
    need("Frozen Fortress", "Stupefy")
    for with_stupefy in (True, False):
        s = fresh()
        s.bf_card[0] = T.id_of("Frozen Fortress")
        s.bf_ctrl[0] = 1
        tok = body(s, 1, bf_loc(0), 2)
        if with_stupefy:
            give(s, 0, "Stupefy")
        phases.start_turn(s, T, V1)                  # seat 0's Beginning Phase
        A._settle(s, T, V1)
        assert s.n_chain >= 1, "the Fortress trigger is a Chain item"
        if with_stupefy:
            cast(s, 0, "Stupefy", tok)
        drain(s)
        assert alive(s, tok) != with_stupefy, (
            "Might 1 with 1 marked is lethal" if with_stupefy
            else "without the Stupefy a 2 survives 1")


@case(12476, "Forbidding Waste's -2 on a lone defender outlasts a Discipline")
def _():
    need("Forbidding Waste", "Discipline")
    s = fresh(seat=1)
    s.bf_card[0] = T.id_of("Forbidding Waste")
    s.bf_ctrl[0] = 0
    s.hand[0, 0], s.n_hand[0] = T.id_of("Smoke Screen"), 1  # keeps it open
    bird = body(s, 0, bf_loc(0), 1)
    atk = body(s, 1, base_loc(1), 5, ready=True)
    attack(s, 1, 0, atk)
    assert combat.might(s, T, bird) == 0, "1 - 2, shown as 0"
    rsv.resolve(s, T, V1, SPECS["Discipline"], 0, [bird], -1, True)
    assert combat.might(s, T, bird) == 1, (
        f"477.3 -- 1 + 2 - 2, got {combat.might(s, T, bird)}")


@case(12477, "Eclipse takes Might negative; Discipline adds on top of it")
def _():
    need("Eclipse", "Discipline")
    s = fresh()
    u = body(s, 0, base_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Eclipse"], 1, [u], -1, True)
    rsv.resolve(s, T, V1, SPECS["Discipline"], 0, [u], -1, True)
    assert combat.might(s, T, u) == 1, (
        f"143.2.b -- -1 is kept for arithmetic: -1 + 2 = 1, "
        f"got {combat.might(s, T, u)}")


@case(12043, "an empowered Mel's extra -1 still respects Stupefy's floor")
def _():
    need("Stupefy", "Mel, Newly Awakened")
    s = fresh()
    mel = s.add_permanent(T.id_of("Mel, Newly Awakened"), 0, base_loc(0))
    s.set_flag(mel, __import__("rl.engine.state", fromlist=["x"]).F_EMPOWERED)
    u = body(s, 1, bf_loc(0), 2)
    rsv.resolve(s, T, V1, SPECS["Stupefy"], 0, [u], -1, True)
    assert combat.might(s, T, u) == 1, (
        f"477.3.b -- the minimum is part of Stupefy's own effect, "
        f"got {combat.might(s, T, u)}")
    big = body(s, 1, bf_loc(1), 5)
    rsv.resolve(s, T, V1, SPECS["Stupefy"], 0, [big], -1, True)
    assert combat.might(s, T, big) == 3, "and with room to spare it is -2"


@case(12416, "a replayed unit sheds its -Might: Eclipse then Temporal Breach")
def _():
    need("Eclipse", "Temporal Breach")
    s = fresh()
    u = body(s, 0, bf_loc(0), 6)
    rsv.resolve(s, T, V1, SPECS["Eclipse"], 1, [u], -1, True)
    assert combat.might(s, T, u) == 2
    rsv.resolve(s, T, V1, SPECS["Temporal Breach"], 0, [u], -1, True)
    drain(s)
    back = [i for i in range(s.n_perms) if alive(s, i)
            and int(s.perms[i, P_CARD]) == VANILLA]
    assert back, "its owner played it back"
    assert int(s.perms[back[0], P_LOC]) == bf_loc(0), "to the same location"
    assert combat.might(s, T, back[0]) == int(T.might[VANILLA]), (
        "124.1 -- a new object: neither the set Might nor the -4 came with it")


@case(12030, "Patched Porobot needs 3 OTHER gear -- it does not count itself")
def _():
    need("Patched Porobot", "Long Sword")
    for n_gear, draws in ((2, 0), (3, 1)):
        s = fresh(hand=[T.id_of("Patched Porobot")])
        for _ in range(n_gear):
            s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
        act(s, A.A_PLAY, 0, 0)
        choose(s, base_loc(0))
        drain(s)
        assert int(s.n_hand[0]) == draws, (
            f"{n_gear} other gear -> draw {draws}, hand is {int(s.n_hand[0])}")


@case(12190, "Long Sword's Quick-Draw attaches as part of the play, no Equip cost")
def _():
    need("Long Sword")
    s = fresh(hand=[T.id_of("Long Sword")])
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Long Sword", base_loc(0))
    drain(s)
    sw = perm_of(s, "Long Sword")
    assert sw and int(s.perms[sw[0], __import__(
        "rl.engine.state", fromlist=["x"]).P_ATTACHED_TO]) == u, "attached on play"
    assert runes(s, 0) == 36 - int(T.power[T.id_of("Long Sword")]), (
        "819 -- only the printed Power was recycled, no Equip [Fury] on top")


@case(12217, "Temporal Breach on an equipped unit: it returns bare, the gear stays")
def _():
    need("Temporal Breach", "Long Sword")
    s = fresh()
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    sw = s.add_permanent(T.id_of("Long Sword"), 0, bf_loc(0))
    s.attach(sw, u)
    rsv.resolve(s, T, V1, SPECS["Temporal Breach"], 0, [u], -1, True)
    A._settle(s, T, V1)
    drain(s)
    back = [i for i in perm_of(s, "Shipyard Skulker")]
    assert back and int(s.perms[back[0], P_LOC]) == bf_loc(0), "replayed in place"
    assert combat.might(s, T, back[0]) == int(T.might[VANILLA]), "with no +2"
    assert alive(s, sw) and not s.is_attached(sw), "435.4.b -- the sword detached"
    assert int(s.perms[sw, P_LOC]) == base_loc(0), (
        "457.1 -- and an unattached gear at a battlefield is recalled")


@case(12327, "Temporal Breach on a token: it ceases to exist and is not replayed")
def _():
    need("Temporal Breach", "Sprite Call")
    s = fresh()
    rsv.resolve(s, T, V1, SPECS["Sprite Call"], 0, [base_loc(0)], -1, True)
    A._settle(s, T, V1)
    tok = [i for i in range(s.n_perms) if alive(s, i)
           and T.is_token(int(s.perms[i, P_CARD]))]
    assert tok, "Sprite Call made a token"
    rsv.resolve(s, T, V1, SPECS["Temporal Breach"], 0, [tok[0]], -1, True)
    drain(s)
    assert not [i for i in range(s.n_perms) if alive(s, i)
                and T.is_token(int(s.perms[i, P_CARD]))], (
        "186.1 / 359.3.e.6 -- nothing is left to play back")
    assert int(s.n_banished[0]) == 0, "and a token never sits in banishment"


@case(12440, "two Eye of the Heralds on one unit make two Recruits on a move")
def _():
    need("Eye of the Herald")
    s = fresh()
    u = body(s, 0, base_loc(0), 3, ready=True)
    for _ in range(2):
        g = s.add_permanent(T.id_of("Eye of the Herald"), 0, base_loc(0))
        s.attach(g, u)
    act(s, A.A_DECLARE, bf_loc(0), 0)
    act(s, A.A_ADD, u, 0)
    act(s, A.A_COMMIT, None, 0)
    drain(s)
    recruits = [i for i in range(s.n_perms) if alive(s, i)
                and "Recruit" in T.names[int(s.perms[i, P_CARD])]]
    assert len(recruits) == 2, f"818.3.b -- one per Eye, got {len(recruits)}"
    assert all(int(s.perms[i, P_LOC]) == bf_loc(0) for i in recruits), "'here'"


@case(12325, "Commander Ledros kills units as his cost, never plain gear")
def _():
    need("Commander Ledros", "Long Sword", "Patched Porobot")
    s = fresh(hand=[T.id_of("Commander Ledros")])
    sw = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
    por = s.add_permanent(T.id_of("Patched Porobot"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    spec = SPECS.get("Commander Ledros") or next(
        iter(abilities_for(T, T.id_of("Commander Ledros"))), None)
    opts = set(rsv.cost_kill_targets(s, T, spec, 0))
    assert u in opts and por in opts, f"units, and a Unit Gear (178.3): {opts}"
    assert sw not in opts, "a Gear is not a Unit"


@case(12049, "Nasus dying alongside the enemy sees no death 'here'")
def _():
    need("Nasus, Guardian of Knowledge")
    for together in (True, False):
        s = fresh()
        rune_deck(s)
        nas = s.add_permanent(T.id_of("Nasus, Guardian of Knowledge"), 0, bf_loc(0))
        foe = body(s, 1, bf_loc(0), 6)
        before = runes(s, 0)
        s.perms[foe, P_DMG] = 6
        if together:
            s.perms[nas, P_DMG] = 6
        combat.enforce_lethal(s, T)
        A._settle(s, T, V1)
        drain(s)
        got = runes(s, 0) - before
        assert got == (0 if together else 1), (
            f"383.2.c.2 -- together={together}: channelled {got}")


@case(12232, "two Ekkos dying at once are two Deathknells, both resolve")
def _():
    need("Ekko - Recurrent")
    s = fresh()
    e1 = s.add_permanent(T.id_of("Ekko - Recurrent"), 0, bf_loc(0))
    e2 = s.add_permanent(T.id_of("Ekko - Recurrent"), 0, bf_loc(0))
    s.runes_spent[0, :] = 2
    s.perms[e1, P_DMG] = 9
    s.perms[e2, P_DMG] = 9
    combat.enforce_lethal(s, T)
    A._settle(s, T, V1)
    drain(s)
    ek = T.id_of("Ekko - Recurrent")
    deck = list(s.deck[0])
    assert deck.count(ek) == 2, "both recycled themselves into the Main Deck"
    assert ek not in list(s.trash[0, :int(s.n_trash[0])]), "neither stayed in trash"
    assert int(s.runes_spent[0].sum()) == 0, "and the runes are ready"


@case(12381, "Soraka saves a smaller friend that dies at the same time as her")
def _():
    need("Soraka - Wanderer")
    s = fresh()
    sor = s.add_permanent(T.id_of("Soraka - Wanderer"), 0, bf_loc(0))
    pal = body(s, 0, bf_loc(0), 2)
    s.perms[sor, P_DMG] = 9
    s.perms[pal, P_DMG] = 5
    combat.enforce_lethal(s, T)
    A._settle(s, T, V1)
    drain(s)
    assert not alive(s, sor), "Soraka herself dies"
    assert alive(s, pal), (
        "370.4 -- a leaving object still applies its replacement to events "
        "simultaneous with its leaving (Soraka is the rule's own example)")
    assert int(s.perms[pal, P_LOC]) == base_loc(0) and int(s.perms[pal, P_DMG]) == 0


@case(12435, "Zhonya's replaces the death, so Siphoning Strike channels nothing")
def _():
    need("Siphoning Strike", "Zhonya's Hourglass")
    s = fresh()
    rune_deck(s)
    s.runes_ready[:, :] = 0
    s.runes_ready[:, 0] = 6                        # 6 runes: the 4-damage mode
    u = body(s, 1, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Eclipse"], 1, [u], -1, True)    # 3 - 4
    rsv.resolve(s, T, V1, SPECS["Discipline"], 1, [u], -1, True) # back to 1
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z                           # what playing it registers
    before = runes(s, 0)
    rsv.resolve(s, T, V1, SPECS["Siphoning Strike"], 0, [u], -1, True)
    A._settle(s, T, V1)
    drain(s)
    assert alive(s, u), "Zhonya's took the death"
    assert not alive(s, z), "by killing itself"
    assert int(s.perms[u, P_LOC]) == base_loc(1), "recalled"
    assert int(s.perms[u, P_DMG]) == 0 and int(s.perms[u, P_READY]) == 0, (
        "healed and exhausted")
    assert combat.might(s, T, u) == 1, (
        "#12595 -- a recall is not a zone change: the Might changes stay")
    assert runes(s, 0) == before, "370.1.a.1 -- no death, so no channel"


@case(12592, "a unit stolen from the trash keeps its Deathknell for its controller")
def _():
    need("Glasc Mixologist")
    s = fresh()
    mix = s.add_permanent(T.id_of("Glasc Mixologist"), 0, bf_loc(0))
    s.perms[mix, __import__("rl.engine.state", fromlist=["x"]).P_OWNER] = 1
    s.trash[0, 0], s.n_trash[0] = VANILLA, 1        # MY trash has the target
    s.bf_ctrl[0] = 0
    combat.destroy(s, T, mix)
    A._settle(s, T, V1)
    drain(s)
    assert T.id_of("Glasc Mixologist") in list(s.trash[1, :int(s.n_trash[1])]), (
        "56 -- the card goes to its OWNER's trash")
    assert [i for i in perm_of(s, "Shipyard Skulker", 0)], (
        "808.1.d.2 -- but its controller's Deathknell played from HIS trash")


@case(12112, "a unit played from the opponent's trash dies into THEIR trash")
def _():
    need("Kharox")
    s = fresh()
    u = body(s, 0, bf_loc(0), 3)
    s.perms[u, __import__("rl.engine.state", fromlist=["x"]).P_OWNER] = 1
    combat.destroy(s, T, u)
    assert int(s.n_trash[0]) == 0 and VANILLA in list(s.trash[1, :int(s.n_trash[1])])


@case(12316, "Shen + one other unit wearing 3 Trinity Forces holds for 5")
def _():
    need("Shen, Leader of the Kinkou Order", "Trinity Force")
    s = fresh()
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Shen, Leader of the Kinkou Order"), 0, bf_loc(0))
    pal = body(s, 0, bf_loc(0), 3)
    for _ in range(3):
        tf = s.add_permanent(T.id_of("Trinity Force"), 0, bf_loc(0))
        s.attach(tf, pal)
    phases.score_holds(s, V1, T)
    A._settle(s, T, V1)
    drain(s)
    assert int(s.points[0]) == 5, (
        f"470 limits Hold, not triggered points: 1 + 1 + 3, got {int(s.points[0])}")


@case(12221, "two Otterpus replace one early score with ONE draw")
def _():
    need("Otterpus")
    s = fresh()
    s.turn = 1
    s.add_permanent(T.id_of("Otterpus"), 1, base_loc(1))
    s.add_permanent(T.id_of("Otterpus"), 1, base_loc(1))
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    drain(s)
    assert int(s.bf_ctrl[0]) == 0, "it conquered"
    assert int(s.points[0]) == 0, "the point was replaced"
    assert int(s.n_hand[0]) == 1, (
        f"370.2 -- one replacement per event: draw 1, got {int(s.n_hand[0])}")


@case(12473, "a 0 Might unit conquers an open battlefield")
def _():
    need("Scuttle Crab")
    s = fresh()
    crab = s.add_permanent(T.id_of("Scuttle Crab"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, crab)
    drain(s)
    assert int(s.bf_ctrl[0]) == 0 and int(s.points[0]) == 1, (
        "Might has nothing to do with control or conquering")


@case(12429, "a lone Temporary unit dies before its battlefield can be held")
def _():
    need("Startipped Peak", "Sprite Call")
    s = fresh()
    rune_deck(s)
    s.bf_card[0] = T.id_of("Startipped Peak")
    rsv.resolve(s, T, V1, SPECS["Sprite Call"], 0, [base_loc(0)], -1, True)
    A._settle(s, T, V1)
    spr = [i for i in range(s.n_perms) if alive(s, i)
           and T.is_token(int(s.perms[i, P_CARD]))][0]
    s.set_location(spr, bf_loc(0))
    s.bf_ctrl[0] = 0
    s.ply += 2                                     # its controller's next turn
    phases.start_turn(s, T, V1)
    A._settle(s, T, V1)                            # the expiry goes on the Chain
    drain(s)                                       # ...resolves, then scoring
    assert s.phase == MAIN, "the turn resumed past the Scoring Step"
    assert not alive(s, spr), "816.1.b -- killed in the Beginning Step"
    assert int(s.points[0]) == 0, "315.2.b -- so there is nothing to Hold"
    assert int(s.bf_ctrl[0]) != 0, "190.4.c -- the empty battlefield was lost"


@case(12339, "effect moves neither exhaust nor ready (Emperor's Divide, Shuriken Flip)")
def _():
    need("Emperor's Divide", "Shuriken Flip")
    s = fresh()
    s.bf_ctrl[0] = 0
    up = body(s, 0, bf_loc(0), 3, ready=True)
    down = body(s, 0, bf_loc(0), 3, ready=False)
    other = body(s, 0, bf_loc(1), 3, ready=True)
    assert rsv.legal_targets(s, T, SPECS["Emperor's Divide"], 1, 0, [up], -1) \
        == [down], "#12045 -- later slots are bound to the first unit's battlefield"
    rsv.resolve(s, T, V1, SPECS["Emperor's Divide"], 0, [up, down, -1, -1], -1, True)
    assert int(s.perms[up, P_LOC]) == base_loc(0) == int(s.perms[down, P_LOC])
    assert int(s.perms[up, P_READY]) == 1 and int(s.perms[down, P_READY]) == 0, (
        "144.2 -- only a Standard Move exhausts")
    assert int(s.perms[other, P_LOC]) == bf_loc(1), (
        "#12045 -- 'at a battlefield' is one battlefield")

    f = fresh()
    mine = body(f, 0, base_loc(0), 3, ready=True)
    rsv.resolve(f, T, V1, SPECS["Shuriken Flip"], 0, [-1, bf_loc(0), mine], -1, True)
    assert int(f.perms[mine, P_LOC]) == bf_loc(0) and int(f.perms[mine, P_READY]) == 1, (
        "#12056 -- Shuriken Flip's move leaves the unit ready")


@case(12421, "Zed at Vilemaw's Lair: the clone comes in, Zed cannot leave")
def _():
    need("Zed, Without a Sound", "Vilemaw's Lair")
    from rl.engine.effects import TR_ACTIVATED
    s = fresh()
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    zed = s.add_permanent(T.id_of("Zed, Without a Sound"), 0, bf_loc(0))
    spec = next(a for a in abilities_for(T, T.id_of("Zed, Without a Sound"))
                if a.trigger == __import__("rl.engine.effects",
                                           fromlist=["x"]).TR_CONQUER)
    rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=zed)
    clone = [i for i in range(s.n_perms) if alive(s, i)
             and "Shadow Clone" in T.names[int(s.perms[i, P_CARD])]][0]
    assert int(s.perms[clone, P_LOC]) == base_loc(0), "the clone starts at base"
    swap = next(a for a in abilities_for(T, T.id_of("Zed, Without a Sound"))
                if a.trigger == TR_ACTIVATED)
    rsv.resolve(s, T, V1, swap, 0, [clone], -1, False, source=zed)
    assert int(s.perms[zed, P_LOC]) == bf_loc(0), "'can't move from here to base'"
    assert int(s.perms[clone, P_LOC]) == bf_loc(0), (
        "356.3.e.11 -- the half that can happen still happens")


@case(12522, "Bellows Breath's Repeat may choose the same unit again")
def _():
    need("Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")])
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Bellows Breath", u, -1, -1, repeat=True)
    for c in (u, -1, -1):                  # the repeat's own choices, if asked
        if s.pend_slot >= 0 or chain_mod.decision_open(s):
            try:
                choose(s, c)
            except AssertionError:
                break
    drain(s)
    assert int(s.perms[u, P_DMG]) == 2, (
        f"820.2.a -- two executions, one unit twice: got {int(s.perms[u, P_DMG])}")


@case(12143, "Existential Dread repeated stuns two different attackers")
def _():
    need("Existential Dread")
    s = fresh(seat=1)
    give(s, 0, "Existential Dread")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 9)
    a1 = body(s, 1, base_loc(1), 3, ready=True)
    a2 = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, a1, a2)
    cast(s, 0, "Existential Dread", a1, repeat=True)
    for c in (a2,):
        if s.pend_slot >= 0 or chain_mod.decision_open(s):
            choose(s, c)
    drain(s)
    assert s.showdown_bf == 0, "still inside the combat's showdown"
    assert s.has_flag(a1, F_STUNNED) and s.has_flag(a2, F_STUNNED), (
        "each execution chooses its own attacking enemy unit")


@case(12491, "Field Musicians may give its +3 to itself")
def _():
    need("Field Musicians")
    s = fresh(hand=[T.id_of("Field Musicians")])
    cast(s, 0, "Field Musicians", base_loc(0))
    fm = perm_of(s, "Field Musicians")[0]
    A._settle(s, T, V1)
    for _ in range(6):
        legal = A.legal_actions(s, T, V1, A.acting_seat(s))
        if any(a.kind == A.A_TARGET and a.arg == fm for a in legal):
            choose(s, fm)
            break
        pick = next((a for a in legal if a.kind in (A.A_ACCEPT, A.A_ORDER)), None)
        assert pick, f"the play trigger never offered Field Musicians itself: {legal}"
        A.apply(s, T, V1, pick)
    drain(s)
    assert combat.might(s, T, fm) == int(T.might[T.id_of("Field Musicians")]) + 3


@case(12123, "Facebreaker cannot be played without an enemy unit to stun")
def _():
    need("Facebreaker")
    s = fresh(hand=[T.id_of("Facebreaker")])
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    assert "Facebreaker" not in hand_plays(s, 0), "355.8 -- both targets required"
    body(s, 1, bf_loc(0), 3)
    assert "Facebreaker" in hand_plays(s, 0), "with an enemy there it plays"


@case(12357, "Siphoning Strike: a Deflect recycle drops you from 7 runes to 6")
def _():
    need("Siphoning Strike", "Commander Ledros")
    s = fresh(hand=[T.id_of("Siphoning Strike")])
    s.runes_ready[:, :] = 0
    s.runes_ready[0, 0] = 7
    led = s.add_permanent(T.id_of("Commander Ledros"), 1, bf_loc(0))   # Deflect
    cast(s, 0, "Siphoning Strike", led)
    drain(s)
    assert runes(s, 0) == 6, f"4 Energy exhausted, 1 rune recycled: {runes(s, 0)}"
    assert int(s.perms[led, P_DMG]) == 4, (
        f"the 7-rune check is at resolution: 4, got {int(s.perms[led, P_DMG])}")


@case(12025, "Astral Heron: Retreating her as the first card loses the discount")
def _():
    need("Astral Heron", "Retreat", "Discipline")
    for first, discount in (("Retreat", False), ("Discipline", True)):
        s = fresh(hand=[T.id_of(first)])
        s.bf_ctrl[0] = 0
        her = s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
        cast(s, 0, first, her)
        drain(s)
        got = int(s.next_discount[0].sum()) > 0
        assert got == discount, (
            f"383.2.c -- {first} first: the 'if I'm at a battlefield' check "
            f"comes after it resolves; discount={got}")


@case(12516, "Rhasa played from the trash does not count herself")
def _():
    need("Rhasa the Sunderer")
    from rl.engine import cost
    rh = T.id_of("Rhasa the Sunderer")
    s = fresh()
    s.trash[0, :10] = [rh] + [VANILLA] * 9
    s.n_trash[0] = 10
    s.trash[0, 0], s.trash[0, 9] = VANILLA, VANILLA
    s.n_trash[0] = 9                               # step 1: she left for the Chain
    assert cost.effective_energy(s, T, 0, rh) == 1, (
        f"354 -- 10 - 9, got {cost.effective_energy(s, T, 0, rh)}")


@case(12594, "Sona's end-of-turn trigger resolves after she is bounced")
def _():
    need("Sona, Harmonious", "Star-Crossed")
    s = fresh()
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Sona, Harmonious"), 0, bf_loc(0))
    body(s, 1, bf_loc(1), 3)
    give(s, 1, "Star-Crossed")
    s.runes_ready[0, :] = 2
    s.runes_spent[0, :] = 4                        # 24 exhausted runes
    act(s, A.A_END_TURN, None, 0)
    A._settle(s, T, V1)
    assert s.n_chain >= 1, "the trigger is on the chain"
    sona = perm_of(s, "Sona, Harmonious")[0]
    theirs = [i for i in perm_of(s, "Shipyard Skulker", 1)][0]
    cast(s, 1, "Star-Crossed", theirs, sona)
    drain(s)
    assert not perm_of(s, "Sona, Harmonious"), "Sona is back in hand"
    assert int(s.runes_spent[0].sum()) == 20, (
        f"383.2.a.1 -- the condition was met when it triggered: 4 readied, "
        f"exhausted now {int(s.runes_spent[0].sum())}")


@case(12601, "Punch First's +5 is still up when Blighted Battleaxe hits for 4")
def _():
    need("Blighted Battleaxe", "Punch First")
    for punched in (True, False):
        s = fresh()
        u = body(s, 0, base_loc(0))                # 3, +4 from the axe
        ax = s.add_permanent(T.id_of("Blighted Battleaxe"), 0, base_loc(0))
        s.attach(ax, u)
        if punched:
            rsv.resolve(s, T, V1, SPECS["Punch First"], 0, [u], -1, True)
        act(s, A.A_END_TURN, None, 0)
        drain(s)                                   # rows compact at turn end
        axe = perm_of(s, "Blighted Battleaxe")
        assert axe and not s.is_attached(axe[0]), "the axe unattached"
        assert bool(perm_of(s, "Shipyard Skulker")) == punched, (
            "317.2.c -- the Ending Step comes before this-turn effects expire: "
            + ("4 on 9 survives" if punched else "4 on 4 dies"))


@case(12365, "both sides stunned: no damage, the attacker is recalled")
def _():
    s = fresh(seat=1)
    s.hand[0, 0], s.n_hand[0] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 0
    dfn = body(s, 0, bf_loc(0), 3)
    atk = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, atk)
    s.stun(dfn)
    s.stun(atk)
    fight(s)
    assert alive(s, dfn) and alive(s, atk), "423.1.b -- nobody dealt damage"
    assert int(s.perms[atk, P_LOC]) == base_loc(1), "466.1.a.2 -- attacker recalled"
    assert int(s.bf_ctrl[0]) == 0, "the defender keeps it"


@case(12499, "a stunned attacker is killed by a pumped defender -- not a tie")
def _():
    need("Nidalee - Cat Form", "Stellacorn Herder", "Defiant Dance")
    s = fresh(seat=1)
    s.hand[0, 0], s.n_hand[0] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 0
    st = s.add_permanent(T.id_of("Stellacorn Herder"), 0, bf_loc(0))
    nid = s.add_permanent(T.id_of("Nidalee - Cat Form"), 1, base_loc(1), ready=True)
    attack(s, 1, 0, nid)
    s.stun(nid)
    rsv.resolve(s, T, V1, SPECS["Defiant Dance"], 0, [st, nid], -1, True)
    hand1 = int(s.n_hand[1])
    fight(s)
    assert not alive(s, nid), "5 damage on a 2 Might Nidalee"
    assert alive(s, st) and int(s.bf_ctrl[0]) == 0, "Stellacorn remains and holds"
    assert int(s.n_hand[1]) == hand1, "Nidalee did not remain, so no draw"


@case(12481, "Trusty Ramhound's 2 damage heals in Combat Cleanup before its ally's death shrinks it")
def _():
    need("Trusty Ramhound")
    s = fresh(seat=1)
    s.hand[0, 0], s.n_hand[0] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 0
    ally = body(s, 0, bf_loc(0), 3)
    ram = s.add_permanent(T.id_of("Trusty Ramhound"), 0, bf_loc(0))
    assert combat.might(s, T, ram) == 3, "2 + 1 while the ally is here"
    atk = body(s, 1, base_loc(1), 5, ready=True)
    attack(s, 1, 0, atk)
    fight(s)                        # 5 assigned: 3 lethal to the ally, 2 on Ram
    assert not alive(s, ally), "the ally took lethal"
    assert alive(s, ram) and int(s.perms[ram, P_DMG]) == 0, (
        "the kill check sees the ally still alive (2 on 3), and 466.1.a.1 "
        "heals before the smaller Might could matter")


@case(12039, "Sacrifice -> Glasc Mixologist -> Vanguard Captain has Legion")
def _():
    need("Sacrifice", "Glasc Mixologist", "Vanguard Captain")
    s = fresh(hand=[T.id_of("Sacrifice")])
    s.bf_ctrl[0] = 0
    glasc = s.add_permanent(T.id_of("Glasc Mixologist"), 0, bf_loc(0))
    s.trash[0, 0], s.n_trash[0] = T.id_of("Vanguard Captain"), 1
    act(s, A.A_PLAY, 0, 0)
    legal = A.legal_actions(s, T, V1, 0)
    pick = next(a for a in legal if a.arg == glasc)
    A.apply(s, T, V1, pick)
    for _ in range(30):
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        if not legal or (s.n_chain == 0 and s.n_trig == 0 and s.pend_slot < 0
                         and s.pend_may < 0 and not chain_mod.decision_open(s)):
            break
        pick = next((a for a in legal if a.kind == A.A_ACCEPT),
                    next((a for a in legal if a.kind == A.A_TARGET
                          and a.arg >= 0 and a.arg != bf_loc(1)),
                         next((a for a in legal if a.kind in (A.A_ORDER, A.A_PASS)),
                              legal[0])))
        A.apply(s, T, V1, pick)
    assert perm_of(s, "Vanguard Captain"), "the Deathknell played the Captain"
    recruits = [i for i in range(s.n_perms) if alive(s, i)
                and "Recruit" in T.names[int(s.perms[i, P_CARD])]]
    assert len(recruits) == 2, (
        f"812.1.c -- Sacrifice was finalized first, so Legion is on: "
        f"{len(recruits)} Recruits")


@case(12284, "Lonely Poro killed for Stalking Wolf still died alone")
def _():
    need("Stalking Wolf", "Lonely Poro")
    s = fresh(hand=[T.id_of("Stalking Wolf")])
    s.bf_ctrl[0] = 0
    poro = s.add_permanent(T.id_of("Lonely Poro"), 0, bf_loc(0))
    act(s, A.A_PLAY, 0, 0)
    for _ in range(4):
        legal = A.legal_actions(s, T, V1, 0)
        if any(a.arg == poro for a in legal):
            choose(s, poro)
            break
    for _ in range(4):
        legal = A.legal_actions(s, T, V1, A.acting_seat(s))
        if any(a.arg == bf_loc(0) and a.kind in _CHOICE_KINDS for a in legal):
            choose(s, bf_loc(0))
            break
    drain(s)
    assert perm_of(s, "Stalking Wolf"), "the Wolf was played"
    assert not alive(s, poro)
    assert int(s.n_hand[0]) == 1, (
        f"808.1.d.3 -- 'alone' is judged at death; Wolf was still on the "
        f"Chain. Hand is {int(s.n_hand[0])}")


@case(12102, "Elder Dragon entering kills an enemy already carrying your damage")
def _():
    need("Elder Dragon")
    s = fresh(hand=[T.id_of("Elder Dragon")])
    foe = body(s, 1, bf_loc(1), 6)
    combat.mark_damage(s, T, foe, 1, by_seat=0)
    assert alive(s, foe)
    cast(s, 0, "Elder Dragon", base_loc(0))
    A._settle(s, T, V1)
    assert not alive(s, foe), (
        "FAQ #10686 -- the static applies the moment the Dragon is on the board")


@case(12141, "Pakaa Protector must draw a revealed unit -- no +2 instead")
def _():
    need("Pakaa Protector")
    for top, draws in ((VANILLA, True), (T.id_of("Discipline"), False)):
        s = fresh()
        s.deck[0, 0] = top
        pk = s.add_permanent(T.id_of("Pakaa Protector"), 0, base_loc(0), ready=True)
        attack(s, 0, 0, pk)
        drain(s)
        assert (int(s.n_hand[0]) == 1) == draws, f"hand {int(s.n_hand[0])}"
        bonus = combat.might(s, T, pk) - int(T.might[T.id_of("Pakaa Protector")])
        assert bonus == (0 if draws else 2), f"bonus {bonus}"


@case(12008, "Baited Hook on a unit Soraka saves: nothing was killed, nothing played")
def _():
    need("Baited Hook", "Soraka - Wanderer")
    s = fresh()
    s.add_permanent(T.id_of("Soraka - Wanderer"), 0, base_loc(0))
    hook = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 2)
    act(s, A.A_ACTIVATE, None, 0)
    for _ in range(20):
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who) if who >= 0 else []
        if not legal or (s.n_chain == 0 and s.n_trig == 0 and s.pend_slot < 0
                         and s.pend_may < 0 and not chain_mod.decision_open(s)):
            break
        pick = next((a for a in legal if a.kind == A.A_TARGET and a.arg == u),
                    next((a for a in legal if a.kind == A.A_PICK), None))
        pick = pick or next((a for a in legal if a.kind in (A.A_ORDER, A.A_PASS,
                                                           A.A_PICK_NONE)),
                            legal[0])
        A.apply(s, T, V1, pick)
    assert alive(s, u) and int(s.perms[u, P_READY]) == 0, "saved, exhausted"
    assert len(perm_of(s, "Shipyard Skulker", 0)) == 1, (
        "359.3.e.12 -- no killed unit to measure, so nothing is played")
    assert int(s.n_banished[0]) == 0


@case(12538, "a countered first card is no card to Astral Heron")
def _():
    need("Astral Heron", "Discipline", "Defy")
    s = fresh(hand=[T.id_of("Discipline")])
    give(s, 1, "Defy")
    s.bf_ctrl[0] = 0
    her = s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    cast(s, 0, "Discipline", her)
    cast(s, 1, "Defy", _top_uid(s))
    drain(s)
    assert int(s.cards_played[0]) == 1, "419.4.b -- Legion still counts it"
    assert int(s.next_discount[0].sum()) == 0, (
        "419.4.a.1 -- it never resolved, so the Heron never triggered")


@case(12337, "Heron's first card is the first to RESOLVE: a Defy on top of Discipline")
def _():
    need("Astral Heron", "Discipline", "Defy", "Hard Bargain")
    s = fresh(hand=[T.id_of("Discipline"), T.id_of("Defy")])
    give(s, 1, "Hard Bargain")
    s.bf_ctrl[0] = 0
    her = s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    cast(s, 0, "Discipline", her)
    cast(s, 1, "Hard Bargain", _top_uid(s))
    cast(s, 0, "Defy", _top_uid(s))
    # Defy resolves first and is the first completed card; the Heron's trigger
    # goes on the Chain above Discipline and resolves before it.
    for _ in range(12):
        if int(s.next_discount[0].sum()):
            break
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who)
        A.apply(s, T, V1, next((a for a in legal if a.kind == A.A_PASS), legal[0]))
    assert int(s.next_discount[0].sum()) > 0, "the discount exists"
    assert s.n_chain >= 1, "while the Discipline is still on the Chain"
    drain(s)
    assert combat.might(s, T, her) == 9, "Discipline resolved (Hard Bargain was countered)"
    assert int(s.next_discount[0].sum()) > 0, (
        "and it did not eat the discount -- it was paid for before it existed")


@case(12418, "Ravenbloom Student grows once Temporal Breach has replayed it")
def _():
    need("Ravenbloom Student", "Temporal Breach")
    s = fresh()
    s.bf_ctrl[0] = 0
    st = s.add_permanent(T.id_of("Ravenbloom Student"), 0, bf_loc(0))
    fd = list(fd_slots(0))[0]
    s.fd_owner[fd], s.fd_card[fd], s.fd_ply[fd] = 0, T.id_of("Temporal Breach"), -5
    hid = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_HIDDEN]
    assert hid, "the facedown Temporal Breach is playable"
    A.apply(s, T, V1, hid[0])
    choose(s, st)
    drain(s)
    new = perm_of(s, "Ravenbloom Student", 0)
    assert new and new[0] != st or not alive(s, st), "a new object came back"
    assert combat.might(s, T, new[0]) == 3, (
        f"FAQ #5601 -- 'when you play a spell' is evaluated after it resolves, "
        f"when the replayed Student is on the board: got {combat.might(s, T, new[0])}")


@case(12580, "Abandoned Hall's +1 waits for Switcheroo to finish resolving")
def _():
    need("Abandoned Hall", "Switcheroo")
    s = fresh(hand=[T.id_of("Switcheroo")])
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 2)
    theirs = body(s, 1, bf_loc(0), 5)
    s.showdown_bf, s.showdown_combat = 0, 1
    cast(s, 0, "Switcheroo", mine, theirs)
    for _ in range(12):
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who)
        if any(a.kind == A.A_ACCEPT for a in legal):
            assert combat.might(s, T, mine) == 5, (
                "the Hall's offer comes only after the swap has happened")
            act(s, A.A_ACCEPT)
            choose(s, mine)
            break
        A.apply(s, T, V1, next((a for a in legal if a.kind == A.A_PASS), legal[0]))
    else:
        raise AssertionError("Abandoned Hall never offered its +1")
    drain(s)
    assert combat.might(s, T, mine) == 6 and combat.might(s, T, theirs) == 2


@case(12198, "a repeated spell pays Master Yi's Deflect for each time it chooses him")
def _():
    need("Bellows Breath", "Master Yi - Tempered")
    s = fresh(hand=[T.id_of("Bellows Breath")])
    s.xp[1] = 6
    yi = s.add_permanent(T.id_of("Master Yi - Tempered"), 1, bf_loc(0))
    assert combat.perm_kw(s, T, yi, "Deflect"), "Level 6: he has Deflect"
    before = runes(s, 0)
    cast(s, 0, "Bellows Breath", yi, -1, -1, repeat=True)
    choose(s, yi)
    choose(s, -1)
    choose(s, -1)
    drain(s)
    power = int(T.power[T.id_of("Bellows Breath")]) + int(
        T.repeat_power[T.id_of("Bellows Breath")])
    assert before - runes(s, 0) == power + 2, (
        f"809.1.c -- the card's Power plus one Deflect per choice: "
        f"spent {before - runes(s, 0)}, expected {power + 2}")
    assert int(s.perms[yi, P_DMG]) == 2


@case(12449, "Akali - Rogue Assassin: retreat-and-conquer are exclusive")
def _():
    # Not `need()`: the coverage metric counts a legend's [Empower] keyword as
    # unread, but both of this legend's abilities are transcribed.
    ak = T.id_of("Akali - Rogue Assassin")
    # Mid-showdown: the lone unit goes home, so nobody is left to conquer.
    s = fresh()
    s.hand[1, 0], s.n_hand[1] = T.id_of("Smoke Screen"), 1   # keeps it open
    s.legend[0], s.legend_ready[0] = ak, 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    assert s.showdown_bf == 0 and not s.showdown_combat, "a Non-Combat Showdown"
    pass_priority_to(s, 0)
    acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
    assert acts, "the legend may act while the unit is in the showdown"
    A.apply(s, T, V1, acts[-1])
    if s.pend_slot >= 0:
        choose(s, u)
    fight(s)
    assert int(s.perms[u, P_LOC]) == base_loc(0), "Akali sent it to base"
    assert int(s.bf_ctrl[0]) != 0 and int(s.points[0]) == 0, (
        "no unit remained, so no Conquer")
    # Conquer first: afterwards it is no longer in a showdown to be chosen.
    c = fresh()
    c.legend[0], c.legend_ready[0] = ak, 1
    v = body(c, 0, base_loc(0), 3, ready=True)
    attack(c, 0, 0, v)
    fight(c)
    assert int(c.bf_ctrl[0]) == 0 and int(c.points[0]) == 1, "it conquered"
    offered = [a for a in A.legal_actions(c, T, V1, 0) if a.kind == A.A_ACTIVATE]
    for a in offered:                    # the Empower may be offered; the move not
        probe = c.clone()
        A.apply(probe, T, V1, a)
        assert not (probe.pend_slot >= 0 and any(
            x.arg == v for x in A.legal_actions(probe, T, V1, 0)
            if x.kind == A.A_TARGET)), (
            "'a friendly unit in a showdown' -- the conquered unit is not one")


@case("A1", "a hidden Sprite Call answering the Temporary trigger keeps the Hold")
def _():
    need("Sprite Call")
    s = fresh()
    rune_deck(s)
    old = _sprite_at(s, 0, 0)
    fd = list(fd_slots(0))[0]
    s.fd_owner[fd], s.fd_card[fd] = 0, T.id_of("Sprite Call")
    _next_own_turn(s)
    s.fd_ply[fd] = int(s.ply) - 1                  # hidden on an earlier turn
    assert s.n_chain >= 1 and alive(s, old), "Temporary is on the Chain (816.1.b)"
    hid = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_HIDDEN]
    assert hid, "811.6 -- the facedown Sprite Call has [Reaction] here"
    A.apply(s, T, V1, hid[0])
    if s.pend_slot >= 0:
        choose(s, bf_loc(0))                       # 811.1.d.3: at that battlefield
    drain(s)
    assert not alive(s, old), "the old Sprite still dies"
    new = [i for i in range(s.n_perms) if alive(s, i)
           and T.is_token(int(s.perms[i, P_CARD]))
           and int(s.perms[i, P_LOC]) == bf_loc(0)]
    assert new, "the new Sprite is at the battlefield"
    assert int(s.bf_ctrl[0]) == 0 and int(s.points[0]) == 1, (
        f"315.2.b -- it Holds in the Scoring Step: ctrl={int(s.bf_ctrl[0])} "
        f"points={int(s.points[0])}")


@case("A2", "Dusk Rose Lab can sacrifice a Sprite for the draw before Temporary kills it")
def _():
    need("Dusk Rose Lab", "Sprite Call")
    s = fresh()
    rune_deck(s)
    s.bf_card[0] = T.id_of("Dusk Rose Lab")
    spr = _sprite_at(s, 0, 0)
    hand = int(s.n_hand[0])
    _next_own_turn(s)
    for _ in range(20):
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        if s.phase == MAIN and s.n_chain == 0 and s.n_trig == 0:
            break
        orders = [a for a in legal if a.kind == A.A_ORDER]
        if orders:
            # 383.3.d -- placed LAST resolves FIRST, so put Temporary down first.
            tmp = [a for a in orders if int(s.trig[a.arg, 1]) == spr]
            A.apply(s, T, V1, (tmp or orders)[0])
            continue
        pick = next((a for a in legal if a.kind == A.A_ACCEPT),
                    next((a for a in legal if a.kind == A.A_TARGET and a.arg == spr),
                         next((a for a in legal if a.kind == A.A_PASS), legal[0])))
        A.apply(s, T, V1, pick)
    assert not alive(s, spr), "the Sprite is gone either way"
    assert int(s.n_hand[0]) == hand + 2, (
        f"Lab's draw plus the Draw Phase: hand went {hand} -> {int(s.n_hand[0])}")


@case("A3", "Steel Paws keeps effect damage; Tornado Warrior's disempower kills it before the heal")
def _():
    need("Steel Paws", "Tornado Warrior", "Shuriken Flip")
    s = fresh()
    s.bf_ctrl[0] = 0
    paws = s.add_permanent(T.id_of("Steel Paws"), 0, bf_loc(0))
    fd = list(fd_slots(0))[0]
    s.fd_owner[fd], s.fd_card[fd], s.fd_ply[fd] = 0, T.id_of("Tornado Warrior"), -5
    hid = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_HIDDEN]
    assert hid, "the facedown Tornado Warrior is playable"
    A.apply(s, T, V1, hid[0])
    for _ in range(10):
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who)
        if s.n_chain == 0 and s.n_trig == 0 and s.pend_may < 0 and s.pend_slot < 0:
            break
        pick = next((a for a in legal if a.kind == A.A_ACCEPT),
                    next((a for a in legal if a.kind == A.A_TARGET and a.arg == paws),
                         next((a for a in legal if a.kind == A.A_PASS), legal[0])))
        A.apply(s, T, V1, pick)
    assert combat.might(s, T, paws) == 7, f"empowered: +7, got {combat.might(s, T, paws)}"
    # Shuriken Flip's 2 from the opponent -- spell damage, so no Combat heal.
    mover = body(s, 1, base_loc(1), 3)
    rsv.resolve(s, T, V1, SPECS["Shuriken Flip"], 1, [paws, bf_loc(1), mover], -1, True)
    A._settle(s, T, V1)
    assert alive(s, paws) and int(s.perms[paws, P_DMG]) == 2, "2 on a 7 survives"
    act(s, A.A_END_TURN, None, 0)
    drain(s)
    assert not perm_of(s, "Steel Paws"), (
        "317.1 before 317.2.b -- 'disempower it at end of turn' happens in the "
        "Ending Step, so a 0 Might Steel Paws with 2 damage dies before the heal")


@case("A4", "Smoke and Mirrors hands the Mask's 'defends alone' bonus to the Sprite")
def _():
    need("Mask of Foresight", "Smoke and Mirrors", "Lillia - Fae Fawn")
    # Austin's line: Lillia holds a battlefield alone, an enemy walks in, and
    # the Mask banks her +1 per copy. Smoke and Mirrors then swaps her with a
    # [Temporary] Sprite in base. Both moves happen at once, so for that moment
    # the Sprite is the one defending alone and the Mask pays IT too; only then
    # does Lillia's own "when I move from a location" trigger drop a second
    # Sprite where she was -- which arrives to company, and so gets nothing.
    for masks in (1, 2):
        s = fresh(runes=32)
        # The spare Discipline keeps a legal answer in hand, so the Showdown
        # stays open to be read instead of resolving inside the COMMIT.
        give(s, 0, "Smoke and Mirrors", "Discipline")
        s.bf_ctrl[0] = 0
        lil = s.add_permanent(T.id_of("Lillia - Fae Fawn"), 0, bf_loc(0))
        for _ in range(masks):
            s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
        s.ply += 1                                # her Might is read next ply
        spr = _sprite_at(s, 0, 0)
        s.perms[spr, P_LOC] = base_loc(0)         # ...but it waits in base
        s.bf_ctrl[0] = 0
        foe = body(s, 1, base_loc(1), 4, ready=True)
        attack(s, 1, 0, foe)
        drain(s)
        assert combat.might(s, T, lil) == 3 + masks, (
            f"{masks} Mask(s): she is defending alone, so +{masks}")
        assert combat.might(s, T, spr) == 3, "the Sprite in base is nobody's defender"

        pass_priority_to(s, 0)
        cast(s, 0, "Smoke and Mirrors", lil, spr)
        drain(s)

        assert int(s.perms[lil, P_LOC]) == base_loc(0), "she went home"
        assert combat.might(s, T, lil) == 3 + masks, (
            "and 'this turn' keeps what the Mask already banked for her")
        assert int(s.perms[spr, P_LOC]) == bf_loc(0), "the Sprite took her place"
        assert combat.might(s, T, spr) == 3 + masks, (
            f"and defended alone for that moment, so the Mask paid it +{masks} too")

        fresh_sprites = [i for i in range(s.n_perms)
                         if alive(s, i) and i != spr
                         and int(s.perms[i, P_CTRL]) == 0
                         and T.is_token(int(s.perms[i, P_CARD]))]
        assert len(fresh_sprites) == 1, "her move trigger made exactly one more"
        new = fresh_sprites[0]
        assert int(s.perms[new, P_LOC]) == bf_loc(0), "'play a Sprite THERE'"
        assert combat.might(s, T, new) == 3, (
            "740.2.a: it arrived to company, so it never defended alone")


@case("A5", "simultaneous triggers ARE offered an order; a later rules step is not")
def _():
    need("Flurry of Blades", "Watchful Sentry", "Tasty Faefolk")
    # The other half of A4. Austin asked why the Mask/Lillia pair never asked
    # him to order the two triggers. The answer is the step stamp (`trig` col
    # 6): `chain.orderable` offers a choice only among triggers sharing the
    # OLDEST step, and 383.3.d only orders abilities triggered *simultaneously*.
    # This case pins both halves so a regression cannot quietly swallow the
    # prompt.
    #
    # (a) Genuinely simultaneous: one Flurry of Blades kills two units with
    #     different [Deathknell]s, so their controller is asked (383.3.d).
    s = fresh(runes=32)
    give(s, 0, "Flurry of Blades")
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Watchful Sentry"), 1, bf_loc(1))    # 1 Might: dies to 1
    faefolk = s.add_permanent(T.id_of("Tasty Faefolk"), 1, bf_loc(1))
    s.perms[faefolk, P_DMG] = 5                                 # 6 Might, 1 more kills
    cast(s, 0, "Flurry of Blades")
    for _ in range(6):
        if int(s.n_trig) >= 2:
            break
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        A.apply(s, T, V1, next((a for a in legal if a.kind == A.A_PASS), legal[0]))
    assert int(s.n_trig) == 2, "two Deathknells are queued"
    assert len({int(s.trig[i, 6]) for i in range(2)}) == 1, \
        "both met in the same rules step, so both are simultaneous"
    assert int(s.pend_order) == 1, "383.3.d asks their controller"
    assert len([a for a in A.legal_actions(s, T, V1, 1)
                if a.kind == A.A_ORDER]) == 2, "with a real choice of two"

    # (b) Not simultaneous: the swap's move fires Lillia at once, while the
    #     arriving Sprite's Defender designation is handed out by 323.2.a in
    #     the NEXT Cleanup -- a later step, so it is placed second (and being
    #     newest, resolves first). No choice exists to offer.
    steps = []
    real_queue = chain_mod.queue

    def spy(state, trigger, src, ctx=-1, subj=-1, ctx2=-1, who=-1):
        real_queue(state, trigger, src, ctx, subj, ctx2, who)
        steps.append((trigger, int(state.trig[int(state.n_trig) - 1, 6])))

    s = fresh(runes=32)
    give(s, 0, "Smoke and Mirrors", "Discipline")
    s.bf_ctrl[0] = 0
    lil = s.add_permanent(T.id_of("Lillia - Fae Fawn"), 0, bf_loc(0))
    s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    s.ply += 1
    spr = _sprite_at(s, 0, 0)
    s.perms[spr, P_LOC] = base_loc(0)
    s.bf_ctrl[0] = 0
    attack(s, 1, 0, body(s, 1, base_loc(1), 4, ready=True))
    drain(s)
    pass_priority_to(s, 0)
    cast(s, 0, "Smoke and Mirrors", lil, spr)
    chain_mod.queue = spy
    try:
        drain(s)
    finally:
        chain_mod.queue = real_queue
    assert len(steps) == 2 and steps[0][1] < steps[1][1], (
        f"the move and the inherited designation are different steps: {steps}")
    assert int(s.pend_order) < 0, "so nothing was there to order"


@case(11026, "Baron Nashor's +2 is for OTHER friendly units")
def _():
    need("Baron Nashor")
    s = fresh()
    b = s.add_permanent(T.id_of("Baron Nashor"), 0, bf_loc(0))
    u = body(s, 0, base_loc(0), 3)
    assert combat.might(s, T, b) == 12 and combat.might(s, T, u) == 5


@case(11038, "Piercing Light's second half resolves after the first target dies")
def _():
    need("Piercing Light", "Hidden Blade")
    s = fresh()
    a = body(s, 1, bf_loc(0), 5)
    b = body(s, 1, base_loc(1), 5)
    combat.destroy(s, T, a)                       # the Hidden Blade answer
    rsv.resolve(s, T, V1, SPECS["Piercing Light"], 0, [a, b], -1, True)
    assert int(s.perms[b, P_DMG]) == 2, "'then' is sequence, not condition"


@case(11050, "Defiant Dance still gives -2 when the +2 target leaves")
def _():
    need("Defiant Dance")
    s = fresh()
    up = body(s, 0, bf_loc(0), 3)
    down = body(s, 1, bf_loc(0), 5)
    combat.return_to_hand(s, T, up)
    rsv.resolve(s, T, V1, SPECS["Defiant Dance"], 0, [up, down], -1, True)
    assert combat.might(s, T, down) == 3, "359.3.e.8 -- the legal half resolves"


@case(11055, "a unit Smite banishes is not killed: no Deathknell")
def _():
    need("Smite", "Carrion Dredger")
    s = fresh()
    dr = s.add_permanent(T.id_of("Carrion Dredger"), 1, bf_loc(0))
    rsv.resolve(s, T, V1, SPECS["Smite"], 0, [dr], -1, True)
    A._settle(s, T, V1)
    drain(s)
    assert not alive(s, dr) and int(s.n_banished[1]) == 1, "banished instead"
    assert not tokens(s, 1), "808.1.d.1 -- no Bird, the Deathknell never fired"


@case(11073, "Assault counts toward Gust's 3 Might limit")
def _():
    need("Gust", "Immortal Phoenix")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.hand[0, 0], s.n_hand[0] = T.id_of("Gust"), 1
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 1, base_loc(1), ready=True)
    attack(s, 1, 0, ph)
    assert combat.might(s, T, ph) == 5, "3 + [Assault 2] while attacking"
    assert ph not in rsv.legal_targets(s, T, SPECS["Gust"], 0, 0, [], -1), (
        "Gust reads current Might, Assault included")


@case(11826, "Thousand-Tailed Watcher hits Baron (no choosing) and not later arrivals")
def _():
    need("Thousand-Tailed Watcher", "Baron Nashor")
    s = fresh()
    baron = s.add_permanent(T.id_of("Baron Nashor"), 1, bf_loc(0))
    w = s.add_permanent(T.id_of("Thousand-Tailed Watcher"), 0, base_loc(0))
    spec = abilities_for(T, T.id_of("Thousand-Tailed Watcher"))[0]
    rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=w)
    assert combat.might(s, T, baron) == 9, "12 - 3: 'enemy units' chooses nobody"
    late = body(s, 1, bf_loc(1), 5)
    assert combat.might(s, T, late) == 7, (
        "#11076 -- a snapshot, not a static: 5 + Baron's +2, and no -3")


@case(11080, "a countered second card does not ready Darius - Trifarian")
def _():
    need("Darius - Trifarian", "Gust", "Defy")
    s = fresh(hand=[T.id_of("Darius - Trifarian"), T.id_of("Gust")])
    give(s, 1, "Defy")
    cast(s, 0, "Darius - Trifarian", base_loc(0))
    drain(s)
    dar = perm_of(s, "Darius - Trifarian")[0]
    foe = body(s, 1, bf_loc(0), 2)
    cast(s, 0, "Gust", foe)
    cast(s, 1, "Defy", _top_uid(s))
    drain(s)
    assert int(s.perms[dar, P_READY]) == 0 and combat.might(s, T, dar) == 5, (
        "425.1.b / 419.4.a.1 -- the Gust was never played for the trigger")


@case(11103, "a repeated spell is played once: Ravenbloom Student +1, not +2")
def _():
    need("Ravenbloom Student", "Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")])
    st = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0))
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Bellows Breath", u, -1, -1, repeat=True)
    run(s, picking(u, -1))
    assert int(s.perms[u, P_DMG]) == 2, "both executions happened"
    assert combat.might(s, T, st) == 3, (
        f"820.3.a -- only Played once: got {combat.might(s, T, st)}")


@case(11113, "Crescent Strike's 4 does not follow a unit Flashed out")
def _():
    need("Crescent Strike", "Flash")
    s = fresh(hand=[T.id_of("Crescent Strike")])
    give(s, 1, "Flash")
    s.bf_ctrl[0] = 1
    tgt = body(s, 1, bf_loc(0), 6)
    other = body(s, 1, bf_loc(0), 6)
    mine = body(s, 0, bf_loc(0), 3)
    s.showdown_bf = 0
    cast(s, 0, "Crescent Strike", bf_loc(0), tgt)
    cast(s, 1, "Flash", tgt, -1)
    drain(s)
    assert int(s.perms[tgt, P_LOC]) == base_loc(1) and int(s.perms[tgt, P_DMG]) == 0, (
        "'an enemy unit there' -- gone from there, so no 4")
    assert int(s.perms[other, P_DMG]) == 1, "the others there still take 1"


@case(11118, "with Elder Dragon, 3 Might kills three defenders, 1 damage each")
def _():
    need("Elder Dragon")
    s = fresh()
    s.hand[1, 0], s.n_hand[1] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 1
    s.add_permanent(T.id_of("Elder Dragon"), 0, base_loc(0))
    foes = [body(s, 1, bf_loc(0), 3) for _ in range(3)]
    atk = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, atk)
    fight(s)
    assert not [f for f in foes if alive(s, f)], (
        "142.4.c -- 1 of your damage is lethal, so each needs only 1")


@case(11124, "Tactical Retreat saves the Deathgrip victim: no 'if you do' Might, still a draw")
def _():
    need("Deathgrip", "Tactical Retreat")
    s = fresh()
    victim = body(s, 0, bf_loc(0), 4)
    taker = body(s, 0, bf_loc(0), 2)
    rsv.resolve(s, T, V1, SPECS["Tactical Retreat"], 0, [victim], -1, True)
    hand = int(s.n_hand[0])
    rsv.resolve(s, T, V1, SPECS["Deathgrip"], 0, [victim, taker], -1, True)
    assert alive(s, victim) and int(s.perms[victim, P_LOC]) == base_loc(0)
    assert combat.might(s, T, taker) == 2, "FAQ #8668 -- not killed, so no +Might"
    assert int(s.n_hand[0]) == hand + 1, "but the draw is unconditional"


@case(11131, "Sacrifice's kill is a cost: a Defy leaves Ekko dead and draws nothing")
def _():
    need("Sacrifice", "Ekko - Recurrent", "Defy")
    s = fresh(hand=[T.id_of("Sacrifice")])
    give(s, 1, "Defy")
    ek = s.add_permanent(T.id_of("Ekko - Recurrent"), 0, base_loc(0))
    act(s, A.A_PLAY, 0, 0)
    choose(s, ek)
    pass_priority_to(s, 1)
    item = next(k for k in range(s.n_chain)
                if T.names[int(s.chain[k, 0])] == "Sacrifice")
    from rl.engine.state import C_UID
    cast(s, 1, "Defy", int(s.chain[item, C_UID]))
    drain(s)
    assert not alive(s, ek), "the cost was paid at play"
    assert int(s.n_hand[0]) == 0, "Sacrifice was countered: no draw 2"


@case(11142, "Gusting a Sprite is not a death: Viktor - Leader makes no Recruit")
def _():
    need("Gust", "Viktor - Leader", "Sprite Call")
    s = fresh()
    s.add_permanent(T.id_of("Viktor - Leader"), 0, base_loc(0))
    spr = _sprite_at(s, 0, 0)
    rsv.resolve(s, T, V1, SPECS["Gust"], 1, [spr], -1, True)
    A._settle(s, T, V1)
    drain(s)
    assert not alive(s, spr) and not tokens(s, 0), "no Recruit"


@case(11164, "a countered Deathgrip kills nothing -- the kill is its effect")
def _():
    need("Deathgrip", "Defy")
    s = fresh(hand=[T.id_of("Deathgrip")])
    give(s, 1, "Defy")
    a = body(s, 0, base_loc(0), 3)
    b = body(s, 0, base_loc(0), 2)
    cast(s, 0, "Deathgrip", a, b)
    cast(s, 1, "Defy", _top_uid(s))
    drain(s)
    assert alive(s, a), "425.1.a"


@case(11187, "Hidden Blade: no draw if the target left, a draw if Zhonya's saved it")
def _():
    need("Hidden Blade", "Gust", "Zhonya's Hourglass")
    s = fresh()
    u = body(s, 1, bf_loc(0), 3)
    combat.return_to_hand(s, T, u)                 # the Gust answer
    rsv.resolve(s, T, V1, SPECS["Hidden Blade"], 0, [u], -1, True)
    assert int(s.n_hand[1]) == 1, "only the Gusted card: no draw 2"
    z = fresh()
    v = body(z, 1, bf_loc(0), 3)
    g = z.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    z.death_guard[1] = g
    rsv.resolve(z, T, V1, SPECS["Hidden Blade"], 0, [v], -1, True)
    assert alive(z, v) and int(z.n_hand[1]) == 2, (
        "#11393 -- the kill was replaced, but the target was still there: draw 2")


@case(11248, "Soraka at base saves a smaller friend dying at base")
def _():
    need("Soraka - Wanderer")
    s = fresh()
    s.add_permanent(T.id_of("Soraka - Wanderer"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 2)
    s.perms[u, P_DMG] = 2
    combat.enforce_lethal(s, T)
    assert alive(s, u) and int(s.perms[u, P_DMG]) == 0 and int(s.perms[u, P_READY]) == 0


@case(11277, "a Defied Wages of Pain plays no Gold token")
def _():
    need("Wages of Pain", "Defy")
    s = fresh(hand=[T.id_of("Wages of Pain")])
    give(s, 1, "Defy")
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Wages of Pain", u)
    cast(s, 1, "Defy", _top_uid(s))
    drain(s)
    assert not tokens(s, 0) and int(s.perms[u, P_DMG]) == 0


@case(11279, "Imperial Decree does not kill damage marked before it resolved")
def _():
    need("Imperial Decree")
    s = fresh()
    u = body(s, 1, bf_loc(0), 5)
    combat.mark_damage(s, T, u, 1, by_seat=1)     # Frozen Fortress's 1
    rsv.resolve(s, T, V1, SPECS["Imperial Decree"], 0, [], -1, True)
    A._settle(s, T, V1)
    assert alive(s, u), "an event trigger, not a state check"
    combat.mark_damage(s, T, u, 1, by_seat=0)
    assert not alive(s, u), "but the next damage it takes kills it"


@case(11323, "Fading Memories' Temporary death is not a kill by a spell (Immortal Phoenix)")
def _():
    need("Fading Memories", "Immortal Phoenix")
    s = fresh()
    s.trash[0, 0], s.n_trash[0] = T.id_of("Immortal Phoenix"), 1
    u = body(s, 1, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Fading Memories"], 0, [u], -1, True)
    s.active = 1
    s.ply += 1
    phases.start_turn(s, T, V1)
    A._settle(s, T, V1)
    offers = 0
    for _ in range(20):
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        if who == 0 and any(a.kind == A.A_ACCEPT for a in legal):
            offers += 1
        if s.phase == MAIN and not s.n_chain and not s.n_trig:
            break
        A.apply(s, T, V1, next((a for a in legal if a.kind in (A.A_ORDER, A.A_PASS,
                                                                  A.A_DECLINE)), legal[0]))
    assert not alive(s, u), "Temporary killed it"
    assert offers == 0 and T.id_of("Immortal Phoenix") in list(s.trash[0, :int(s.n_trash[0])]), (
        "FAQ #1453 -- no 'kill a unit with a spell', so no Phoenix offer")


@case(11336, "Thrill of the Hunt replays a new object: Punch First's +5 is gone")
def _():
    need("Thrill of the Hunt", "Punch First")
    s = fresh()
    u = body(s, 0, base_loc(0))
    rsv.resolve(s, T, V1, SPECS["Punch First"], 0, [u], -1, True)
    assert combat.might(s, T, u) == 8
    rsv.resolve(s, T, V1, SPECS["Thrill of the Hunt"], 0, [u, bf_loc(0)], -1, True)
    drain(s)
    new = perm_of(s, "Shipyard Skulker", 0)
    assert new and combat.might(s, T, new[0]) == 3


@case(11344, "a unit recalled after a tied combat did not move: Stellacorn draws nothing")
def _():
    need("Stellacorn Herder")
    s = fresh()
    s.hand[1, 0], s.n_hand[1] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 5)
    st = s.add_permanent(T.id_of("Stellacorn Herder"), 0, base_loc(0), ready=True)
    s.perms[st, __import__("rl.engine.state", fromlist=["x"]).P_MIGHT_MOD] = 0
    attack(s, 0, 0, st)
    drain(s)
    after_move = int(s.n_hand[0])
    assert after_move == 1, "the Move itself drew 1"
    s.stun(st)
    for i in perm_of(s, "Shipyard Skulker", 1):
        s.stun(i)
    fight(s)
    assert int(s.perms[st, P_LOC]) == base_loc(0), "recalled"
    assert int(s.n_hand[0]) == after_move, "450 -- a Recall is not a Move"


@case(11411, "Unyielding Spirit does not stop Challenge -- the units deal it")
def _():
    need("Unyielding Spirit", "Challenge")
    s = fresh()
    mine = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, bf_loc(0), 4)
    rsv.resolve(s, T, V1, SPECS["Unyielding Spirit"], 1, [], -1, True)
    rsv.resolve(s, T, V1, SPECS["Challenge"], 0, [mine, theirs], -1, True)
    A._settle(s, T, V1)
    assert int(s.perms[theirs, P_DMG]) == 3 or not alive(s, theirs), (
        "FAQ 8394 -- not spell or ability damage")


@case(11421, "Ruined Rex killed for Sacrifice: its Deathknell resolves before Sacrifice")
def _():
    need("Sacrifice", "Ruined Rex")
    s = fresh(hand=[T.id_of("Sacrifice")])
    rex = s.add_permanent(T.id_of("Ruined Rex"), 0, base_loc(0))
    foe = body(s, 1, bf_loc(0), 9)
    act(s, A.A_PLAY, 0, 0)
    choose(s, rex)
    seen = []
    for _ in range(30):
        who = A.acting_seat(s)
        if who < 0 or (s.n_chain == 0 and s.n_trig == 0 and s.pend_slot < 0
                       and s.pend_may < 0 and not chain_mod.decision_open(s)):
            break
        legal = A.legal_actions(s, T, V1, who)
        before = (int(s.perms[foe, P_DMG]), int(s.n_hand[0]))
        pick = next((a for a in legal if a.kind == A.A_TARGET and a.arg == foe),
                    next((a for a in legal if a.kind in (A.A_ORDER, A.A_PASS)), legal[0]))
        A.apply(s, T, V1, pick)
        after = (int(s.perms[foe, P_DMG]), int(s.n_hand[0]))
        if after[0] != before[0]:
            seen.append("rex")
        if after[1] > before[1]:
            seen.append("sacrifice")
    assert seen[:2] == ["rex", "sacrifice"], (
        f"the Deathknell is the newest item, so it resolves first: {seen}")


@case(11441, "a repeated Bellows Breath cannot pick a Bird that its first pass made")
def _():
    need("Bellows Breath", "Carrion Dredger")
    s = fresh(hand=[T.id_of("Bellows Breath")])
    dr = s.add_permanent(T.id_of("Carrion Dredger"), 1, base_loc(1))
    cast(s, 0, "Bellows Breath", dr, -1, -1, repeat=True)
    legal = A.legal_actions(s, T, V1, 0)
    offered = {a.arg for a in legal if a.kind == A.A_TARGET}
    assert not tokens(s), "no Bird exists yet when the repeat's choices are made"
    assert offered <= {dr, -1}, f"820.2 -- chosen at play: {offered}"


@case(11463, "Yordle Explorer reads the printed Power: Switcheroo from Hidden draws")
def _():
    need("Yordle Explorer", "Switcheroo")
    s = fresh()
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Yordle Explorer"), 0, bf_loc(0))
    a = body(s, 0, bf_loc(0), 2)
    b = body(s, 1, bf_loc(0), 5)
    fd = list(fd_slots(0))[0]
    s.fd_owner[fd], s.fd_card[fd], s.fd_ply[fd] = 0, T.id_of("Switcheroo"), -5
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(a, b))
    assert int(s.n_hand[0]) == 1, f"FAQ #6912 -- [A][A] printed: hand {int(s.n_hand[0])}"


@case(11523, "moving a gear off a damaged unit can make its damage lethal")
def _():
    need("Jax - Grandmaster At Arms", "Long Sword")
    s = fresh()
    u = body(s, 0, base_loc(0), 4)
    sw = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
    s.attach(sw, u)
    other = body(s, 0, base_loc(0), 3)
    s.perms[u, P_DMG] = 5
    assert alive(s, u) and combat.might(s, T, u) == 6
    s.attach(sw, other)                            # Jax's re-attach
    A._settle(s, T, V1)
    combat.enforce_lethal(s, T)
    assert not alive(s, u), "143.2.a -- 5 damage on 4 Might, nothing new needed"


@case(11526, "a stolen attacker becomes a defender and loses its Assault")
def _():
    need("Hostile Takeover", "Immortal Phoenix")
    s = fresh(seat=1)
    s.hand[0, 0], s.n_hand[0] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 1, base_loc(1), ready=True)
    other = body(s, 1, base_loc(1), 2, ready=True)
    attack(s, 1, 0, ph, other)
    assert combat.might(s, T, ph) == 5
    rsv.resolve(s, T, V1, SPECS["Hostile Takeover"], 0, [ph], -1, True)
    combat.cleanup(s, T, V1)
    assert int(s.perms[ph, P_CTRL]) == 0 and combat.might(s, T, ph) == 3, (
        f"323.2.b -- it is now a defender: got {combat.might(s, T, ph)}")


@case(11530, "a countered spell still counts for Battering Ram (419.4.b)")
def _():
    need("Battering Ram", "Gust", "Defy")
    from rl.engine import cost
    s = fresh(hand=[T.id_of("Gust"), T.id_of("Battering Ram")])
    give(s, 1, "Defy")
    foe = body(s, 1, bf_loc(0), 2)
    ram = T.id_of("Battering Ram")
    full = cost.effective_energy(s, T, 0, ram)
    cast(s, 0, "Gust", foe)
    cast(s, 1, "Defy", _top_uid(s))
    drain(s)
    assert alive(s, foe), "the Gust was countered"
    assert cost.effective_energy(s, T, 0, ram) == full - 1, "finalized, so it counts"


@case(11638, "Turn to Dust's granted Temporary kills an ATTACHED gear next turn")
def _():
    need("Turn to Dust", "Long Sword")
    s = fresh()
    rune_deck(s)
    u = body(s, 0, base_loc(0))
    sw = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
    s.attach(sw, u)
    rsv.resolve(s, T, V1, SPECS["Turn to Dust"], 1, [sw], -1, True)
    _next_own_turn(s)
    drain(s)
    assert not perm_of(s, "Long Sword"), "granted text stays Active while attached"
    assert perm_of(s, "Shipyard Skulker"), "the unit is fine"


@case(11553, "Imperial Decree: 5 Might into five 3s kills two defenders and dies")
def _():
    need("Imperial Decree")
    s = fresh()
    s.hand[1, 0], s.n_hand[1] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 1
    foes = [body(s, 1, bf_loc(0), 3) for _ in range(5)]
    atk = body(s, 0, base_loc(0), 5, ready=True)
    rsv.resolve(s, T, V1, SPECS["Imperial Decree"], 0, [], -1, True)
    attack(s, 0, 0, atk)
    fight(s)
    dead = [f for f in foes if not alive(s, f)]
    assert len(dead) == 2, f"lethal first, then the rest: 3 + 2 -> {len(dead)} dead"
    assert not alive(s, atk) and int(s.bf_ctrl[0]) == 1


@case(11575, "a Reflection copying a unit does not get its play effect")
def _():
    need("Mirror Image", "Field Musicians")
    s = fresh()
    fm = s.add_permanent(T.id_of("Field Musicians"), 1, base_loc(1))
    rsv.resolve(s, T, V1, SPECS["Mirror Image"], 0, [fm], -1, True)
    A._settle(s, T, V1)
    assert s.n_chain == 0 and s.n_trig == 0 and s.pend_may < 0, (
        "the copy was never PLAYED as Field Musicians")
    ref = tokens(s, 0)
    assert ref and combat.perm_kw(s, T, ref[0], "Temporary"), "#11967 -- the copy has Temporary"
    assert not combat.perm_kw(s, T, fm, "Temporary"), "the original does not"


@case(11690, "Zhonya's saves a Sprite from Temporary; it keeps Temporary")
def _():
    need("Zhonya's Hourglass", "Sprite Call")
    s = fresh()
    rune_deck(s)
    spr = _sprite_at(s, 0, 0)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    s.death_guard[0] = z
    _next_own_turn(s)
    drain(s)
    assert alive(s, spr) and int(s.perms[spr, P_LOC]) == base_loc(0), "saved, recalled"
    assert combat.perm_kw(s, T, spr, "Temporary"), "#11582 -- and will die next turn"


@case(11605, "Abandoned Hall cannot buff a unit Flash moved away")
def _():
    need("Abandoned Hall", "Flash")
    s = fresh(hand=[T.id_of("Flash")])
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Flash", u, -1)
    run(s, picking(u))
    assert int(s.perms[u, P_LOC]) == base_loc(0) and combat.might(s, T, u) == 3, (
        "'a unit you control HERE' -- it is not here any more")


@case(11672, "Emperor's Divide cannot move units off Vilemaw's Lair")
def _():
    need("Emperor's Divide", "Vilemaw's Lair")
    s = fresh()
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Emperor's Divide"], 0, [u, -1, -1, -1], -1, True)
    assert int(s.perms[u, P_LOC]) == bf_loc(0), "can't beats can"


@case(11797, "Minotaur Reckoner stops a Flash to base")
def _():
    need("Minotaur Reckoner", "Flash")
    s = fresh()
    s.add_permanent(T.id_of("Minotaur Reckoner"), 1, base_loc(1))
    u = body(s, 0, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Flash"], 0, [u, -1], -1, True)
    assert int(s.perms[u, P_LOC]) == bf_loc(0), "Units can't move to base"


@case(11225, "Blue Sentinel doubles Chem-Baroness's hold trigger, but she exhausts once")
def _():
    need("Blue Sentinel", "Renata Glasc - Chem-Baroness")
    s = fresh()
    s.legend[0], s.legend_ready[0] = T.id_of("Renata Glasc - Chem-Baroness"), 1
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Blue Sentinel"), 0, bf_loc(0))
    phases.score_holds(s, V1, T)
    A._settle(s, T, V1)
    run(s, picking())
    golds = [i for i in tokens(s, 0) if T.names[int(s.perms[i, P_CARD])].startswith("Gold")]
    assert len(golds) == 1, f"414.4 -- an exhausted legend cannot pay again: {len(golds)}"


@case(11309, "Blue Sentinel at Power Nexus: two paid triggers, two extra points")
def _():
    need("Blue Sentinel", "Power Nexus")
    s = fresh()
    s.bf_card[0] = T.id_of("Power Nexus")
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Blue Sentinel"), 0, bf_loc(0))
    phases.score_holds(s, V1, T)
    A._settle(s, T, V1)
    run(s, picking())
    assert int(s.points[0]) == 3, (
        f"the Hold, plus 1 per Nexus trigger (470 limits only Hold/Conquer): "
        f"{int(s.points[0])}")


@case(11296, "Dusk Rose Lab on a Temporary Deathknell unit: the draw AND the Deathknell")
def _():
    need("Dusk Rose Lab", "Soaring Scout", "Fading Memories")
    s = fresh()
    rune_deck(s)
    s.bf_card[0] = T.id_of("Dusk Rose Lab")
    s.bf_ctrl[0] = 0
    sc = s.add_permanent(T.id_of("Soaring Scout"), 0, bf_loc(0))
    body(s, 0, bf_loc(0), 3)                       # keep the ground afterwards
    rsv.resolve(s, T, V1, SPECS["Fading Memories"], 0, [sc], -1, True)
    before_runes, hand = runes(s, 0), int(s.n_hand[0])
    _next_own_turn(s)

    def pref(s, who, legal):
        orders = [a for a in legal if a.kind == A.A_ORDER]
        if orders:
            tmp = [a for a in orders if int(s.trig[a.arg, 1]) == sc]
            return (tmp or orders)[0]              # Temporary down first
        return picking(sc)(s, who, legal)
    run(s, pref, limit=80)
    assert not alive(s, sc)
    assert int(s.n_hand[0]) == hand + 2, "the Lab's draw plus the Draw Phase"
    assert runes(s, 0) >= before_runes + 3, (
        f"Deathknell channelled 1 on top of the turn's 2: {runes(s, 0) - before_runes}")


@case(11363, "a hidden Hidden Blade on your own expiring Sprite draws you 2")
def _():
    need("Hidden Blade", "Sprite Call")
    s = fresh()
    rune_deck(s)
    spr = _sprite_at(s, 0, 0)
    fd = list(fd_slots(0))[0]
    s.fd_owner[fd], s.fd_card[fd] = 0, T.id_of("Hidden Blade")
    hand = int(s.n_hand[0])
    _next_own_turn(s)
    s.fd_ply[fd] = int(s.ply) - 1
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(spr))
    assert not alive(s, spr)
    assert int(s.n_hand[0]) == hand + 3, "Hidden Blade's 2 plus the Draw Phase"


@case(11612, "Ride the Wind from one Abandoned Hall to another: +1 from the destination only")
def _():
    need("Abandoned Hall", "Ride The Wind")
    s = fresh(hand=[T.id_of("Ride The Wind")])
    s.bf_card[0] = s.bf_card[1] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    u = body(s, 0, bf_loc(0), 3)
    s.add_permanent(T.id_of("Soaring Scout"), 0, bf_loc(1))   # keeps bf1 ours
    cast(s, 0, "Ride The Wind", u, bf_loc(1))
    run(s, picking(u))
    assert int(s.perms[u, P_LOC]) == bf_loc(1) and combat.might(s, T, u) == 4, (
        f"FAQ #11430 -- one +1: got {combat.might(s, T, u)}")


@case(11620, "Brutalizer's +3 leaves with it")
def _():
    need("Brutalizer")
    s = fresh()
    u = body(s, 0, base_loc(0))
    br = s.add_permanent(T.id_of("Brutalizer"), 0, base_loc(0))
    s.attach(br, u)
    assert combat.might(s, T, u) == 6, f"3 + 1 + 2 this turn: {combat.might(s, T, u)}"
    s.detach(br)
    assert combat.might(s, T, u) == 3


@case(11621, "a Deathknell's damage after the Combat heal stays marked")
def _():
    need("Ruined Rex")
    s = fresh()
    s.hand[1, 0], s.n_hand[1] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 0
    rex = s.add_permanent(T.id_of("Ruined Rex"), 0, bf_loc(0))
    elsewhere = body(s, 1, bf_loc(1), 9)
    atk = body(s, 1, base_loc(1), 6, ready=True)
    attack(s, 1, 0, atk)
    run(s, picking(elsewhere))
    assert not alive(s, rex) and not alive(s, atk), "they traded"
    assert int(s.perms[elsewhere, P_DMG]) == 4, (
        f"461.1.a.1 heals before the Deathknell resolves: {int(s.perms[elsewhere, P_DMG])}")


@case(11667, "Elder Dragon: pre-marked 1 damage kills Irelia, Guardian Angel saves her")
def _():
    need("Elder Dragon", "Guardian Angel", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("Elder Dragon")])
    s.bf_ctrl[0] = 1
    ire = s.add_permanent(T.id_of("Irelia, Fervent"), 1, bf_loc(0))
    ga = s.add_permanent(T.id_of("Guardian Angel"), 1, bf_loc(0))
    s.attach(ga, ire)
    combat.mark_damage(s, T, ire, 1, by_seat=0)
    cast(s, 0, "Elder Dragon", base_loc(0))
    assert alive(s, ire) and int(s.perms[ire, P_LOC]) == base_loc(1), (
        "the entry kill is replaced: healed, exhausted, recalled")
    assert not alive(s, ga) and int(s.perms[ire, P_DMG]) == 0


@case(11679, "two Astral Herons discount the next card twice")
def _():
    need("Astral Heron", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")])
    s.bf_ctrl[0] = 0
    h1 = s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    cast(s, 0, "Discipline", h1)
    drain(s)
    assert int(s.next_discount[0, 0]) == 4 and int(s.next_discount[0, 1]) == 4, (
        f"356.4 -- the discounts add: {list(s.next_discount[0])}")


@case(11714, "Vex - Apathetic stuns an enemy Sprite token as it is played")
def _():
    need("Vex - Apathetic", "Sprite Call")
    s = fresh()
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    spr = _sprite_at(s, 0, 0)
    drain(s)
    assert s.has_flag(spr, F_STUNNED), "a token is played (187), so Vex sees it"


@case(11785, "Blighted Battleaxe checks the UNIT's conquest, whenever it was equipped")
def _():
    need("Blighted Battleaxe")
    s = fresh()
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    fight(s)
    assert int(s.bf_ctrl[0]) == 0, "it conquered"
    ax = s.add_permanent(T.id_of("Blighted Battleaxe"), 0, bf_loc(0))
    s.attach(ax, u)
    act(s, A.A_END_TURN, None, 0)
    drain(s)
    axe = perm_of(s, "Blighted Battleaxe")
    assert axe and s.is_attached(axe[0]), "the condition failed: it stays on"


@case(11792, "Astral Heron dying after her trigger does not cancel the discount")
def _():
    need("Astral Heron", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")])
    s.bf_ctrl[0] = 0
    her = s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    cast(s, 0, "Discipline", her)
    for _ in range(8):                      # to the Heron's trigger on the Chain
        if s.n_chain and T.names[int(s.chain[s.n_chain - 1, 0])] == "Astral Heron":
            break
        A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, A.acting_seat(s))
                               if a.kind in (A.A_PASS, A.A_ORDER)))
    combat.destroy(s, T, her)                        # killed in response
    drain(s)
    assert int(s.next_discount[0].sum()) > 0, "383.2.c -- evaluated when it triggered"


@case(11811, "Baron Nashor cannot be chosen by an enemy Back Off or The List")
def _():
    need("Baron Nashor", "Back Off", "The List")
    s = fresh()
    baron = s.add_permanent(T.id_of("Baron Nashor"), 1, bf_loc(0))
    mine = s.add_permanent(T.id_of("Baron Nashor"), 0, bf_loc(1))
    assert baron not in rsv.legal_targets(s, T, SPECS["Back Off"], 0, 0, [], -1)
    assert mine in rsv.legal_targets(s, T, SPECS["Back Off"], 0, 0, [], -1), (
        "only ENEMY spells are shut out")
    lst = next(a for a in abilities_for(T, T.id_of("The List")) if a.targets)
    assert baron not in rsv.legal_targets(s, T, lst, 0, 0, [], -1)


@case(11863, "a stunned unit still conquers an open battlefield")
def _():
    s = fresh()
    u = body(s, 0, base_loc(0), 3, ready=True)
    act(s, A.A_DECLARE, bf_loc(0), 0)
    act(s, A.A_ADD, u, 0)
    s.stun(u)
    act(s, A.A_COMMIT, None, 0)
    fight(s)
    assert int(s.bf_ctrl[0]) == 0 and int(s.points[0]) == 1


@case(11871, "spell damage on a defender heals when its Combat ends")
def _():
    need("Falling Star")
    s = fresh(seat=1)
    s.hand[0, 0], s.n_hand[0] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 0
    her = body(s, 0, bf_loc(0), 7)
    rsv.resolve(s, T, V1, SPECS["Falling Star"], 1, [her, her], -1, True)
    assert int(s.perms[her, P_DMG]) == 6
    atk = body(s, 1, base_loc(1), 2, ready=True)
    attack(s, 1, 0, atk)
    s.stun(atk)
    fight(s)
    assert alive(s, her) and int(s.perms[her, P_DMG]) == 0, "466.1.a.1 heals all units"


@case(11895, "Assault does nothing in a Non-Combat Showdown")
def _():
    s = fresh()
    s.hand[1, 0], s.n_hand[1] = T.id_of("Smoke Screen"), 1
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, ph)
    assert s.showdown_bf == 0 and not s.showdown_combat
    assert combat.might(s, T, ph) == 3, "807.1.d -- no Attacker without a Combat"


@case(11955, "a repeated Bellows Breath at Void Gate is two hits of 2")
def _():
    need("Bellows Breath", "Void Gate")
    s = fresh(hand=[T.id_of("Bellows Breath")])
    s.bf_card[0] = T.id_of("Void Gate")
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Bellows Breath", u, -1, -1, repeat=True)
    run(s, picking(u, -1))
    assert int(s.perms[u, P_DMG]) == 4


@case(11956, "Stupefy on a 1 Might unit does nothing; +2 afterwards makes it 3")
def _():
    need("Stupefy", "Discipline")
    s = fresh()
    u = body(s, 1, base_loc(1), 1)
    rsv.resolve(s, T, V1, SPECS["Stupefy"], 0, [u], -1, True)
    rsv.resolve(s, T, V1, SPECS["Discipline"], 1, [u], -1, True)
    assert combat.might(s, T, u) == 3, f"477.3.b snapshot: {combat.might(s, T, u)}"


@case(11983, "Discipline still draws when its target was Gusted")
def _():
    need("Discipline")
    s = fresh()
    u = body(s, 0, bf_loc(0), 3)
    combat.return_to_hand(s, T, u)
    hand = int(s.n_hand[0])
    rsv.resolve(s, T, V1, SPECS["Discipline"], 0, [u], -1, True)
    assert int(s.n_hand[0]) == hand + 1


@case(11994, "Rampage paid: the +2 lands even if the enemy target was Gusted")
def _():
    need("Rampage")
    s = fresh(hand=[T.id_of("Rampage")])
    mine = body(s, 0, bf_loc(0), 3)
    foe = body(s, 1, bf_loc(0), 3)
    act(s, A.A_PLAY_REPEAT, 0, 0)                  # pay the optional [Body]
    choose(s, mine)
    choose(s, foe)
    combat.return_to_hand(s, T, foe)               # the Gust answer
    drain(s)
    assert combat.might(s, T, mine) == 5 and int(s.perms[mine, P_DMG]) == 0, (
        f"359.3.e.5 -- got Might {combat.might(s, T, mine)}")



# Later batches live in rl/tests/judge/cases_*.py; importing one runs its cases.
import importlib as _il
import pkgutil as _pu
import rl.tests.judge as _pkg
for _m in sorted(m.name for m in _pu.iter_modules(_pkg.__path__)
                 if m.name.startswith("cases_")):
    _il.import_module(f"rl.tests.judge.{_m}")


def _report():
    RESULTS = _h.RESULTS
    width = max(len(t) for _, _, t, _ in RESULTS) if RESULTS else 10
    for status, qid, title, msg in RESULTS:
        colour = {"PASS": "\033[32m", "FAIL": "\033[31m", "SKIP": "\033[33m",
                  "KNOWN": "\033[35m"}[status]
        line = f"  {colour}{status}\033[0m #{qid:<6} {title:<{width}}"
        print(line + (f"  -- {msg}" if msg else ""))
    bad = sum(1 for r in RESULTS if r[0] == "FAIL")
    skipped = sum(1 for r in RESULTS if r[0] == "SKIP")
    known = sum(1 for r in RESULTS if r[0] == "KNOWN")
    print(f"\n{len(RESULTS) - bad - skipped - known} pass / {bad} fail / "
          f"{skipped} skip / {known} known-bad")
    if known:
        print("\nKNOWN-BAD -- the ruling is right and the engine is wrong. "
              "Each one's rule and why the fix is not small:")
        for _, qid, _, _ in [r for r in RESULTS if r[0] == "KNOWN"]:
            print(f"  #{qid}: {_h.KNOWN_BAD[qid]}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    _report()
