"""RiftJudge batch 24 -- unused questions from 9970-10057."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_NO_MOVE, P_ATTACHED_TO
from rl.engine.effects import ABILITIES, pack_trash


@case(10055, "Star-Crossing Deathgrip's buff target: the kill still happens")
def _():
    need("Deathgrip", "Star-Crossed")
    s = fresh(hand=[T.id_of("Deathgrip")], runes=9)
    give(s, 1, "Star-Crossed")
    s.runes_ready[1, :] = 9
    dead = body(s, 0, base_loc(0), 3)
    buffed = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Deathgrip", dead, buffed)
    cast(s, 1, "Star-Crossed", theirs, buffed)
    run(s)
    assert not alive(s, dead) and not alive(s, buffed)
    assert int(s.n_hand[0]) == 2, "the bounced unit and Deathgrip's draw"


@case(10053, "Moonfall's -2 does not reach a unit arriving afterwards")
def _():
    need("Moonfall", "Determined Sentry")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    early = body(s, 1, bf_loc(0), 5)
    # resolved directly: both seats at one battlefield would stage a Combat
    rsv.resolve(s, T, V1, SPECS["Moonfall"], 0, [bf_loc(0), -1], -1, True)
    assert combat.might(s, T, early) == 3
    late = s.add_permanent(T.id_of("Determined Sentry"), 1, bf_loc(0))
    assert combat.might(s, T, late) == 1, "its printed 1, untouched"


@case(10045, "Vi killed in answer to her attack trigger stuns nothing")
def _():
    need("Vi - Peacekeeper")
    s = fresh()
    s.bf_ctrl[0] = 1
    vi = s.add_permanent(T.id_of("Vi - Peacekeeper"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, vi)
    assert "Vi - Peacekeeper" in chain_names(s)
    combat.destroy(s, T, vi)                  # the Hidden Blade in answer
    run(s, picking(d))
    assert not s.has_flag(d, F_STUNNED), "'here' left with her"


@case(10044, "Falling Comet may be played in the opponent's non-combat showdown")
def _():
    need("Falling Comet")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    give(s, 0, "Falling Comet")
    give(s, 1, "Smoke Screen")
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    assert int(s.showdown_bf) == 0 and not s.showdown_combat
    pass_priority_to(s, 0)
    assert "Falling Comet" in hand_plays(s, 0), hand_plays(s, 0)


@case(10039, "Reckoner's Arena runs [Hunt] once more on a hold")
def _():
    need("Reckoner's Arena", "Scorchclaw")
    s = fresh()
    s.bf_card[0] = T.id_of("Reckoner's Arena")
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Scorchclaw"), 0, bf_loc(0))
    _next_own_turn(s)
    run(s, picking())
    assert int(s.xp[0]) == 4, int(s.xp[0])


@case(10035, "Thrill of the Hunt makes a new object: Falling Star misses it")
def _():
    need("Falling Star", "Thrill of the Hunt")
    s = fresh(hand=[T.id_of("Falling Star")], runes=9)
    give(s, 1, "Thrill of the Hunt")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    foe = s.add_permanent(T.id_of("Mindsplitter"), 1, bf_loc(0))
    cast(s, 0, "Falling Star", foe, foe)
    cast(s, 1, "Thrill of the Hunt", foe)
    run(s, picking(bf_loc(0), bf_loc(1)))
    back = perm_of(s, "Mindsplitter", 1)
    assert back and all(int(s.perms[i, P_DMG]) == 0 for i in back)


@case(10034, "Vi - Peacekeeper played by [Ambush] into a combat stuns")
def _():
    need("Vi - Peacekeeper")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 1
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 6
    a = body(s, 0, base_loc(0), 3, ready=True)
    d = body(s, 1, bf_loc(0), 9)
    give(s, 0, "Vi - Peacekeeper")
    attack(s, 0, 0, a)
    cast(s, 0, "Vi - Peacekeeper", bf_loc(0))
    run(s, picking(d), stop=lambda s: s.has_flag(d, F_STUNNED))
    assert s.has_flag(d, F_STUNNED)


@case(10032, "Baited Hook cannot be activated in answer to a spell")
def _():
    need("Baited Hook", "Discipline")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0))
    body(s, 0, base_loc(0), 3)
    give(s, 1, "Discipline")
    u = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Discipline", u)
    pass_priority_to(s, 0)
    assert not any(a.kind == A.A_ACTIVATE and a.arg == bh
                   for a in A.legal_actions(s, T, V1, 0))


@case(10029, "Riposte counts the spell's printed Energy, not what was paid")
def _():
    need("Riposte", "Call to Glory")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    give(s, 0, "Riposte")
    give(s, 1, "Call to Glory")
    theirs = body(s, 1, base_loc(1), 3)
    s.set_flag(theirs, F_BUFFED)
    mine = body(s, 0, base_loc(0), 3)
    # paid with the buff, so its cost is ignored -- 0 Energy actually spent
    act(s, A.A_PLAY_REPEAT, hand_index(s, 1, "Call to Glory"), 1)
    choose(s, theirs)
    choose(s, theirs)
    cast(s, 0, "Riposte", mine, top_uid(s))
    run(s)
    assert combat.might(s, T, mine) == 6, combat.might(s, T, mine)


@case(10028, "Vex - Apathetic stuns Baron Nashor arriving at the Baron Pit")
def _():
    need("Vex - Apathetic", "Baron Nashor")
    s = fresh(hand=[T.id_of("Baron Nashor")], runes=12)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    cast(s, 0, "Baron Nashor", base_loc(0))
    run(s, picking())
    bn = perm_of(s, "Baron Nashor")
    assert bn and s.has_flag(bn[0], F_STUNNED), "a trigger that chooses nothing"


@case(10026, "Void Assault into an open battlefield: you are the attacker")
def _():
    need("Void Assault")
    s = fresh(hand=[T.id_of("Void Assault")], runes=9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 6
    mine = body(s, 0, base_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Void Assault", mine, bf_loc(0), foe, bf_loc(0))
    run(s, stop=lambda s: bool(s.showdown_combat))
    assert int(s.perms[foe, P_LOC]) == bf_loc(0) and int(s.attacker) == 0


@case(10008, "Discipline still draws after Star-Crossed takes its unit")
def _():
    need("Discipline", "Star-Crossed")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    give(s, 1, "Star-Crossed")
    s.runes_ready[1, :] = 9
    u = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Star-Crossed", theirs, u)
    run(s)
    assert int(s.n_hand[0]) == 2, "the unit back, and the draw"


@case(10006, "Crescent Strike's splash does not pay for [Deflect]")
def _():
    need("Crescent Strike", "Vex - Apathetic")
    s = fresh(hand=[T.id_of("Crescent Strike")], runes=9)
    s.bf_ctrl[1] = 1
    main = body(s, 1, bf_loc(0), 9)
    # printed [Deflect] on itself only (Allay would grant it to the main target)
    allay = s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(0))
    before = runes(s, 0)
    cast(s, 0, "Crescent Strike", bf_loc(0), main)
    run(s)
    assert int(s.perms[allay, P_DMG]) == 1
    assert runes(s, 0) == before - int(T.power[T.id_of("Crescent Strike")]), \
        "its own Power only: the splash chose nobody, so no Deflect"


@case(10004, "a repeated spell is played once: Ravenbloom Student +1")
def _():
    need("Ravenbloom Student", "Upstage Comedy")
    s = fresh(hand=[T.id_of("Upstage Comedy")], runes=9)
    st = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Upstage Comedy", u, u, repeat=True)
    run(s)
    assert combat.might(s, T, st) == 3, combat.might(s, T, st)


@case(9996, "Forgotten Signpost is exhausted by its own ability")
def _():
    need("Forgotten Signpost")
    s = fresh()
    sp = s.add_permanent(T.id_of("Forgotten Signpost"), 0, base_loc(0))
    s.bf_ctrl[0] = 0
    anchor = body(s, 0, bf_loc(0), 3, ready=True)
    mover = body(s, 0, base_loc(0), 3)
    act(s, A.A_ACTIVATE, sp, 0)
    run(s, picks(anchor, mover))
    assert int(s.perms[sp, P_READY]) == 0 and int(s.perms[anchor, P_READY]) == 0
    assert int(s.perms[mover, P_LOC]) == bf_loc(0)


@case(9982, "Rengar - Pridestalker's legend sees token units being played")
def _():
    need("Rengar - Pridestalker", "Sprite Call")
    s = fresh(hand=[T.id_of("Sprite Call")], runes=9)
    s.legend[0], s.legend_ready[0] = T.id_of("Rengar - Pridestalker"), 1
    s.bf_ctrl[0] = 0
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Sprite Call", bf_loc(0))
    run(s, picking(u))
    assert combat.might(s, T, u) == 4, combat.might(s, T, u)


@case(9977, "Kinkou Initiate adds up all your other units' Might")
def _():
    need("Kinkou Initiate")
    s = fresh(hand=[T.id_of("Kinkou Initiate")], runes=9)
    body(s, 0, base_loc(0), 3)
    body(s, 0, bf_loc(0), 2)
    cast(s, 0, "Kinkou Initiate", base_loc(0))
    run(s)
    assert int(s.n_hand[0]) == 1, "3 + 2 is 5"


@case(9973, "a spell Abandon countered does not count for Jhin - Virtuoso")
def _():
    need("Jhin - Virtuoso", "Abandon", "Falling Comet")
    s = fresh(hand=[T.id_of("Falling Comet")], runes=9)
    s.legend[0], s.legend_ready[0] = T.id_of("Jhin - Virtuoso"), 1
    give(s, 1, "Abandon")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Falling Comet", foe)
    cast(s, 1, "Abandon", top_uid(s))
    run(s, picking())
    assert "Jhin - Virtuoso" not in str(chain_names(s))
    assert T.id_of("Falling Comet") in list(s.hand[0, :int(s.n_hand[0])])
    assert int(s.banished[0].max()) < 0 or T.id_of("Falling Comet") not in list(s.banished[0])
