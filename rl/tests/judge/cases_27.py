"""RiftJudge batch 27 -- unused questions from 9737-9812."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_NO_MOVE, P_ATTACHED_TO
from rl.engine.effects import ABILITIES, pack_trash


@case(9812, "Ruin Runner's protection does not cover gear attached to it")
def _():
    need("Ruin Runner", "Salvage", "Spinning Axe")
    s = fresh(hand=[T.id_of("Salvage")], runes=9)
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1))
    ax = s.add_permanent(T.id_of("Spinning Axe"), 1, base_loc(1))
    s.attach(ax, rr)
    act(s, A.A_PLAY, hand_index(s, 0, "Salvage"), 0)
    assert ax in targets_offered(s, 0)
    choose(s, ax)
    run(s)
    assert not alive(s, ax) and alive(s, rr)


@case(9808, "Forbidding Waste is not a choice, so [Deflect] never taxes it")
def _():
    need("Forbidding Waste", "Vex - Apathetic")
    s = fresh(seat=1)
    s.bf_card[0] = T.id_of("Forbidding Waste")
    s.bf_ctrl[0] = 0
    vx = s.add_permanent(T.id_of("Vex - Apathetic"), 0, bf_loc(0))
    give(s, 0, "Smoke Screen")
    s.runes_ready[0, :] = 6
    a = body(s, 1, base_loc(1), 1, ready=True)
    attack(s, 1, 0, a)
    run(s, stop=lambda s: bool(s.showdown_combat))
    assert combat.might(s, T, vx) == 2, combat.might(s, T, vx)


@case(9804, "after a showdown chain resolves, focus passes on")
def _():
    need("Counter Strike")
    s = fresh(hand=[T.id_of("Counter Strike")], runes=9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 6
    s.bf_ctrl[0] = 1
    a = body(s, 0, base_loc(0), 3, ready=True)
    body(s, 1, bf_loc(0), 3)
    attack(s, 0, 0, a)
    assert A.acting_seat(s) == 0, "the attacker has focus first"
    cast(s, 0, "Counter Strike", a)
    run(s, picking(accept=False), stop=lambda s: s.n_chain == 0 and s.n_trig == 0)
    assert int(s.showdown_bf) == 0 and A.acting_seat(s) == 1, A.acting_seat(s)


@case(9798, "Not So Fast on Overzealous Fan's trigger: the Fan still died")
def _():
    need("Not So Fast", "Overzealous Fan")
    s = fresh(runes=9)
    give(s, 0, "Not So Fast")
    s.bf_ctrl[0] = 1
    fan = s.add_permanent(T.id_of("Overzealous Fan"), 1, bf_loc(0))
    a = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, a)
    act(s, A.A_ACCEPT, None, 1)
    assert not alive(s, fan), "killing itself was the cost, paid now"
    choose(s, a)
    cast(s, 0, "Not So Fast", top_uid(s))
    run(s)
    assert int(s.perms[a, P_LOC]) == bf_loc(0), "the move was countered"


@case(9789, "Imperial Decree kills the moment a unit takes damage")
def _():
    need("Imperial Decree", "Bellows Breath")
    s = fresh(hand=[T.id_of("Imperial Decree")], runes=9)
    u = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Imperial Decree")
    run(s)
    rsv.resolve(s, T, V1, SPECS["Bellows Breath"], 0, [u, -1, -1], -1, True)
    run(s)
    assert not alive(s, u)


@case(9788, "a hidden Wages of Pain can only reach its own battlefield")
def _():
    need("Wages of Pain")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 0
    hidden_at(s, 0, 0, "Wages of Pain")
    s.bf_ctrl[1] = 1
    here = s.add_permanent(T.id_of("Mindsplitter"), 0, bf_loc(0))
    there = body(s, 1, bf_loc(1), 3)
    act(s, A.A_PLAY_HIDDEN, None, 0)
    off = targets_offered(s, 0)
    assert here in off and there not in off, off


@case(9783, "Glasc Mixologist may revive a unit that died with it")
def _():
    need("Glasc Mixologist", "Determined Sentry")
    s = fresh()
    g = s.add_permanent(T.id_of("Glasc Mixologist"), 0, base_loc(0))
    ds = s.add_permanent(T.id_of("Determined Sentry"), 0, base_loc(0))
    combat.RESOLVING[0] += 1
    try:
        combat.destroy(s, T, g)
        combat.destroy(s, T, ds)
    finally:
        combat.RESOLVING[0] -= 1
    run(s, picks(pack_trash(0, T.id_of("Determined Sentry")), base_loc(0)))
    assert perm_of(s, "Determined Sentry")


@case(9780, "Undying Loyalty costs 2 less when it chooses a Poro")
def _():
    need("Undying Loyalty", "Lonely Poro")
    s = fresh(hand=[T.id_of("Undying Loyalty")])
    s.trash[0, 0], s.n_trash[0] = T.id_of("Lonely Poro"), 1
    dom = int(T.domain_mask[T.id_of("Undying Loyalty")]).bit_length() - 1
    s.runes_ready[0, :] = 0
    s.runes_ready[0, dom] = 1
    assert "Undying Loyalty" in hand_plays(s, 0), "{2 energy} off leaves only its rune"
    cast(s, 0, "Undying Loyalty", pack_trash(0, T.id_of("Lonely Poro")))
    run(s, picking(base_loc(0)))
    assert perm_of(s, "Lonely Poro")


@case(9777, "Thrill of the Hunt may send a unit to a battlefield you don't control")
def _():
    need("Thrill of the Hunt")
    s = fresh(hand=[T.id_of("Thrill of the Hunt")], runes=9)
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(1), 3)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Thrill of the Hunt", u)
    seen = set()

    def pref(s, who, legal):
        seen.update(a.arg for a in legal if a.kind in (A.A_TARGET, A.A_PLAY_AT, A.A_PICK))
        return None
    run(s, pref, stop=lambda s: bool(seen))
    assert bf_loc(1) in seen, seen


@case(9775, "Switcheroo's swapped Might goes with the unit")
def _():
    need("Switcheroo", "Ride The Wind")
    s = fresh(hand=[T.id_of("Switcheroo")], runes=9)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    small = body(s, 0, bf_loc(0), 2)
    big = s.add_permanent(T.id_of("Mindsplitter"), 0, bf_loc(0))
    cast(s, 0, "Switcheroo", small, big)
    run(s)
    assert combat.might(s, T, small) == 7
    cast(s, 0, "Ride The Wind", small, bf_loc(1))
    run(s, picking())
    assert combat.might(s, T, small) == 7


@case(9752, "Noxian Drummer at Rockfall Path plays no Recruit there")
def _():
    need("Noxian Drummer", "Rockfall Path")
    s = fresh()
    s.bf_card[0] = T.id_of("Rockfall Path")
    nd = s.add_permanent(T.id_of("Noxian Drummer"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, nd)
    run(s, picking())
    assert not tokens(s, 0), "can't beats can"


@case(9751, "Sprite Mother's Sprite can't move after Vex - Apathetic sees it")
def _():
    need("Sprite Mother", "Vex - Apathetic")
    s = fresh(hand=[T.id_of("Sprite Mother")], runes=9)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    cast(s, 0, "Sprite Mother", base_loc(0))
    run(s)
    sp = tokens(s, 0)
    assert sp and s.has_flag(sp[0], F_NO_MOVE) and s.has_flag(sp[0], F_STUNNED)


@case(9748, "a hidden Here to Help still works while you are being attacked")
def _():
    need("Here to Help", "Determined Sentry")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 0, "Here to Help")
    give(s, 0, "Determined Sentry")
    give(s, 1, "Smoke Screen")
    a = body(s, 1, base_loc(1), 5, ready=True)
    attack(s, 1, 0, a)
    assert int(s.bf_ctrl[0]) == 0
    pass_priority_to(s, 0)
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picks(hand_index(s, 0, "Determined Sentry"), bf_loc(0)),
        stop=lambda s: bool(perm_of(s, "Determined Sentry")))
    ds = perm_of(s, "Determined Sentry")
    assert ds and int(s.perms[ds[0], P_LOC]) == bf_loc(0)


@case(9746, "Grim Apothecary may return itself")
def _():
    need("Grim Apothecary")
    s = fresh(hand=[T.id_of("Grim Apothecary")], runes=9)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Grim Apothecary", bf_loc(0))
    A._settle(s, T, V1)
    ga = perm_of(s, "Grim Apothecary")[0]
    run(s, picks(ga))
    assert not alive(s, ga) and T.id_of("Grim Apothecary") in list(s.hand[0, :int(s.n_hand[0])])


@case(9744, "Not So Fast counters the whole Icathian Rain")
def _():
    need("Icathian Rain", "Not So Fast")
    s = fresh(hand=[T.id_of("Icathian Rain")], runes=12)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 9
    u = body(s, 1, base_loc(1), 9)
    v = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Icathian Rain", u, u, u, v, v, v)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert int(s.perms[u, P_DMG]) == 0 and int(s.perms[v, P_DMG]) == 0


@case(9740, "Ashe - Focused's banished card comes back on a hold after she dies")
def _():
    need("Ashe - Focused")
    s = fresh(hand=[T.id_of("Ashe - Focused")], runes=9)
    give(s, 1, "Discipline")
    cast(s, 0, "Ashe - Focused", base_loc(0))
    run(s, picks(0))
    assert int(s.n_hand[1]) == 0
    combat.destroy(s, T, perm_of(s, "Ashe - Focused")[0])
    run(s)
    s.bf_ctrl[1] = 1
    s.add_permanent(VANILLA, 1, bf_loc(1))
    s.ply += 1
    s.active = s.priority = 1
    phases.start_turn(s, T, V1)
    run(s, picking())
    assert T.id_of("Discipline") in list(s.hand[1, :int(s.n_hand[1])])


@case(9739, "Smoke and Mirrors needs two units at different locations")
def _():
    need("Smoke and Mirrors", "Sprite Call")
    s = fresh(hand=[T.id_of("Smoke and Mirrors")], runes=9)
    body(s, 0, base_loc(0), 3)
    body(s, 0, base_loc(0), 3)
    assert "Smoke and Mirrors" not in hand_plays(s, 0)
    body(s, 0, bf_loc(0), 3)
    assert "Smoke and Mirrors" in hand_plays(s, 0)
