"""RiftJudge batch 17 -- unused questions from 10567-10696."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_EMPOWERED, F_BUFFED, P_ATTACHED_TO, P_MIGHT_MOD
from rl.engine.effects import ABILITIES, pack_trash


def ready_runes(s, seat):
    return int(s.runes_ready[seat].sum())


@case(10695, "Clash of Giants: the units are the damage's source, not you")
def _():
    need("Clash of Giants", "Elder Dragon")
    s = fresh(hand=[T.id_of("Clash of Giants")], runes=12)
    s.add_permanent(T.id_of("Elder Dragon"), 0, base_loc(0))
    a = body(s, 1, base_loc(1), 6)
    b = body(s, 1, base_loc(1), 1)
    cast(s, 0, "Clash of Giants", a, b)
    run(s)
    assert alive(s, a) and int(s.perms[a, P_DMG]) == 1, "not YOUR damage, so not lethal"
    assert not alive(s, b)


@case(10694, "a countered spell gives Diana, No Longer Human no +2")
def _():
    need("Diana, No Longer Human", "Discipline", "Defy")
    s = fresh(hand=[T.id_of("Discipline")])
    give(s, 1, "Defy")
    di = s.add_permanent(T.id_of("Diana, No Longer Human"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert combat.might(s, T, di) == int(T.might[T.id_of("Diana, No Longer Human")])


@case(10688, "Immortal Phoenix from the trash goes to your base, not the battlefield you attack")
def _():
    need("Immortal Phoenix", "Hextech Ray")
    s = fresh(runes=12)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Immortal Phoenix"), 1
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    from rl.engine import combat as C
    C.KILLER[:] = [0, True]
    try:
        rsv.resolve(s, T, V1, SPECS["Hextech Ray"], 0, [u], -1, True)
    finally:
        C.KILLER[:] = [-1, False]
    run(s, picking())
    ph = perm_of(s, "Immortal Phoenix")
    assert ph and int(s.perms[ph[0], P_LOC]) == base_loc(0)


@case(10682, "Svellsongur on Ahri - Alluring: holding scores 1 + 1 + 1")
def _():
    need("Svellsongur", "Ahri - Alluring")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    ah = s.add_permanent(T.id_of("Ahri - Alluring"), 0, bf_loc(0))
    sv = s.add_permanent(T.id_of("Svellsongur"), 0, bf_loc(0))
    s.attach(sv, ah)
    act(s, A.A_END_TURN, None, 1)
    run(s, picking(), stop=lambda s: int(s.active) == 0 and s.phase == MAIN
        and s.n_chain == 0 and s.n_trig == 0)
    assert int(s.points[0]) == 3, int(s.points[0])


@case(10680, "Moonfall pays Deflect for the enemy unit it moves")
def _():
    need("Moonfall", "Vex - Apathetic")
    s = fresh(hand=[T.id_of("Moonfall")], runes=12)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    vex = s.add_permanent(T.id_of("Vex - Apathetic"), 1, base_loc(1))
    before = runes(s, 0)
    cast(s, 0, "Moonfall", bf_loc(0), vex)
    run(s, picking())
    assert before - runes(s, 0) == int(T.power[T.id_of("Moonfall")]) + 1


@case(10678, "Zhonya's Hourglass may be played from hidden with nothing dying")
def _():
    need("Zhonya's Hourglass")
    s = fresh()
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 0, "Zhonya's Hourglass")
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s)
    assert perm_of(s, "Zhonya's Hourglass")


@case(10677, "Beast Below played into Vex - Apathetic is stunned")
def _():
    need("Beast Below", "Vex - Apathetic")
    s = fresh(hand=[T.id_of("Beast Below")], runes=12)
    other = body(s, 0, base_loc(0), 3)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Beast Below", base_loc(0))
    run(s, picks(other, foe))
    bb = perm_of(s, "Beast Below")
    assert bb and s.has_flag(bb[0], F_STUNNED)


@case(10669, "Rengar - Pouncing may be played to the battlefield you are attacking")
def _():
    need("Rengar - Pouncing")
    s = fresh()
    give(s, 0, "Rengar - Pouncing")
    s.runes_ready[0, :] = 9
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    a = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, a)
    assert s.showdown_bf == 0
    pass_priority_to(s, 0)
    act(s, A.A_PLAY, hand_index(s, 0, "Rengar - Pouncing"), 0)
    dests = {x.arg for x in A.legal_actions(s, T, V1, 0)
             if x.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)}
    assert bf_loc(0) in dests, dests


@case(10667, "Sacred Shears' unit returned to hand did not die: no draw")
def _():
    need("Sacred Shears", "Star-Crossed")
    s = fresh(hand=[T.id_of("Star-Crossed")])
    u = body(s, 0, base_loc(0), 3)
    sh = s.add_permanent(T.id_of("Sacred Shears"), 0, base_loc(0))
    s.attach(sh, u)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Star-Crossed", u, foe)
    run(s)
    assert int(s.n_hand[0]) == 1, "the unit itself, and no Deathknell draw"


@case(10666, "Lillia moving off a battlefield leaves your hidden card alone")
def _():
    need("Lillia - Fae Fawn", "Ride The Wind")
    s = fresh()
    s.bf_ctrl[0] = 0
    li = s.add_permanent(T.id_of("Lillia - Fae Fawn"), 0, bf_loc(0))
    fd = hidden_at(s, 0, 0, "Back Off")
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [li, base_loc(0)], -1, True)
    run(s)
    assert int(s.fd_card[fd]) == T.id_of("Back Off") and int(s.bf_ctrl[0]) == 0


@case(10663, "Mask of Foresight does not choose: Irelia gets its +1 only")
def _():
    need("Mask of Foresight", "Irelia, Fervent")
    s = fresh()
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0), ready=True)
    s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    attack(s, 0, 0, ir)
    run(s, stop=lambda s: s.n_chain == 0 and s.n_trig == 0 and s.showdown_bf >= 0
        and int(s.priority) >= 0)
    assert combat.might(s, T, ir) == int(T.might[T.id_of("Irelia, Fervent")]) + 1


@case(10656, "Flurry of Feathers' Birds cannot be played to the battlefield you attack")
def _():
    need("Flurry of Feathers")
    s = fresh(hand=[T.id_of("Flurry of Feathers")])
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    a = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, a)
    pass_priority_to(s, 0)
    act(s, A.A_PLAY, hand_index(s, 0, "Flurry of Feathers"), 0)
    choose(s, 1)                                       # mode: the Birds
    offered = {x.arg for x in A.legal_actions(s, T, V1, 0) if x.kind == A.A_TARGET}
    assert bf_loc(0) not in offered, offered


@case(10655, "Thrill of the Hunt on your own lone unit at your own battlefield: no point")
def _():
    need("Thrill of the Hunt", "Discipline")
    s = fresh(seat=1, hand=[T.id_of("Discipline")])
    give(s, 0, "Thrill of the Hunt")
    s.runes_ready[0, :] = 6
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Discipline", theirs)
    cast(s, 0, "Thrill of the Hunt", u, bf_loc(0))
    run(s, picking())
    assert int(s.points[0]) == 0


@case(10653, "Drag Under costs 2 less from the trash")
def _():
    need("Drag Under")
    s = fresh()
    from rl.engine.cost import effective_energy, flow_energy
    hand_cost = effective_energy(s, T, 0, T.id_of("Drag Under"))
    assert hand_cost == int(T.energy[T.id_of("Drag Under")])
    s.trash[0, 0], s.n_trash[0] = T.id_of("Drag Under"), 1
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    s.runes_ready[0, :] = 12
    plays = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_FLOW]
    if plays:
        before = ready_runes(s, 0)
        A.apply(s, T, V1, plays[0])
        run(s, picking())
        assert before - ready_runes(s, 0) <= hand_cost - 2 + int(T.power[T.id_of("Drag Under")])


@case(10650, "Friendship gives +1 per distinct animal tag, not per unit")
def _():
    need("Friendship")
    s = fresh(hand=[T.id_of("Friendship")])
    u = body(s, 0, base_loc(0), 3)
    for n in ("Loyal Poro", "Loyal Poro", "Loyal Poro", "Fretful Feline"):
        s.add_permanent(T.id_of(n), 0, base_loc(0))
    cast(s, 0, "Friendship", u)
    run(s)
    assert combat.might(s, T, u) == 3 + 2, combat.might(s, T, u)


@case(10644, "Warwick - Hunter's attack trigger goes on the Chain with nothing damaged")
def _():
    need("Warwick - Hunter")
    s = fresh()
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    w = s.add_permanent(T.id_of("Warwick - Hunter"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, w)
    assert "Warwick - Hunter" in chain_names(s) or s.n_trig


@case(10638, "Soraka dying with the others still saves a smaller ally")
def _():
    need("Soraka - Wanderer", "Unchecked Power")
    s = fresh(seat=1, hand=[T.id_of("Unchecked Power")], runes=12)
    s.bf_ctrl[0] = 0
    so = s.add_permanent(T.id_of("Soraka - Wanderer"), 0, bf_loc(0))
    small = body(s, 0, bf_loc(0), 2)
    cast(s, 1, "Unchecked Power")
    run(s, picking(accept=False))
    assert not alive(s, so) and alive(s, small) and int(s.perms[small, P_LOC]) == base_loc(0)


@case(10634, "Ruined Rex's Deathknell killing the last defender: no conquer")
def _():
    need("Ruined Rex")
    s = fresh()
    s.bf_ctrl[0] = 1
    rex = s.add_permanent(T.id_of("Ruined Rex"), 1, bf_loc(0))
    a = body(s, 0, base_loc(0), 6, ready=True)
    attack(s, 0, 0, a)
    fight(s)
    run(s, picking(a))
    assert not alive(s, rex) and not alive(s, a) and int(s.points[0]) == 0


@case(10629, "a unit saved by Zhonya's Hourglass never died: no Deathknell")
def _():
    need("Zhonya's Hourglass", "Lonely Poro", "Drag Under")
    s = fresh()
    s.bf_ctrl[0] = 0
    lp = s.add_permanent(T.id_of("Lonely Poro"), 0, bf_loc(0))
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    s.death_guard[0] = z
    rsv.resolve(s, T, V1, SPECS["Drag Under"], 1, [lp], -1, True)
    run(s)
    assert alive(s, lp) and int(s.n_hand[0]) == 0, "no Deathknell draw"


@case(10616, "Rengar - Pouncing cannot be played to a battlefield you are not attacking")
def _():
    need("Rengar - Pouncing", "Discipline")
    s = fresh(seat=1, hand=[T.id_of("Discipline")])
    give(s, 0, "Rengar - Pouncing")
    s.runes_ready[0, :] = 9
    u = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Discipline", u)
    pass_priority_to(s, 0)
    if "Rengar - Pouncing" in hand_plays(s, 0):
        act(s, A.A_PLAY, hand_index(s, 0, "Rengar - Pouncing"), 0)
        dests = {x.arg for x in A.legal_actions(s, T, V1, 0)
                 if x.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)}
        assert dests == {base_loc(0)}, dests


@case(10614, "Draven - Audacious dying in combat gives the 8th point: no Final Point gate")
def _():
    need("Draven - Audacious")
    s = fresh()
    s.points[0] = 7
    s.bf_ctrl[0] = 1
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 1, bf_loc(0))
    a = body(s, 0, base_loc(0), 9, ready=True)
    attack(s, 0, 0, a)
    fight(s)
    run(s, picking())
    assert not alive(s, dr)
    assert int(s.points[0]) >= 8, int(s.points[0])


@case(10608, "an attached Spinning Axe does not die to its own printed Temporary")
def _():
    need("Spinning Axe")
    s = fresh(seat=1)
    u = body(s, 0, base_loc(0), 3)
    ax = s.add_permanent(T.id_of("Spinning Axe"), 0, base_loc(0))
    s.attach(ax, u)
    act(s, A.A_END_TURN, None, 1)
    run(s, picking(), stop=lambda s: int(s.active) == 0 and s.phase == MAIN
        and s.n_chain == 0 and s.n_trig == 0)
    assert perm_of(s, "Spinning Axe")


@case(10599, "Frozen Fortress kills a 1 Might unit at the start of a Beginning Phase")
def _():
    need("Frozen Fortress", "Determined Sentry")
    s = fresh(seat=1)
    s.bf_card[0] = T.id_of("Frozen Fortress")
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Determined Sentry"), 0, bf_loc(0))   # printed 1 Might
    act(s, A.A_END_TURN, None, 1)
    run(s, picking(), stop=lambda s: int(s.active) == 0 and s.phase == MAIN
        and s.n_chain == 0 and s.n_trig == 0)
    assert not perm_of(s, "Determined Sentry")


@case(10596, "Frozen Fortress' 1 damage under Imperial Decree kills")
def _():
    need("Frozen Fortress", "Imperial Decree")
    from rl.engine.effects import BF_ABILITIES, TR_BEGINNING
    from rl.engine.state import bf_src
    s = fresh()
    s.bf_card[0] = T.id_of("Frozen Fortress")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    rsv.resolve(s, T, V1, SPECS["Imperial Decree"], 0, [], -1, True)
    # the Fortress' own trigger, this turn, while the Decree is live
    chain_mod.queue(s, TR_BEGINNING, bf_src(0), bf_loc(0), who=0)
    run(s)
    assert not alive(s, u)


@case(10594, "the Baron Pit stays after Baron Nashor dies")
def _():
    need("Baron Nashor")
    s = fresh(hand=[T.id_of("Baron Nashor")], runes=12)
    cast(s, 0, "Baron Nashor", base_loc(0))
    run(s)
    bn = perm_of(s, "Baron Nashor")[0]
    pit = [i for i in range(len(s.bf_card)) if int(s.bf_card[i]) == T.id_of("Baron Pit")]
    assert pit, "the Pit was added"
    combat.destroy(s, T, bn)
    run(s)
    assert int(s.bf_card[pit[0]]) == T.id_of("Baron Pit")


@case(10590, "a conquer with no defenders left recalls nobody, stunned or not")
def _():
    need("Back Off")
    s = fresh()
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 1)
    a1 = body(s, 0, base_loc(0), 3, ready=True)
    a2 = body(s, 0, base_loc(0), 3, ready=True)
    s.stun(a1)
    attack(s, 0, 0, a1, a2)
    fight(s)
    run(s)
    assert not alive(s, d)
    assert int(s.perms[a1, P_LOC]) == bf_loc(0) and int(s.perms[a2, P_LOC]) == bf_loc(0)


@case(10578, "after the combat ends nobody is defending: Forbidding Waste stops applying")
def _():
    need("Forbidding Waste")
    s = fresh()
    give(s, 1, "Smoke Screen")                          # keeps the showdown open
    s.bf_card[0] = T.id_of("Forbidding Waste")
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 5)
    a = body(s, 0, base_loc(0), 1, ready=True)
    attack(s, 0, 0, a)
    assert s.showdown_bf == 0 and combat.might(s, T, d) == 3
    fight(s)
    run(s)
    assert alive(s, d) and combat.might(s, T, d) == 5


@case(10575, "Darius - Trifarian entering after the second card was played does not trigger")
def _():
    need("Darius - Trifarian", "The Harrowing", "Discipline")
    s = fresh(hand=[VANILLA, T.id_of("Discipline"), T.id_of("The Harrowing")], runes=12)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Darius - Trifarian"), 1
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Shipyard Skulker", base_loc(0))
    run(s)
    cast(s, 0, "Discipline", u)                         # the second card
    run(s)
    cast(s, 0, "The Harrowing", pack_trash(0, T.id_of("Darius - Trifarian")), base_loc(0))
    run(s)
    d = perm_of(s, "Darius - Trifarian")
    assert d and int(s.perms[d[0], P_READY]) == 0 and combat.might(s, T, d[0]) == 5


@case(10574, "Lux - Lady of Luminosity reads the printed cost: a Repeated 4 does not draw")
def _():
    need("Lux - Lady of Luminosity", "Rocket Barrage")
    s = fresh(hand=[T.id_of("Rocket Barrage")], runes=12)
    s.legend[0], s.legend_ready[0] = T.id_of("Lux - Lady of Luminosity"), 1
    foe = body(s, 1, base_loc(1), 9)
    act(s, A.A_PLAY_REPEAT, 0, 0)
    for _ in range(6):
        legal = A.legal_actions(s, T, V1, 0)
        pick = next((a for a in legal if a.kind in _CHOICE_KINDS
                     and a.arg in (0, foe)), None)
        if pick is None:
            break
        A.apply(s, T, V1, pick)
    run(s)
    assert int(s.n_hand[0]) == 0, "printed 4 is under Lux's 5"
