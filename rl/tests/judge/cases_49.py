"""RiftJudge batch 49 -- unused questions from 8196-8241."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8241, "Time Warp takes the next turn, so nobody else holds")
def _():
    need("Time Warp")
    s = fresh(hand=[T.id_of("Time Warp")], runes=32)
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Time Warp")
    run(s)
    act(s, A.A_END_TURN, None, 0)
    run(s, limit=40)
    assert int(s.active) == 0, "the extra turn is yours"
    assert int(s.points[1]) == 0, "they never reached their Beginning Phase"


@case(8239, "Possession's new controller keeps the unit at their base")
def _():
    need("Possession")
    s = fresh(hand=[T.id_of("Possession")], runes=32)
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Possession", foe)
    run(s)
    assert int(s.perms[foe, P_CTRL]) == 0
    assert int(s.perms[foe, P_LOC]) == base_loc(0), "recalled to YOUR base"


@case(8238, "Ravenbloom Student grows only once the spell has resolved")
def _():
    need("Ravenbloom Student", "Discipline")
    s = fresh(runes=24)
    give(s, 0, "Discipline")
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 24
    rs = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0), ready=True)
    cast(s, 0, "Discipline", rs)
    assert combat.might(s, T, rs) == 2, "on the chain, nothing has happened yet"
    run(s)
    assert combat.might(s, T, rs) == 2 + 2 + 1


@case(8236, "a Ravenbloom Student Gusted in response never grows")
def _():
    need("Ravenbloom Student", "Gust")
    s = fresh(runes=24)
    give(s, 0, "Gust")
    s.bf_ctrl[0] = 0
    rs = s.add_permanent(T.id_of("Ravenbloom Student"), 0, bf_loc(0), ready=True)
    assert combat.might(s, T, rs) == 2
    cast(s, 0, "Gust", rs)
    run(s)
    assert not alive(s, rs), "3 Might or less, and it went home to hand"


@case(8235, "Hextech Ray's target is chosen at cast and rechecked at resolution")
def _():
    need("Hextech Ray", "Retreat")
    s = fresh(hand=[T.id_of("Hextech Ray")], runes=24)
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Hextech Ray", u)
    cast(s, 1, "Retreat", u)
    run(s)
    assert not alive(s, u), "it left before the Ray resolved"


@case(8233, "a permanent played from hidden finalizes and resolves at once")
def _():
    need("Tideturner", "Smoke Screen")
    s = fresh(runes=24)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    slot = hidden_at(s, 0, 0, "Tideturner")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    assert perm_of(s, "Tideturner", 0), "it is on the board already"


@case(8232, "[Assault] needs no trigger, so there is no window for it")
def _():
    need("Cleave")
    s = fresh(runes=24)
    give(s, 0, "Cleave")
    s.bf_ctrl[0] = 1
    att = body(s, 0, base_loc(0), 3, ready=True)
    body(s, 1, bf_loc(0), 9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 24
    attack(s, 0, 0, att)
    cast(s, 0, "Cleave", att)
    drain(s)
    assert combat.might(s, T, att) == 6, "3 plus [Assault 3], with no chain item"


@case(8230, "Volibear, Furious killed in response deals nothing")
def _():
    need("Volibear - Furious", "Hidden Blade")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    vb = s.add_permanent(T.id_of("Volibear - Furious"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 4)
    slot = hidden_at(s, 1, 0, "Hidden Blade")
    s.bf_ctrl[0] = 1
    attack(s, 0, 0, vb)
    pass_priority_to(s, 1)
    act(s, A.A_PLAY_HIDDEN, slot, 1)
    choose(s, vb)
    run(s, limit=40)
    assert not alive(s, vb)
    assert int(s.perms[d, P_DMG]) == 0, "383.2.c.2: no source, no 'here'"


@case(8226, "a trigger belongs to whoever controlled its source when it fired")
def _():
    need("Hostile Takeover", "Yasuo - Remorseful")
    s = fresh(runes=32)
    give(s, 1, "Hostile Takeover")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, ya)
    choose(s, d)
    drain(s)
    assert int(s.perms[d, P_DMG]) == 6, "his controller at the time dealt it"


@case(8223, "you order two conquer triggers, so a spent buff can come back")
def _():
    need("Monastery of Hirana", "Sett, Brawler", "Warmog's Armor")
    s = fresh(runes=24)
    s.bf_card[0] = T.id_of("Monastery of Hirana")
    s.bf_ctrl[0] = 1
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    s.set_flag(sett, F_BUFFED)
    before = int(s.n_hand[0])
    attack(s, 0, 0, sett)
    run(s, picking(accept=True), limit=40)
    assert int(s.n_hand[0]) == before + 1, "the Monastery spent the buff to draw"
    assert s.has_flag(sett, F_BUFFED), "and his own conquer buff refilled it"


@case(8222, "a 0 Might unit survives until something damages it")
def _():
    need("Frostcoat Cub", "Stupefy")
    s = fresh(runes=24)
    give(s, 0, "Stupefy", "Stupefy")
    u = body(s, 1, base_loc(1), 2)
    cast(s, 0, "Stupefy", u)
    run(s)
    cast(s, 0, "Stupefy", u)
    run(s)
    assert alive(s, u), "142.2.a wants nonzero damage"
    assert combat.might(s, T, u) == 1, "and Stupefy floors at 1"


@case(8221, "the player who contested the ground is the attacker, and loses it")
def _():
    need("Facebreaker", "Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Facebreaker")
    give(s, 1, "Ride The Wind")
    s.runes_ready[1, :] = 32
    att = body(s, 0, base_loc(0), 3, ready=True)
    d = body(s, 1, base_loc(1), 3, ready=False)
    attack(s, 0, 0, att)
    cast(s, 1, "Ride The Wind", d, bf_loc(0))
    drain(s)
    cast(s, 0, "Facebreaker", att, d)
    fight(s)
    assert s.has_flag(att, F_STUNNED) or not alive(s, att)
    assert int(s.bf_ctrl[0]) == 1, "the defender kept the ground"


@case(8218, "a unit recalled by a save keeps its 'this turn' Might")
def _():
    need("Primal Strength", "Zhonya's Hourglass", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade"), T.id_of("Primal Strength")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Primal Strength", u)
    run(s)
    assert combat.might(s, T, u) == 10
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u) and combat.might(s, T, u) == 10, "only damage is cleared"


@case(8213, "Zhonya's Hourglass replaces a death and never uses the chain")
def _():
    need("Zhonya's Hourglass", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=24)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u) and not alive(s, z)
    assert int(s.n_chain) == 0, "nothing of it was ever a chain item"


@case(8211, "Dropboarder counts your gear as its trigger resolves")
def _():
    need("Dropboarder", "Cloth Armor")
    s = fresh(hand=[T.id_of("Dropboarder"), T.id_of("Cloth Armor")], runes=24)
    s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    body(s, 0, base_loc(0), 3, ready=True)
    act(s, A.A_PLAY, hand_index(s, 0, "Dropboarder"), 0)
    choose(s, base_loc(0))
    run(s, picking(accept=True), limit=40)
    db = perm_of(s, "Dropboarder", 0)[0]
    assert int(s.perms[db, P_READY]) == 0, "one gear only, so no ready"


@case(8210, "Ravenbloom Student's own trigger resolves before the damage")
def _():
    need("Ravenbloom Student", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=24)
    rs = s.add_permanent(T.id_of("Ravenbloom Student"), 1, base_loc(1), ready=True)
    cast(s, 0, "Falling Star", rs, rs)
    run(s)
    assert not alive(s, rs), "6 damage against 2 Might, whatever the order"


@case(8203, "Baited Hook whose kill was replaced plays nothing")
def _():
    need("Baited Hook", "Zhonya's Hourglass", "Riptide Rex")
    s = fresh(runes=32)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, base_loc(0), 5)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    s.death_guard[0] = z
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Riptide Rex")
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, 0, base_loc(0), accept=True), limit=60)
    assert alive(s, victim), "the Hourglass replaced the kill"
    assert not perm_of(s, "Riptide Rex", 0), "so nothing was killed, and none played"


@case(8198, "Gust on Vanguard Captain in response leaves her trigger empty")
def _():
    need("Vanguard Captain", "Gust")
    s = fresh(hand=[T.id_of("Vanguard Captain")], runes=24)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.cards_played[0] = 1
    act(s, A.A_PLAY, hand_index(s, 0, "Vanguard Captain"), 0)
    choose(s, bf_loc(0))
    cap = perm_of(s, "Vanguard Captain", 0)[0]
    cast(s, 1, "Gust", cap)
    run(s)
    assert not alive(s, cap), "3 Might, and off she goes"
    assert len(tokens(s, 0)) == 0, "her [Legion] tokens had nowhere to land"


@case(8196, "control is never lost in the middle of an ability resolving")
def _():
    need("Tideturner", "Gust")
    s = fresh(runes=24)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    mate = body(s, 0, base_loc(0), 3)
    slot = hidden_at(s, 0, 0, "Tideturner")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    tt = perm_of(s, "Tideturner", 0)[0]
    act(s, A.A_ACCEPT, None, 0)
    choose(s, mate)
    cast(s, 1, "Gust")
    choose(s, tt)
    run(s)
    assert not alive(s, tt), "the Tideturner went back to hand"
    assert int(s.points[1]) == 0, "187.4: no Cleanup ran inside the resolution"
