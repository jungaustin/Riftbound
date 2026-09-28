"""RiftJudge batch 19 -- unused questions from 10294-10436."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_EMPOWERED, F_BUFFED, P_ATTACHED_TO, P_MIGHT_MOD
from rl.engine.effects import ABILITIES, pack_trash


def ready_runes(s, seat):
    return int(s.runes_ready[seat].sum())


@case(10432, "Convergent Mutation resolves fully before Ravenbloom Student's +1")
def _():
    need("Convergent Mutation", "Ravenbloom Student")
    s = fresh(hand=[T.id_of("Convergent Mutation")])
    st = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0))
    big = body(s, 0, base_loc(0), 6)
    cast(s, 0, "Convergent Mutation", st, big)
    run(s)
    assert combat.might(s, T, st) == 7, combat.might(s, T, st)


@case(10427, "a hidden Zhonya's you never flipped is trashed with the battlefield")
def _():
    need("Zhonya's Hourglass", "Hidden Blade")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    fd = hidden_at(s, 0, 0, "Zhonya's Hourglass")
    rsv.resolve(s, T, V1, SPECS["Hidden Blade"], 1, [u], -1, True)
    run(s, picking(accept=False))
    assert not alive(s, u) and int(s.fd_card[fd]) < 0 and int(s.bf_ctrl[0]) < 0


@case(10422, "Falling Star's damage plus a Stupefy kills the unit")
def _():
    need("Falling Star", "Stupefy")
    s = fresh()
    u = body(s, 1, base_loc(1), 4)
    rsv.resolve(s, T, V1, SPECS["Falling Star"], 0, [u, -1], -1, True)
    assert alive(s, u) and int(s.perms[u, P_DMG]) == 3
    rsv.resolve(s, T, V1, SPECS["Stupefy"], 0, [u], -1, True)
    run(s)
    assert not alive(s, u)


@case(10420, "Gust in answer to Stellacorn Herder's move trigger: the draw still happens")
def _():
    need("Stellacorn Herder", "Gust", "Ride The Wind")
    s = fresh()
    h = s.add_permanent(T.id_of("Stellacorn Herder"), 0, base_loc(0))
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [h, bf_loc(0)], -1, True)
    A._settle(s, T, V1)
    assert "Stellacorn Herder" in chain_names(s), "a window opened before it resolves"
    combat.return_to_hand(s, T, h)
    run(s)
    # the trigger names nothing about its source, so it resolves anyway
    assert int(s.n_hand[0]) == 2, int(s.n_hand[0])


@case(10416, "with Elder Dragon, 1 combat damage each kills every defender")
def _():
    need("Elder Dragon")
    s = fresh()
    s.add_permanent(T.id_of("Elder Dragon"), 0, base_loc(0))
    s.bf_ctrl[0] = 1
    foes = [body(s, 1, bf_loc(0), 6) for _ in range(3)]
    a = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, a)
    fight(s)
    run(s)
    assert not any(alive(s, f) for f in foes)


@case(10414, "Frigid Jewel does not count the turn's own draw")
def _():
    need("Frigid Jewel")
    s = fresh()
    s.add_permanent(T.id_of("Frigid Jewel"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    phases.draw_for(s, 0, 1)
    A._settle(s, T, V1)
    assert s.n_chain == 0 and s.n_trig == 0, "one draw is not the second"
    phases.draw_for(s, 0, 1)
    run(s, picking(u))
    assert combat.might(s, T, u) == 5


@case(10403, "Star Spring is not triggered by a token unit")
def _():
    need("Star Spring", "Sprite Call")
    s = fresh()
    s.bf_card[0] = T.id_of("Star Spring")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Sprite Call"], 0, [bf_loc(0)], -1, True)
    A._settle(s, T, V1)
    assert "Star Spring" not in chain_names(s) and s.pend_may < 0


@case(10402, "Cull the Weak is your spell: killing an enemy unit wakes Immortal Phoenix")
def _():
    need("Cull the Weak", "Immortal Phoenix")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=9)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Immortal Phoenix"), 1
    mine = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Cull the Weak")
    run(s, picks(mine, theirs))
    assert not alive(s, theirs)
    assert perm_of(s, "Immortal Phoenix") or int(s.n_trash[0]) == 0


@case(10398, "Pack of Wonders may return an equipped gear")
def _():
    need("Pack of Wonders", "B.F. Sword")
    s = fresh()
    p = s.add_permanent(T.id_of("Pack of Wonders"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 3)
    g = s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    s.attach(g, u)
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, 0)                                       # mode: a gear or unit
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert g in offered, offered


@case(10394, "Undertitan's +2 reaches only the units already there")
def _():
    need("Undertitan", "Shipyard Skulker")
    s = fresh(hand=[T.id_of("Undertitan"), VANILLA], runes=12)
    early = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Undertitan", base_loc(0))
    run(s)
    assert combat.might(s, T, early) == 5
    cast(s, 0, "Shipyard Skulker", base_loc(0))
    run(s)
    late = [i for i in units(s, 0) if i not in (early,)
            and T.names[int(s.perms[i, P_CARD])] == "Shipyard Skulker"]
    assert late and combat.might(s, T, late[-1]) == int(T.might[VANILLA])


@case(10391, "Falling Star twice into Guardian Angel: one save, and the unit lives")
def _():
    need("Falling Star", "Guardian Angel")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 0, bf_loc(0))
    s.attach(ga, u)
    rsv.resolve(s, T, V1, SPECS["Falling Star"], 1, [u, u], -1, True)
    run(s)
    assert alive(s, u) and not alive(s, ga) and int(s.perms[u, P_LOC]) == base_loc(0)


@case(10388, "a Reflection of Darius - Trifarian is no card played: it enters exhausted")
def _():
    need("Mirror Image", "Darius - Trifarian")
    s = fresh(hand=[T.id_of("Mirror Image")], runes=9)
    d = s.add_permanent(T.id_of("Darius - Trifarian"), 1, base_loc(1))
    cast(s, 0, "Mirror Image", d)
    run(s)
    tok = tokens(s, 0)
    assert tok and int(s.perms[tok[0], P_READY]) == 1, "Mirror Image plays it READY"
    assert combat.might(s, T, tok[0]) == int(T.might[T.id_of("Darius - Trifarian")])


@case(10380, "[Assault] does nothing moving onto an open battlefield")
def _():
    need("Inferna")
    s = fresh()
    inf = s.add_permanent(T.id_of("Inferna"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, inf)
    assert combat.might(s, T, inf) == int(T.might[T.id_of("Inferna")])


@case(10378, "Blue Sentinel doubles hold EFFECTS, not the hold's point")
def _():
    need("Blue Sentinel")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Blue Sentinel"), 0, bf_loc(0))
    act(s, A.A_END_TURN, None, 1)
    run(s, picking(), stop=lambda s: int(s.active) == 0 and s.phase == MAIN
        and s.n_chain == 0 and s.n_trig == 0)
    assert int(s.points[0]) == 1, int(s.points[0])


@case(10370, "Stare Down may be played with no enemy units at the battlefield")
def _():
    need("Stare Down")
    s = fresh(hand=[T.id_of("Stare Down")])
    body(s, 0, base_loc(0), 3)
    assert "Stare Down" in hand_plays(s, 0)
    cast(s, 0, "Stare Down", units(s, 0)[0], bf_loc(0))
    run(s)
    assert int(s.xp[0]) == 1


@case(10365, "Salvage still kills the gear after its unit was sacrificed")
def _():
    need("Salvage")
    s = fresh(hand=[T.id_of("Salvage")])
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    g = s.add_permanent(T.id_of("B.F. Sword"), 1, bf_loc(0))
    s.attach(g, u)
    cast(s, 0, "Salvage", g)
    combat.destroy(s, T, u)
    run(s)
    assert not alive(s, g) and int(s.n_hand[0]) == 1


@case(10364, "keeping control through a swap of units is no Conquer")
def _():
    need("Windsinger", "Sprite Call")
    s = fresh(hand=[T.id_of("Windsinger")], runes=9)
    s.bf_ctrl[0] = 1
    rsv.resolve(s, T, V1, SPECS["Sprite Call"], 1, [bf_loc(0)], -1, True)
    spr = tokens(s, 1)[0]
    fd = hidden_at(s, 1, 0, "Sprite Call")
    cast(s, 0, "Windsinger", base_loc(0))
    run(s, picking(spr))
    assert not alive(s, spr)
    pts = int(s.points[1])
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(accept=False), stop=lambda s: int(s.active) == 1)
    assert int(s.points[1]) >= pts


@case(10361, "playing Undertitan from hand reveals nothing: no Energy")
def _():
    need("Undertitan")
    s = fresh(hand=[T.id_of("Undertitan")], runes=12)
    cast(s, 0, "Undertitan", base_loc(0))
    run(s)
    assert int(s.pool_energy[0]) == 0


@case(10355, "Tianna Crownguard stops points, not the hold trigger")
def _():
    need("Tianna Crownguard", "Blue Sentinel")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Blue Sentinel"), 0, bf_loc(0))
    s.add_permanent(T.id_of("Tianna Crownguard"), 1, bf_loc(1))
    s.bf_ctrl[1] = 1
    act(s, A.A_END_TURN, None, 1)
    run(s, picking(), stop=lambda s: int(s.active) == 0 and s.phase == MAIN
        and s.n_chain == 0 and s.n_trig == 0)
    assert int(s.points[0]) == 0, "no points while Tianna stands"
    assert int(s.pending_add_any[0]) or int(s.pool_power[0].sum()), "the hold effect still fired"


@case(10345, "Baited Hook's target killed in answer: nothing is found")
def _():
    need("Baited Hook", "Hidden Blade")
    s = fresh()
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    u = body(s, 0, bf_loc(0), 3)
    s.deck[0, :5] = [VANILLA] * 5
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, u)
    rsv.resolve(s, T, V1, SPECS["Hidden Blade"], 1, [u], -1, True)
    run(s, picking(0))
    assert not units(s, 0, bf_loc(0)) and not perm_of(s, "Shipyard Skulker")


@case(10334, "Deathgrip's sacrifice happens even when the buff target was Gusted")
def _():
    need("Deathgrip")
    s = fresh(hand=[T.id_of("Deathgrip")])
    kill = body(s, 0, base_loc(0), 3)
    buff = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Deathgrip", kill, buff)
    combat.return_to_hand(s, T, buff)
    run(s)
    assert not alive(s, kill) and int(s.n_hand[0]) == 2


@case(10331, "a stunned unit may still Exhaust for an activated ability")
def _():
    need("Baited Hook", "Lonely Poro")
    s = fresh()
    g = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 3)
    s.stun(g)
    s.deck[0, :5] = [VANILLA] * 5
    assert A.A_ACTIVATE in kinds(s, 0)


@case(10323, "Gust resolves before Punch First: the +5 lands on nothing")
def _():
    need("Gust", "Punch First")
    s = fresh(seat=1, hand=[T.id_of("Punch First")])
    give(s, 0, "Gust")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 2)
    cast(s, 1, "Punch First", u)
    cast(s, 0, "Gust", u)
    run(s)
    assert not alive(s, u) and T.id_of("Shipyard Skulker") in list(s.hand[0, :int(s.n_hand[0])])


@case(10314, "Thrill of the Hunt detaches the equipment")
def _():
    need("Thrill of the Hunt", "B.F. Sword")
    s = fresh(hand=[T.id_of("Thrill of the Hunt")])
    u = body(s, 0, base_loc(0), 3)
    g = s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    s.attach(g, u)
    cast(s, 0, "Thrill of the Hunt", u, bf_loc(0))
    run(s, picking(accept=False))
    assert int(s.perms[g, P_ATTACHED_TO]) < 0 and alive(s, g)


@case(10313, "Grim Apothecary returning a unit leaves its gear behind")
def _():
    need("Grim Apothecary", "B.F. Sword")
    s = fresh(hand=[T.id_of("Grim Apothecary")], runes=9)
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    g = s.add_permanent(T.id_of("B.F. Sword"), 0, bf_loc(0))
    s.attach(g, u)
    cast(s, 0, "Grim Apothecary", bf_loc(0))
    run(s, picking(u))
    assert not alive(s, u) and alive(s, g) and int(s.perms[g, P_ATTACHED_TO]) < 0


@case(10310, "Wages of Pain whose unit was moved home does nothing to it")
def _():
    need("Wages of Pain", "Flash")
    s = fresh(hand=[T.id_of("Wages of Pain")], runes=9)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Wages of Pain", u)
    rsv.resolve(s, T, V1, SPECS["Flash"], 1, [u, -1], -1, True)
    run(s, picking())
    assert int(s.perms[u, P_DMG]) == 0 and tokens(s, 0), "the Gold token still arrives"


@case(10305, "Facebreaker chooses both units: Not So Fast can answer it")
def _():
    need("Facebreaker", "Not So Fast")
    s = fresh(hand=[T.id_of("Facebreaker")])
    give(s, 1, "Not So Fast")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Facebreaker", mine, theirs)
    pass_priority_to(s, 1)
    assert "Not So Fast" in hand_plays(s, 1)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert not s.has_flag(mine, F_STUNNED) and not s.has_flag(theirs, F_STUNNED)


@case(10302, "Arcane Shift's damage lands before the replayed unit's play trigger")
def _():
    need("Arcane Shift", "Scuttle Crab")
    s = fresh(hand=[T.id_of("Arcane Shift")], runes=9)
    s.bf_ctrl[0] = 1
    crab = s.add_permanent(T.id_of("Scuttle Crab"), 0, base_loc(0))
    foe = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Arcane Shift", crab, foe)
    order = []

    def watch(s):
        if int(s.perms[foe, P_DMG]) and "damage" not in order:
            order.append("damage")
        if int(s.n_hand[0]) and "draw" not in order:
            order.append("draw")
        return False
    run(s, picking(), stop=watch)
    assert order and order[0] == "damage", order


@case(10298, "Sacrifice killing Stupefy's target: Stupefy still draws")
def _():
    need("Sacrifice", "Stupefy")
    s = fresh(seat=1, hand=[T.id_of("Stupefy")])
    give(s, 0, "Sacrifice")
    rune_deck(s)
    u = body(s, 0, base_loc(0), 5)
    cast(s, 1, "Stupefy", u)
    cast(s, 0, "Sacrifice", u)
    run(s)
    assert not alive(s, u) and int(s.n_hand[1]) == 1, "Stupefy's own draw"


@case(10294, "Mask of Foresight does nothing in a non-combat Showdown")
def _():
    need("Mask of Foresight")
    s = fresh()
    s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    assert combat.might(s, T, u) == 3, combat.might(s, T, u)
