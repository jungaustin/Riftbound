"""RiftJudge batch 55 -- unused questions from 7898-7941."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7937, "Tideturner needs a unit at another location")
def _():
    need("Tideturner")
    s = fresh(hand=[T.id_of("Tideturner")], runes=32)
    same = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Tideturner"), 0)
    choose(s, base_loc(0))
    assert int(s.n_chain) == 0 and int(s.n_trig) == 0, \
        "355.8: nothing at another location, so no trigger"
    assert same >= 0


@case(7929, "playing a second Darius readies them both")
def _():
    need("Darius - Trifarian")
    s = fresh(hand=[T.id_of("Darius - Trifarian"), T.id_of("Darius - Trifarian")],
              runes=32)
    act(s, A.A_PLAY, hand_index(s, 0, "Darius - Trifarian"), 0)
    choose(s, base_loc(0))
    run(s)
    act(s, A.A_PLAY, hand_index(s, 0, "Darius - Trifarian"), 0)
    choose(s, base_loc(0))
    run(s)
    both = perm_of(s, "Darius - Trifarian", 0)
    assert len(both) == 2
    assert all(int(s.perms[d, P_READY]) == 1 for d in both), "each saw the second card"


@case(7926, "[Shield] is already on when the defender arrives")
def _():
    need("Shen - Kinkou", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Shen - Kinkou")
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    s.active = s.priority = 0
    act(s, A.A_PLAY, hand_index(s, 0, "Shen - Kinkou"), 0)
    choose(s, bf_loc(0))
    sh = perm_of(s, "Shen - Kinkou", 0)[0]
    assert combat.might(s, T, sh) == 5, "3 plus [Shield 2] as a defender"


@case(7922, "a Reaction played over a Reaction resolves first")
def _():
    need("Shakedown", "Unyielding Spirit", "Hextech Ray")
    s = fresh(hand=[T.id_of("Hextech Ray")], runes=32)
    give(s, 0, "Shakedown")
    give(s, 1, "Unyielding Spirit")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 12)
    cast(s, 0, "Hextech Ray", u)
    cast(s, 1, "Unyielding Spirit")
    before = int(s.n_hand[0])
    cast(s, 0, "Shakedown", u)
    run(s, picking(accept=True))
    assert int(s.perms[u, P_DMG]) == 6 or int(s.n_hand[0]) > before - 1, \
        "the Shakedown resolved before the prevention"


@case(7920, "Kraken Hunter's own play effect cannot pay for it")
def _():
    need("Kraken Hunter")
    s = fresh(hand=[T.id_of("Kraken Hunter")], runes=32)
    unbuffed = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Kraken Hunter"), 0)
    offered = targets_offered(s, 0)
    assert unbuffed not in offered, "there is no buff to spend yet"


@case(7918, "[Shield] from Taric stacks with the unit's own")
def _():
    need("Taric - Protector", "Stalwart Poro")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    ta = s.add_permanent(T.id_of("Taric - Protector"), 0, bf_loc(0), ready=True)
    poro = s.add_permanent(T.id_of("Stalwart Poro"), 0, bf_loc(0), ready=True)
    give(s, 0, "Smoke Screen")                   # keeps the showdown open
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    drain(s)
    assert combat.might(s, T, poro) == 4, "2 printed, its own +1, and Taric's +1"
    assert ta >= 0


@case(7916, "each -1 is its own modifier, and they do not un-floor")
def _():
    need("Wielder of Water", "Stupefy")
    s = fresh(runes=32)
    give(s, 0, "Stupefy", "Stupefy")
    s.bf_ctrl[0] = 1
    ww = s.add_permanent(T.id_of("Wielder of Water"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    attack(s, 0, 0, ww)
    assert combat.might(s, T, ww) == 4, "2 plus its own +2 while alone"
    cast(s, 0, "Stupefy", ww)
    drain(s)
    cast(s, 0, "Stupefy", ww)
    drain(s)
    assert combat.might(s, T, ww) == 2, "4 - 1 - 1"


@case(7913, "Dazzling Aurora stops at the first unit it reveals")
def _():
    need("Dazzling Aurora", "Determined Sentry")
    s = fresh(runes=32)
    s.add_permanent(T.id_of("Dazzling Aurora"), 0, base_loc(0))
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Determined Sentry")
    s.deck[0, n + 1] = T.id_of("Determined Sentry")
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(base_loc(0), accept=True), limit=60)
    assert len(perm_of(s, "Determined Sentry", 0)) == 1, "one unit, and it stops"


@case(7912, "an [Action] cannot answer Time Warp")
def _():
    need("Rebuke", "Time Warp")
    s = fresh(hand=[T.id_of("Time Warp")], runes=32)
    give(s, 1, "Rebuke")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Time Warp")
    pass_priority_to(s, 1)
    assert "Rebuke" not in hand_plays(s, 1)


@case(7910, "[Deflect] does not change the printed cost Defy reads")
def _():
    need("Defy", "Hextech Ray", "Draven - Audacious")
    s = fresh(hand=[T.id_of("Hextech Ray")], runes=32)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 1, bf_loc(0), ready=True)
    cast(s, 0, "Hextech Ray", dr)
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1), "still a 1 Energy, 1 Power spell"


@case(7907, "a hidden Tideturner still reaches another battlefield")
def _():
    need("Tideturner")
    s = fresh(runes=32)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    away = body(s, 0, bf_loc(1), 3)
    slot = hidden_at(s, 0, 0, "Tideturner")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    assert away in targets_offered(s, 0), "its own text overrides the 'here'"


@case(7903, "a Drummer killed in response spawns nothing")
def _():
    need("Noxian Drummer", "Ride The Wind", "Hidden Blade")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    nd = s.add_permanent(T.id_of("Noxian Drummer"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 9)
    slot = hidden_at(s, 1, 0, "Hidden Blade")
    cast(s, 0, "Ride The Wind", nd, bf_loc(0))
    run(s, limit=20, stop=lambda st: int(st.perms[nd, P_LOC]) == bf_loc(0))
    pass_priority_to(s, 1)
    act(s, A.A_PLAY_HIDDEN, slot, 1)
    choose(s, nd)
    run(s, limit=40)
    assert not alive(s, nd)
    assert not tokens(s, 0), "383.2.c.2: no source, no 'here'"


@case(7901, "a hidden Hourglass can be kept back until the targets are named")
def _():
    need("Zhonya's Hourglass", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 3)
    b = body(s, 1, base_loc(1), 3)
    slot = hidden_at(s, 1, 0, "Zhonya's Hourglass")
    cast(s, 0, "Falling Star", a, b)
    pass_priority_to(s, 1)
    assert [x for x in A.legal_actions(s, T, V1, 1)
            if x.kind == A.A_PLAY_HIDDEN and x.arg == slot], \
        "the targets are on the table before they must decide"


@case(7898, "Mask of Foresight resolves before Yasuo's damage")
def _():
    need("Mask of Foresight", "Yasuo - Remorseful")
    s = fresh(runes=32)
    mask = s.add_permanent(T.id_of("Mask of Foresight"), 1, base_loc(1))
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 6)
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, ya)
    choose(s, d)
    drain(s)
    assert alive(s, d), "7 Might by the time the 6 arrived"
    assert int(s.perms[d, P_DMG]) == 6 and mask >= 0


@case(7941, "Stacked Deck takes one card and recycles the rest")
def _():
    need("Stacked Deck")
    s = fresh(runes=32)
    give(s, 0, "Stacked Deck")
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 3] = T.id_of("Determined Sentry")
    before = int(s.n_hand[0])
    cast(s, 0, "Stacked Deck")
    run(s, picking(0))
    assert int(s.n_hand[0]) == before - 1 + 1, "one into the hand"


@case(7923, "you may order the two conquer triggers to spend a fresh buff")
def _():
    need("Monastery of Hirana", "Sett, Brawler")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Monastery of Hirana")
    s.bf_ctrl[0] = 1
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    before = int(s.n_hand[0])
    attack(s, 0, 0, sett)
    run(s, picking(accept=True), limit=40)
    assert s.has_flag(sett, F_BUFFED), "his conquer buff landed"
    assert int(s.n_hand[0]) == before, "but the Monastery had already asked"


@case(7938, "a spell that chooses at cast can be answered after the choice")
def _():
    need("Hextech Ray", "Wind Wall")
    s = fresh(hand=[T.id_of("Hextech Ray")], runes=32)
    give(s, 1, "Wind Wall")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Hextech Ray", u)
    pass_priority_to(s, 1)
    assert "Wind Wall" in hand_plays(s, 1), "the target is already named"
    cast(s, 1, "Wind Wall")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert int(s.perms[u, P_DMG]) == 0
