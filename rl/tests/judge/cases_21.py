"""RiftJudge batch 21 -- unused questions from 10166-10292 (second pass)."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_NO_MOVE, P_ATTACHED_TO
from rl.engine.effects import ABILITIES, pack_trash


@case(10229, "Ride The Wind into an open battlefield contests it: no conquer")
def _():
    need("Ride The Wind")
    s = fresh()
    give(s, 1, "Ride The Wind")
    s.runes_ready[1, :] = 6
    a = body(s, 0, base_loc(0), 3, ready=True)
    d = body(s, 1, base_loc(1), 3)
    attack(s, 0, 0, a)
    assert int(s.showdown_bf) == 0, "a non-combat showdown"
    cast(s, 1, "Ride The Wind", d, bf_loc(0))
    fight(s)
    assert int(s.points[0]) == 0 and int(s.bf_scored[0, 0]) == 0


@case(10226, "Deathgrip's kill happens even when the unit it would buff leaves")
def _():
    need("Deathgrip")
    s = fresh(hand=[T.id_of("Deathgrip")])
    dead = body(s, 0, base_loc(0), 3)
    buffed = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Deathgrip", dead, buffed)
    combat.return_to_hand(s, T, buffed)
    run(s)
    assert not alive(s, dead) and int(s.n_hand[0]) == 2, "the unit back, and the draw"


@case(10225, "Diana - Lunari's trigger resolves after she is Gusted away")
def _():
    need("Diana - Lunari", "Gust")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    give(s, 0, "Gust")
    s.bf_ctrl[0] = 0
    di = s.add_permanent(T.id_of("Diana - Lunari"), 0, bf_loc(0))
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    assert "Diana - Lunari" in chain_names(s)
    # 383.3.a -- "you may pay {1 energy}" is answered as the trigger is put on
    # the Chain, before anyone reacts to it.
    act(s, A.A_ACCEPT, None, 0)
    cast(s, 0, "Gust", di)
    fight(s)
    assert not alive(s, di) and int(s.n_hand[0]) >= 1, "her effect still resolved"


@case(10224, "Power Nexus' own point is not a Conquer: 6 to 7 to 8 wins")
def _():
    need("Power Nexus")
    s = fresh()
    s.bf_card[0] = T.id_of("Power Nexus")
    s.bf_ctrl[0] = 0
    s.points[0] = 6
    s.add_permanent(VANILLA, 0, bf_loc(0))
    _next_own_turn(s)
    run(s, picking())
    assert int(s.points[0]) == 8, int(s.points[0])
    assert s.check_winner(8) == 0


@case(10221, "Ride The Wind emptying your battlefield mid-showdown keeps it")
def _():
    need("Ride The Wind", "Facebreaker")
    s = fresh(seat=1)
    give(s, 0, "Ride The Wind")
    s.runes_ready[0, :] = 6
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    fd = hidden_at(s, 0, 0, "Facebreaker")
    foe = body(s, 1, base_loc(1), 5, ready=True)
    attack(s, 1, 0, foe)
    cast(s, 0, "Ride The Wind", mine, base_loc(0))
    drain(s)
    assert int(s.perms[mine, P_LOC]) == base_loc(0)
    assert int(s.bf_ctrl[0]) == 0, "187.4.b -- control cannot change in a showdown"
    assert int(s.fd_card[fd]) == T.id_of("Facebreaker"), "still hidden, still playable"


@case(10217, "Abandoned Hall does not trigger for a countered spell")
def _():
    need("Abandoned Hall", "Discipline", "Lilting Lullaby")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    give(s, 1, "Lilting Lullaby")
    s.runes_ready[1, :] = 6
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Lilting Lullaby", top_uid(s))
    run(s)
    assert combat.might(s, T, u) == 3, "no +2, and no Abandoned Hall +1 either"


@case(10215, "Atakhan returned to hand before his attack trigger resolves")
def _():
    need("Atakhan")
    s = fresh(runes=12)
    s.bf_ctrl[0] = 1
    at = s.add_permanent(T.id_of("Atakhan"), 0, base_loc(0), ready=True)
    keep = body(s, 1, bf_loc(0), 3)
    body(s, 1, base_loc(1), 3)
    attack(s, 0, 0, at)
    assert "Atakhan" in chain_names(s)
    combat.return_to_hand(s, T, at)
    run(s, picking())
    assert alive(s, keep), "with Atakhan gone, 'here' names nothing"


@case(10214, "Frozen Fortress' damage plus a later -3 Might kills")
def _():
    need("Frozen Fortress", "Thousand-Tailed Watcher")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=12)
    s.bf_card[0] = T.id_of("Frozen Fortress")
    foe = body(s, 1, bf_loc(0), 4)
    _next_own_turn(s)
    run(s, picking())
    assert alive(s, foe) and int(s.perms[foe, P_DMG]) == 1
    cast(s, 0, "Thousand-Tailed Watcher", base_loc(0))
    run(s)
    assert not alive(s, foe), "1 damage on a 1 Might unit"


@case(10211, "Leona - Zealot floors a stunned enemy at 1, and an increase "
             "does not lift it off the floor (see rejected.json)")
def _():
    need("Leona - Zealot", "Discipline")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Leona - Zealot"), 0, bf_loc(0))
    foe = body(s, 1, bf_loc(0), 4)
    assert s.stun(foe)
    assert combat.might(s, T, foe) == 1, combat.might(s, T, foe)
    # Resolved directly: Leona and the enemy share a battlefield, and any
    # Cleanup would open the Showdown that presence asks for.
    rsv.resolve(s, T, V1, SPECS["Discipline"], 0, [foe], -1, True)
    # 477.3.e.1.a/2.a -- increases first, decreases last, and 479's own worked
    # example puts the passive AFTER the +2 it depends on: 4 + 2 = 6, then
    # -8 to a minimum of 1.
    assert combat.might(s, T, foe) == 1, combat.might(s, T, foe)


@case(10209, "Thousand-Tailed Watcher does not reach a unit played after it")
def _():
    need("Thousand-Tailed Watcher", "Determined Sentry")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=12)
    before = body(s, 1, base_loc(1), 4)
    cast(s, 0, "Thousand-Tailed Watcher", base_loc(0))
    run(s)
    assert combat.might(s, T, before) == 1
    s.active = s.priority = 1
    s.ply += 1
    give(s, 1, "Determined Sentry")
    s.runes_ready[1, :] = 6
    cast(s, 1, "Determined Sentry", base_loc(1))
    run(s)
    after = perm_of(s, "Determined Sentry")
    assert after and combat.might(s, T, after[0]) == 1, "its own printed 1"
    assert int(s.perms[after[0], 0]) >= 0


@case(10206, "Crescent Strike reads the battlefield at resolution: Ambush is hit")
def _():
    need("Crescent Strike", "Vi - Peacekeeper")
    s = fresh(hand=[T.id_of("Crescent Strike")], runes=12)
    s.bf_ctrl[1] = 1
    main = body(s, 1, bf_loc(0), 9)
    body(s, 1, bf_loc(0), 9)
    give(s, 1, "Vi - Peacekeeper")
    s.runes_ready[1, :] = 9
    cast(s, 0, "Crescent Strike", bf_loc(0), main)
    cast(s, 1, "Vi - Peacekeeper", bf_loc(0))
    run(s, picking())
    vi = perm_of(s, "Vi - Peacekeeper")
    assert vi and int(s.perms[vi[0], P_DMG]) == 1, "it was there when the spell resolved"


@case(10205, "Vi - Peacekeeper's attack trigger stuns exactly one unit")
def _():
    need("Vi - Peacekeeper")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 1
    a = s.add_permanent(T.id_of("Vi - Peacekeeper"), 0, base_loc(0), ready=True)
    d1 = body(s, 1, bf_loc(0), 3)
    d2 = body(s, 1, bf_loc(0), 3)
    attack(s, 0, 0, a)
    drain(s)
    assert [s.has_flag(d1, F_STUNNED), s.has_flag(d2, F_STUNNED)].count(True) == 1


@case(10204, "Alpha Wildclaw does not stop Crescent Strike's splash")
def _():
    need("Alpha Wildclaw", "Crescent Strike")
    s = fresh(hand=[T.id_of("Crescent Strike")], runes=12)
    s.bf_ctrl[1] = 1
    aw = s.add_permanent(T.id_of("Alpha Wildclaw"), 1, bf_loc(0))
    small = body(s, 1, bf_loc(0), 2)
    act(s, A.A_PLAY, hand_index(s, 0, "Crescent Strike"), 0)
    choose(s, bf_loc(0))
    assert small not in targets_offered(s, 0), "less Might than the Wildclaw"
    choose(s, aw)
    run(s)
    assert int(s.perms[small, P_DMG]) == 1, "the splash chooses nothing"


@case(10203, "Heedless Resurrection's cost does not cost you the battlefield")
def _():
    need("Heedless Resurrection", "Determined Sentry")
    s = fresh(hand=[T.id_of("Heedless Resurrection")], runes=9)
    s.bf_ctrl[0] = 0
    only = body(s, 0, bf_loc(0), 3)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Determined Sentry"), 1
    cast(s, 0, "Heedless Resurrection", only)
    run(s, picks(pack_trash(0, T.id_of("Determined Sentry")), bf_loc(0)))
    ds = perm_of(s, "Determined Sentry")
    assert ds and int(s.perms[ds[0], P_LOC]) == bf_loc(0)
    assert int(s.bf_ctrl[0]) == 0


@case(10199, "Navori Fighting Pit still triggers when the unit is already buffed")
def _():
    need("Navori Fighting Pit")
    s = fresh()
    s.bf_card[0] = T.id_of("Navori Fighting Pit")
    s.bf_ctrl[0] = 0
    u = s.add_permanent(VANILLA, 0, bf_loc(0))
    s.set_flag(u, F_BUFFED)
    _next_own_turn(s)
    assert "Navori Fighting Pit" in chain_names(s), chain_names(s)


@case(10197, "The Grand Plaza does not trigger at all below 7 units")
def _():
    need("The Grand Plaza")
    s = fresh()
    s.bf_card[0] = T.id_of("The Grand Plaza")
    s.bf_ctrl[0] = 0
    s.add_permanent(VANILLA, 0, bf_loc(0))
    _next_own_turn(s)
    assert "The Grand Plaza" not in chain_names(s), chain_names(s)
    run(s, picking())
    assert s.check_winner(8) < 0


@case(10195, "Cursed Sarcophagus cannot be activated on your opponent's turn")
def _():
    need("Cursed Sarcophagus", "Rengar, Trophy Hunter")
    s = fresh(hand=[T.id_of("Cursed Sarcophagus")], runes=9)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Rengar, Trophy Hunter"), 1
    cast(s, 0, "Cursed Sarcophagus", base_loc(0))
    run(s)
    assert int(s.n_sarc[0]) == 1, "the play banished the trash unit"
    assert A.A_ACTIVATE in kinds(s, 0), "on your own turn it is available"
    s.ply += 1
    s.active = s.priority = 1
    assert A.A_ACTIVATE not in kinds(s, 0), kinds(s, 0)


@case(10193, "Vanguard Armory's Recruit tokens enter exhausted")
def _():
    need("Vanguard Armory")
    s = fresh()
    va = s.add_permanent(T.id_of("Vanguard Armory"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, va, 0)
    run(s, picks(base_loc(0), base_loc(0), base_loc(0)))
    toks = tokens(s, 0)
    assert len(toks) == 3 and not any(int(s.perms[i, P_READY]) for i in toks)


@case(10191, "Star-Crossed cannot be played without a friendly unit")
def _():
    need("Star-Crossed")
    s = fresh(hand=[T.id_of("Star-Crossed")], runes=9)
    body(s, 1, base_loc(1), 3)
    assert "Star-Crossed" not in hand_plays(s, 0)
    body(s, 0, base_loc(0), 3)
    assert "Star-Crossed" in hand_plays(s, 0)


@case(10190, "a stunned attacker deals no damage but still needs its full Might")
def _():
    need("Back Off")
    s = fresh(hand=[T.id_of("Back Off")], runes=9)
    s.bf_ctrl[0] = 1
    a = body(s, 0, base_loc(0), 6, ready=True)
    d = body(s, 1, bf_loc(0), 3)
    attack(s, 0, 0, a)
    pass_priority_to(s, 0)
    cast(s, 0, "Back Off", a)
    fight(s)
    assert alive(s, a) and alive(s, d), "0 damage out, 3 damage in on a 6"


@case(10185, "Conscription takes the unit with its gear still attached")
def _():
    need("Conscription", "Warmog's Armor")
    s = fresh(hand=[T.id_of("Conscription")], runes=9)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 2)
    g = s.add_permanent(T.id_of("Warmog's Armor"), 1, bf_loc(0))
    s.attach(g, foe)
    assert combat.might(s, T, foe) == 3, "still inside 'no more than 3 Might'"
    cast(s, 0, "Conscription", foe)
    run(s, picking())
    assert int(s.perms[foe, P_CTRL]) == 0 and int(s.perms[foe, P_LOC]) == base_loc(0)
    assert int(s.perms[g, P_ATTACHED_TO]) == foe, "the gear rode along"


@case(10183, "Targon's Peak readies runes even if you leave the battlefield")
def _():
    need("Targon's Peak", "Ride The Wind")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Targon's Peak")
    give(s, 0, "Ride The Wind")
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    run(s, picking())
    assert int(s.bf_ctrl[0]) == 0 and int(s.points[0]) == 1
    assert int(s.pending_ready_runes[0]) == 2, "banked for the end of the turn"
    cast(s, 0, "Ride The Wind", u, base_loc(0))
    run(s)
    assert int(s.perms[u, P_LOC]) == base_loc(0) and int(s.bf_ctrl[0]) < 0
    s.runes_ready[0, :] = 0
    s.runes_spent[0, 0] = 4
    phases.ending(s)
    assert int(s.total_ready_runes(0)) == 2, "the trigger no longer needs its source"


@case(10182, "Ruined Rex's Deathknell lands after the combat heal")
def _():
    need("Ruined Rex")
    s = fresh()
    s.bf_ctrl[1] = 1
    rex = s.add_permanent(T.id_of("Ruined Rex"), 0, base_loc(0), ready=True)
    big = body(s, 1, bf_loc(0), 10)
    attack(s, 0, 0, rex)
    run(s, picking(big))
    assert not alive(s, rex) and alive(s, big)
    assert int(s.perms[big, P_DMG]) == 4, "healed first, then dealt 4"


@case(10180, "Treasure Hunter returned to hand has not moved: no Gold")
def _():
    need("Treasure Hunter", "Gust")
    s = fresh(seat=1, hand=())
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 6
    s.bf_ctrl[0] = 0
    th = s.add_permanent(T.id_of("Treasure Hunter"), 0, bf_loc(0))
    cast(s, 1, "Gust", th)
    run(s)
    assert not alive(s, th) and not tokens(s, 0), "a zone change is not a move"


@case(10179, "equipping Boots of Swiftness chooses the unit, so Irelia sees it")
def _():
    need("Boots of Swiftness", "Irelia - Blade Dancer")
    s = fresh(runes=9)
    s.legend[0], s.legend_ready[0] = T.id_of("Irelia - Blade Dancer"), 1
    g = s.add_permanent(T.id_of("Boots of Swiftness"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, u)
    A._settle(s, T, V1)
    assert "Irelia - Blade Dancer" in chain_names(s), chain_names(s)


@case(10178, "a Gold token may be spent in answer to Acceptable Losses")
def _():
    need("Acceptable Losses", "Wages of Pain")
    s = fresh(hand=[T.id_of("Acceptable Losses")], runes=9)
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(0), 9)
    # a Gold they have had since a previous turn, so it is ready to Exhaust
    gold = s.add_permanent(T.id_of("Gold // Buff"), 1, base_loc(1), ready=True)
    assert tokens(s, 1) == [gold]
    cast(s, 0, "Acceptable Losses")
    pass_priority_to(s, 1)
    assert A.A_ACTIVATE in kinds(s, 1), kinds(s, 1)


@case(10177, "Grim Apothecary's trigger resolves after Wages of Pain kills it")
def _():
    need("Grim Apothecary", "Wages of Pain")
    s = fresh(hand=[T.id_of("Grim Apothecary")], runes=9)
    s.bf_ctrl[0] = 0
    other = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Grim Apothecary", bf_loc(0))
    A._settle(s, T, V1)
    ga = perm_of(s, "Grim Apothecary")
    assert ga and "Grim Apothecary" in chain_names(s)
    rsv.resolve(s, T, V1, SPECS["Wages of Pain"], 1, [ga[0]], -1, True)
    run(s, picks(other))
    assert not alive(s, ga[0]), "3 damage on a 3 Might unit"
    assert not alive(s, other), "its play trigger resolved anyway"


@case(10175, "a hidden Sprite Call must place its Sprite at that battlefield")
def _():
    need("Sprite Call")
    s = fresh()
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    hidden_at(s, 0, 1, "Sprite Call")
    act(s, A.A_PLAY_HIDDEN, None, 0)
    dests = {a.arg for a in A.legal_actions(s, T, V1, 0)
             if a.kind in (A.A_TARGET, A.A_PLAY_AT, A.A_PLAY_AT_FAST)}
    assert dests == {bf_loc(1)}, dests
    run(s, picking())
    tok = tokens(s, 0)
    assert tok and int(s.perms[tok[0], P_LOC]) == bf_loc(1)


@case(10171, "Flurry of Blades with Elder Dragon out kills every enemy unit")
def _():
    need("Flurry of Blades", "Elder Dragon")
    s = fresh(hand=[T.id_of("Flurry of Blades")], runes=9)
    s.add_permanent(T.id_of("Elder Dragon"), 0, base_loc(0))
    s.bf_ctrl[1] = 1
    f1 = body(s, 1, bf_loc(0), 9)
    f2 = body(s, 1, bf_loc(1), 9)
    mine = body(s, 0, bf_loc(0), 9)
    cast(s, 0, "Flurry of Blades")
    run(s)
    assert not alive(s, f1) and not alive(s, f2) and alive(s, mine)


@case(10169, "Death from Below may be replayed out of the trash it just reached")
def _():
    need("Death from Below")
    s = fresh(hand=[T.id_of("Death from Below")], runes=9)
    s.bf_ctrl[1] = 1
    small = body(s, 1, bf_loc(0), 3)
    other = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Death from Below", small)
    run(s)
    assert not alive(s, small) and int(s.n_trash[0]) == 1
    act(s, A.A_PLAY_FLOW, 0, 0)
    choose(s, other)
    run(s)
    assert not alive(s, other), "the same copy, twice"


@case(10167, "Scorchclaw's [Level 3] turns on once the XP arrives")
def _():
    need("Scorchclaw")
    s = fresh()
    sc = s.add_permanent(T.id_of("Scorchclaw"), 0, base_loc(0))
    assert combat.might(s, T, sc) == 3
    s.xp[0] = 3
    assert combat.might(s, T, sc) == 4


@case(10166, "Vilemaw's Lair stops The Syren from sending a unit home")
def _():
    need("Vilemaw's Lair", "The Syren")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    syr = s.add_permanent(T.id_of("The Syren"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, syr, 0)
    choose(s, u)
    run(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(0), "'can't' beats 'move it'"
