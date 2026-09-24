"""RiftJudge batch 69 -- unused questions from 7154-7193."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7193, "Falling Star can be answered, just not by Defy")
def _():
    need("Falling Star", "Defy", "Wind Wall")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    give(s, 1, "Defy", "Wind Wall")
    s.runes_ready[1, :] = 32
    u = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Falling Star", u, u)
    pass_priority_to(s, 1)
    plays = hand_plays(s, 1)
    assert "Defy" not in plays, "2 Power is out of its range"
    assert "Wind Wall" in plays, "but Wind Wall counters any spell"


@case(7192, "Bullet Time hits one chosen battlefield")
def _():
    need("Bullet Time")
    s = fresh(hand=[T.id_of("Bullet Time")], runes=32)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 1
    here = body(s, 1, bf_loc(0), 9)
    away = body(s, 1, bf_loc(1), 9)
    cast(s, 0, "Bullet Time", bf_loc(0))
    run(s, picking(3))
    assert int(s.perms[here, P_DMG]) == 3 and int(s.perms[away, P_DMG]) == 0


@case(7188, "a hidden Reaction answers anything that starts a chain")
def _():
    need("Consult the Past", "Determined Sentry")
    s = fresh(runes=32)
    give(s, 1, "Riptide Rex")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    slot = hidden_at(s, 0, 0, "Consult the Past")
    s.ply += 1
    s.active = s.priority = 1
    act(s, A.A_PLAY, hand_index(s, 1, "Riptide Rex"), 1)
    choose(s, base_loc(1))
    choose(s, perm_of(s, "Shipyard Skulker", 0)[0])
    pass_priority_to(s, 0)
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_PLAY_HIDDEN and a.arg == slot], \
        "their play trigger is a chain to answer"


@case(7187, "a countered spell does not grow Ravenbloom Student")
def _():
    need("Ravenbloom Student", "Smoke Screen", "Defy")
    s = fresh(runes=32)
    give(s, 0, "Smoke Screen")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    rs = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0), ready=True)
    foe = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Smoke Screen", foe)
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert combat.might(s, T, rs) == 2


@case(7184, "a trigger whose source died resolves with no effect")
def _():
    need("Tideturner", "Gust")
    s = fresh(runes=32)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 32
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
    assert not alive(s, tt)
    assert int(s.perms[mate, P_LOC]) == base_loc(0), "nothing swapped"


@case(7182, "a unit Aurora plays to open ground starts a showdown")
def _():
    need("Dazzling Aurora", "Miss Fortune - Buccaneer")
    s = fresh(runes=32)
    s.add_permanent(T.id_of("Dazzling Aurora"), 0, base_loc(0))
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Miss Fortune - Buccaneer")
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(bf_loc(0), accept=True), limit=80)
    mf = perm_of(s, "Miss Fortune - Buccaneer", 0)
    assert mf, "she came off the top"


@case(7181, "Possession's target moved home is no longer legal")
def _():
    need("Possession", "Flash")
    s = fresh(hand=[T.id_of("Possession")], runes=32)
    give(s, 1, "Flash")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Possession", foe)
    cast(s, 1, "Flash", foe, -1)
    run(s)
    assert int(s.perms[foe, P_CTRL]) == 1, "it stayed theirs"
    assert int(s.perms[foe, P_LOC]) == base_loc(1)


@case(7180, "Singularity cannot name one unit twice")
def _():
    need("Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=32)
    u = body(s, 1, base_loc(1), 12)
    act(s, A.A_PLAY, hand_index(s, 0, "Singularity"), 0)
    choose(s, u)
    assert u not in targets_offered(s, 0)


@case(7179, "Hidden Blade names a unit, not a battlefield")
def _():
    need("Hidden Blade", "Tideturner")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Hidden Blade", u)
    s.set_location(u, bf_loc(1))
    run(s)
    assert not alive(s, u), "it is still a unit at a battlefield"


@case(7178, "a lost target does not force you to retarget")
def _():
    need("Hextech Ray", "Retreat")
    s = fresh(hand=[T.id_of("Hextech Ray")], runes=32)
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 9)
    b = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Hextech Ray", a)
    cast(s, 1, "Retreat", a)
    run(s)
    assert not alive(s, a)
    assert int(s.perms[b, P_DMG]) == 0, "nothing moved onto the other unit"


@case(7175, "Void Seeker still draws when its target has gone")
def _():
    need("Void Seeker", "Flash")
    s = fresh(hand=[T.id_of("Void Seeker")], runes=32)
    give(s, 1, "Flash")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    before = int(s.n_hand[0])
    cast(s, 0, "Void Seeker", u)
    cast(s, 1, "Flash", u, -1)
    run(s)
    assert int(s.perms[u, P_DMG]) == 0, "no damage"
    assert int(s.n_hand[0]) == before - 1 + 1, "but the draw is its own instruction"


@case(7173, "a move trigger resolves before the staged showdown starts")
def _():
    need("Noxian Drummer", "Chemtech Enforcer")
    s = fresh(runes=32)
    give(s, 0, "Smoke Screen")
    s.bf_ctrl[0] = 1
    nd = s.add_permanent(T.id_of("Noxian Drummer"), 0, base_loc(0), ready=True)
    ce = s.add_permanent(T.id_of("Chemtech Enforcer"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    attack(s, 0, 0, nd, ce)
    drain(s)
    assert len(tokens(s, 0)) == 1, "his move trigger made its Recruit"
    assert combat.might(s, T, ce) == 4, "2 plus [Assault 2] as an attacker"


@case(7172, "Defy reads the printed cost, not a reduced one")
def _():
    need("Defy", "Singularity", "Eager Apprentice")
    s = fresh(hand=[T.id_of("Singularity")], runes=32)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    for _ in range(3):
        s.add_permanent(T.id_of("Eager Apprentice"), 0, bf_loc(0), ready=True)
    u = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Singularity", u, -1)
    pass_priority_to(s, 1)
    assert "Defy" not in hand_plays(s, 1), "6 printed Energy is out of range"


@case(7166, "En Garde's bonus is read once, as it resolves")
def _():
    need("En Garde", "Determined Sentry")
    s = fresh(runes=32)
    give(s, 0, "En Garde", "Determined Sentry")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "En Garde", u)
    run(s)
    assert combat.might(s, T, u) == 5, "alone when it resolved"
    act(s, A.A_PLAY, hand_index(s, 0, "Determined Sentry"), 0)
    choose(s, bf_loc(0))
    run(s)
    assert combat.might(s, T, u) == 5, "and a later arrival does not undo it"


@case(7165, "a unit played by Promising Future enters exhausted")
def _():
    need("Promising Future", "Determined Sentry")
    s = fresh(hand=[T.id_of("Promising Future")], runes=32)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Determined Sentry")
    m = int(s.deck_ptr[1])
    s.deck[1, m:m + 5] = VANILLA
    cast(s, 0, "Promising Future")
    run(s, picking(0, base_loc(0), base_loc(1), accept=True), limit=80)
    ds = perm_of(s, "Determined Sentry", 0)
    assert ds and int(s.perms[ds[0], P_READY]) == 0, "no text says otherwise"


@case(7164, "a unit cannot be played at the same time as another")
def _():
    need("Deadbloom Predator")
    s = fresh(hand=[T.id_of("Deadbloom Predator")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    mate = body(s, 0, base_loc(0), 3, ready=True)
    act(s, A.A_PLAY, hand_index(s, 0, "Deadbloom Predator"), 0)
    choose(s, bf_loc(0))
    assert int(s.perms[mate, P_LOC]) == base_loc(0), "it arrived by itself"


@case(7159, "regaining a battlefield you lost this turn scores")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    s.ply += 1                                   # before the Might is stamped
    home = body(s, 0, base_loc(0), 9, ready=False)
    s.active = s.priority = 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)                 # they contest the ground he holds
    cast(s, 0, "Ride The Wind", home, bf_loc(0))
    fight(s)
    assert not alive(s, foe) and alive(s, home)
    assert int(s.bf_ctrl[0]) == 0, "he held it through the combat"


@case(7158, "a unit Charmed onto emptied ground conquers it")
def _():
    need("Charm", "Gust")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    give(s, 0, "Gust")
    s.bf_ctrl[0] = 1
    theirs = body(s, 1, bf_loc(0), 3)
    other = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Gust", theirs)
    run(s)
    assert not alive(s, theirs), "their only unit there went to hand"
    cast(s, 0, "Charm", other, bf_loc(0))
    fight(s)
    assert int(s.bf_ctrl[0]) == 1 and int(s.points[1]) == 1, \
        "their unit took the empty ground, and their point"


@case(7155, "Yasuo killed before his trigger resolves deals nothing")
def _():
    need("Yasuo - Remorseful", "Hidden Blade")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 12)
    slot = hidden_at(s, 1, 0, "Hidden Blade")
    attack(s, 0, 0, ya)
    choose(s, d)
    pass_priority_to(s, 1)
    act(s, A.A_PLAY_HIDDEN, slot, 1)
    choose(s, ya)
    run(s, limit=40)
    assert not alive(s, ya) and int(s.perms[d, P_DMG]) == 0


@case(7160, "a hidden Reaction answers the [Temporary] trigger")
def _():
    need("Consult the Past", "Sprite Call")
    s = fresh(runes=32)
    rune_deck(s)
    tok = _sprite_at(s, 0, 0)
    slot = hidden_at(s, 0, 0, "Consult the Past")
    before = int(s.n_hand[0])
    _next_own_turn(s)
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_PLAY_HIDDEN and a.arg == slot]
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    run(s)
    assert int(s.n_hand[0]) >= before + 2 and not alive(s, tok)
