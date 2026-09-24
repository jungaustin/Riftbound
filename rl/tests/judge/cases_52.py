"""RiftJudge batch 52 -- unused questions from 8041-8081."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8080, "a staged showdown waits for the chain to empty")
def _():
    need("Deadbloom Predator")
    s = fresh(hand=[T.id_of("Deadbloom Predator")], runes=32)
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Deadbloom Predator"), 0)
    choose(s, bf_loc(0))
    assert int(s.showdown_bf) < 0, "323.13: a Cleanup starts it, not the play"
    fight(s)
    assert int(s.bf_ctrl[0]) == 0, "and then it happened"


@case(8079, "[Shield] is passive, so there is no window before it applies")
def _():
    need("Stalwart Poro")
    s = fresh(hand=[T.id_of("Stalwart Poro")], runes=24)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Stalwart Poro"), 0)
    choose(s, bf_loc(0))
    poro = perm_of(s, "Stalwart Poro", 0)[0]
    assert int(s.n_chain) == 0, "nothing to respond to"
    assert combat.might(s, T, poro) == 2, "[Shield] shows only while defending"


@case(8077, "a hidden Fox-Fire chooses only at its own battlefield")
def _():
    need("Fox-Fire")
    s = fresh(runes=24)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    here = body(s, 1, bf_loc(0), 2)
    away = body(s, 1, bf_loc(1), 2)
    slot = hidden_at(s, 0, 0, "Fox-Fire")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    offered = targets_offered(s, 0)
    assert here in offered and away not in offered, "737.1.d.2 adds 'here'"


@case(8075, "a countered spell never grows Ravenbloom Student")
def _():
    need("Ravenbloom Student", "Discipline", "Defy")
    s = fresh(runes=24)
    give(s, 0, "Discipline")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 24
    rs = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0), ready=True)
    cast(s, 0, "Discipline", rs)
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert combat.might(s, T, rs) == 2


@case(8072, "the Hourglass's controller picks, attacker or defender")
def _():
    need("Zhonya's Hourglass")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 3)
    b = body(s, 1, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    att = body(s, 0, base_loc(0), 9, ready=True)
    attack(s, 0, 0, att)
    fight(s)
    assert alive(s, a) != alive(s, b), "exactly one of them was saved"
    assert not alive(s, z)


@case(8061, "Arena Bar's ability goes on the chain and can be answered")
def _():
    need("Arena Bar", "Smoke Screen")
    s = fresh(runes=24)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 24
    ab = s.add_permanent(T.id_of("Arena Bar"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 3, ready=False)
    act(s, A.A_ACTIVATE, ab, 0)
    choose(s, u)
    assert int(s.n_chain) >= 1
    pass_priority_to(s, 1)
    assert "Smoke Screen" in hand_plays(s, 1)


@case(8059, "damage does not lower Might, so both units die")
def _():
    need("Yasuo - Remorseful")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 10)
    attack(s, 0, 0, ya)
    choose(s, d)
    fight(s)
    assert not alive(s, ya), "10 combat damage against 6 Might"
    assert not alive(s, d), "6 from his trigger plus 6 combat damage"


@case(8058, "Battering Ram counts the card that played it")
def _():
    need("Void Rush", "Battering Ram")
    from rl.engine import cost as cost_mod
    s = fresh(hand=[T.id_of("Void Rush")], runes=32)
    cid = T.id_of("Battering Ram")
    assert cost_mod.apply_discounts(
        int(T.energy[cid]), cost_mod.energy_discounts(s, T, 0, cid)) == 5
    s.cards_played[0] = 1
    assert cost_mod.apply_discounts(
        int(T.energy[cid]), cost_mod.energy_discounts(s, T, 0, cid)) == 4, \
        "one card played, one Energy less"


@case(8057, "Defy needs BOTH halves of its range")
def _():
    need("Defy", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    u = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Falling Star", u, u)
    pass_priority_to(s, 1)
    assert "Defy" not in hand_plays(s, 1), "2 Power is more than {any rune}"


@case(8055, "a cost paid before the unit lands cannot be replaced by it")
def _():
    need("Cruel Patron")
    s = fresh(hand=[T.id_of("Cruel Patron")], runes=32)
    victim = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Cruel Patron"), 0)
    choose(s, victim)
    choose(s, base_loc(0))
    run(s)
    assert not alive(s, victim), "killed as the cost"
    assert perm_of(s, "Cruel Patron", 0), "and the unit arrived after"


@case(8052, "'any number of units' still wants one to reach the chain")
def _():
    need("Volibear - Furious")
    s = fresh(runes=32)
    vb = s.add_permanent(T.id_of("Volibear - Furious"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, vb)
    assert int(s.n_chain) == 0 and int(s.n_trig) == 0, \
        "355.8: an empty battlefield gives his trigger nothing"


@case(8048, "Siphon Power is a one-time effect on who is there")
def _():
    need("Siphon Power", "Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Siphon Power", "Ride The Wind")
    s.bf_ctrl[0] = 0
    here = body(s, 0, bf_loc(0), 3)
    later = body(s, 0, base_loc(0), 3, ready=False)
    cast(s, 0, "Siphon Power", bf_loc(0))
    run(s)
    assert combat.might(s, T, here) == 4
    cast(s, 0, "Ride The Wind", later, bf_loc(0))
    run(s)
    assert combat.might(s, T, later) == 3, "it arrived after the spell resolved"


@case(8047, "a Charmed unit is the attacker, and keeps its [Assault]")
def _():
    need("Charm", "Immortal Phoenix")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 1, base_loc(1), ready=True)
    cast(s, 0, "Charm", ph, bf_loc(0))
    drain(s)
    assert int(s.attacker) == 1
    assert combat.might(s, T, ph) == 5, "3 plus [Assault 2] as an attacker"


@case(8045, "Defy reads the printed cost, not what a Repeat added")
def _():
    need("Defy", "Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=32)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Bellows Breath", u, -1, -1, repeat=True)
    choose(s, u)
    choose(s, -1)
    choose(s, -1)
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1), "still a 1 Energy, 1 Power spell"


@case(8043, "Teemo, Strategist chooses one unit, whatever he reveals")
def _():
    need("Teemo - Strategist")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    tm = s.add_permanent(T.id_of("Teemo - Strategist"), 0, bf_loc(0), ready=True)
    s.ply += 1
    a = body(s, 1, base_loc(1), 9, ready=True)
    b = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, a, b)
    offered = targets_offered(s, 0)
    assert len(offered) == 2
    choose(s, sorted(offered)[0])
    assert not targets_offered(s, 0, limit=2), "one choice only"
    assert tm >= 0


@case(8042, "a countered Bullet Time recycles nothing")
def _():
    need("Bullet Time", "Defy")
    s = fresh(hand=[T.id_of("Bullet Time")], runes=32)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    before = runes(s, 0)
    cast(s, 0, "Bullet Time", bf_loc(0))
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert alive(s, u)
    assert runes(s, 0) == before, "the Power was never chosen, let alone paid"


@case(8041, "a base-speed spell cannot be played inside your own showdown")
def _():
    need("Cull the Weak")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    att = body(s, 0, base_loc(0), 3, ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, att)
    assert "Cull the Weak" not in hand_plays(s, 0), "no [Action], no showdown"


@case(8081, "a hidden card flipped with nothing to choose does nothing")
def _():
    need("Tideturner")
    s = fresh(runes=24)
    s.bf_ctrl[0] = 0
    slot = hidden_at(s, 0, 0, "Tideturner")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    tt = perm_of(s, "Tideturner", 0)[0]
    assert int(s.perms[tt, P_LOC]) == bf_loc(0), "it still arrives"
    run(s)
    assert alive(s, tt)
