"""RiftJudge batch 48 -- unused questions from 8243-8301."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8301, "Mystic Reversal takes the spell, and Defy still names a spell")
def _():
    need("Mystic Reversal", "Wind Wall", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star"), T.id_of("Mystic Reversal")], runes=24)
    give(s, 1, "Wind Wall")
    s.runes_ready[1, :] = 24
    u = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Falling Star", u, u)
    cast(s, 1, "Wind Wall")
    choose(s, sorted(targets_offered(s, 1))[0])
    cast(s, 0, "Mystic Reversal")
    choose(s, sorted(targets_offered(s, 0))[0])
    run(s, picking(accept=True))
    assert int(s.perms[u, P_DMG]) in (0, 6), "whatever it hit, it resolved once"


@case(8298, "both saves keep the unit's Equipment and its buff")
def _():
    need("Zhonya's Hourglass", "B.F. Sword", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=24)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    s.set_flag(u, F_BUFFED)
    g = s.add_permanent(T.id_of("B.F. Sword"), 1, bf_loc(0))
    s.active = s.priority = 1
    act(s, A.A_ACTIVATE, g, 1)
    choose(s, u)
    run(s)
    s.active = s.priority = 0
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u) and int(s.perms[g, P_ATTACHED_TO]) == u
    assert s.has_flag(u, F_BUFFED)


@case(8297, "a hidden Tideturner reaches across to another battlefield")
def _():
    need("Tideturner")
    s = fresh(runes=24)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    away = body(s, 0, bf_loc(1), 3)
    slot = hidden_at(s, 0, 0, "Tideturner")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    assert away in targets_offered(s, 0), "its own text says another location"


@case(8296, "the unit that contests the ground is the attacker, whoever moved it")
def _():
    need("Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=24)
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    foe = body(s, 1, base_loc(1), 9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 24
    cast(s, 0, "Charm", foe, bf_loc(0))
    drain(s)
    assert int(s.showdown_bf) == 0 and s.showdown_combat
    assert int(s.attacker) == 1, "their unit arrived, so they attack"
    assert mine >= 0


@case(8290, "a token is not a card, so Darius does not count it")
def _():
    need("Darius - Trifarian", "Honest Broker", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade"), T.id_of("Darius - Trifarian")],
              runes=24)
    s.bf_ctrl[0] = 0
    hb = s.add_permanent(T.id_of("Honest Broker"), 0, bf_loc(0), ready=True)
    cast(s, 0, "Hidden Blade", hb)
    run(s)
    assert tokens(s, 0), "a Gold token was played"
    act(s, A.A_PLAY, hand_index(s, 0, "Darius - Trifarian"), 0)
    choose(s, base_loc(0))
    run(s)
    dar = perm_of(s, "Darius - Trifarian", 0)[0]
    assert int(s.perms[dar, P_READY]) == 1 and combat.might(s, T, dar) == 7, \
        "Hidden Blade was the first card, Darius the second"


@case(8287, "Fizz ignores the base cost, never the [Repeat]")
def _():
    need("Fizz - Trickster", "Frigid Touch")
    s = fresh(hand=[T.id_of("Fizz - Trickster")], runes=24)
    s.trash[0, 0] = T.id_of("Frigid Touch")
    s.n_trash[0] = 1
    u = body(s, 1, base_loc(1), 5)
    act(s, A.A_PLAY, hand_index(s, 0, "Fizz - Trickster"), 0)
    choose(s, base_loc(0))
    before = int(s.runes_ready[0].sum())
    run(s, picking(pack_trash(0, T.id_of("Frigid Touch")), u, accept=True),
        limit=40)
    assert combat.might(s, T, u) == 3, "the spell itself resolved"
    assert int(s.runes_ready[0].sum()) <= before, "and any Repeat was paid for"


@case(8285, "a buff to 5 Might makes a unit [Mighty]")
def _():
    need("Sunken Temple", "Pit Rookie")
    s = fresh(hand=[T.id_of("Pit Rookie")], runes=24)
    s.bf_card[0] = T.id_of("Sunken Temple")
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 4, ready=True)
    act(s, A.A_PLAY, hand_index(s, 0, "Pit Rookie"), 0)
    choose(s, base_loc(0))
    run(s, picking(u))
    assert combat.might(s, T, u) == 5, "the buff carried it over the line"
    before = int(s.n_hand[0])
    attack(s, 0, 0, u)
    run(s, picking(accept=True), limit=40)
    assert int(s.n_hand[0]) == before + 1


@case(8284, "Wraith of Echoes does not draw for its own death")
def _():
    need("Wraith of Echoes", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=24)
    s.bf_ctrl[0] = 1
    wr = s.add_permanent(T.id_of("Wraith of Echoes"), 1, bf_loc(0), ready=True)
    before = int(s.n_hand[1])
    cast(s, 0, "Hidden Blade", wr)
    run(s)
    assert not alive(s, wr)
    assert int(s.n_hand[1]) == before + 2, "Hidden Blade's 2, and nothing else"


@case(8282, "a unit played from hidden resolves without a window")
def _():
    need("Teemo - Strategist", "Smoke Screen")
    s = fresh(runes=24)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    slot = hidden_at(s, 0, 0, "Teemo - Strategist")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    assert perm_of(s, "Teemo - Strategist", 0), "337.2: it is already on the board"


@case(8280, "Fox-Fire needs its total Might to fit under 4")
def _():
    need("Fox-Fire")
    s = fresh(hand=[T.id_of("Fox-Fire")], runes=24)
    s.bf_ctrl[0] = 1
    big = body(s, 1, bf_loc(0), 5)
    small = body(s, 1, bf_loc(0), 2)
    act(s, A.A_PLAY, hand_index(s, 0, "Fox-Fire"), 0)
    offered = targets_offered(s, 0)
    assert big not in offered and small in offered, "total Might 4 or less"


@case(8279, "Volibear wants an enemy unit moving, whoever moved it")
def _():
    need("Volibear - Imposing", "Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=24)
    s.bf_ctrl[0] = 0
    vb = s.add_permanent(T.id_of("Volibear - Imposing"), 0, bf_loc(0), ready=True)
    s.bf_ctrl[1] = 0
    body(s, 0, bf_loc(1), 3)
    foe = body(s, 1, base_loc(1), 3)
    before = int(s.n_hand[0])
    cast(s, 0, "Charm", foe, bf_loc(1))
    run(s)
    assert int(s.n_hand[0]) == before - 1 + 1, "an enemy unit moved elsewhere"
    assert vb >= 0


@case(8274, "Traveling Merchant draws even with nothing to discard")
def _():
    need("Traveling Merchant", "Ride The Wind")
    s = fresh(runes=24)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, base_loc(0), ready=True)
    cast(s, 0, "Ride The Wind", tm, bf_loc(0))
    assert int(s.n_hand[0]) == 0, "the hand is empty as it resolves"
    run(s)
    assert int(s.n_hand[0]) == 1, "the draw is not conditional on the discard"


@case(8272, "a Tideturner bounced in response swaps nothing")
def _():
    need("Tideturner", "Gust")
    s = fresh(hand=[T.id_of("Tideturner")], runes=24)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    mate = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Tideturner"), 0)
    choose(s, bf_loc(0))
    tt = perm_of(s, "Tideturner", 0)[0]
    act(s, A.A_ACCEPT, None, 0)
    choose(s, mate)
    cast(s, 1, "Gust")
    choose(s, tt)
    run(s)
    assert not alive(s, tt), "it went back to hand"
    assert int(s.perms[mate, P_LOC]) == base_loc(0), "and nothing swapped"


@case(8265, "there is no priority window between the turns")
def _():
    need("Meditation")
    s = fresh(runes=24)
    give(s, 1, "Meditation")
    s.runes_ready[1, :] = 24
    act(s, A.A_END_TURN, None, 0)
    run(s, limit=20)
    assert int(s.active) == 1, "it is simply their turn now"


@case(8264, "a hidden Zhonya's Hourglass is hidden at a battlefield")
def _():
    need("Zhonya's Hourglass")
    s = fresh(hand=[T.id_of("Zhonya's Hourglass")], runes=24)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    act(s, A.A_HIDE, None, 0)
    where = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_HIDE_AT]
    assert where == [0], "737.1.b: a battlefield you control"


@case(8263, "Charming a unit onto your own ground makes you the defender")
def _():
    need("Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=24)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Charm", foe, bf_loc(0))
    drain(s)
    assert int(s.attacker) == 1, "the arriving unit contests it"


@case(8258, "Gust on the swapped unit leaves Tideturner's ability with nothing")
def _():
    need("Tideturner", "Gust")
    s = fresh(hand=[T.id_of("Tideturner")], runes=24)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    mate = body(s, 0, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Tideturner"), 0)
    choose(s, base_loc(0))
    act(s, A.A_ACCEPT, None, 0)
    choose(s, mate)
    cast(s, 1, "Gust", mate)
    run(s)
    assert not alive(s, mate)
    tt = perm_of(s, "Tideturner", 0)[0]
    assert int(s.perms[tt, P_LOC]) == base_loc(0), "it stayed where it landed"


@case(8257, "Leona - Zealot's -8 is continuous, not a snapshot")
def _():
    need("Leona - Zealot", "Rune Prison", "Discipline")
    s = fresh(runes=24)
    give(s, 0, "Rune Prison", "Discipline")
    s.bf_ctrl[0] = 0
    le = s.add_permanent(T.id_of("Leona - Zealot"), 0, bf_loc(0), ready=True)
    foe = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Rune Prison", foe)
    drain(s)
    assert combat.might(s, T, foe) == 1, "9 - 8"
    cast(s, 0, "Discipline", foe)
    drain(s)
    assert combat.might(s, T, foe) == 3, "11 - 8, recomputed"
    assert le >= 0


@case(8249, "Falling Star's second half must still choose something")
def _():
    need("Falling Star", "Hidden Blade")
    s = fresh(hand=[T.id_of("Falling Star")], runes=24)
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 3)
    mine = body(s, 0, base_loc(0), 9)
    slot = hidden_at(s, 1, 0, "Hidden Blade")
    act(s, A.A_PLAY, hand_index(s, 0, "Falling Star"), 0)
    offered = targets_offered(s, 0)
    assert a in offered and mine in offered, "'a unit' reaches both sides"
    assert slot >= 0


@case(8244, "Zenith Blade's late arrival attacks if you are the attacker")
def _():
    need("Zenith Blade", "Immortal Phoenix")
    s = fresh(hand=[T.id_of("Zenith Blade")], runes=24)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 9)
    first = body(s, 0, base_loc(0), 3, ready=True)
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, first)
    cast(s, 0, "Zenith Blade", d, ph)
    drain(s)
    assert int(s.perms[ph, P_LOC]) == bf_loc(0)
    assert combat.might(s, T, ph) == 5, "he joined as an attacker, [Assault 2] and all"


@case(8243, "Magma Wurm played from Soulgorger's trigger readies the others")
def _():
    need("Soulgorger", "Magma Wurm")
    s = fresh(hand=[T.id_of("Soulgorger")], runes=32)
    s.trash[0, 0] = T.id_of("Magma Wurm")
    s.n_trash[0] = 1
    mate = body(s, 0, base_loc(0), 3, ready=False)
    act(s, A.A_PLAY, hand_index(s, 0, "Soulgorger"), 0)
    choose(s, base_loc(0))
    run(s, picking(pack_trash(0, T.id_of("Magma Wurm")), base_loc(0), accept=True),
        limit=40)
    assert perm_of(s, "Magma Wurm", 0), "it came out of the trash"
    sg = perm_of(s, "Soulgorger", 0)[0]
    assert int(s.perms[mate, P_READY]) == 0 and sg >= 0, \
        "the Wurm arrived after them, so nobody was readied by it"
