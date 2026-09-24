"""RiftJudge batch 61 -- unused questions from 7569-7621."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7621, "Confront reaches only the units played after it")
def _():
    need("Confront", "Determined Sentry")
    s = fresh(hand=[T.id_of("Determined Sentry"), T.id_of("Confront")], runes=32)
    already = body(s, 0, base_loc(0), 3, ready=False)
    cast(s, 0, "Confront")
    run(s)
    assert int(s.perms[already, P_READY]) == 0, "it was already there"
    act(s, A.A_PLAY, hand_index(s, 0, "Determined Sentry"), 0)
    choose(s, base_loc(0))
    run(s)
    ds = perm_of(s, "Determined Sentry", 0)[0]
    assert int(s.perms[ds, P_READY]) == 1, "and this one came after"


@case(7620, "a Reaction to Snapvine's trigger lands before the fight")
def _():
    need("Carnivorous Snapvine", "Discipline")
    s = fresh(hand=[T.id_of("Carnivorous Snapvine")], runes=32)
    give(s, 0, "Discipline")
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 6)
    act(s, A.A_PLAY, hand_index(s, 0, "Carnivorous Snapvine"), 0)
    choose(s, base_loc(0))
    cs = perm_of(s, "Carnivorous Snapvine", 0)[0]
    choose(s, foe)
    cast(s, 0, "Discipline", cs)
    run(s)
    assert alive(s, cs), "8 Might by the time the 6 arrived"
    assert not alive(s, foe), "and it dealt 8 back"


@case(7616, "a hidden Hidden Blade is bound to its own battlefield")
def _():
    need("Hidden Blade")
    s = fresh(runes=32)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    here = body(s, 1, bf_loc(0), 3)
    away = body(s, 1, bf_loc(1), 3)
    slot = hidden_at(s, 0, 0, "Hidden Blade")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    offered = targets_offered(s, 0)
    assert here in offered and away not in offered


@case(7614, "a hidden spell's 'here' is checked again at resolution")
def _():
    need("Fight or Flight", "Tideturner")
    s = fresh(runes=32)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 1
    target = body(s, 1, bf_loc(0), 3)
    tt_slot = hidden_at(s, 1, 1, "Tideturner", slot=0)
    slot = hidden_at(s, 0, 0, "Fight or Flight")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    choose(s, target)
    pass_priority_to(s, 1)
    act(s, A.A_PLAY_HIDDEN, tt_slot, 1)
    act(s, A.A_ACCEPT, None, 1)
    choose(s, target)
    run(s, limit=40)
    assert int(s.perms[target, P_LOC]) == bf_loc(1), "it swapped away"


@case(7612, "Darius, Trifarian wants exactly the second card")
def _():
    need("Darius - Trifarian", "Discipline")
    s = fresh(hand=[T.id_of("Discipline"), T.id_of("Darius - Trifarian")], runes=32)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    run(s)
    act(s, A.A_PLAY, hand_index(s, 0, "Darius - Trifarian"), 0)
    choose(s, base_loc(0))
    run(s)
    dar = perm_of(s, "Darius - Trifarian", 0)[0]
    assert int(s.perms[dar, P_READY]) == 1, "exactly the second"


@case(7611, "Dazzling Aurora's unit lands at your base or your ground")
def _():
    need("Dazzling Aurora", "Master Yi - Honed")
    s = fresh(runes=32)
    s.add_permanent(T.id_of("Dazzling Aurora"), 0, base_loc(0))
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Master Yi - Honed")
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(base_loc(0), accept=True), limit=60)
    yi = perm_of(s, "Master Yi - Honed", 0)
    assert yi and int(s.perms[yi[0], P_LOC]) == base_loc(0), "806.3"
    assert int(s.perms[yi[0], P_READY]) == 1, "and he enters ready"


@case(7610, "a battlefield scored this turn is not scored again")
def _():
    need("Retreat", "Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Retreat", "Ride The Wind")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    home = body(s, 0, base_loc(0), 3, ready=False)
    _next_own_turn(s)
    run(s, limit=40)
    assert int(s.points[0]) == 1, "the Hold"
    cast(s, 0, "Ride The Wind", home, bf_loc(0))
    run(s)
    assert int(s.points[0]) == 1, "470: once per battlefield per turn"
    assert u >= 0


@case(7608, "Fox-Fire kills what it locked in, as far as it can")
def _():
    need("Fox-Fire", "Discipline")
    s = fresh(hand=[T.id_of("Fox-Fire")], runes=32)
    give(s, 1, "Discipline")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 2)
    b = body(s, 1, bf_loc(0), 2)
    act(s, A.A_PLAY, hand_index(s, 0, "Fox-Fire"), 0)
    choose(s, a)
    choose(s, b)
    for _ in range(2):
        choose(s, -1)
    cast(s, 1, "Discipline", a)
    run(s)
    assert alive(s, a) != alive(s, b), "6 Might between them, and the pool is 4"


@case(7604, "Void Gate's bonus asks where the unit is as the damage lands")
def _():
    need("Falling Star", "Flash", "Void Gate")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    give(s, 1, "Flash")
    s.runes_ready[1, :] = 32
    s.bf_card[0] = T.id_of("Void Gate")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Falling Star", u, u)
    cast(s, 1, "Flash", u, -1)
    run(s)
    assert int(s.perms[u, P_LOC]) == base_loc(1)
    assert int(s.perms[u, P_DMG]) == 6, "no Void Gate bonus off the ground"


@case(7602, "a hidden Tideturner reaches outside its battlefield")
def _():
    need("Tideturner")
    s = fresh(runes=32)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    away = body(s, 0, bf_loc(1), 3)
    slot = hidden_at(s, 0, 0, "Tideturner")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    assert away in targets_offered(s, 0)


@case(7598, "Here to Help only plays a unit to ground you control")
def _():
    need("Here to Help", "Deadbloom Predator")
    s = fresh(runes=32)
    give(s, 0, "Here to Help", "Deadbloom Predator")
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 3)
    s.bf_ctrl[1] = 0
    body(s, 0, bf_loc(1), 3)
    cast(s, 0, "Here to Help")
    where = targets_offered(s, 0)
    assert bf_loc(0) not in where, "not the enemy's ground, whatever the unit says"


@case(7597, "a Teemo Gusted away reveals but deals nothing")
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
    assert not alive(s, tm), "back to hand, and safe"
    assert int(s.perms[foe, P_DMG]) == 0


@case(7592, "Teemo, Strategist deals one lump of damage")
def _():
    need("Teemo - Strategist", "Hidden Blade")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    tm = s.add_permanent(T.id_of("Teemo - Strategist"), 0, bf_loc(0), ready=True)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Hidden Blade")
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    choose(s, foe)
    drain(s)
    assert int(s.perms[foe, P_DMG]) == 5, "five [Hidden] cards, five damage at once"
    assert tm >= 0


@case(7587, "Zhonya's Hourglass can be played face up for its cost")
def _():
    need("Zhonya's Hourglass")
    s = fresh(hand=[T.id_of("Zhonya's Hourglass")], runes=32)
    before = int(s.runes_ready[0].sum())
    act(s, A.A_PLAY, hand_index(s, 0, "Zhonya's Hourglass"), 0)
    choose(s, base_loc(0))
    run(s)
    z = perm_of(s, "Zhonya's Hourglass", 0)
    assert z, "it is a gear like any other"
    assert before - int(s.runes_ready[0].sum()) == 2, "2 Energy paid"


@case(7586, "Rebuke's target is declared before anyone may answer")
def _():
    need("Rebuke")
    s = fresh(hand=[T.id_of("Rebuke")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Rebuke"), 0)
    assert u in targets_offered(s, 0)
    choose(s, u)
    pass_priority_to(s, 1)
    assert "Smoke Screen" in hand_plays(s, 1), "now they may answer"


@case(7583, "Sett - Kingpin counts himself")
def _():
    need("Sett - Kingpin")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    st = s.add_permanent(T.id_of("Sett - Kingpin"), 0, bf_loc(0), ready=True)
    assert combat.might(s, T, st) == 5
    s.set_flag(st, F_BUFFED)
    assert combat.might(s, T, st) == 5 + 1 + 1, "his buff's +1 and his own count"


@case(7577, "Altar of Memories waits for the ability that killed the unit")
def _():
    need("Altar of Memories", "Baited Hook", "Determined Sentry")
    s = fresh(runes=32)
    al = s.add_permanent(T.id_of("Altar of Memories"), 0, base_loc(0), ready=True)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, base_loc(0), 3)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Determined Sentry")
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, 0, base_loc(0), accept=True), limit=60)
    assert perm_of(s, "Determined Sentry", 0), "the Hook finished first"
    assert int(s.perms[al, P_READY]) == 0, "and then the Altar was used"


@case(7575, "an Attach from Azir pays no Equip cost")
def _():
    need("Azir - Ascendant", "Doran's Shield")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    az = s.add_permanent(T.id_of("Azir - Ascendant"), 0, base_loc(0), ready=True)
    u = body(s, 0, bf_loc(0), 3)
    g = s.add_permanent(T.id_of("Doran's Shield"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, u)
    run(s)
    before = int(s.runes_ready[0].sum())
    act(s, A.A_ACTIVATE, az, 0)
    run(s, picking(u, accept=True), limit=40)
    assert int(s.perms[g, P_ATTACHED_TO]) in (u, az)
    assert before - int(s.runes_ready[0].sum()) <= 1, "only his own rune"


@case(7571, "Sivir's bonus is on the moment the Power is spent")
def _():
    need("Sivir - Mercenary", "Switcheroo")
    s = fresh(hand=[T.id_of("Switcheroo")], runes=32)
    s.bf_ctrl[0] = 0
    si = s.add_permanent(T.id_of("Sivir - Mercenary"), 0, bf_loc(0), ready=True)
    mate = body(s, 0, bf_loc(0), 3)
    assert combat.might(s, T, si) == 4, "nothing spent yet"
    act(s, A.A_PLAY, hand_index(s, 0, "Switcheroo"), 0)
    choose(s, si)
    choose(s, mate)
    assert combat.might(s, T, si) == 6, "two Power spent as it was played"


@case(7569, "Defiant Dance's -2 cannot kill on its own")
def _():
    need("Defiant Dance")
    s = fresh(runes=32)
    give(s, 0, "Defiant Dance")
    mine = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 2)
    cast(s, 0, "Defiant Dance", mine, theirs)
    run(s)
    assert alive(s, theirs) and combat.might(s, T, theirs) == 0
