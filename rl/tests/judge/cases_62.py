"""RiftJudge batch 62 -- unused questions from 7508-7567."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7567, "a second showdown waits for the first to finish")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    att = body(s, 0, base_loc(0), 3, ready=True)
    home = body(s, 0, base_loc(0), 3, ready=False)
    body(s, 1, bf_loc(0), 9)
    s.bf_ctrl[1] = -1
    attack(s, 0, 0, att)
    cast(s, 0, "Ride The Wind", home, bf_loc(1))
    drain(s)
    assert int(s.showdown_bf) == 0, "the first one is still the open one"


@case(7566, "only combat damage counts for Tryndamere's excess")
def _():
    need("Tryndamere - Barbarian", "Hidden Blade")
    s = fresh(runes=32)
    give(s, 0, "Hidden Blade")
    s.bf_ctrl[0] = 1
    tr = s.add_permanent(T.id_of("Tryndamere - Barbarian"), 0, base_loc(0),
                         ready=True)
    d = body(s, 1, bf_loc(0), 1)
    attack(s, 0, 0, tr)
    fight(s)
    assert not alive(s, d)
    assert int(s.points[0]) == 2, "the conquer, and 7 excess combat damage"


@case(7565, "a unit played to enemy ground starts the showdown alone")
def _():
    need("Deadbloom Predator")
    s = fresh(hand=[T.id_of("Deadbloom Predator")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    ready_mate = body(s, 0, base_loc(0), 3, ready=True)
    act(s, A.A_PLAY, hand_index(s, 0, "Deadbloom Predator"), 0)
    choose(s, bf_loc(0))
    drain(s)
    assert int(s.perms[ready_mate, P_LOC]) == base_loc(0), "nobody came along"


@case(7558, "'when I attack' asks once, as the designation lands")
def _():
    need("Mask of Foresight", "Fight or Flight")
    s = fresh(runes=32)
    give(s, 0, "Fight or Flight")
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    mask = s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    a = body(s, 0, base_loc(0), 3, ready=True)
    b = body(s, 0, base_loc(0), 3, ready=True)
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, a, b)
    assert combat.might(s, T, a) == 3, "two of them, so nobody was alone"
    cast(s, 0, "Fight or Flight", b)
    drain(s)
    assert combat.might(s, T, a) == 3, "and going alone later does not retrigger"
    assert mask >= 0


@case(7556, "Hidden Blade from hand reaches any battlefield")
def _():
    need("Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(0), 3)
    b = body(s, 1, bf_loc(1), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Hidden Blade"), 0)
    offered = targets_offered(s, 0)
    assert a in offered and b in offered, "from hand there is no 'here'"


@case(7555, "Defy reads the printed cost, Deflect or no Deflect")
def _():
    need("Defy", "Hidden Blade", "Draven - Audacious")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 1, bf_loc(0), ready=True)
    cast(s, 0, "Hidden Blade", dr)
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1)


@case(7552, "En Garde in response takes Gust's target out of range")
def _():
    need("Gust", "En Garde")
    s = fresh(runes=32)
    give(s, 0, "Gust")
    give(s, 1, "En Garde")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Gust", u)
    cast(s, 1, "En Garde", u)
    run(s)
    assert alive(s, u), "5 Might by the time Gust looked again"


@case(7544, "Hidden Blade's target moved to base kills nobody")
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
    assert alive(s, u)
    assert int(s.n_hand[1]) == before - 1, "no draw for anybody"


@case(7541, "Draven's die-in-combat trigger is the one that fires")
def _():
    need("Draven - Audacious")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 0, base_loc(0), ready=True)
    mate = body(s, 0, base_loc(0), 9, ready=True)
    body(s, 1, bf_loc(0), 6)
    attack(s, 0, 0, dr, mate)
    fight(s)
    assert not alive(s, dr), "the defender's 6 went to him"
    assert int(s.points[1]) == 1, "and he handed them a point"


@case(7539, "a Defy on their Defy lets the first spell through")
def _():
    need("Discipline", "Defy")
    s = fresh(runes=32)
    give(s, 0, "Discipline", "Defy")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    u = body(s, 0, base_loc(0), 3)
    before = int(s.n_hand[0])
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    cast(s, 0, "Defy")
    choose(s, sorted(targets_offered(s, 0))[-1])
    run(s)
    assert combat.might(s, T, u) == 5, "their Defy was countered"
    assert int(s.n_hand[0]) == before - 2 + 1


@case(7536, "a Deathknell is placed before the tutored unit arrives")
def _():
    need("Honest Broker", "Baited Hook", "Determined Sentry")
    s = fresh(runes=6)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    hb = s.add_permanent(T.id_of("Honest Broker"), 0, base_loc(0), ready=True)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Determined Sentry")
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(hb, 0, base_loc(0), accept=True), limit=60)
    assert not alive(s, hb)
    assert perm_of(s, "Determined Sentry", 0), "the Hook finished its own work"
    assert len(tokens(s, 0)) == 1, "and then the Deathknell paid out"


@case(7535, "an [Action] cannot be added to a chain")
def _():
    need("Fox-Fire", "Ride The Wind")
    s = fresh(hand=[T.id_of("Fox-Fire")], runes=32)
    give(s, 1, "Ride The Wind")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 2)
    act(s, A.A_PLAY, hand_index(s, 0, "Fox-Fire"), 0)
    choose(s, u)
    for _ in range(3):
        choose(s, -1)
    pass_priority_to(s, 1)
    assert "Ride The Wind" not in hand_plays(s, 1)


@case(7534, "you order Falling Star's two halves")
def _():
    need("Falling Star", "Lonely Poro")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    s.bf_ctrl[0] = 1
    poro = s.add_permanent(T.id_of("Lonely Poro"), 1, bf_loc(0), ready=True)
    mate = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Falling Star", poro, mate)
    run(s)
    assert not alive(s, poro) and not alive(s, mate), "3 each against 2 and 3"


@case(7524, "bonuses are added and penalties subtracted from the base")
def _():
    need("Leona - Zealot", "Master Yi - Wuju Bladesman", "Rune Prison")
    from rl.engine.effects import SPECS
    s = fresh(runes=32)
    s.legend[1], s.legend_ready[1] = T.id_of("Master Yi - Wuju Bladesman"), 1
    s.bf_ctrl[0] = 0
    le = s.add_permanent(T.id_of("Leona - Zealot"), 0, bf_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 9)
    rsv.resolve(s, T, V1, SPECS["Rune Prison"], 0, [d], -1, True)
    assert s.has_flag(d, F_STUNNED)
    assert combat.might(s, T, d) == 1, "9 - 8, and the floor holds"
    assert le >= 0


@case(7521, "Annie's bonus damage is her controller's spells only")
def _():
    need("Annie - Fiery", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    s.add_permanent(T.id_of("Annie - Fiery"), 1, base_loc(1), ready=True)
    u = body(s, 1, base_loc(1), 12)
    cast(s, 0, "Falling Star", u, u)
    run(s)
    assert int(s.perms[u, P_DMG]) == 6, "her +1 is for HER spells"


@case(7516, "a Reaction may answer another Reaction")
def _():
    need("Hidden Blade", "Defy")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    slot = hidden_at(s, 0, 0, "Hidden Blade")
    s.bf_ctrl[0] = 1
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    choose(s, u)
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1), "a hidden card is a chain item like any other"
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert alive(s, u)


@case(7514, "a shrink after the damage finishes the job")
def _():
    need("Singularity", "Thousand-Tailed Watcher", "Mindsplitter")
    s = fresh(hand=[T.id_of("Singularity"), T.id_of("Thousand-Tailed Watcher")],
              runes=32)
    ms = s.add_permanent(T.id_of("Mindsplitter"), 1, base_loc(1), ready=True)
    cast(s, 0, "Singularity", ms, -1)
    run(s)
    assert alive(s, ms) and int(s.perms[ms, P_DMG]) == 6
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    run(s)
    assert not alive(s, ms), "7 - 3 is 4, and 6 was already marked"


@case(7513, "Unyielding Spirit prevents damage to everybody")
def _():
    need("Unyielding Spirit", "Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=32)
    give(s, 1, "Unyielding Spirit")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 5)
    cast(s, 0, "Bellows Breath", mine, -1, -1)
    cast(s, 1, "Unyielding Spirit")
    run(s)
    assert int(s.perms[mine, P_DMG]) == 0, "'all' is all of them"


@case(7508, "Sun Disc readies the unit The Harrowing brought back")
def _():
    need("Sun Disc", "The Harrowing", "Determined Sentry")
    from rl.engine.state import P_ARRIVED
    s = fresh(hand=[T.id_of("The Harrowing")], runes=32)
    sd = s.add_permanent(T.id_of("Sun Disc"), 0, base_loc(0), ready=True)
    s.perms[sd, P_ARRIVED] = -1
    s.trash[0, 0] = T.id_of("Determined Sentry")
    s.n_trash[0] = 1
    s.cards_played[0] = 1
    act(s, A.A_ACTIVATE, sd, 0)
    run(s)
    cast(s, 0, "The Harrowing")
    run(s, picking(pack_trash(0, T.id_of("Determined Sentry")), base_loc(0),
                   accept=True), limit=40)
    ds = perm_of(s, "Determined Sentry", 0)
    assert ds and int(s.perms[ds[0], P_READY]) == 1, "the next unit entered ready"
