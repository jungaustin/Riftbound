"""RiftJudge batch 16 -- unused questions from 10697-10853."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_EMPOWERED, F_BUFFED, P_ATTACHED_TO, P_MIGHT_MOD
from rl.engine.effects import ABILITIES, pack_trash


def ready_runes(s, seat):
    return int(s.runes_ready[seat].sum())


@case(10853, "Frigid Touch on a unit already carrying 4 damage kills it")
def _():
    need("Frigid Touch")
    s = fresh(hand=[T.id_of("Frigid Touch")])
    y = body(s, 1, base_loc(1), 5)
    s.perms[y, P_DMG] = 4
    cast(s, 0, "Frigid Touch", y)
    run(s)
    assert not alive(s, y)


@case(10850, "Repulse cannot counter Cull the Weak: it chooses nothing")
def _():
    need("Repulse", "Cull the Weak")
    s = fresh(hand=[T.id_of("Cull the Weak")])
    give(s, 1, "Repulse")
    body(s, 0, base_loc(0), 3)
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Cull the Weak")
    pass_priority_to(s, 1)
    assert "Repulse" not in hand_plays(s, 1)


@case(10849, "Flash moves a ready unit home still ready")
def _():
    need("Flash")
    s = fresh(hand=[T.id_of("Flash")])
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3, ready=True)
    cast(s, 0, "Flash", u, -1)
    run(s)
    assert int(s.perms[u, P_LOC]) == base_loc(0) and int(s.perms[u, P_READY]) == 1


@case(10848, "Death from Below whose target was Gusted: no replay from the trash")
def _():
    need("Death from Below", "Gust")
    s = fresh(hand=[T.id_of("Death from Below")])
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 2)
    cast(s, 0, "Death from Below", u)
    combat.return_to_hand(s, T, u)
    run(s)
    assert A.A_PLAY_FLOW not in kinds(s, 0)


@case(10845, "Not So Fast counters Blitzcrank - Impassive pulling your unit")
def _():
    need("Not So Fast", "Blitzcrank - Impassive")
    s = fresh(hand=[T.id_of("Blitzcrank - Impassive")], runes=9)
    give(s, 1, "Not So Fast")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Blitzcrank - Impassive", bf_loc(0))
    run(s, picks(foe), stop=lambda s: s.n_chain and chain_names(s)[-1] == "Blitzcrank - Impassive"
        and s.pend_slot < 0 and s.pend_may < 0)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert int(s.perms[foe, P_LOC]) == base_loc(1)


@case(10842, "Acceptable Losses can be played with no gear anywhere")
def _():
    need("Acceptable Losses")
    s = fresh(hand=[T.id_of("Acceptable Losses")])
    assert "Acceptable Losses" in hand_plays(s, 0)


@case(10828, "Guards! from hidden plays its Sand Soldier at that battlefield")
def _():
    need("Guards!")
    s = fresh()
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 0, "Guards!")
    act(s, A.A_PLAY_HIDDEN, None, 0)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert offered <= {bf_loc(0)}, offered
    run(s, picking(bf_loc(0), accept=False))
    assert tokens(s, 0, bf_loc(0))


@case(10827, "Galio - Indefatigable adds nothing to his side's combat damage")
def _():
    need("Galio - Indefatigable")
    s = fresh()
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 9)
    g = s.add_permanent(T.id_of("Galio - Indefatigable"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, g)
    fight(s)
    assert alive(s, d) and int(s.perms[d, P_DMG]) == 0


@case(10820, "Scuttle Crab Gusted in answer to its play trigger: still draw 1")
def _():
    need("Scuttle Crab", "Gust")
    s = fresh(hand=[T.id_of("Scuttle Crab")])
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Scuttle Crab", bf_loc(0))
    A._settle(s, T, V1)
    crab = perm_of(s, "Scuttle Crab")[0]
    combat.return_to_hand(s, T, crab)
    run(s)
    assert int(s.n_hand[0]) == 2, "the Crab back in hand, plus the draw"


@case(10818, "Smoke and Mirrors needs two of your units at different locations")
def _():
    need("Smoke and Mirrors")
    s = fresh(hand=[T.id_of("Smoke and Mirrors")])
    body(s, 0, base_loc(0), 3)
    assert "Smoke and Mirrors" not in hand_plays(s, 0)
    body(s, 0, base_loc(0), 3)
    assert "Smoke and Mirrors" not in hand_plays(s, 0), "same location twice is not enough"
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    assert "Smoke and Mirrors" in hand_plays(s, 0)


@case(10816, "Moonfall on a 1 Might unit leaves -1: a +2 afterwards makes it 1")
def _():
    need("Moonfall", "Discipline")
    s = fresh()
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    u = body(s, 1, bf_loc(0), 1)
    rsv.resolve(s, T, V1, SPECS["Moonfall"], 0, [bf_loc(0), -1], -1, True)
    assert combat.might(s, T, u) == 0
    rsv.resolve(s, T, V1, SPECS["Discipline"], 1, [u], -1, True)
    assert combat.might(s, T, u) == 1


@case(10811, "Hard Bargain cannot be played with no spell on the Chain")
def _():
    need("Hard Bargain")
    s = fresh(hand=[T.id_of("Hard Bargain")])
    assert "Hard Bargain" not in hand_plays(s, 0)


@case(10805, "Edge of Night from hidden attaches for free to a unit there")
def _():
    need("Edge of Night")
    s = fresh()
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 0, "Edge of Night")
    before = runes(s, 0), ready_runes(s, 0)
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(u))
    g = perm_of(s, "Edge of Night")
    assert g and int(s.perms[g[0], P_ATTACHED_TO]) == u
    assert (runes(s, 0), ready_runes(s, 0)) == before


@case(10792, "Thrill of the Hunt's replayed unit enters exhausted")
def _():
    need("Thrill of the Hunt")
    s = fresh(hand=[T.id_of("Thrill of the Hunt")])
    u = body(s, 0, base_loc(0), 3, ready=True)
    cast(s, 0, "Thrill of the Hunt", u, bf_loc(0))
    run(s, picking(accept=False))
    sk = perm_of(s, "Shipyard Skulker")
    assert sk and int(s.perms[sk[0], P_READY]) == 0


@case(10786, "Janna - Savior's heal in answer to Elder Dragon's trigger saves nothing")
def _():
    need("Janna - Savior", "Elder Dragon")
    s = fresh(hand=[T.id_of("Elder Dragon")], runes=12)
    give(s, 1, "Janna - Savior")
    s.runes_ready[1, :] = 6
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Elder Dragon", base_loc(0))
    run(s, picks(u, -1, -1, -1), stop=lambda s: s.n_chain and chain_names(s)[-1] == "Elder Dragon"
        and s.pend_slot < 0)
    cast(s, 1, "Janna - Savior", bf_loc(0))
    run(s, picking(accept=False))
    assert not alive(s, u)


@case(10783, "Stellacorn Herder returned to hand is not a move: no draw")
def _():
    need("Stellacorn Herder", "Star-Crossed")
    s = fresh(hand=[T.id_of("Star-Crossed")])
    h = s.add_permanent(T.id_of("Stellacorn Herder"), 0, base_loc(0))
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Star-Crossed", h, foe)
    run(s)
    assert int(s.n_hand[0]) == 1 and T.id_of("Stellacorn Herder") in list(s.hand[0, :1])


@case(10763, "Existential Dread cannot choose a unit that moved into an open battlefield")
def _():
    need("Existential Dread")
    s = fresh(seat=1)
    give(s, 0, "Existential Dread")
    a = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, a)
    pass_priority_to(s, 0)
    assert "Existential Dread" not in hand_plays(s, 0)


@case(10762, "Moonfall pulling an enemy into your battlefield: they attack")
def _():
    need("Moonfall")
    s = fresh(hand=[T.id_of("Moonfall")])
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    vi = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Moonfall", bf_loc(0), vi)
    run(s, stop=lambda s: s.showdown_bf >= 0 and s.n_chain == 0)
    assert int(s.attacker) == 1


@case(10760, "a unit played by Rift Herald's Deathknell still pays its Power")
def _():
    need("Rift Herald", "Ruin Runner")
    s = fresh(hand=[T.id_of("Ruin Runner")])
    h = s.add_permanent(T.id_of("Rift Herald"), 0, base_loc(0))
    before = runes(s, 0)
    combat.destroy(s, T, h)
    run(s, picking(0))
    assert perm_of(s, "Ruin Runner")
    assert before - runes(s, 0) == int(T.power[T.id_of("Ruin Runner")])


@case(10758, "Windsinger played to base still gets its play trigger")
def _():
    need("Windsinger")
    s = fresh(hand=[T.id_of("Windsinger")])
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 2)
    cast(s, 0, "Windsinger", base_loc(0))
    run(s, picking(foe))
    assert not alive(s, foe)


@case(10754, "Defy cannot choose Blind Fury: its Power is over the limit")
def _():
    need("Defy", "Blind Fury")
    s = fresh(hand=[T.id_of("Blind Fury")], runes=9)
    give(s, 1, "Defy")
    cast(s, 0, "Blind Fury")
    pass_priority_to(s, 1)
    if int(T.power[T.id_of("Blind Fury")]) > 1:
        assert "Defy" not in hand_plays(s, 1)


@case(10753, "Thrill of the Hunt to the other battlefield does not dodge Unchecked Power")
def _():
    need("Thrill of the Hunt", "Unchecked Power")
    s = fresh(seat=1, hand=[T.id_of("Unchecked Power")], runes=12)
    give(s, 0, "Thrill of the Hunt")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 1, "Unchecked Power")
    cast(s, 0, "Thrill of the Hunt", u, bf_loc(1))
    run(s, picking(accept=False))
    assert not perm_of(s, "Shipyard Skulker")


@case(10743, "a stunned Yasuo - Remorseful still deals his attack damage")
def _():
    need("Yasuo - Remorseful")
    s = fresh()
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 9)
    y = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    s.stun(y)
    attack(s, 0, 0, y)
    run(s, picks(d), stop=lambda s: "Yasuo - Remorseful" not in chain_names(s) and s.n_trig == 0
        and s.pend_slot < 0 and s.showdown_bf >= 0)
    assert int(s.perms[d, P_DMG]) == 6


@case(10741, "Vilemaw does not stop an 8 Might attacker's combat damage")
def _():
    need("Vilemaw")
    s = fresh()
    s.bf_ctrl[0] = 1
    vm = s.add_permanent(T.id_of("Vilemaw"), 1, bf_loc(0))
    a = body(s, 0, base_loc(0), 8, ready=True)
    attack(s, 0, 0, a)
    fight(s)
    assert not alive(s, vm) or int(s.perms[vm, P_DMG]) == 8


@case(10740, "a unit saved by Guardian Angel keeps its Discipline +2")
def _():
    need("Guardian Angel", "Discipline", "Hidden Blade")
    s = fresh()
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 0, bf_loc(0))
    s.attach(ga, u)
    rsv.resolve(s, T, V1, SPECS["Discipline"], 0, [u], -1, True)
    rsv.resolve(s, T, V1, SPECS["Hidden Blade"], 1, [u], -1, True)
    run(s)
    assert alive(s, u) and combat.might(s, T, u) == 5


@case(10732, "Angler Beast reads current Might")
def _():
    need("Angler Beast", "Discipline")
    s = fresh(hand=[T.id_of("Angler Beast")], runes=9)
    pumped = body(s, 1, base_loc(1), 2)
    rsv.resolve(s, T, V1, SPECS["Discipline"], 1, [pumped], -1, True)
    shrunk = body(s, 1, base_loc(1), 3)
    rsv.resolve(s, T, V1, SPECS["Frigid Touch"], 0, [shrunk], -1, True)
    cast(s, 0, "Angler Beast", base_loc(0))
    run(s)
    assert alive(s, pumped) and not alive(s, shrunk)


@case(10727, "Gust whose target was pumped to 4 does nothing")
def _():
    need("Gust")
    s = fresh(hand=[T.id_of("Gust")])
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Gust", u)
    rsv.resolve(s, T, V1, SPECS["Combat Experience"], 1, [u], -1, True)
    run(s)
    assert alive(s, u)


@case(10716, "a Gold token played is not a card: Battering Ram gets no discount")
def _():
    need("Battering Ram")
    s = fresh(hand=[T.id_of("Battering Ram")])
    from rl.engine.cost import effective_energy
    base = effective_energy(s, T, 0, T.id_of("Battering Ram"))
    rsv.resolve(s, T, V1, ABILITIES["Plundering Poro"][0], 0, [], -1, False,
                source=s.add_permanent(T.id_of("Plundering Poro"), 0, base_loc(0)))
    assert tokens(s, 0) and effective_energy(s, T, 0, T.id_of("Battering Ram")) == base


@case(10698, "Renata Glasc - Industrialist makes a Reflection enter ready")
def _():
    need("Renata Glasc - Industrialist", "Sprite Call")
    s = fresh()
    s.add_permanent(T.id_of("Renata Glasc - Industrialist"), 0, base_loc(0))
    rsv.resolve(s, T, V1, SPECS["Guards!"], 0, [base_loc(0)], -1, True)
    run(s, picking(accept=False))
    assert tokens(s, 0) and int(s.perms[tokens(s, 0)[0], P_READY]) == 1
