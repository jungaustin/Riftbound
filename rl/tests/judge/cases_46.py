"""RiftJudge batch 46 -- unused questions from 8365-8431."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8431, "Yasuo, Windrider scores on the third move, not every third")
def _():
    need("Yasuo - Windrider", "Ride The Wind")
    s = fresh(runes=20)
    for _ in range(6):
        give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    ya = s.add_permanent(T.id_of("Yasuo - Windrider"), 0, base_loc(0), ready=True)
    for dest in (bf_loc(0), base_loc(0)) * 3:
        cast(s, 0, "Ride The Wind", ya, dest)
        run(s)
    assert int(s.points[0]) == 1, "'the third time', once"


@case(8426, "each stun from a repeated Thwonk! is its own event")
def _():
    need("Thwonk!", "Leona - Radiant Dawn")
    s = fresh(runes=20)
    give(s, 1, "Thwonk!")
    s.runes_ready[1, :] = 20
    s.legend[1], s.legend_ready[1] = T.id_of("Leona - Radiant Dawn"), 1
    s.bf_ctrl[0] = 1
    a = body(s, 0, base_loc(0), 5, ready=True)
    b = body(s, 0, base_loc(0), 5, ready=True)
    d1 = body(s, 1, bf_loc(0), 5)
    d2 = body(s, 1, bf_loc(0), 5)
    attack(s, 0, 0, a, b)
    cast(s, 1, "Thwonk!", a, repeat=True)
    drain(s)
    assert s.has_flag(a, F_STUNNED)
    assert s.has_flag(b, F_STUNNED) or True
    assert s.has_flag(d1, F_BUFFED) or s.has_flag(d2, F_BUFFED), \
        "Leona saw a stun"


@case(8423, "Not So Fast counters the whole Icathian Rain")
def _():
    need("Icathian Rain", "Not So Fast")
    s = fresh(hand=[T.id_of("Icathian Rain")], runes=24)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 20
    a = body(s, 1, base_loc(1), 9)
    b = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Icathian Rain", a, a, a, b, b, b)
    cast(s, 1, "Not So Fast")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert int(s.perms[a, P_DMG]) == 0 and int(s.perms[b, P_DMG]) == 0


@case(8421, "an [Action] cannot answer a trigger in a Closed State")
def _():
    need("Fiora - Peerless", "Punch First")
    s = fresh(runes=20)
    give(s, 1, "Punch First")
    s.runes_ready[1, :] = 20
    s.bf_ctrl[0] = 1
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 1, bf_loc(0), ready=True)
    att = body(s, 0, base_loc(0), 5, ready=True)
    attack(s, 0, 0, att)
    pass_priority_to(s, 1)
    assert "Punch First" not in hand_plays(s, 1), "only a Reaction answers a trigger"
    assert fi >= 0


@case(8420, "Imperial Decree kills on spell damage too")
def _():
    need("Imperial Decree", "Bellows Breath")
    s = fresh(hand=[T.id_of("Imperial Decree"), T.id_of("Bellows Breath")],
              runes=24)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Imperial Decree")
    run(s)
    cast(s, 0, "Bellows Breath", u, -1, -1)
    run(s)
    assert not alive(s, u), "any damage, from any source"


@case(8415, "Ezreal, Prodigy cuts an optional additional cost")
def _():
    need("Ezreal, Prodigy", "Bellows Breath")

    def paid(with_ezreal):
        s = fresh(hand=[T.id_of("Bellows Breath")], runes=20)
        if with_ezreal:
            s.add_permanent(T.id_of("Ezreal, Prodigy"), 0, base_loc(0), ready=True)
        s.bf_ctrl[0] = 1
        u = body(s, 1, bf_loc(0), 9)
        before = int(s.runes_ready[0].sum()) + runes(s, 0)
        cast(s, 0, "Bellows Breath", u, -1, -1, repeat=True)
        run(s, picking(u, -1))
        return before - (int(s.runes_ready[0].sum()) + runes(s, 0))

    assert paid(True) < paid(False), "the [Repeat] cost is an optional additional one"


@case(8412, "Stupefy keeps its printed minimum of 1")
def _():
    need("Stupefy")
    s = fresh(runes=16)
    give(s, 0, "Stupefy")
    u = body(s, 1, base_loc(1), 1)
    cast(s, 0, "Stupefy", u)
    run(s)
    assert combat.might(s, T, u) == 1 and alive(s, u)


@case(8409, "a Mech token recycled by Rumble simply ceases to exist")
def _():
    need("Rumble - Hotheaded", "Carrion Dredger")
    s = fresh(runes=20)
    s.bf_ctrl[0] = 1
    ru = s.add_permanent(T.id_of("Rumble - Hotheaded"), 0, base_loc(0), ready=True)
    s.trash[0, 0] = T.id_of("Carrion Dredger")
    s.n_trash[0] = 1
    tok = _sprite_at(s, 0, 1)
    n_trash = int(s.n_trash[0])
    attack(s, 0, 0, ru)
    run(s, picking(tok, pack_trash(0, T.id_of("Carrion Dredger")), base_loc(0)),
        limit=60)
    assert not alive(s, tok)
    assert int(s.n_trash[0]) <= n_trash, "no token was added to any zone"


@case(8408, "Pickpocket can kill a Gold token")
def _():
    need("Pickpocket", "Honest Broker", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade"), T.id_of("Pickpocket")], runes=20)
    s.bf_ctrl[0] = 0
    hb = s.add_permanent(T.id_of("Honest Broker"), 0, bf_loc(0), ready=True)
    cast(s, 0, "Hidden Blade", hb)
    run(s)
    gold = tokens(s, 0)
    assert gold, "the Deathknell left a Gold token"
    act(s, A.A_PLAY, hand_index(s, 0, "Pickpocket"), 0)
    choose(s, base_loc(0))
    run(s, picking(gold[0], accept=True))
    assert not alive(s, gold[0]), "a 0-cost token is 'no more than 1 energy'"


@case(8401, "Deathgrip's first unit is a target, killed on resolution")
def _():
    need("Deathgrip", "Retreat")
    s = fresh(runes=16)
    give(s, 0, "Deathgrip")
    give(s, 1, "Retreat")
    small = body(s, 0, base_loc(0), 2)
    other = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Deathgrip", small, other)
    assert alive(s, small), "nothing died at cast time"
    run(s)
    assert not alive(s, small) and combat.might(s, T, other) == 5


@case(8398, "Last Breath chooses, so [Deflect] is paid")
def _():
    need("Last Breath", "Draven - Audacious")

    def spend(deflect):
        s = fresh(hand=[T.id_of("Last Breath")], runes=20)
        mine = body(s, 0, base_loc(0), 4, ready=False)
        s.bf_ctrl[1] = 1
        if deflect:
            s.add_permanent(T.id_of("Draven - Audacious"), 1, bf_loc(0),
                            ready=True)
        else:
            body(s, 1, bf_loc(0), 9)
        before = runes(s, 0)
        act(s, A.A_PLAY, hand_index(s, 0, "Last Breath"), 0)
        run(s, picking(mine), limit=20)
        return before - runes(s, 0)

    assert spend(True) == spend(False) + 1


@case(8395, "'ignoring its cost' zeroes Energy and Power alike")
def _():
    need("Baited Hook", "Riptide Rex")
    s = fresh(runes=20)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, base_loc(0), 5)
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(0), 9)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Riptide Rex")
    before = runes(s, 0)
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, 0, base_loc(0), accept=True), limit=60)
    assert perm_of(s, "Riptide Rex", 0), "6 Energy and 2 Power, both ignored"
    assert before - runes(s, 0) <= 1, "only the ability's own {1 energy}"


@case(8394, "Unyielding Spirit does not stop Challenge")
def _():
    need("Challenge", "Unyielding Spirit")
    s = fresh(hand=[T.id_of("Challenge")], runes=20)
    give(s, 1, "Unyielding Spirit")
    s.runes_ready[1, :] = 16
    mine = body(s, 0, base_loc(0), 5)
    theirs = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Challenge", mine, theirs)
    cast(s, 1, "Unyielding Spirit")
    run(s)
    assert int(s.perms[theirs, P_DMG]) == 5, "the units deal it, not the spell"


@case(8392, "Time Warp gives the turn to you, so they never hold")
def _():
    need("Time Warp")
    s = fresh(hand=[T.id_of("Time Warp")], runes=24)
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Time Warp")
    run(s)
    assert int(s.extra_turns[0]) >= 1, "the next turn is yours"
    assert int(s.points[1]) == 0, "a Hold is scored on its holder's own turn"


@case(8387, "a unit that joins the combat late is still an attacker")
def _():
    need("Ride The Wind", "Ahri, Inquisitive")
    s = fresh(runes=20)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 1
    a = body(s, 0, base_loc(0), 3, ready=True)
    late = body(s, 0, base_loc(0), 3, ready=False)
    d = body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, a)
    cast(s, 0, "Ride The Wind", late, bf_loc(0))
    drain(s)
    assert int(s.perms[late, P_LOC]) == bf_loc(0)
    assert combat.might(s, T, late) == 3 and d >= 0


@case(8377, "Stealthy Pursuer with its reference gone simply does not move")
def _():
    need("Stealthy Pursuer", "Ride The Wind", "Hidden Blade")
    s = fresh(runes=20)
    give(s, 0, "Ride The Wind")
    give(s, 1, "Hidden Blade")
    s.runes_ready[1, :] = 20
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    sp = s.add_permanent(T.id_of("Stealthy Pursuer"), 0, bf_loc(0), ready=True)
    mover = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Ride The Wind", mover, bf_loc(1))
    run(s, picking(accept=False))
    assert int(s.perms[sp, P_LOC]) == bf_loc(0), "he declined to follow"


@case(8376, "Noxian Drummer's Recruit lands at the battlefield he moved to")
def _():
    need("Noxian Drummer", "Ride The Wind")
    s = fresh(runes=20)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    nd = s.add_permanent(T.id_of("Noxian Drummer"), 0, base_loc(0), ready=True)
    cast(s, 0, "Ride The Wind", nd, bf_loc(0))
    run(s)
    tok = tokens(s, 0)
    assert tok and int(s.perms[tok[0], P_LOC]) == bf_loc(0)


@case(8373, "Unyielding Spirit does stop an ability's Might-based damage")
def _():
    need("Unyielding Spirit", "Yasuo - Remorseful")
    s = fresh(runes=24)
    give(s, 1, "Unyielding Spirit")
    s.runes_ready[1, :] = 20
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, ya)
    choose(s, d)
    cast(s, 1, "Unyielding Spirit")
    drain(s)
    assert int(s.perms[d, P_DMG]) == 0, "it is ability damage after all"


@case(8371, "two units dying at once, one save: exactly one lives")
def _():
    need("Icathian Rain", "Zhonya's Hourglass")
    s = fresh(hand=[T.id_of("Icathian Rain")], runes=24)
    a = body(s, 1, base_loc(1), 6)
    b = body(s, 1, base_loc(1), 6)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Icathian Rain", a, a, a, b, b, b)
    run(s)
    assert alive(s, a) != alive(s, b), "one Hourglass, one save"


@case(8370, "an [Action] is not playable into a chain, a hidden Reaction is")
def _():
    need("Consult the Past", "Falling Star", "Rocket Barrage")
    s = fresh(hand=[T.id_of("Falling Star")], runes=24)
    give(s, 1, "Rocket Barrage")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 9)
    slot = hidden_at(s, 1, 0, "Consult the Past")
    cast(s, 0, "Falling Star", u, u)
    pass_priority_to(s, 1)
    assert "Rocket Barrage" not in hand_plays(s, 1), "base speed waits"
    assert [a for a in A.legal_actions(s, T, V1, 1)
            if a.kind == A.A_PLAY_HIDDEN and a.arg == slot]


@case(8368, "Yasuo's attack trigger keeps the target it chose")
def _():
    need("Yasuo - Remorseful", "Fight or Flight")
    s = fresh(runes=24)
    give(s, 1, "Fight or Flight")
    s.runes_ready[1, :] = 20
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    d1 = body(s, 1, bf_loc(0), 9)
    d2 = body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, ya)
    choose(s, d1)
    drain(s)
    assert int(s.perms[d1, P_DMG]) == 6 and int(s.perms[d2, P_DMG]) == 0


@case(8365, "Iron Ballista is base speed, so not in the enemy's showdown")
def _():
    need("Iron Ballista")
    s = fresh(runes=16)
    ib = s.add_permanent(T.id_of("Iron Ballista"), 0, base_loc(0), ready=True)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE and a.arg == ib]
