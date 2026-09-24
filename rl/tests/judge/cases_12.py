"""RiftJudge batch 12 -- unused questions from 11501-11769."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_EMPOWERED, P_ATTACHED_TO, P_MIGHT_MOD, P_EMPOWER
from rl.engine.effects import ABILITIES, pack_trash


def ready_runes(s, seat):
    return int(s.runes_ready[seat].sum())


@case(11768, "Renekton, Brute already at 10+ never 'becomes' 10 or more")
def _():
    need("Renekton, Brute", "Stupefy")
    s = fresh()
    r = s.add_permanent(T.id_of("Renekton, Brute"), 0, base_loc(0))
    s.base_might_ply[r], s.base_might_val[r] = int(s.ply), 11
    A._settle(s, T, V1)
    run(s)
    s.clear_flag(r, F_EMPOWERED)
    s.perms[r, P_EMPOWER] = 0
    rsv.resolve(s, T, V1, SPECS["Stupefy"], 1, [r], -1, True)
    run(s)
    act(s, A.A_ACTIVATE, None, 0)
    run(s)
    assert combat.might(s, T, r) == 11 and s.empower_count(r) == 0
    # ...while climbing from 9 to 10 IS becoming 10 or more.
    s2 = fresh()
    r2 = s2.add_permanent(T.id_of("Renekton, Brute"), 0, base_loc(0))
    s2.base_might_ply[r2], s2.base_might_val[r2] = int(s2.ply), 9
    run(s2)
    act(s2, A.A_ACTIVATE, None, 0)
    run(s2)
    assert combat.might(s2, T, r2) == 10 and s2.empower_count(r2) == 1


@case(11758, "Back Off on an already stunned empowered Gangplank: no stun, so no +3")
def _():
    need("Back Off", "Gangplank, Naval")
    s = fresh(hand=[T.id_of("Back Off")])
    gp = s.add_permanent(T.id_of("Gangplank, Naval"), 0, base_loc(0))
    s.set_flag(gp, F_EMPOWERED)
    s.stun(gp)
    cast(s, 0, "Back Off", gp)
    run(s)
    assert combat.might(s, T, gp) == 6


@case(11757, "Switcheroo on an empowered Gangplank: his decrease becomes +3")
def _():
    need("Switcheroo", "Gangplank, Naval")
    s = fresh(seat=1)
    gp = s.add_permanent(T.id_of("Gangplank, Naval"), 0, bf_loc(0))
    s.set_flag(gp, F_EMPOWERED)
    small = body(s, 1, bf_loc(0), 2)
    rsv.resolve(s, T, V1, SPECS["Switcheroo"], 1, [small, gp], -1, True)
    assert combat.might(s, T, small) == 6 and combat.might(s, T, gp) == 9, (
        combat.might(s, T, small), combat.might(s, T, gp))


@case(11749, "Hwei - Brooding Painter discarding Patched Porobot gets both bonuses")
def _():
    need("Hwei - Brooding Painter", "Patched Porobot")
    s = fresh(hand=[T.id_of("Patched Porobot")])
    s.deck[0, :3] = [VANILLA] * 3
    hw = s.add_permanent(T.id_of("Hwei - Brooding Painter"), 0, base_loc(0))
    s.runes_ready[0, :] = 0
    s.runes_spent[0, 0] = 2
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [hw, bf_loc(0)], -1, True)
    run(s, picks(0))                                   # discard the Porobot
    assert combat.might(s, T, hw) == 8 and int(s.runes_ready[0].sum()) == 2, (
        combat.might(s, T, hw), int(s.runes_ready[0].sum()))


@case(11743, "Rebuttal against an empowered Mel's spell, not paid: the counter fails")
def _():
    need("Rebuttal", "Mel, Newly Awakened", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")])
    give(s, 1, "Rebuttal")
    mel = s.add_permanent(T.id_of("Mel, Newly Awakened"), 0, base_loc(0))
    s.set_flag(mel, F_EMPOWERED)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Rebuttal", top_uid(s))
    run(s, picking(accept=False))
    assert combat.might(s, T, u) == 5


@case(11741, "Stupefy with an empowered Mel: -2, still to a minimum of 1")
def _():
    need("Stupefy", "Mel, Newly Awakened")
    s = fresh()
    mel = s.add_permanent(T.id_of("Mel, Newly Awakened"), 0, base_loc(0))
    s.set_flag(mel, F_EMPOWERED)
    two = body(s, 1, base_loc(1), 2)
    five = body(s, 1, base_loc(1), 5)
    rsv.resolve(s, T, V1, SPECS["Stupefy"], 0, [two], -1, True)
    rsv.resolve(s, T, V1, SPECS["Stupefy"], 0, [five], -1, True)
    assert combat.might(s, T, two) == 1 and combat.might(s, T, five) == 3


@case(11733, "Irresistible Faefolk Gusted in answer: the enemy unit still moves there")
def _():
    need("Irresistible Faefolk", "Gust")
    s = fresh()
    ff = s.add_permanent(T.id_of("Irresistible Faefolk"), 0, base_loc(0))
    foe = body(s, 1, base_loc(1), 3)
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [ff, bf_loc(0)], -1, True)
    run(s, picking(foe), stop=lambda s: s.n_chain and chain_names(s)[-1] == "Irresistible Faefolk"
        and s.pend_slot < 0 and s.pend_may < 0)
    combat.return_to_hand(s, T, ff)
    run(s, picking(foe), stop=lambda s: s.n_chain == 0)
    assert int(s.perms[foe, P_LOC]) == bf_loc(0)


@case(11723, "a Defy that counters nothing (empowered Mel) still triggers Abandoned Hall")
def _():
    need("Defy", "Mel, Newly Awakened", "Abandoned Hall")
    s = fresh(seat=1, hand=[T.id_of("Discipline")])
    give(s, 0, "Defy")
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    mel = s.add_permanent(T.id_of("Mel, Newly Awakened"), 1, base_loc(1))
    s.set_flag(mel, F_EMPOWERED)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Discipline", theirs)
    cast(s, 0, "Defy", top_uid(s))
    run(s, picking(mine))
    assert combat.might(s, T, theirs) == 5 and combat.might(s, T, mine) == 4


@case(11687, "Baited Hook on a lone Lonely Poro: it died alone, so it draws")
def _():
    need("Baited Hook", "Lonely Poro")
    s = fresh()
    s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    lp = s.add_permanent(T.id_of("Lonely Poro"), 0, base_loc(0))
    s.deck[0, :6] = [VANILLA] * 6
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, lp)
    run(s, picking(0))
    assert int(s.n_hand[0]) == 1 and perm_of(s, "Shipyard Skulker")


@case(11684, "Bellows Breath whose targets were split up: one location's units are hit")
def _():
    need("Bellows Breath")
    s = fresh()
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 3)
    b = body(s, 1, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 1, [b, base_loc(1)], -1, True)
    log = rsv.resolve(s, T, V1, SPECS["Bellows Breath"], 0, [a, b, -1], -1, True)
    run(s, picking(bf_loc(0)))
    hit = [int(s.perms[i, P_DMG]) for i in (a, b)]
    assert sorted(hit) == [0, 1], hit


@case(11641, "Tideturner at base swapping with a unit at Vilemaw's Lair: only Tideturner moves")
def _():
    need("Tideturner", "Vilemaw's Lair")
    s = fresh()
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    tt = s.add_permanent(T.id_of("Tideturner"), 0, base_loc(0))
    rsv.resolve(s, T, V1, ABILITIES["Tideturner"][0], 0, [u], -1, False, source=tt)
    assert int(s.perms[u, P_LOC]) == bf_loc(0) and int(s.perms[tt, P_LOC]) == bf_loc(0)


@case(11634, "Falling Star on Vex - Apathetic twice pays Deflect twice")
def _():
    need("Falling Star", "Vex - Apathetic")
    s = fresh(hand=[T.id_of("Falling Star")], runes=12)
    vex = s.add_permanent(T.id_of("Vex - Apathetic"), 1, base_loc(1))
    before = runes(s, 0)
    cast(s, 0, "Falling Star", vex, vex)
    run(s)
    assert before - runes(s, 0) == int(T.power[T.id_of("Falling Star")]) + 2


@case(11629, "Svellsongur on Gearhead does not double the doubling")
def _():
    need("Svellsongur", "Gearhead", "B.F. Sword")
    s = fresh()
    g = s.add_permanent(T.id_of("Gearhead"), 0, base_loc(0))
    sv = s.add_permanent(T.id_of("Svellsongur"), 0, base_loc(0))
    bf = s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    s.attach(sv, g)
    s.attach(bf, g)
    bonus = int(T.might_bonus[T.id_of("B.F. Sword")]) + int(T.might_bonus[T.id_of("Svellsongur")])
    assert combat.might(s, T, g) == 3 + 2 * bonus, (combat.might(s, T, g), bonus)


@case(11624, "Guardian Angel and Svellsongur on a dying unit: only the Angel dies")
def _():
    need("Guardian Angel", "Svellsongur")
    s = fresh()
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 0, bf_loc(0))
    sv = s.add_permanent(T.id_of("Svellsongur"), 0, bf_loc(0))
    s.attach(ga, u)
    s.attach(sv, u)
    rsv.resolve(s, T, V1, SPECS["Hidden Blade"], 1, [u], -1, True)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_LOC]) == base_loc(0)
    assert not alive(s, ga) and alive(s, sv) and int(s.perms[sv, P_ATTACHED_TO]) == u


@case(11622, "Discipline's +2 is still up when Glowstone's end-of-turn 5 lands")
def _():
    need("Discipline", "Glowstone")
    s = fresh()
    s.add_permanent(T.id_of("Glowstone"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 4)
    rsv.resolve(s, T, V1, SPECS["Discipline"], 0, [u], -1, True)
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(), stop=lambda s: int(s.active) == 1)
    assert perm_of(s, "Shipyard Skulker"), "4 + 2 = 6 > 5 at the Ending Step"


@case(11614, "Ride the Wind into Abandoned Hall: the unit gets the Hall's +1")
def _():
    need("Ride The Wind", "Abandoned Hall")
    s = fresh(hand=[T.id_of("Ride The Wind")])
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Ride The Wind", u, bf_loc(0))
    run(s, picking(u))
    assert int(s.perms[u, P_LOC]) == bf_loc(0) and combat.might(s, T, u) == 4


@case(11606, "Thrill of the Hunt: the replayed unit loses its +2 this turn")
def _():
    need("Thrill of the Hunt", "Discipline")
    s = fresh()
    u = body(s, 0, base_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Discipline"], 0, [u], -1, True)
    rsv.resolve(s, T, V1, SPECS["Thrill of the Hunt"], 0, [u, bf_loc(0)], -1, True)
    run(s)
    sk = perm_of(s, "Shipyard Skulker")
    assert sk and combat.might(s, T, sk[0]) == int(T.might[VANILLA])


@case(11593, "a countered Stupefy is not played: Ravenbloom Student gets nothing")
def _():
    need("Ravenbloom Student", "Stupefy", "Defy")
    s = fresh(hand=[T.id_of("Stupefy")])
    give(s, 1, "Defy")
    st = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0))
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Stupefy", foe)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert combat.might(s, T, st) == 2


@case(11592, "Star-Crossed cannot be played with only friendly units")
def _():
    need("Star-Crossed")
    s = fresh(hand=[T.id_of("Star-Crossed")])
    body(s, 0, base_loc(0), 3)
    assert "Star-Crossed" not in hand_plays(s, 0)


@case(11551, "Fiora - Peerless one on one at the attack: an Ambush later does not undo it")
def _():
    need("Fiora - Peerless")
    s = fresh()
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 1)
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, fi)
    run(s, stop=lambda s: s.n_chain and chain_names(s)[-1] == "Fiora - Peerless"
        and s.pend_slot < 0)
    body(s, 1, bf_loc(0), 1)                            # the Ambush arrives
    run(s, stop=lambda s: "Fiora - Peerless" not in chain_names(s))
    assert combat.might(s, T, fi) == 2 * int(T.might[T.id_of("Fiora - Peerless")])


@case(11529, "Void Assault on a unit Vex forbids to move: the enemy half still moves")
def _():
    need("Void Assault", "Vex - Apathetic")
    from rl.engine.state import F_NO_MOVE
    s = fresh(hand=[T.id_of("Void Assault")])
    mine = body(s, 0, base_loc(0), 3)
    s.set_flag(mine, F_NO_MOVE)
    foe = body(s, 1, bf_loc(1), 3)
    s.bf_ctrl[1] = 1
    cast(s, 0, "Void Assault", mine, bf_loc(0), foe, base_loc(1))
    run(s)
    assert int(s.perms[mine, P_LOC]) == base_loc(0) and int(s.perms[foe, P_LOC]) == base_loc(1)


@case(11507, "Switcheroo on two units at equal Might changes nothing")
def _():
    need("Switcheroo")
    s = fresh()
    a = body(s, 0, bf_loc(0), 5)
    b = body(s, 1, bf_loc(0), 5)
    rsv.resolve(s, T, V1, SPECS["Switcheroo"], 0, [a, b], -1, True)
    assert combat.might(s, T, a) == 5 and combat.might(s, T, b) == 5
    assert int(s.perms[a, P_MIGHT_MOD]) == 0 and int(s.perms[b, P_MIGHT_MOD]) == 0
