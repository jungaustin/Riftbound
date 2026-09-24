"""RiftJudge batch 53 -- unused questions from 8004-8040."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8039, "Master Yi's passive applies before Ahri's trigger resolves")
def _():
    need("Master Yi - Wuju Bladesman", "Ahri, Inquisitive")
    s = fresh(runes=32)
    s.legend[1], s.legend_ready[1] = T.id_of("Master Yi - Wuju Bladesman"), 1
    s.bf_ctrl[0] = 1
    ah = s.add_permanent(T.id_of("Ahri, Inquisitive"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 5)
    attack(s, 0, 0, ah)
    drain(s)
    assert combat.might(s, T, d) == 5 + 2 - 2, "his +2 is passive, her -2 resolved"


@case(8037, "conquering one battlefield is not scoring them all")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.points[0] = 7
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    home = body(s, 0, base_loc(0), 3, ready=False)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    s.bf_ctrl[1] = -1
    attack(s, 1, 1, foe)
    cast(s, 0, "Ride The Wind", home, bf_loc(1))
    fight(s)
    assert int(s.points[0]) == 7, "471.1.b wants every battlefield scored"


@case(8035, "Hidden Blade whose target left draws nobody cards")
def _():
    need("Hidden Blade", "Flash")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    give(s, 1, "Flash")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    before = int(s.n_hand[1])
    cast(s, 0, "Hidden Blade", u)
    cast(s, 1, "Flash", u, -1)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_LOC]) == base_loc(1)
    assert int(s.n_hand[1]) == before - 1, "only the Flash left their hand"


@case(8031, "Thousand-Tailed Watcher's floor does not linger")
def _():
    need("Thousand-Tailed Watcher", "Discipline")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher"), T.id_of("Discipline")],
              runes=32)
    u = body(s, 1, base_loc(1), 2)
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    run(s)
    assert combat.might(s, T, u) == 1
    cast(s, 0, "Discipline", u)
    run(s)
    assert combat.might(s, T, u) == 3, "it climbs from 1, not from -1"


@case(8030, "Trinity Force's point comes after the Hold points")
def _():
    need("Trinity Force")
    s = fresh(runes=32)
    s.points[0] = 5
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    u = body(s, 0, bf_loc(0), 3)
    body(s, 0, bf_loc(1), 3)
    g = s.add_permanent(T.id_of("Trinity Force"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, u)
    run(s)
    _next_own_turn(s)
    run(s, picking(accept=True), limit=40)
    assert int(s.points[0]) == 8, "5 + 2 Holds + the gear's own point"


@case(8027, "a floored reduction is a fixed modifier, and a pump adds to it")
def _():
    need("Thousand-Tailed Watcher", "Discipline")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher"), T.id_of("Discipline")],
              runes=32)
    u = body(s, 1, base_loc(1), 2)
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    run(s)
    cast(s, 0, "Discipline", u)
    run(s)
    assert combat.might(s, T, u) == 3


@case(8026, "the heal at the end of a combat happens even with no damage dealt")
def _():
    need("Yasuo - Remorseful", "Fight or Flight")
    s = fresh(runes=32)
    give(s, 0, "Fight or Flight")
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 12)
    attack(s, 0, 0, ya)
    choose(s, d)
    drain(s)
    assert int(s.perms[d, P_DMG]) == 6
    cast(s, 0, "Fight or Flight", ya)
    fight(s)
    assert int(s.perms[ya, P_LOC]) == base_loc(0)
    assert int(s.perms[d, P_DMG]) == 0, "it was still a combat, so it healed"


@case(8018, "Switcheroo snapshots the difference as a pair of modifiers")
def _():
    need("Switcheroo", "Traveling Merchant")
    s = fresh(hand=[T.id_of("Switcheroo")], runes=32)
    s.bf_ctrl[0] = 0
    big = body(s, 0, bf_loc(0), 7)
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, bf_loc(0), ready=True)
    cast(s, 0, "Switcheroo", big, tm)
    run(s)
    assert combat.might(s, T, big) == 2 and combat.might(s, T, tm) == 7


@case(8016, "Immortal Phoenix wants a real death")
def _():
    need("Immortal Phoenix", "Zhonya's Hourglass", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    s.bf_ctrl[0] = 0
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, bf_loc(0), ready=True)
    victim = body(s, 0, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    s.death_guard[0] = z
    cast(s, 0, "Hidden Blade", ph)
    run(s, picking(accept=True), limit=40)
    assert alive(s, ph), "the Hourglass replaced it"
    assert len(perm_of(s, "Immortal Phoenix", 0)) == 1, "and nothing came back"
    assert victim >= 0


@case(8015, "Teemo's reveal happens even when he has left the board")
def _():
    need("Teemo - Strategist", "Gust")
    s = fresh(runes=32)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    tm = s.add_permanent(T.id_of("Teemo - Strategist"), 0, bf_loc(0), ready=True)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    choose(s, foe)
    cast(s, 1, "Gust", tm)
    run(s, limit=40)
    assert not alive(s, tm), "2 Might, and off he goes"
    assert int(s.perms[foe, P_DMG]) == 0, "no source, no damage"


@case(8013, "Vi, Destructive is base speed and repeatable")
def _():
    need("Vi, Destructive")
    s = fresh(runes=32)
    vi = s.add_permanent(T.id_of("Vi, Destructive"), 0, base_loc(0), ready=True)
    for j in range(2):
        s.trash[0, j] = VANILLA
    s.n_trash[0] = 2
    for _ in range(2):
        act(s, A.A_ACTIVATE, vi, 0)
        run(s, picking(pack_trash(0, VANILLA)))
    assert combat.might(s, T, vi) == 5
    s.bf_ctrl[0] = 1
    give(s, 1, "Smoke Screen")                   # keeps the showdown open
    s.runes_ready[1, :] = 32
    body(s, 1, bf_loc(0), 9)
    att = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, att)
    assert int(s.showdown_bf) == 0
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE and a.arg == vi], "not in a showdown"


@case(8012, "a card drawn mid-showdown can be played in that showdown")
def _():
    need("Hidden Blade", "Find Your Center")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Find Your Center")
    slot = hidden_at(s, 0, 0, "Hidden Blade")
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    s.active = s.priority = 0
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    choose(s, mine)
    drain(s)
    assert not alive(s, mine), "you may kill your own unit for the draw"
    assert "Find Your Center" in hand_plays(s, 0), "drawn, and playable here"


@case(8008, "a card played by an ability counts for [Legion]")
def _():
    need("Baited Hook", "Darius - Trifarian")
    s = fresh(runes=32)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, base_loc(0), 5)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Darius - Trifarian")
    s.cards_played[0] = 1
    s.cards_completed[0] = 1                     # one card already resolved
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, 0, base_loc(0), accept=True), limit=60)
    dar = perm_of(s, "Darius - Trifarian", 0)
    assert dar, "he came off the Hook"
    assert int(s.perms[dar[0], P_READY]) == 1, "and counted as a card played"


@case(8005, "damage is assigned lethally in order, so one Decree kill")
def _():
    need("Imperial Decree")
    s = fresh(hand=[T.id_of("Imperial Decree")], runes=32)
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 6)
    b = body(s, 1, bf_loc(0), 6)
    t1 = body(s, 0, base_loc(0), 1, ready=True)
    t2 = body(s, 0, base_loc(0), 1, ready=True)
    cast(s, 0, "Imperial Decree")
    run(s)
    attack(s, 0, 0, t1, t2)
    fight(s)
    assert alive(s, a) != alive(s, b), "2 damage cannot spread across both"


@case(8004, "units die in a Cleanup, after the end-of-turn tidy-up")
def _():
    need("Back to Back", "Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=32)
    give(s, 0, "Back to Back")
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 2)
    b = body(s, 1, bf_loc(0), 2)
    cast(s, 0, "Bellows Breath", a, b, -1)
    run(s)
    assert alive(s, a) and alive(s, b), "1 damage against 2 Might"
    act(s, A.A_END_TURN, None, 0)
    run(s, limit=40)
    assert alive(s, a) and alive(s, b), "the heal beat the check"


@case(8019, "a unit played for free may still pay [Accelerate]")
def _():
    need("Baited Hook", "Jinx, Demolitionist")
    s = fresh(runes=32)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, base_loc(0), 3)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Jinx, Demolitionist")
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, 0, base_loc(0), accept=True), limit=60)
    jx = perm_of(s, "Jinx, Demolitionist", 0)
    assert jx, "4 Might is 'up to 1 more' than a 3 Might unit"


@case(8034, "Karma buffs the unit a recycle brought along")
def _():
    need("Karma - Channeler", "Vi, Destructive")
    s = fresh(runes=32)
    ka = s.add_permanent(T.id_of("Karma - Channeler"), 0, base_loc(0), ready=True)
    vi = s.add_permanent(T.id_of("Vi, Destructive"), 0, base_loc(0), ready=True)
    s.trash[0, 0] = VANILLA
    s.n_trash[0] = 1
    act(s, A.A_ACTIVATE, vi, 0)
    run(s, picking(pack_trash(0, VANILLA), vi))
    assert s.has_flag(vi, F_BUFFED) or s.has_flag(ka, F_BUFFED), \
        "a card went back to the Main Deck"


@case(8038, "Dazzling Aurora plays the unit it banished")
def _():
    need("Dazzling Aurora")
    s = fresh(runes=32)
    s.add_permanent(T.id_of("Dazzling Aurora"), 0, base_loc(0))
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Determined Sentry")
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(base_loc(0), accept=True), limit=60)
    assert perm_of(s, "Determined Sentry", 0), "revealed, banished and played"
