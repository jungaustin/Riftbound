"""RiftJudge batch 29 -- unused questions from 9535-9620."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_NO_MOVE, P_ATTACHED_TO
from rl.engine.effects import ABILITIES, pack_trash


@case(9620, "Glasc Mixologist revives a unit Singularity killed with it, there")
def _():
    need("Glasc Mixologist", "Singularity", "Determined Sentry")
    s = fresh(seat=1, runes=12)
    give(s, 1, "Singularity")
    s.bf_ctrl[0] = 0
    g = s.add_permanent(T.id_of("Glasc Mixologist"), 0, bf_loc(0))
    ds = s.add_permanent(T.id_of("Determined Sentry"), 0, bf_loc(0))
    cast(s, 1, "Singularity", g, ds)
    run(s, picks(pack_trash(0, T.id_of("Determined Sentry")), bf_loc(0)))
    back = perm_of(s, "Determined Sentry")
    assert back and int(s.perms[back[0], P_LOC]) == bf_loc(0)


@case(9616, "Sun Disc does not count itself for its [Legion]")
def _():
    need("Sun Disc")
    s = fresh(hand=[T.id_of("Sun Disc")], runes=9)
    cast(s, 0, "Sun Disc", base_loc(0))
    run(s)
    sd = perm_of(s, "Sun Disc")[0]
    assert not any(a.kind == A.A_ACTIVATE and a.arg == sd
                   for a in A.legal_actions(s, T, V1, 0))


@case(9615, "Tianna blocks the point, not the Scoring: the last battlefield can still win")
def _():
    need("Tianna Crownguard")
    s = fresh(runes=9)
    s.points[0] = 7
    s.bf_ctrl[0] = 0
    s.add_permanent(VANILLA, 0, bf_loc(0))
    s.bf_ctrl[1] = 1
    tc = s.add_permanent(T.id_of("Tianna Crownguard"), 1, bf_loc(1))
    _next_own_turn(s)
    run(s, picking())
    assert int(s.points[0]) == 7 and int(s.bf_scored[0, 0]) == 1
    combat.destroy(s, T, tc)
    run(s)
    a = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 1, a)
    run(s, picking())
    assert int(s.points[0]) == 8, "every battlefield Scored this turn"


@case(9614, "a unit Thrill of the Hunt plays counts as a card played")
def _():
    need("Thrill of the Hunt", "Darius - Trifarian")
    s = fresh(hand=[T.id_of("Thrill of the Hunt")], runes=9)
    dar = s.add_permanent(T.id_of("Darius - Trifarian"), 0, base_loc(0), ready=False)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Thrill of the Hunt", u)
    run(s, picking(bf_loc(0)))
    assert combat.might(s, T, dar) == 7 and int(s.perms[dar, P_READY]) == 1


@case(9612, "Ruined Rex's Deathknell may hit an enemy anywhere")
def _():
    need("Ruined Rex")
    s = fresh()
    s.bf_ctrl[0] = 0
    rex = s.add_permanent(T.id_of("Ruined Rex"), 0, bf_loc(0))
    far = body(s, 1, bf_loc(1), 9)
    combat.destroy(s, T, rex)
    run(s, picking(far))
    assert int(s.perms[far, P_DMG]) == 4


@case(9604, "Stormbringer hits every enemy unit at the battlefield")
def _():
    need("Stormbringer")
    s = fresh(hand=[T.id_of("Stormbringer")], runes=12)
    u = body(s, 0, base_loc(0), 4)
    s.bf_ctrl[1] = 1
    e1 = body(s, 1, bf_loc(0), 9)
    e2 = body(s, 1, bf_loc(0), 9)
    give(s, 1, "Smoke Screen")                # hold the combat open to look
    s.runes_ready[1, :] = 6
    cast(s, 0, "Stormbringer", u, bf_loc(0))
    run(s, stop=lambda s: int(s.perms[u, P_LOC]) == bf_loc(0))
    assert int(s.perms[e1, P_DMG]) == 4 and int(s.perms[e2, P_DMG]) == 4


@case(9602, "En Garde on a lone Irelia, Fervent: +3 in all")
def _():
    need("En Garde", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("En Garde")], runes=9)
    s.bf_ctrl[0] = 0
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, bf_loc(0))
    cast(s, 0, "En Garde", ir)
    run(s)
    assert combat.might(s, T, ir) == 7, combat.might(s, T, ir)


@case(9598, "Atakhan's attack makes the defender kill even a Ruin Runner")
def _():
    need("Atakhan", "Ruin Runner")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 1
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, bf_loc(0))
    at = s.add_permanent(T.id_of("Atakhan"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, at)
    run(s, picking(rr), stop=lambda s: not alive(s, rr))
    assert not alive(s, rr), "the defender chose it; Atakhan chose nothing"


@case(9597, "Piercing Light's first unit must be at a battlefield")
def _():
    need("Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=9)
    body(s, 1, base_loc(1), 3)
    body(s, 0, base_loc(0), 3)
    assert "Piercing Light" not in hand_plays(s, 0)


@case(9577, "Gust on a Quick-Draw's unit: the Equipment stays unattached")
def _():
    need("Long Sword", "Gust")
    s = fresh(hand=[T.id_of("Long Sword")], runes=9)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Long Sword", base_loc(0))
    choose(s, u)                             # Quick-Draw's attach trigger
    cast(s, 1, "Gust", u)
    run(s)
    ls = perm_of(s, "Long Sword")
    assert ls and int(s.perms[ls[0], P_ATTACHED_TO]) < 0 and not alive(s, u)


@case(9575, "a unit hurt by Challenge in base heals when the combat ends")
def _():
    need("Challenge")
    s = fresh(hand=[T.id_of("Challenge")], runes=9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 6
    s.bf_ctrl[0] = 1
    a = body(s, 0, base_loc(0), 5, ready=True)
    home = body(s, 0, base_loc(0), 5)
    d = body(s, 1, bf_loc(0), 2)
    attack(s, 0, 0, a)
    rsv.resolve(s, T, V1, SPECS["Challenge"], 0, [home, d], -1, True)
    assert int(s.perms[home, P_DMG]) == 2
    fight(s)
    assert int(s.perms[home, P_DMG]) == 0, "every unit heals at the combat's end"


@case(9569, "Friendship with no tags gives +0")
def _():
    need("Friendship")
    s = fresh(hand=[T.id_of("Friendship")], runes=9)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Friendship", u)
    run(s)
    assert combat.might(s, T, u) == 3


@case(9565, "Frigid Touch repeated takes a 2 Might unit to -2")
def _():
    need("Frigid Touch")
    s = fresh(hand=[T.id_of("Frigid Touch")], runes=9)
    u = body(s, 1, base_loc(1), 2)
    cast(s, 0, "Frigid Touch", u, u, repeat=True)
    run(s)
    assert combat.might(s, T, u) == 0 and alive(s, u)
    combat.set_might_mod(s, T, u, 3)
    assert combat.might(s, T, u) == 1, "-2 + 3"


@case(9562, "The Dreaming Tree draws even if the spell is countered")
def _():
    need("The Dreaming Tree", "Discipline", "Defy")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    s.bf_card[0] = T.id_of("The Dreaming Tree")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Discipline", u)
    from rl.engine.state import C_UID
    assert chain_names(s) == ["Discipline", "The Dreaming Tree"], "it triggers on the CHOOSING"
    cast(s, 1, "Defy", int(s.chain[0, C_UID]))
    run(s)
    assert combat.might(s, T, u) == 3 and int(s.n_hand[0]) == 1


@case(9553, "Defy reads Death from Below's printed cost")
def _():
    need("Death from Below", "Defy")
    s = fresh(hand=[T.id_of("Death from Below")], runes=9)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Death from Below", foe)
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1)


@case(9536, "Tideturner's swap to base fails under Minotaur Reckoner")
def _():
    need("Tideturner", "Minotaur Reckoner")
    s = fresh(hand=[T.id_of("Tideturner")], runes=9)
    s.add_permanent(T.id_of("Minotaur Reckoner"), 1, base_loc(1))
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Tideturner", base_loc(0))
    run(s, picking(u))
    assert int(s.perms[u, P_LOC]) == bf_loc(0), "units can't move to base"


@case(9535, "Eclipse then Discipline: 3 - 4 + 2 is 1")
def _():
    need("Eclipse", "Discipline")
    s = fresh(hand=[T.id_of("Eclipse")], runes=9)
    give(s, 0, "Discipline")
    u = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Eclipse", u)
    run(s, picking(accept=False))
    assert combat.might(s, T, u) == 0
    cast(s, 0, "Discipline", u)
    run(s)
    assert combat.might(s, T, u) == 1
