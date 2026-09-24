"""RiftJudge batch 54 -- unused questions from 7949-8003."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8003, "Kinkou Monk's 'up to two' reaches the chain with one friend")
def _():
    need("Kinkou Monk")
    s = fresh(hand=[T.id_of("Kinkou Monk")], runes=32)
    mate = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Kinkou Monk"), 0)
    choose(s, base_loc(0))
    run(s, picking(mate, -1))
    assert s.has_flag(mate, F_BUFFED), "the one friend it had"


@case(8001, "Call to Glory's spent buff need not be the unit it pumps")
def _():
    need("Call to Glory")
    s = fresh(runes=32)
    give(s, 0, "Call to Glory")
    holder = body(s, 0, base_loc(0), 3)
    s.set_flag(holder, F_BUFFED)
    other = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY_REPEAT, hand_index(s, 0, "Call to Glory"), 0)
    run(s, picking(other))
    assert not s.has_flag(holder, F_BUFFED), "his buff paid for it"
    assert combat.might(s, T, other) == 6, "and the other one grew"


@case(7997, "Discipline still draws when its target is gone")
def _():
    need("Discipline", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Discipline")
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    before = int(s.n_hand[0])
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Gust", u)
    run(s)
    assert not alive(s, u)
    assert int(s.n_hand[0]) == before - 1 + 1 + 1, "the unit back, and the draw"


@case(7993, "Dazzling Aurora stays put and fires every turn")
def _():
    need("Dazzling Aurora")
    s = fresh(runes=32)
    da = s.add_permanent(T.id_of("Dazzling Aurora"), 0, base_loc(0))
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Determined Sentry")
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(base_loc(0), accept=True), limit=60)
    assert alive(s, da) and int(s.perms[da, P_READY]) == 1, \
        "neither killed nor exhausted"


@case(7983, "the heal comes before the passive it depended on is gone")
def _():
    need("Cannon Barrage")
    s = fresh(runes=32)
    give(s, 1, "Cannon Barrage")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    a = body(s, 0, base_loc(0), 5, ready=True)
    b = body(s, 0, base_loc(0), 5, ready=True)
    body(s, 1, bf_loc(0), 1)
    attack(s, 0, 0, a, b)
    cast(s, 1, "Cannon Barrage")
    fight(s)
    assert alive(s, a) and alive(s, b), "3 damage against 5 Might, then healed"
    assert int(s.perms[a, P_DMG]) == 0


@case(7979, "Ride the Wind exhausts nothing, so a recall comes home ready")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3, ready=True)
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(1), 9)
    cast(s, 0, "Ride The Wind", u, bf_loc(1))
    fight(s)
    assert int(s.perms[u, P_READY]) == 1, "it was never exhausted for the move"


@case(7978, "Singularity reaches a base as readily as a battlefield")
def _():
    need("Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=32)
    s.bf_ctrl[0] = 1
    at_bf = body(s, 1, bf_loc(0), 5)
    at_base = body(s, 1, base_loc(1), 5)
    act(s, A.A_PLAY, hand_index(s, 0, "Singularity"), 0)
    offered = targets_offered(s, 0)
    assert at_bf in offered and at_base in offered


@case(7976, "Kraken Hunter's spent buffs cut its Power")
def _():
    need("Kraken Hunter")
    s = fresh(hand=[T.id_of("Kraken Hunter")], runes=32)
    a = body(s, 0, base_loc(0), 3)
    s.set_flag(a, F_BUFFED)
    before = runes(s, 0)
    act(s, A.A_PLAY, hand_index(s, 0, "Kraken Hunter"), 0)
    choose(s, a)                                 # spend his buff as the cost
    choose(s, base_loc(0))
    run(s)
    assert perm_of(s, "Kraken Hunter", 0), "it came down"
    assert alive(s, a) and not s.has_flag(a, F_BUFFED), "the buff went, not the unit"
    assert before - runes(s, 0) == 1, "2 Power, one of them paid by the buff"


@case(7970, "Blastcone Fae bounced in response still gives its -2")
def _():
    need("Blastcone Fae", "Gust")
    s = fresh(runes=32)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    foe = body(s, 1, bf_loc(0), 5)
    slot = hidden_at(s, 0, 0, "Blastcone Fae")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    bf = perm_of(s, "Blastcone Fae", 0)[0]
    choose(s, foe)
    cast(s, 1, "Gust", bf)
    run(s)
    assert not alive(s, bf), "2 Might, and back to hand it goes"
    assert combat.might(s, T, foe) == 3, "the ability had already been placed"


@case(7959, "Meditation's exhausted unit is a cost, not a choice")
def _():
    need("Meditation", "The Dreaming Tree")
    s = fresh(hand=[T.id_of("Meditation")], runes=32)
    s.bf_card[0] = T.id_of("The Dreaming Tree")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3, ready=True)
    before = int(s.n_hand[0])
    cast(s, 0, "Meditation", repeat=True)
    run(s, picking(u))
    assert int(s.n_hand[0]) == before - 1 + 2, "two drawn, and the Tree slept"


@case(7957, "Fox-Fire's targets are locked before anyone can answer")
def _():
    need("Fox-Fire", "Determined Sentry")
    s = fresh(hand=[T.id_of("Fox-Fire")], runes=32)
    give(s, 1, "Rengar - Pouncing")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    small = body(s, 1, bf_loc(0), 2)
    act(s, A.A_PLAY, hand_index(s, 0, "Fox-Fire"), 0)
    choose(s, small)
    for _ in range(3):
        choose(s, -1)                            # it offers four slots
    late = s.add_permanent(T.id_of("Determined Sentry"), 1, bf_loc(0), ready=True)
    run(s)
    assert not alive(s, small) and alive(s, late), "it was never chosen"


@case(7953, "Fight or Flight leaves a ready unit ready")
def _():
    need("Fight or Flight")
    s = fresh(hand=[T.id_of("Fight or Flight")], runes=32)
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3, ready=True)
    cast(s, 0, "Fight or Flight", u)
    run(s)
    assert int(s.perms[u, P_LOC]) == base_loc(0) and int(s.perms[u, P_READY]) == 1


@case(7952, "a cost paid on the way in is not re-checked")
def _():
    need("Sky Splitter", "Smoke Screen")
    s = fresh(hand=[T.id_of("Sky Splitter")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    big = body(s, 0, base_loc(0), 8)
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Sky Splitter", foe)
    cast(s, 1, "Smoke Screen", big)
    run(s)
    assert int(s.perms[foe, P_DMG]) == 5, "it resolved, whatever their answer"


@case(7951, "Viktor, Innovator is gone before the card is played")
def _():
    need("Viktor, Innovator", "Retreat")
    s = fresh(runes=32)
    give(s, 0, "Retreat")
    vi = s.add_permanent(T.id_of("Viktor, Innovator"), 0, base_loc(0), ready=True)
    s.ply += 1
    s.active = s.priority = 1
    s.active = s.priority = 0
    cast(s, 0, "Retreat", vi)
    run(s)
    assert not alive(s, vi), "he went back to hand"
    assert not tokens(s, 0), "and was not there to see the card played"


@case(7949, "Charm cannot push a unit into a base that is not its own")
def _():
    need("Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    foe = body(s, 1, base_loc(1), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Charm"), 0)
    choose(s, foe)
    where = targets_offered(s, 0)
    assert base_loc(0) not in where, "never into your base"
    assert bf_loc(0) in where


@case(7977, "Find Your Center still costs what you cannot pay")
def _():
    need("Find Your Center")
    s = fresh(runes=0)
    give(s, 0, "Find Your Center")
    s.runes_ready[0, :] = 0
    s.runes_ready[0, 0] = 1
    assert "Find Your Center" not in hand_plays(s, 0), "3 Energy, and 1 rune up"
    s.runes_ready[0, 0] = 3
    assert "Find Your Center" in hand_plays(s, 0)


@case(7974, "Trifarian War Camp's +1 is a battlefield static, not a play event")
def _():
    need("Trifarian War Camp", "Fiora - Grand Duelist", "Determined Sentry")
    s = fresh(hand=[T.id_of("Determined Sentry")], runes=32)
    s.bf_card[0] = T.id_of("Trifarian War Camp")
    s.bf_ctrl[0] = 0
    s.legend[0], s.legend_ready[0] = T.id_of("Fiora - Grand Duelist"), 1
    act(s, A.A_PLAY, hand_index(s, 0, "Determined Sentry"), 0)
    choose(s, bf_loc(0))
    run(s, picking(accept=True), limit=20)
    ds = perm_of(s, "Determined Sentry", 0)[0]
    assert combat.might(s, T, ds) == 2, "1 printed plus the ground's +1"
    assert int(s.legend_ready[0]) == 1, "never Mighty, so Fiora slept"


@case(7958, "a hidden unit flipped after the sweep was never in it")
def _():
    need("Unchecked Power", "Teemo - Strategist")
    s = fresh(hand=[T.id_of("Unchecked Power")], runes=32)
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 5)
    slot = hidden_at(s, 1, 0, "Teemo - Strategist")
    cast(s, 0, "Unchecked Power")
    run(s)
    assert not alive(s, d), "12 damage to all units at battlefields"
    assert int(s.fd_card[slot]) < 0 or not perm_of(s, "Teemo - Strategist", 1)


@case(7980, "a Deathknell waits for the ability that killed it to finish")
def _():
    need("Baited Hook", "Honest Broker", "Determined Sentry")
    s = fresh(runes=32)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    hb = s.add_permanent(T.id_of("Honest Broker"), 0, base_loc(0), ready=True)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Determined Sentry")
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(hb, 0, base_loc(0), accept=True), limit=60)
    assert not alive(s, hb)
    assert perm_of(s, "Determined Sentry", 0), "the Hook finished first"
    assert tokens(s, 0), "and then the Deathknell paid out"
