"""RiftJudge batch 10 -- unused questions from 12235-12422."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_EMPOWERED, P_ATTACHED_TO, P_MIGHT_MOD
from rl.engine.effects import ABILITIES, pack_trash


def ready_runes(s, seat):
    return int(s.runes_ready[seat].sum())


@case(12237, "Decree of Focus on a unit whose Fury enemy was Thrilled away: no +4")
def _():
    need("Decree of Focus", "Thrill of the Hunt")
    fury = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
                and int(T.domain_mask[c]) == 1 << 3 and not T.residual_text(c)
                and int(T.might[c]) == 3)
    s = fresh(hand=[T.id_of("Decree of Focus")])
    give(s, 1, "Thrill of the Hunt", "Smoke Screen")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    red = s.add_permanent(fury, 1, base_loc(1), ready=True)
    attack(s, 1, 0, red)
    assert s.showdown_bf == 0
    pass_priority_to(s, 0)
    cast(s, 0, "Decree of Focus", mine)
    cast(s, 1, "Thrill of the Hunt", red, bf_loc(1))
    run(s, stop=lambda s: s.n_chain == 0)
    assert combat.might(s, T, mine) == 3


@case(12239, "6 Might into Ferrous Forerunner and a Scuttle Crab: only one can die")
def _():
    need("Ferrous Forerunner", "Scuttle Crab")
    s = fresh()
    s.bf_ctrl[0] = 1
    ff = s.add_permanent(T.id_of("Ferrous Forerunner"), 1, bf_loc(0))
    crab = s.add_permanent(T.id_of("Scuttle Crab"), 1, bf_loc(0))
    a = body(s, 0, base_loc(0), 6, ready=True)
    attack(s, 0, 0, a)
    fight(s)
    assert not (not alive(s, ff) and not alive(s, crab)), "142.4.b -- the Crab needs 1 of its own"


@case(12241, "Mel, Defiant Soul may Empower with no enemy unit to banish")
def _():
    need("Mel, Defiant Soul")
    s = fresh(hand=[T.id_of("Discipline")])
    mel = s.add_permanent(T.id_of("Mel, Defiant Soul"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, None, 0)
    run(s, picking(0))
    assert s.empower_count(mel) == 1 and int(s.n_trash[0]) == 1


@case(12258, "Disposal Order recycles The Harrowing's target: it plays nothing")
def _():
    need("Disposal Order", "The Harrowing")
    s = fresh(hand=[T.id_of("The Harrowing")], runes=12)
    give(s, 1, "Disposal Order")
    s.trash[0, 0], s.n_trash[0] = VANILLA, 1
    cast(s, 0, "The Harrowing", pack_trash(0, VANILLA), base_loc(0))
    pass_priority_to(s, 1)
    act(s, A.A_PLAY, hand_index(s, 1, "Disposal Order"), 1)
    choose(s, 0)                                       # mode: recycle
    choose(s, pack_trash(0, VANILLA))
    choose(s, -1)
    choose(s, -1)
    run(s)
    assert not units(s, 0) and int(s.n_trash[0]) == 1, "only The Harrowing itself"


@case(12260, "Glowstone handed to the opponent hits their units at the end of THEIR turn")
def _():
    need("Glowstone")
    s = fresh()
    g = s.add_permanent(T.id_of("Glowstone"), 1, base_loc(1))
    body(s, 0, base_loc(0), 3)
    body(s, 1, base_loc(1), 3)
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(), stop=lambda s: int(s.active) == 1 and s.n_chain == 0 and s.n_trig == 0)
    assert len(units(s, 0)) == 1 and len(units(s, 1)) == 1 and perm_of(s, "Glowstone")


@case(12261, "Alpha Strike's units Flashed to base are no longer hit")
def _():
    need("Alpha Strike", "Flash")
    s = fresh(hand=[T.id_of("Alpha Strike")])
    s.bf_ctrl[0] = 0
    mine = body(s, 0, base_loc(0), 4)
    foes = [body(s, 1, bf_loc(1), 1) for _ in range(4)]
    s.bf_ctrl[1] = 1
    cast(s, 0, "Alpha Strike", mine)
    rsv.resolve(s, T, V1, SPECS["Flash"], 1, foes[:2], -1, True)
    run(s, picks(foes[2], foes[3], foes[2], foes[3]))
    assert all(alive(s, f) for f in foes[:2]) and not any(alive(s, f) for f in foes[2:])


@case(12278, "Thrill of the Hunt dodges a kill spell aimed at the unit")
def _():
    need("Thrill of the Hunt", "Hidden Blade")
    s = fresh(seat=1, hand=[T.id_of("Hidden Blade")])
    give(s, 0, "Thrill of the Hunt")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 1, "Hidden Blade", u)
    cast(s, 0, "Thrill of the Hunt", u, bf_loc(0))
    run(s)
    assert len(units(s, 0)) == 1, "a new object the Blade never chose"


@case(12285, "Sandswept Tomb: Void Assault moving a unit in from base gets no discount")
def _():
    need("Sandswept Tomb", "Void Assault")
    s = fresh(hand=[T.id_of("Void Assault")])
    s.bf_card[0] = T.id_of("Sandswept Tomb")
    mine = body(s, 0, base_loc(0), 3)
    foe = body(s, 1, bf_loc(1), 3)
    s.bf_ctrl[1] = 1
    before = runes(s, 0)
    cast(s, 0, "Void Assault", mine, bf_loc(0), foe, base_loc(1))
    run(s, picking())
    assert before - runes(s, 0) == int(T.power[T.id_of("Void Assault")])


@case(12286, "Frozen Fortress triggers with no unit on it")
def _():
    need("Frozen Fortress")
    s = fresh()
    s.bf_card[0] = T.id_of("Frozen Fortress")
    act(s, A.A_END_TURN, None, 0)
    saw = []
    run(s, stop=lambda s: saw.append(chain_names(s)) or False)
    assert any("Frozen Fortress" in c for c in saw), "the trigger goes on the Chain"


@case(12287, "Baited Hook on Rift Herald: the look comes before the Deathknell")
def _():
    need("Baited Hook", "Rift Herald")
    s = fresh()
    s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    h = s.add_permanent(T.id_of("Rift Herald"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, h)
    order = []

    def watch(s):
        if s.pend_look >= 0 and "look" not in order:
            order.append("look")
        if "Rift Herald" in chain_names(s) and "dk" not in order:
            order.append("dk")
        return False
    run(s, picking(accept=False), stop=watch)
    assert order and order[0] == "look", order


@case(12289, "Astral Heron played after the first card: no discount")
def _():
    need("Astral Heron")
    s = fresh(hand=[VANILLA, T.id_of("Astral Heron")], runes=12)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Shipyard Skulker", base_loc(0))
    run(s)
    cast(s, 0, "Astral Heron", bf_loc(0))
    run(s)
    assert int(s.next_discount[0].sum()) == 0


@case(12294, "Star-Crossed on Pickpocket does not stop its play trigger")
def _():
    need("Pickpocket", "Star-Crossed")
    s = fresh(hand=[T.id_of("Pickpocket")])
    give(s, 1, "Star-Crossed")
    seal = s.add_permanent(T.id_of("Seal of Discord"), 1, base_loc(1))
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Pickpocket", base_loc(0))
    run(s, picking(seal), stop=lambda s: "Pickpocket" in chain_names(s) and s.pend_slot < 0
        and s.pend_may < 0)
    pp = perm_of(s, "Pickpocket")[0]
    cast(s, 1, "Star-Crossed", theirs, pp)
    run(s, picking(seal))
    assert not perm_of(s, "Pickpocket") and not alive(s, seal) and tokens(s, 0)


@case(12296, "Star Spring cannot send back the unit whose play triggered it")
def _():
    need("Star Spring", "Lillia - Fae Fawn")
    s = fresh(hand=[T.id_of("Lillia - Fae Fawn")])
    s.bf_card[0] = T.id_of("Star Spring")
    s.bf_ctrl[0] = 0
    other = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Lillia - Fae Fawn", bf_loc(0))
    offered = targets_offered(s, 0)
    li = perm_of(s, "Lillia - Fae Fawn")[0]
    assert other in offered and li not in offered, offered


@case(12304, "Bone Skewer can pick Baron Nashor from the hand: he enters stunned")
def _():
    need("Bone Skewer", "Baron Nashor")
    s = fresh(hand=[T.id_of("Bone Skewer")])
    give(s, 1, "Baron Nashor")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Bone Skewer", bf_loc(0))
    run(s, picking(0))
    bn = perm_of(s, "Baron Nashor")
    assert bn and s.has_flag(bn[0], F_STUNNED)


@case(12306, "Existential Dread stuns the attacker: no result, attacker recalled")
def _():
    need("Existential Dread")
    s = fresh(seat=1)
    give(s, 0, "Existential Dread", "Smoke Screen")
    s.bf_ctrl[0] = 0
    d = body(s, 0, bf_loc(0), 4)
    a = body(s, 1, base_loc(1), 6, ready=True)
    attack(s, 1, 0, a)
    assert s.showdown_bf == 0
    pass_priority_to(s, 0)
    cast(s, 0, "Existential Dread", a)
    fight(s)
    run(s)
    assert alive(s, a) and alive(s, d) and int(s.perms[a, P_LOC]) == base_loc(1)
    assert int(s.bf_ctrl[0]) == 0


@case(12314, "Repulse counters Star-Crossed whole: neither unit returns")
def _():
    need("Repulse", "Star-Crossed")
    s = fresh(seat=1, hand=[T.id_of("Star-Crossed")])
    give(s, 0, "Repulse")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Star-Crossed", theirs, mine)
    cast(s, 0, "Repulse", mine, top_uid(s))
    run(s)
    assert alive(s, mine) and alive(s, theirs)


@case(12315, "Ride the Wind off Abandoned Hall: the Hall's +1 has no unit there")
def _():
    need("Abandoned Hall", "Ride The Wind")
    s = fresh(hand=[T.id_of("Ride The Wind")])
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Ride The Wind", u, base_loc(0))
    run(s, picking(u))
    assert int(s.perms[u, P_LOC]) == base_loc(0) and combat.might(s, T, u) == 3


@case(12318, "Counter Strike prevents one whole combat damage event, from both attackers")
def _():
    need("Counter Strike")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    d = body(s, 0, bf_loc(0), 3)
    a1 = body(s, 1, base_loc(1), 2, ready=True)
    a2 = body(s, 1, base_loc(1), 2, ready=True)
    rsv.resolve(s, T, V1, SPECS["Counter Strike"], 0, [d], -1, True)
    attack(s, 1, 0, a1, a2)
    fight(s)
    run(s)
    assert alive(s, d)


@case(12328, "Lillia moving off Rockfall Path: no Sprite can be played there")
def _():
    need("Lillia - Fae Fawn", "Rockfall Path", "Ride The Wind")
    s = fresh()
    s.bf_card[0] = T.id_of("Rockfall Path")
    s.bf_ctrl[0] = 0
    li = s.add_permanent(T.id_of("Lillia - Fae Fawn"), 0, bf_loc(0))
    body(s, 0, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [li, base_loc(0)], -1, True)
    run(s)
    assert not tokens(s, 0)


@case(12329, "Svellsongur on Ornn - Forge God doubles his Deflect to 4")
def _():
    need("Svellsongur", "Ornn - Forge God")
    s = fresh()
    o = s.add_permanent(T.id_of("Ornn - Forge God"), 1, base_loc(1))
    sv = s.add_permanent(T.id_of("Svellsongur"), 1, base_loc(1))
    s.attach(sv, o)
    assert combat.perm_kw(s, T, o, "Deflect") == 4, combat.perm_kw(s, T, o, "Deflect")


@case(12330, "a hidden Temporal Breach can only choose a unit at its battlefield")
def _():
    need("Temporal Breach")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    here = body(s, 0, bf_loc(0), 3)
    home = body(s, 0, base_loc(0), 3)
    hidden_at(s, 0, 0, "Temporal Breach")
    s.active = s.priority = 0
    act(s, A.A_PLAY_HIDDEN, None, 0)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert here in offered and home not in offered, offered


@case(12341, "Astral Heron's discount does not pay an Equip cost")
def _():
    need("Astral Heron", "Svellsongur")
    s = fresh()
    s.next_discount[0, :] = 2
    u = body(s, 0, base_loc(0), 3)
    s.add_permanent(T.id_of("Svellsongur"), 0, base_loc(0), ready=True)
    before = ready_runes(s, 0)
    act(s, A.A_ACTIVATE, None, 0)
    run(s, picking(u))
    assert before - ready_runes(s, 0) == 2 and list(s.next_discount[0]) == [2, 2]


@case(12343, "Helm of Suppression adds its increase once to a Repeated spell")
def _():
    need("Helm of Suppression", "Frigid Touch")
    s = fresh(hand=[T.id_of("Frigid Touch")], runes=12)
    s.add_permanent(T.id_of("Helm of Suppression"), 1, base_loc(1))
    u = body(s, 1, base_loc(1), 9)
    before = ready_runes(s, 0)
    cast(s, 0, "Frigid Touch", u, u, repeat=True)
    run(s)
    assert before - ready_runes(s, 0) == 2 + 2 + 1, before - ready_runes(s, 0)


@case(12349, "Blade Dancer's ready resolves even if the spell that chose is Defied")
def _():
    need("Irelia - Blade Dancer", "Discipline", "Defy")
    s = fresh(hand=[T.id_of("Discipline")])
    s.legend[0], s.legend_ready[0] = T.id_of("Irelia - Blade Dancer"), 1
    give(s, 1, "Defy")
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    run(s, picking(), stop=lambda s: s.n_chain and chain_names(s)[-1] != "Discipline"
        and s.pend_may < 0 and s.pend_slot < 0)
    from rl.engine.state import C_CARD, C_UID
    disc = next(int(s.chain[i, C_UID]) for i in range(s.n_chain)
                if T.names[int(s.chain[i, C_CARD])] == "Discipline")
    cast(s, 1, "Defy", disc)
    run(s)
    assert int(s.perms[u, P_READY]) == 1 and combat.might(s, T, u) == 3


@case(12350, "Shuriken Flip moving Astral Heron to a battlefield as the first card")
def _():
    need("Astral Heron", "Shuriken Flip")
    s = fresh(hand=[T.id_of("Shuriken Flip")])
    her = s.add_permanent(T.id_of("Astral Heron"), 0, base_loc(0))
    act(s, A.A_PLAY, 0, 0)
    choose(s, -1)
    choose(s, bf_loc(1))
    choose(s, her)
    run(s)
    assert int(s.perms[her, P_LOC]) == bf_loc(1) and list(s.next_discount[0]) == [2, 2]


@case(12361, "an Ambush unit played by Rift Herald's Deathknell still goes to base")
def _():
    need("Rift Herald", "Rengar, Trophy Hunter")
    s = fresh(hand=[T.id_of("Rengar, Trophy Hunter")], runes=12)
    s.bf_ctrl[0] = 0
    h = s.add_permanent(T.id_of("Rift Herald"), 0, bf_loc(0))
    body(s, 0, bf_loc(0), 3)
    combat.destroy(s, T, h)
    run(s, picking(0, base_loc(0)))
    r = perm_of(s, "Rengar, Trophy Hunter")
    assert r and int(s.perms[r[0], P_LOC]) == base_loc(0)


@case(12367, "Falling Star's 3 and 3 on one unit: a Zhonya's Hourglass saves it once")
def _():
    need("Falling Star", "Zhonya's Hourglass")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    s.death_guard[0] = z                               # what playing it registers
    rsv.resolve(s, T, V1, SPECS["Falling Star"], 1, [u, u], -1, True)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_LOC]) == base_loc(0) and not alive(s, z)


@case(12391, "Switcheroo on a Rumble-pumped Ferrous Forerunner: it ends at 1, the other at 7")
def _():
    need("Switcheroo", "Rumble - Scrapper", "Ferrous Forerunner")
    s = fresh(seat=1, hand=[T.id_of("Switcheroo")])
    s.add_permanent(T.id_of("Rumble - Scrapper"), 0, base_loc(0))
    ff = s.add_permanent(T.id_of("Ferrous Forerunner"), 0, bf_loc(0))
    s.bf_ctrl[0] = 0
    small = body(s, 1, bf_loc(0), 1)
    rsv.resolve(s, T, V1, SPECS["Switcheroo"], 1, [ff, small], -1, True)
    assert combat.might(s, T, ff) == 1 and combat.might(s, T, small) == 7


@case(12396, "Switcheroo at Trifarian War Camp: the Camp's +1 stays on top")
def _():
    need("Switcheroo", "Trifarian War Camp")
    s = fresh(hand=[T.id_of("Switcheroo")])
    s.bf_card[0] = T.id_of("Trifarian War Camp")
    a = body(s, 0, bf_loc(0), 4)
    b = body(s, 1, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Switcheroo"], 0, [a, b], -1, True)
    assert combat.might(s, T, a) == 4 and combat.might(s, T, b) == 5
    s.set_location(a, base_loc(0))
    assert combat.might(s, T, a) == 3, "leaving the Camp takes only the Camp's +1"


@case(12401, "Riposte against an empowered Mel's spell: the +Might still lands")
def _():
    need("Riposte", "Mel, Newly Awakened", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")])
    give(s, 1, "Riposte")
    mel = s.add_permanent(T.id_of("Mel, Newly Awakened"), 0, base_loc(0))
    s.set_flag(mel, F_EMPOWERED)
    u = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Riposte", theirs, top_uid(s))
    run(s)
    assert combat.might(s, T, u) == 5
    assert combat.might(s, T, theirs) == 3 + int(T.energy[T.id_of("Discipline")])


@case(12410, "Retreat needs a friendly unit to be played")
def _():
    need("Retreat")
    s = fresh(hand=[T.id_of("Retreat")])
    body(s, 1, base_loc(1), 3)
    assert "Retreat" not in hand_plays(s, 0)


@case(12412, "Vex - Apathetic dying does not lift 'can't move it this turn'")
def _():
    need("Vex - Apathetic")
    from rl.engine.state import F_NO_MOVE
    s = fresh(hand=[VANILLA])
    s.bf_ctrl[1] = 1
    vex = s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    cast(s, 0, "Shipyard Skulker", base_loc(0))
    run(s)
    u = perm_of(s, "Shipyard Skulker")[0]
    combat.destroy(s, T, vex)
    run(s)
    s.perms[u, P_READY] = 1
    assert s.has_flag(u, F_NO_MOVE) and A.A_DECLARE not in kinds(s, 0)


@case(12415, "Mirror Image of a Switcherooed unit copies its printed Might")
def _():
    need("Mirror Image", "Switcheroo")
    s = fresh()
    w = s.add_permanent(T.id_of("Watchful Sentry"), 0, bf_loc(0))
    big = body(s, 1, bf_loc(0), 6)
    rsv.resolve(s, T, V1, SPECS["Switcheroo"], 0, [w, big], -1, True)
    assert combat.might(s, T, w) == 6
    rsv.resolve(s, T, V1, SPECS["Mirror Image"], 0, [w], -1, True)
    A._settle(s, T, V1)
    assert combat.might(s, T, tokens(s, 0)[0]) == 1


@case(12417, "Tornado Warrior flipped in answer to Unchecked Power still takes 12")
def _():
    need("Tornado Warrior", "Unchecked Power")
    s = fresh(seat=1, hand=[T.id_of("Unchecked Power")], runes=12)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 0, "Tornado Warrior")
    theirs = body(s, 1, bf_loc(1), 3)
    s.bf_ctrl[1] = 1
    cast(s, 1, "Unchecked Power")
    pass_priority_to(s, 0)
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(accept=False))
    assert not perm_of(s, "Tornado Warrior") and not units(s, 0, bf_loc(0))
