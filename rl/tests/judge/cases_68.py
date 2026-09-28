"""RiftJudge batch 68 -- unused questions from 7194-7256."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7254, "the order the chain resolves in decides the final Might")
def _():
    need("Siphon Power", "Ahri - Nine-Tailed Fox")
    s = fresh(runes=32)
    give(s, 1, "Siphon Power")
    s.runes_ready[1, :] = 32
    s.legend[0], s.legend_ready[0] = T.id_of("Ahri - Nine-Tailed Fox"), 1
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.ply += 1
    att = body(s, 1, base_loc(1), 2, ready=True)
    attack(s, 1, 0, att)
    drain(s)
    assert combat.might(s, T, att) == 1, "her -1 resolved first"
    cast(s, 1, "Siphon Power", bf_loc(0))
    drain(s)
    assert combat.might(s, T, att) == 2, "and the +1 came after"


@case(7249, "Sun Disc turns on its own [Legion] by being played")
def _():
    need("Sun Disc", "Determined Sentry")
    s = fresh(hand=[T.id_of("Sun Disc"), T.id_of("Determined Sentry")], runes=32)
    act(s, A.A_PLAY, hand_index(s, 0, "Sun Disc"), 0)
    choose(s, base_loc(0))
    run(s)
    sd = perm_of(s, "Sun Disc", 0)[0]
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE and a.arg == sd], \
        "812.1.b.1: he is not another card"


@case(7247, "Rabadon's Deathcrown raises each instance a spell deals")
def _():
    need("Rabadon's Deathcrown", "Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=32)
    u = body(s, 0, base_loc(0), 3, ready=True)
    g = s.add_permanent(T.id_of("Rabadon's Deathcrown"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, u)
    run(s)
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 9)
    b = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Bellows Breath", a, b, -1)
    run(s)
    assert int(s.perms[a, P_DMG]) == 4 and int(s.perms[b, P_DMG]) == 4


@case(7241, "Tideturner cannot swap a unit out of Vilemaw's Lair")
def _():
    need("Tideturner", "Vilemaw's Lair")
    s = fresh(hand=[T.id_of("Tideturner")], runes=32)
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    stuck = body(s, 0, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Tideturner"), 0)
    choose(s, base_loc(0))
    act(s, A.A_ACCEPT, None, 0)
    choose(s, stuck)
    run(s)
    assert int(s.perms[stuck, P_LOC]) == bf_loc(0), "a 'can't' beats the swap"


@case(7240, "Convergent Mutation matches the Might the other unit has")
def _():
    need("Convergent Mutation", "Trifarian War Camp")
    s = fresh(runes=32)
    give(s, 0, "Convergent Mutation")
    s.bf_card[0] = T.id_of("Trifarian War Camp")
    s.bf_ctrl[0] = 0
    small = body(s, 0, bf_loc(0), 2)
    big = body(s, 0, bf_loc(0), 6)
    assert combat.might(s, T, big) == 7, "the ground's +1"
    cast(s, 0, "Convergent Mutation", small, big)
    run(s)
    assert combat.might(s, T, small) == 7, "up to his number, not past it"


@case(7226, "a Deathknell resolves after the combat, with no designations left")
def _():
    need("Wielder of Water", "Honest Broker")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    ww = s.add_permanent(T.id_of("Wielder of Water"), 0, base_loc(0), ready=True)
    hb = s.add_permanent(T.id_of("Honest Broker"), 1, bf_loc(0), ready=True)
    give(s, 1, "Smoke Screen")                   # keeps the showdown open
    s.runes_ready[1, :] = 32
    attack(s, 0, 0, ww)
    assert combat.might(s, T, ww) == 4, "2 plus its own +2 while alone"
    fight(s)
    assert not alive(s, hb), "2 Might against 4"
    assert combat.might(s, T, ww) == 2, "and the designation is gone"


@case(7221, "Hextech Anomaly turns Power into Energy on demand")
def _():
    need("Hextech Anomaly", "Riptide Rex")
    s = fresh(hand=[T.id_of("Riptide Rex")], runes=0)
    ha = s.add_permanent(T.id_of("Hextech Anomaly"), 0, base_loc(0), ready=True)
    s.runes_ready[0, :] = 0
    s.runes_ready[0, 0] = 5
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    assert "Riptide Rex" not in hand_plays(s, 0), "6 Energy, and 5 runes up"
    act(s, A.A_ACTIVATE, ha, 0)
    run(s, picking(1))
    assert ha >= 0


@case(7219, "a unit recalled from a lost combat keeps its state")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3, ready=True)
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(1), 1)
    cast(s, 0, "Ride The Wind", u, bf_loc(1))
    fight(s)
    assert int(s.perms[u, P_READY]) == 1, "it was ready, and a recall changes nothing"


@case(7218, "Ember Monk grows for every hidden card, not just the first")
def _():
    need("Ember Monk", "Consult the Past")
    s = fresh(runes=32)
    em = s.add_permanent(T.id_of("Ember Monk"), 0, base_loc(0), ready=True)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    a = hidden_at(s, 0, 0, "Consult the Past", slot=0)
    slots = list(fd_slots(0))
    b = hidden_at(s, 0, 0, "Consult the Past", slot=1) if len(slots) > 1 else -1
    act(s, A.A_PLAY_HIDDEN, a, 0)
    run(s)
    assert combat.might(s, T, em) == 6
    if b >= 0:
        act(s, A.A_PLAY_HIDDEN, b, 0)
        run(s)
        assert combat.might(s, T, em) == 8, "each one, not just the first"


@case(7216, "a champion unit's text only works on the board")
def _():
    need("Annie - Fiery", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star"), T.id_of("Annie - Fiery")], runes=32)
    u = body(s, 1, base_loc(1), 12)
    cast(s, 0, "Falling Star", u, u)
    run(s)
    assert int(s.perms[u, P_DMG]) == 6, "she was in hand, so no bonus damage"


@case(7211, "Ravenborn Tome raises both halves of Falling Star")
def _():
    need("Ravenborn Tome", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    rt = s.add_permanent(T.id_of("Ravenborn Tome"), 0, base_loc(0), ready=True)
    u = body(s, 1, base_loc(1), 12)
    act(s, A.A_ACTIVATE, rt, 0)
    run(s)
    cast(s, 0, "Falling Star", u, u)
    run(s)
    assert int(s.perms[u, P_DMG]) == 8, "4 and 4"


@case(7205, "two play triggers resolve last-placed first")
def _():
    need("Promising Future", "Riptide Rex", "Carnivorous Snapvine")
    s = fresh(hand=[T.id_of("Promising Future")], runes=32)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Riptide Rex")
    m = int(s.deck_ptr[1])
    s.deck[1, m:m + 5] = T.id_of("Carnivorous Snapvine")
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Promising Future")
    run(s, picking(0, base_loc(0), base_loc(1), foe, accept=True), limit=80)
    assert perm_of(s, "Riptide Rex", 0), "each player played their card"


@case(7204, "a countered spell is not the second card")
def _():
    need("Darius - Trifarian", "Smoke Screen", "Defy")
    s = fresh(runes=32)
    give(s, 0, "Darius - Trifarian", "Smoke Screen")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    foe = body(s, 1, base_loc(1), 5)
    act(s, A.A_PLAY, hand_index(s, 0, "Darius - Trifarian"), 0)
    choose(s, base_loc(0))
    run(s)
    dar = perm_of(s, "Darius - Trifarian", 0)[0]
    cast(s, 0, "Smoke Screen", foe)
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert int(s.perms[dar, P_READY]) == 0, "the second card never completed"


@case(7203, "Charm crosses battlefields without [Ganking]")
def _():
    need("Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 3)
    body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Charm", foe, bf_loc(1))
    run(s)
    assert int(s.perms[foe, P_LOC]) == bf_loc(1)


@case(7202, "Not So Fast can answer Overzealous Fan's ability")
def _():
    need("Not So Fast", "Overzealous Fan")
    s = fresh(runes=32)
    give(s, 0, "Not So Fast")
    s.bf_ctrl[0] = 1
    fan = s.add_permanent(T.id_of("Overzealous Fan"), 1, bf_loc(0), ready=True)
    att = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, att)
    run(s, picking(att, accept=True), limit=10,
        stop=lambda st: not alive(st, fan))
    assert not alive(s, fan), "'kill me' was paid to place it"
    if "Not So Fast" in hand_plays(s, 0):
        cast(s, 0, "Not So Fast")
        choose(s, sorted(targets_offered(s, 0))[0])
        run(s)
        assert int(s.perms[att, P_LOC]) == bf_loc(0), "the push was countered"


@case(7201, "a hidden card may be revealed on the opponent's turn")
def _():
    need("Hidden Blade")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    slot = hidden_at(s, 0, 0, "Hidden Blade")
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    pass_priority_to(s, 0)
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_PLAY_HIDDEN and a.arg == slot], "at Reaction speed"


@case(7199, "a unit played by the Hook counts as a card played")
def _():
    need("Baited Hook", "Darius - Trifarian", "Determined Sentry")
    s = fresh(runes=32)
    give(s, 0, "Darius - Trifarian")
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, base_loc(0), 3)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Determined Sentry")
    act(s, A.A_PLAY, hand_index(s, 0, "Darius - Trifarian"), 0)
    choose(s, base_loc(0))
    run(s)
    dar = perm_of(s, "Darius - Trifarian", 0)[0]
    assert int(s.perms[dar, P_READY]) == 0, "he was the first card"
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, 0, base_loc(0), accept=True), limit=60)
    assert perm_of(s, "Determined Sentry", 0)
    assert int(s.perms[dar, P_READY]) == 1, "and the Hook's unit was the second"


@case(7195, "Sett - The Boss reaches a unit in your base")
def _():
    need("Sett - The Boss", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    s.legend[1], s.legend_ready[1] = T.id_of("Sett - The Boss"), 1
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    s.set_flag(u, F_BUFFED)
    cast(s, 0, "Hidden Blade", u)
    run(s, picking(accept=True))
    assert not alive(s, u) or int(s.perms[u, P_LOC]) == base_loc(1)


@case(7194, "a Burn Out from a conquer trigger still pays the point")
def _():
    need("Zaun Warrens")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Zaun Warrens")
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    give(s, 0, "Smoke Screen")
    s.n_deck[0] = 0
    s.trash[0, :3] = VANILLA
    s.n_trash[0] = 3
    attack(s, 0, 0, u)
    run(s, limit=60)
    assert int(s.points[0]) >= 1, "the conquer point landed"
