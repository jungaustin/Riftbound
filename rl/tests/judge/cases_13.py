"""RiftJudge batch 13 -- unused questions from 11252-11500."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_EMPOWERED, P_ATTACHED_TO, P_MIGHT_MOD, P_EMPOWER
from rl.engine.effects import ABILITIES, pack_trash


@case(11500, "Challenge is not combat: an [Assault] unit deals only its own Might")
def _():
    need("Challenge")
    s = fresh(hand=[T.id_of("Challenge")])
    poro = s.add_permanent(T.id_of("Daring Poro"), 0, base_loc(0))
    foe = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Challenge", poro, foe)
    run(s)
    assert int(s.perms[foe, P_DMG]) == int(T.might[T.id_of("Daring Poro")])


@case(11499, "Imperial Decree does not look back at damage dealt before it resolved")
def _():
    need("Imperial Decree")
    s = fresh()
    u = body(s, 1, base_loc(1), 3)
    s.perms[u, P_DMG] = 1
    rsv.resolve(s, T, V1, SPECS["Imperial Decree"], 0, [], -1, True)
    run(s)
    assert alive(s, u)


@case(11484, "Grim Apothecary cannot be Ambushed to your base on the opponent's turn")
def _():
    need("Grim Apothecary", "Discipline")
    s = fresh(seat=1, hand=[T.id_of("Discipline")])
    give(s, 0, "Grim Apothecary")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    u = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Discipline", u)
    pass_priority_to(s, 0)
    act(s, A.A_PLAY, hand_index(s, 0, "Grim Apothecary"), 0)
    dests = {a.arg for a in A.legal_actions(s, T, V1, 0)
             if a.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)}
    assert bf_loc(0) in dests and base_loc(0) not in dests, dests


@case(11477, "Eye of the Herald plays its Recruit where the unit moved to")
def _():
    need("Eye of the Herald", "Ride The Wind")
    s = fresh()
    u = body(s, 0, base_loc(0), 3)
    e = s.add_permanent(T.id_of("Eye of the Herald"), 0, base_loc(0))
    s.attach(e, u)
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [u, bf_loc(0)], -1, True)
    run(s)
    assert tokens(s, 0, bf_loc(0)) and not tokens(s, 0, base_loc(0))


@case(11471, "Fiora - Peerless defending alone with Master Yi: 3 + 2, doubled to 10")
def _():
    need("Fiora - Peerless", "Master Yi - Wuju Bladesman")
    s = fresh()
    s.legend[1], s.legend_ready[1] = T.id_of("Master Yi - Wuju Bladesman"), 1
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 1, bf_loc(0))
    a = body(s, 0, base_loc(0), 1, ready=True)
    attack(s, 0, 0, a)
    run(s, stop=lambda s: "Fiora - Peerless" not in chain_names(s) and s.n_trig == 0
        and s.pend_slot < 0)
    assert combat.might(s, T, fi) == 10, combat.might(s, T, fi)


@case(11470, "Rengar, Trophy Hunter cannot be played to an open battlefield")
def _():
    need("Rengar, Trophy Hunter", "Discipline")
    s = fresh(seat=1, hand=[T.id_of("Discipline")])
    give(s, 0, "Rengar, Trophy Hunter")
    s.runes_ready[0, :] = 9
    u = body(s, 1, bf_loc(1), 3)                        # enemies at bf 1; bf 0 is open
    s.bf_ctrl[1] = 1
    cast(s, 1, "Discipline", u)
    pass_priority_to(s, 0)
    act(s, A.A_PLAY, hand_index(s, 0, "Rengar, Trophy Hunter"), 0)
    dests = {a.arg for a in A.legal_actions(s, T, V1, 0)
             if a.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)}
    assert bf_loc(1) in dests and bf_loc(0) not in dests, dests


@case(11460, "Hidden Blade whose target Wages of Pain killed first: no draw 2")
def _():
    need("Hidden Blade", "Wages of Pain")
    s = fresh(hand=[T.id_of("Hidden Blade")])
    s.bf_ctrl[0] = 0
    r = body(s, 0, bf_loc(0), 1)
    cast(s, 0, "Hidden Blade", r)
    rsv.resolve(s, T, V1, SPECS["Wages of Pain"], 1, [r], -1, True)
    run(s)
    assert not alive(s, r) and int(s.n_hand[0]) == 0


@case(11459, "Forbidding Waste and Master Yi cancel on a lone defender")
def _():
    need("Forbidding Waste", "Master Yi - Wuju Bladesman")
    s = fresh()
    s.legend[1], s.legend_ready[1] = T.id_of("Master Yi - Wuju Bladesman"), 1
    give(s, 1, "Smoke Screen")
    s.bf_card[0] = T.id_of("Forbidding Waste")
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 4)
    a = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, a)
    assert s.showdown_bf == 0 and combat.might(s, T, d) == 4


@case(11446, "Garbage Grabber cannot be activated with fewer than 3 cards in the trash")
def _():
    need("Garbage Grabber")
    s = fresh()
    s.add_permanent(T.id_of("Garbage Grabber"), 0, base_loc(0), ready=True)
    s.trash[0, :2], s.n_trash[0] = [VANILLA, VANILLA], 2
    assert A.A_ACTIVATE not in kinds(s, 0)
    s.trash[0, 2], s.n_trash[0] = VANILLA, 3
    assert A.A_ACTIVATE in kinds(s, 0)


@case(11444, "Thrill of the Hunt as the first card: Darius - Trifarian is the second")
def _():
    need("Thrill of the Hunt", "Darius - Trifarian")
    s = fresh(hand=[T.id_of("Thrill of the Hunt")])
    d = s.add_permanent(T.id_of("Darius - Trifarian"), 0, base_loc(0))
    cast(s, 0, "Thrill of the Hunt", d, bf_loc(0))
    run(s)
    dd = perm_of(s, "Darius - Trifarian")
    assert dd and combat.might(s, T, dd[0]) == 7 and int(s.perms[dd[0], P_READY]) == 1


@case(11439, "The List cannot choose an enemy Ruin Runner")
def _():
    need("The List", "Ruin Runner")
    from rl.engine.effects import tag_vocab
    s = fresh()
    g = s.add_permanent(T.id_of("The List"), 0, base_loc(0), ready=True)
    tag = sorted(T.tags[T.id_of("Ruin Runner")])[0]
    s.named[g] = tag_vocab(T).index(tag)
    s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1))
    assert A.A_ACTIVATE not in kinds(s, 0)


@case(11431, "Eye of the Herald's unit Gusted in answer: no Recruit is played")
def _():
    need("Eye of the Herald", "Gust")
    s = fresh()
    u = body(s, 0, base_loc(0), 3)
    e = s.add_permanent(T.id_of("Eye of the Herald"), 0, base_loc(0))
    s.attach(e, u)
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [u, bf_loc(0)], -1, True)
    A._settle(s, T, V1)
    combat.return_to_hand(s, T, u)
    run(s)
    assert not tokens(s, 0)


@case(11410, "Blitzcrank - Impassive cannot be played to an open battlefield")
def _():
    need("Blitzcrank - Impassive")
    s = fresh(hand=[T.id_of("Blitzcrank - Impassive")])
    act(s, A.A_PLAY, 0, 0)
    dests = {a.arg for a in A.legal_actions(s, T, V1, 0)
             if a.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)}
    assert dests == {base_loc(0)}, dests


@case(11404, "Bone Skewer brings in a Ruin Runner from the hand, stunned")
def _():
    need("Bone Skewer", "Ruin Runner")
    s = fresh(hand=[T.id_of("Bone Skewer")])
    give(s, 1, "Ruin Runner")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Bone Skewer", bf_loc(0))
    run(s, picking(0))
    rr = perm_of(s, "Ruin Runner")
    assert rr and s.has_flag(rr[0], F_STUNNED)


@case(11395, "Turn to Dust's Temporary on an attached Doran's Shield still kills it")
def _():
    need("Turn to Dust", "Doran's Shield")
    s = fresh(seat=1)
    u = body(s, 0, base_loc(0), 3)
    ds = s.add_permanent(T.id_of("Doran's Shield"), 0, base_loc(0))
    s.attach(ds, u)
    rsv.resolve(s, T, V1, SPECS["Turn to Dust"], 1, [ds], -1, True)
    act(s, A.A_END_TURN, None, 1)
    run(s, picking(), stop=lambda s: int(s.active) == 0 and s.phase == MAIN
        and s.n_chain == 0 and s.n_trig == 0)
    assert not perm_of(s, "Doran's Shield") and perm_of(s, "Shipyard Skulker")


@case(11393, "Hidden Blade on a unit saved by Zhonya's: its controller still draws 2")
def _():
    need("Hidden Blade", "Zhonya's Hourglass")
    s = fresh(hand=[T.id_of("Hidden Blade")])
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u) and int(s.n_hand[1]) == 2


@case(11390, "Hidden Blade whose target was Star-Crossed away: no draw 2")
def _():
    need("Hidden Blade", "Star-Crossed")
    s = fresh(hand=[T.id_of("Hidden Blade")])
    s.bf_ctrl[0] = 1
    hw = body(s, 1, bf_loc(0), 3)
    mine = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Hidden Blade", hw)
    rsv.resolve(s, T, V1, SPECS["Star-Crossed"], 1, [hw, mine], -1, True)
    run(s)
    assert int(s.n_hand[1]) == 1, "only the returned unit, no draw 2"


@case(11386, "Safety Inspector unpaid, alone: he kills himself")
def _():
    need("Safety Inspector")
    s = fresh(hand=[T.id_of("Safety Inspector")])
    cast(s, 0, "Safety Inspector", base_loc(0))
    run(s, picking())
    assert not perm_of(s, "Safety Inspector")


@case(11374, "Eclipse taking an undamaged unit to 0 Might does not kill it")
def _():
    need("Eclipse")
    s = fresh()
    u = body(s, 1, base_loc(1), 3)
    rsv.resolve(s, T, V1, SPECS["Eclipse"], 0, [u], -1, True)
    run(s, picking(accept=False))
    assert alive(s, u) and combat.might(s, T, u) == 0


@case(11360, "Thousand-Tailed Watcher's -3 reaches Ruin Runner: it chooses nothing")
def _():
    need("Thousand-Tailed Watcher", "Ruin Runner")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=12)
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1))
    cast(s, 0, "Thousand-Tailed Watcher", base_loc(0))
    run(s, picking(accept=False))
    assert combat.might(s, T, rr) == int(T.might[T.id_of("Ruin Runner")]) - 3


@case(11351, "a hidden Windsinger can only return a unit at its own battlefield")
def _():
    need("Windsinger")
    s = fresh()
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    here = body(s, 0, bf_loc(0), 2)
    there = body(s, 1, bf_loc(1), 2)
    s.bf_ctrl[1] = 1
    hidden_at(s, 0, 0, "Windsinger")
    act(s, A.A_PLAY_HIDDEN, None, 0)
    offered = targets_offered(s, 0)
    assert here in offered and there not in offered, offered


@case(11303, "Defy on a spell Fizz played from the trash: it is still recycled")
def _():
    need("Defy", "Fizz - Trickster", "Discipline")
    s = fresh(hand=[T.id_of("Fizz - Trickster")])
    give(s, 1, "Defy")
    s.trash[0, 0], s.n_trash[0] = T.id_of("Discipline"), 1
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Fizz - Trickster", base_loc(0))
    run(s, picks(pack_trash(0, T.id_of("Discipline")), u),
        stop=lambda s: "Discipline" in chain_names(s) and s.pend_slot < 0)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert int(s.n_trash[0]) == 0 and T.id_of("Discipline") not in list(s.hand[0, :int(s.n_hand[0])])
    assert T.id_of("Discipline") in list(s.deck[0, :int(s.n_deck[0])])


@case(11275, "Existential Dread Repeated may choose two different attackers")
def _():
    need("Existential Dread")
    s = fresh(seat=1, runes=12)
    give(s, 0, "Existential Dread", "Smoke Screen")
    s.runes_ready[0, :] = 12
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 9)
    a1 = body(s, 1, base_loc(1), 2, ready=True)
    a2 = body(s, 1, base_loc(1), 2, ready=True)
    attack(s, 1, 0, a1, a2)
    assert s.showdown_bf == 0
    pass_priority_to(s, 0)
    act(s, A.A_PLAY_REPEAT, hand_index(s, 0, "Existential Dread"), 0)
    choose(s, a1)
    choose(s, a2)
    run(s, stop=lambda s: s.n_chain == 0)
    assert s.has_flag(a1, F_STUNNED) and s.has_flag(a2, F_STUNNED)


@case(11274, "Svellsongur on Draven - Audacious: the first combat win scores twice")
def _():
    need("Svellsongur", "Draven - Audacious")
    s = fresh()
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 1)
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 0, base_loc(0), ready=True)
    sv = s.add_permanent(T.id_of("Svellsongur"), 0, base_loc(0))
    s.attach(sv, dr)
    attack(s, 0, 0, dr)
    fight(s)
    run(s)
    assert int(s.points[0]) == 3, int(s.points[0])


@case(11252, "Not So Fast counters Elder Dragon's whole play trigger")
def _():
    need("Not So Fast", "Elder Dragon")
    s = fresh(hand=[T.id_of("Elder Dragon")], runes=12)
    give(s, 1, "Not So Fast")
    a = body(s, 1, base_loc(1), 3)
    b = body(s, 1, bf_loc(0), 3)
    s.bf_ctrl[0] = 1
    cast(s, 0, "Elder Dragon", base_loc(0))
    run(s, picks(a, b, -1, -1), stop=lambda s: s.n_chain and chain_names(s)[-1] == "Elder Dragon"
        and s.pend_slot < 0)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert alive(s, a) and alive(s, b) and int(s.perms[a, P_DMG]) == 0
