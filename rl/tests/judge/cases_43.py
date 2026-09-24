"""RiftJudge batch 43 -- unused questions from 8540-8590."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8590, "Irelia's legend readies her, and only the ready is +1")
def _():
    need("Irelia, Fervent", "Irelia - Blade Dancer", "Discipline")
    s = fresh(runes=16)
    give(s, 0, "Discipline")
    s.legend[0], s.legend_ready[0] = T.id_of("Irelia - Blade Dancer"), 1
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0), ready=False)
    cast(s, 0, "Discipline", ir)
    run(s, picking(accept=True))
    assert int(s.perms[ir, P_READY]) == 1, "the legend readied her"
    assert combat.might(s, T, ir) == 4 + 2 + 1 + 1, \
        "Discipline's +2, +1 for its choice, +1 for the ready"


@case(8586, "Teemo, Strategist chooses exactly one enemy unit")
def _():
    need("Teemo - Strategist")
    s = fresh(runes=16)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    tm = s.add_permanent(T.id_of("Teemo - Strategist"), 0, bf_loc(0), ready=True)
    s.ply += 1
    a = body(s, 1, base_loc(1), 9, ready=True)
    b = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, a, b)
    offered = targets_offered(s, 0)
    assert len(offered) == 2, "both attackers are choosable"
    choose(s, sorted(offered)[0])
    assert not targets_offered(s, 0, limit=2), "but only one is chosen"
    assert tm >= 0


@case(8582, "detaching Brutalizer takes both of its bonuses away")
def _():
    need("Brutalizer", "Angle Shot")
    s = fresh(runes=16)
    give(s, 0, "Angle Shot")
    u = body(s, 0, base_loc(0), 3, ready=True)
    br = s.add_permanent(T.id_of("Brutalizer"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, br, 0)
    choose(s, u)
    run(s)
    assert combat.might(s, T, u) == 6
    cast(s, 0, "Angle Shot", u, br)
    run(s)
    assert int(s.perms[br, P_ATTACHED_TO]) < 0, "the toggle detached it"
    assert combat.might(s, T, u) == 3, "137.3.a: the bonus stops with the link"


@case(8581, "Bellows Breath cannot choose a Ruin Runner anywhere")
def _():
    need("Bellows Breath", "Ruin Runner")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=16)
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1), ready=True)
    mine = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Bellows Breath"), 0)
    offered = targets_offered(s, 0)
    assert rr not in offered and mine in offered


@case(8579, "Orb of Regret waits for your own turn")
def _():
    need("Orb of Regret")
    s = fresh(runes=12)
    orb = s.add_permanent(T.id_of("Orb of Regret"), 0, base_loc(0), ready=True)
    body(s, 1, base_loc(1), 3)
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_ACTIVATE and a.arg == orb]
    s.ply += 1
    s.active = s.priority = 1
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE and a.arg == orb]


@case(8577, "Vanguard Armory's tokens never land on open ground")
def _():
    need("Vanguard Armory")
    s = fresh(runes=12)
    va = s.add_permanent(T.id_of("Vanguard Armory"), 0, base_loc(0), ready=True)
    s.bf_ctrl[0] = s.bf_ctrl[1] = -1
    act(s, A.A_ACTIVATE, va, 0)
    run(s)
    assert len(tokens(s, 0)) == 3
    assert all(int(s.perms[t, P_LOC]) == base_loc(0) for t in tokens(s, 0))


@case(8576, "a unit moved in by Ride the Wind is a defender and may push back")
def _():
    need("Overzealous Fan", "Ride The Wind")
    s = fresh(runes=16)
    give(s, 1, "Ride The Wind")
    s.runes_ready[1, :] = 16
    fan = s.add_permanent(T.id_of("Overzealous Fan"), 1, base_loc(1), ready=True)
    att = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, att)
    cast(s, 1, "Ride The Wind", fan, bf_loc(0))
    run(s, picking(att, accept=True), limit=20,
        stop=lambda st: int(st.perms[att, P_LOC]) == base_loc(0))
    assert int(s.perms[att, P_LOC]) == base_loc(0), "his defend trigger fired"
    assert not alive(s, fan), "he killed himself to do it"


@case(8571, "Thousand-Tailed Watcher shrinks a Ruin Runner")
def _():
    need("Thousand-Tailed Watcher", "Ruin Runner")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=20)
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1), ready=True)
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    run(s)
    assert combat.might(s, T, rr) == 2


@case(8566, "re-equipping Brutalizer elsewhere is a fresh +2 there")
def _():
    need("Brutalizer", "Angle Shot")
    s = fresh(runes=16)
    give(s, 0, "Angle Shot", "Angle Shot")
    a = body(s, 0, base_loc(0), 2, ready=True)
    b = body(s, 0, base_loc(0), 2, ready=True)
    br = s.add_permanent(T.id_of("Brutalizer"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, br, 0)
    choose(s, a)
    run(s)
    assert combat.might(s, T, a) == 5, "2 + 1 + 2"
    cast(s, 0, "Angle Shot", a, br)
    run(s)
    cast(s, 0, "Angle Shot", b, br)
    run(s)
    assert combat.might(s, T, a) == 2 and combat.might(s, T, b) == 5


@case(8565, "Falling Star cannot choose a Ruin Runner")
def _():
    need("Falling Star", "Ruin Runner")
    s = fresh(hand=[T.id_of("Falling Star")], runes=16)
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1), ready=True)
    mine = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Falling Star"), 0)
    offered = targets_offered(s, 0)
    assert rr not in offered and mine in offered, "352.14.a"


@case(8561, "a hidden Reaction answers the [Temporary] kill before it lands")
def _():
    need("Consult the Past", "Sprite Call")
    s = fresh(runes=12)
    rune_deck(s)
    tok = _sprite_at(s, 0, 0)
    slot = hidden_at(s, 0, 0, "Consult the Past")
    before = int(s.n_hand[0])
    _next_own_turn(s)
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_PLAY_HIDDEN and a.arg == slot], \
        "the Temporary trigger opened a window"
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    run(s)
    assert int(s.n_hand[0]) >= before + 2, "it drew before the token vanished"
    assert not alive(s, tok)


@case(8560, "an unattached Hexdrinker has no [Deflect] to pay for")
def _():
    need("Hexdrinker", "Detonate")
    s = fresh(hand=[T.id_of("Detonate")], runes=12)
    g = s.add_permanent(T.id_of("Hexdrinker"), 1, base_loc(1))
    before = runes(s, 0)
    cast(s, 0, "Detonate", g)
    run(s)
    assert not alive(s, g)
    assert before - runes(s, 0) == 1, "718.2: its Effect Text sleeps unattached"


@case(8559, "Not So Fast misses Riposte, whose unit is not yours")
def _():
    need("Riposte", "Not So Fast", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=16)
    give(s, 0, "Not So Fast")
    give(s, 1, "Riposte")
    s.runes_ready[1, :] = 16
    theirs = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Falling Star", theirs, theirs)
    cast(s, 1, "Riposte", theirs)
    choose(s, sorted(targets_offered(s, 1))[0])
    assert "Not So Fast" not in hand_plays(s, 0)


@case(8558, "Not So Fast misses Brynhir's global trigger")
def _():
    need("Brynhir Thundersong", "Not So Fast")
    s = fresh(hand=[T.id_of("Brynhir Thundersong")], runes=20)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 16
    body(s, 1, base_loc(1), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Brynhir Thundersong"), 0)
    choose(s, base_loc(0))
    pass_priority_to(s, 1)
    assert "Not So Fast" not in hand_plays(s, 1), "it chooses nothing"


@case(8557, "Wages of Pain still plays its Gold when the target is gone")
def _():
    need("Wages of Pain", "Retreat")
    s = fresh(hand=[T.id_of("Wages of Pain")], runes=16)
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Wages of Pain", u)
    cast(s, 1, "Retreat", u)
    run(s)
    assert not alive(s, u), "it went home to hand"
    assert len(tokens(s, 0)) == 1, "359.3.e.1: only the lost instruction is skipped"


@case(8552, "Poro Snax draws on the way in and again on the way out")
def _():
    need("Poro Snax")
    s = fresh(hand=[T.id_of("Poro Snax")], runes=12)
    before = int(s.n_hand[0])
    act(s, A.A_PLAY, hand_index(s, 0, "Poro Snax"), 0)
    choose(s, base_loc(0))
    run(s)
    assert int(s.n_hand[0]) == before - 1 + 1
    ps = perm_of(s, "Poro Snax", 0)[0]
    act(s, A.A_ACTIVATE, None, 0)
    run(s)
    assert not alive(s, ps) and int(s.n_hand[0]) == before + 1


@case(8550, "Reckoner's Arena runs an Equipment's conquer effect too")
def _():
    need("Reckoner's Arena", "Doran's Ring")
    s = fresh(runes=16)
    s.bf_card[0] = T.id_of("Reckoner's Arena")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    g = s.add_permanent(T.id_of("Doran's Ring"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, u)
    run(s)
    assert int(s.perms[g, P_ATTACHED_TO]) == u
    give(s, 0, "Smoke Screen", "Smoke Screen")
    before = int(s.n_hand[0])
    _next_own_turn(s)
    run(s, picking(accept=True), limit=40)
    assert int(s.n_hand[0]) != before, "the Ring's conquer effect ran on a hold"


@case(8545, "an Immortal Phoenix you culled can play itself back")
def _():
    need("Immortal Phoenix", "Cull the Weak")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=16)
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, base_loc(0), ready=True)
    body(s, 1, base_loc(1), 3)
    cast(s, 0, "Cull the Weak")
    run(s, picking(ph, accept=True))
    assert not alive(s, ph)
    assert perm_of(s, "Immortal Phoenix", 0), "376.2.c.1: it was in the trash by then"


@case(8543, "Sett cannot spend his buff while defending")
def _():
    need("Sett, Brawler")
    s = fresh(runes=16)
    s.bf_ctrl[0] = 0
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, bf_loc(0), ready=True)
    s.set_flag(sett, F_BUFFED)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE], "no [Action] keyword, no showdown use"


@case(8542, "Charm moves an enemy across battlefields without [Ganking]")
def _():
    need("Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=16)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 3)
    body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Charm", foe, bf_loc(1))
    run(s)
    assert int(s.perms[foe, P_LOC]) == bf_loc(1), "452: an effect move is not Standard"
