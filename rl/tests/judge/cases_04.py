"""RiftJudge batch 4 -- the unused questions from 11000-11199."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.engine.state import C_UID, P_OWNER


def top_uid(s):
    return int(s.chain[s.n_chain - 1, C_UID])


def chain_names(s):
    return [T.names[int(s.chain[k, 0])] for k in range(s.n_chain)]


def units(s, seat, loc=None):
    return [i for i in range(s.n_perms) if alive(s, i)
            and int(s.perms[i, P_CTRL]) == seat
            and T.is_type(int(s.perms[i, P_CARD]), "Unit")
            and (loc is None or int(s.perms[i, P_LOC]) == loc)]


@case(11002, "Elder Dragon's play effect misses a unit Flashed away from where it was chosen")
def _():
    need("Elder Dragon", "Flash")
    s = fresh(hand=[T.id_of("Elder Dragon")])
    give(s, 1, "Flash")
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Elder Dragon", base_loc(0))
    run(s, picking(foe, -1), stop=lambda s: s.n_chain and s.pend_slot < 0
        and not chain_mod.decision_open(s))
    pass_priority_to(s, 1)
    cast(s, 1, "Flash", foe, -1)
    run(s)
    assert alive(s, foe) and int(s.perms[foe, P_LOC]) == base_loc(1), (
        "'an enemy unit AT EACH LOCATION' -- moved, it no longer qualifies")


@case(11000, "a stunned Elder Dragon's play effect and static still work (Vex)")
def _():
    need("Elder Dragon", "Vex - Apathetic")
    s = fresh(hand=[T.id_of("Elder Dragon")])
    s.bf_ctrl[0] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    foe = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Elder Dragon", base_loc(0))
    run(s, picking(foe, -1))
    ed = perm_of(s, "Elder Dragon")[0]
    assert s.has_flag(ed, F_STUNNED), "Vex stunned it"
    assert not alive(s, foe), "1 of your damage kills (the static is not stunned)"


@case(11085, "Cull the Weak: each player chooses on resolution, nothing is targeted")
def _():
    need("Cull the Weak")
    assert SPECS["Cull the Weak"].n_targets == 0, "no targets at play"
    s = fresh(hand=[T.id_of("Cull the Weak")])
    mine = [body(s, 0, base_loc(0), 3), body(s, 0, base_loc(0), 5)]
    theirs = [body(s, 1, base_loc(1), 3), body(s, 1, base_loc(1), 5)]
    cast(s, 0, "Cull the Weak")
    run(s)
    assert len(units(s, 0)) == 1 and len(units(s, 1)) == 1, "one each"


@case(11016, "Sacrifice cannot kill a 0 Might Reflection: it is not Mighty")
def _():
    need("Sacrifice")
    s = fresh()
    small = body(s, 0, base_loc(0), 0)
    big = body(s, 0, base_loc(0), 5)
    opts = set(rsv.cost_kill_targets(s, T, SPECS["Sacrifice"], 0))
    assert big in opts and small not in opts


@case(11024, "Challenge ([Action]) cannot answer a Star-Crossed on the Chain")
def _():
    need("Challenge", "Star-Crossed")
    s = fresh(hand=[T.id_of("Star-Crossed")])
    give(s, 1, "Challenge", "Discipline")
    a = body(s, 0, bf_loc(0), 3)
    b = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Star-Crossed", a, b)
    pass_priority_to(s, 1)
    offered = hand_plays(s, 1)
    assert "Discipline" in offered and "Challenge" not in offered, offered


@case(11032, "Anivia bounced in answer to her attack trigger deals nothing 'here'")
def _():
    need("Anivia - Primal", "Star-Crossed")
    s = fresh()
    give(s, 1, "Star-Crossed")
    s.bf_ctrl[0] = 1
    stay = body(s, 1, bf_loc(0), 5)
    bounce = body(s, 1, bf_loc(0), 5)
    an = s.add_permanent(T.id_of("Anivia - Primal"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, an)
    run(s, stop=lambda s: s.n_chain > 0 and int(s.priority) == 1
        or (s.n_chain > 0 and chain_names(s)[-1].startswith("Anivia")))
    pass_priority_to(s, 1)
    cast(s, 1, "Star-Crossed", bounce, an)
    run(s, picking())
    assert int(s.perms[stay, P_DMG]) == 0, "383.2.c.2 -- no 'here' without Anivia"


@case(11035, "Void Seeker: the Flashed unit takes nothing, the caster still draws")
def _():
    need("Void Seeker", "Flash")
    s = fresh(hand=[T.id_of("Void Seeker")])
    give(s, 1, "Flash")
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Void Seeker", foe)
    cast(s, 1, "Flash", foe, -1)
    run(s)
    assert int(s.perms[foe, P_DMG]) == 0, "'a unit at a battlefield' -- it isn't"
    assert int(s.n_hand[0]) == 1, "359.3.e.1 -- Draw 1 still happens"


@case(11036, "Thrill of the Hunt onto Abandoned Hall: the replayed unit may take the +1")
def _():
    need("Thrill of the Hunt", "Abandoned Hall")
    s = fresh(hand=[T.id_of("Thrill of the Hunt")])
    s.bf_card[1] = T.id_of("Abandoned Hall")
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Thrill of the Hunt", u, bf_loc(1))
    def pref(s, who, legal):
        cands = [a for a in legal if a.kind in _CHOICE_KINDS and a.arg >= 0
                 and a.arg < s.n_perms and alive(s, a.arg)
                 and int(s.perms[a.arg, P_LOC]) == bf_loc(1)]
        return cands[0] if cands else next((a for a in legal if a.kind == A.A_ACCEPT), None)
    run(s, pref)
    new = units(s, 0, bf_loc(1))
    assert new and combat.might(s, T, new[0]) == 4, "FAQ #10728"


@case(11039, "Acceptable Losses needs no gear of your own")
def _():
    need("Acceptable Losses", "Long Sword")
    s = fresh(hand=[T.id_of("Acceptable Losses")])
    g = s.add_permanent(T.id_of("Long Sword"), 1, base_loc(1))
    assert "Acceptable Losses" in hand_plays(s, 0), "no targets, so no requirement"
    cast(s, 0, "Acceptable Losses")
    run(s)
    assert not alive(s, g), "the opponent kills theirs; your half is ignored"


@case(11040, "Windsinger played from Hidden can only reach units at its own battlefield")
def _():
    need("Windsinger")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    body(s, 0, bf_loc(0), 3)
    fd = list(fd_slots(0))[0]
    s.fd_owner[fd], s.fd_card[fd], s.fd_ply[fd] = 0, T.id_of("Windsinger"), -5
    near = body(s, 1, bf_loc(0), 2)
    far = body(s, 1, bf_loc(1), 2)
    s.priority = 0
    s.showdown_bf = 0
    act(s, A.A_PLAY_HIDDEN, None, 0)
    offered = set()
    for _ in range(10):
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who)
        if any(a.kind == A.A_TARGET for a in legal):
            offered = {a.arg for a in legal if a.kind == A.A_TARGET}
            break
        pick = next((a for a in legal if a.kind == A.A_ACCEPT),
                    next((a for a in legal if a.kind in (A.A_ORDER, A.A_PASS)), None))
        if pick is None:
            break
        A.apply(s, T, V1, pick)
    assert near in offered and far not in offered, f"811.1.d.2: {offered}"


@case(11041, "a damaged lone defender at Forbidding Waste dies as the attacker arrives")
def _():
    need("Forbidding Waste")
    s = fresh()
    s.hand[1, 0], s.n_hand[1] = T.id_of("Smoke Screen"), 1
    s.bf_card[0] = T.id_of("Forbidding Waste")
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 4)
    combat.mark_damage(s, T, d, 2, by_seat=0)
    assert alive(s, d), "not defending yet: 4 Might"
    a = body(s, 0, base_loc(0), 1, ready=True)
    attack(s, 0, 0, a)
    run(s, stop=lambda s: not alive(s, d))
    assert not alive(s, d), "defending alone: 2 Might with 2 damage"


@case(11044, "a Reflection copies the unit, not its gear")
def _():
    need("Mirror Image", "Long Sword")
    s = fresh()
    u = body(s, 1, base_loc(1))
    sw = s.add_permanent(T.id_of("Long Sword"), 1, base_loc(1))
    s.attach(sw, u)
    rsv.resolve(s, T, V1, SPECS["Mirror Image"], 0, [u], -1, True)
    A._settle(s, T, V1)
    ref = tokens(s, 0)
    assert ref and combat.might(s, T, ref[0]) == int(T.might[VANILLA]), (
        f"copyable traits only: {combat.might(s, T, ref[0]) if ref else None}")


@case(11046, "Moonfall's -2 is a snapshot: later arrivals are untouched")
def _():
    need("Moonfall")
    s = fresh()
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    there = body(s, 1, bf_loc(0), 5)
    rsv.resolve(s, T, V1, SPECS["Moonfall"], 0,
                [bf_loc(0)] + [-1] * (SPECS["Moonfall"].n_targets - 1), -1, True)
    assert combat.might(s, T, there) == 3
    late = body(s, 1, bf_loc(0), 5)
    assert combat.might(s, T, late) == 5


@case(11053, "Safety Inspector: each player kills one of their units")
def _():
    need("Safety Inspector")
    s = fresh(hand=[T.id_of("Safety Inspector")])
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, bf_loc(1), 3)
    act(s, A.A_PLAY, 0, 0)
    choose(s, bf_loc(0))
    run(s, picking(mine, theirs))
    assert not alive(s, theirs), "the opponent had to kill theirs"
    assert not alive(s, mine) and perm_of(s, "Safety Inspector"), (
        "and you killed yours (the Inspector could have been the one, too)")


@case(11059, "Tideturner does not move if the unit it swaps with was bounced")
def _():
    need("Tideturner", "Star-Crossed")
    s = fresh()
    give(s, 1, "Star-Crossed")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    other = body(s, 0, base_loc(0), 3)
    enemy = body(s, 1, bf_loc(1), 3)
    fd = list(fd_slots(0))[0]
    s.fd_owner[fd], s.fd_card[fd], s.fd_ply[fd] = 0, T.id_of("Tideturner"), -5
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(other), stop=lambda s: s.n_chain and s.pend_slot < 0
        and s.pend_may < 0 and not chain_mod.decision_open(s)
        and chain_names(s)[-1] == "Tideturner")
    tt = perm_of(s, "Tideturner")[0]
    cast(s, 1, "Star-Crossed", enemy, other)
    run(s)
    assert int(s.perms[tt, P_LOC]) == bf_loc(0), "359.3.e.2 -- no location to go to"


@case(11064, "Pit Rookie choosing an already-buffed Irelia still triggers her +1")
def _():
    need("Pit Rookie", "Irelia, Fervent")
    from rl.engine.state import F_BUFFED
    s = fresh(hand=[T.id_of("Pit Rookie")])
    ire = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0))
    s.set_flag(ire, F_BUFFED)
    before = combat.might(s, T, ire)
    cast(s, 0, "Pit Rookie", base_loc(0))
    run(s, picking(ire))
    assert combat.might(s, T, ire) == before + 1, "no second buff, but she was chosen"


@case(11066, "Defy counters a repeated spell whole -- it reads the base cost")
def _():
    need("Defy", "Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")])
    give(s, 1, "Defy")
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Bellows Breath", u, -1, -1, repeat=True)
    run(s, picking(u, -1), stop=lambda s: s.pend_slot < 0 and not chain_mod.decision_open(s))
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1), "#11117 -- the Repeat cost does not count"
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert int(s.perms[u, P_DMG]) == 0


@case(11067, "Ruined Rex's Deathknell lands after the Combat heal: the Watcher survives")
def _():
    need("Ruined Rex", "Thousand-Tailed Watcher")
    s = fresh(seat=1)
    s.hand[0, 0], s.n_hand[0] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 0
    rex = s.add_permanent(T.id_of("Ruined Rex"), 0, bf_loc(0))
    w = s.add_permanent(T.id_of("Thousand-Tailed Watcher"), 1, base_loc(1), ready=True)
    attack(s, 1, 0, w)
    run(s, picking(w))
    assert not alive(s, rex) and alive(s, w), "6 healed, then 4 on a 7"
    assert int(s.perms[w, P_DMG]) == 4


@case(11069, "Not So Fast can counter a Star-Crossed that chose your unit")
def _():
    need("Not So Fast", "Star-Crossed")
    s = fresh(hand=[T.id_of("Star-Crossed")])
    give(s, 1, "Not So Fast")
    a = body(s, 0, base_loc(0), 3)
    b = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Star-Crossed", a, b)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert alive(s, a) and alive(s, b)


@case(11077, "Brynhir's lock still lands if she is bounced in response")
def _():
    need("Brynhir Thundersong", "Star-Crossed")
    s = fresh(hand=[T.id_of("Brynhir Thundersong")])
    give(s, 1, "Star-Crossed", "Discipline")
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Brynhir Thundersong", base_loc(0))
    bry = perm_of(s, "Brynhir Thundersong")[0]
    cast(s, 1, "Star-Crossed", theirs, bry)
    run(s)
    assert not perm_of(s, "Brynhir Thundersong"), "she went back to hand"
    s.priority = 1
    assert not hand_plays(s, 1), "FAQ #10679 -- the trigger resolved anyway"


@case(11083, "Pyke - Bloodharbor Ripper: target bounced first, the Gold still comes")
def _():
    need("Pyke - Bloodharbor Ripper", "Star-Crossed")
    s = fresh()
    s.legend[0], s.legend_ready[0] = T.id_of("Pyke - Bloodharbor Ripper"), 1
    u = body(s, 0, bf_loc(0), 3)
    from rl.engine.effects import legend_abilities_for
    rip = next(a for a in legend_abilities_for(T, T.id_of("Pyke - Bloodharbor Ripper"))
               if a.targets)
    combat.return_to_hand(s, T, u)                 # Star-Crossed resolved first
    rsv.resolve(s, T, V1, rip, 0, [u], -1, False)
    golds = [i for i in tokens(s, 0) if T.names[int(s.perms[i, P_CARD])].startswith("Gold")]
    assert golds, "359.3.e.7 -- the Gold instruction does not need the target"


@case(11084, "Kog'Maw killed for Heedless Resurrection: its Deathknell resolves first")
def _():
    need("Heedless Resurrection", "Kog'Maw - Caustic")
    s = fresh(hand=[T.id_of("Heedless Resurrection")])
    s.bf_ctrl[0] = 0
    kog = s.add_permanent(T.id_of("Kog'Maw - Caustic"), 0, bf_loc(0))
    s.trash[0, 0], s.n_trash[0] = T.id_of("Soaring Scout"), 1
    act(s, A.A_PLAY, 0, 0)
    choose(s, kog)
    from rl.engine.effects import pack_trash
    run(s, picking(pack_trash(0, T.id_of("Soaring Scout")), bf_loc(0)))
    scout = perm_of(s, "Soaring Scout")
    assert not alive(s, kog)
    assert scout and int(s.perms[scout[0], P_DMG]) == 0, (
        "the Deathknell's 4 resolved before the unit was played")


@case(11087, "Vi - Peacekeeper Gusted in answer to her attack trigger stuns nobody")
def _():
    need("Vi - Peacekeeper", "Gust")
    s = fresh()
    give(s, 1, "Gust")
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 3)
    vi = s.add_permanent(T.id_of("Vi - Peacekeeper"), 0, base_loc(0), ready=True)
    s.base_might_ply[vi], s.base_might_val[vi] = int(s.ply), 3   # Gust-able
    attack(s, 0, 0, vi)
    run(s, picking(d), stop=lambda s: s.n_chain and s.pend_slot < 0
        and chain_names(s)[-1].startswith("Vi"))
    pass_priority_to(s, 1)
    cast(s, 1, "Gust", vi)
    run(s, picking(d))
    assert not s.has_flag(d, F_STUNNED), "'an enemy unit HERE' -- Vi is gone"


@case(11092, "Guards! played from Hidden puts its Sand Soldier at that battlefield")
def _():
    need("Guards!")
    s = fresh()
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    fd = list(fd_slots(0))[0]
    s.fd_owner[fd], s.fd_card[fd], s.fd_ply[fd] = 0, T.id_of("Guards!"), -5
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(bf_loc(0)), stop=None)
    assert tokens(s, 0, bf_loc(0)) and not tokens(s, 0, base_loc(0)), "811.1.d.3"


@case(11094, "Irresistible Faefolk Gusted: her move trigger still pulls the enemy in")
def _():
    need("Irresistible Faefolk", "Gust")
    s = fresh()
    give(s, 1, "Gust")
    foe = body(s, 1, base_loc(1), 3)
    ff = s.add_permanent(T.id_of("Irresistible Faefolk"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, ff)
    run(s, picking(foe), stop=lambda s: s.n_chain and s.pend_slot < 0
        and s.pend_may < 0 and not chain_mod.decision_open(s))
    pass_priority_to(s, 1)
    cast(s, 1, "Gust", ff)
    run(s, picking(foe))
    assert int(s.perms[foe, P_LOC]) == bf_loc(0), "FAQ #10923 -- 'that battlefield' was pinned"


@case(11100, "Shakedown cannot be played without an enemy unit")
def _():
    need("Shakedown")
    s = fresh(hand=[T.id_of("Shakedown")])
    assert "Shakedown" not in hand_plays(s, 0)
    body(s, 1, base_loc(1), 3)
    assert "Shakedown" in hand_plays(s, 0)


@case(11106, "Wily Newtfish's +1 and Ganking last only the turn XP was gained")
def _():
    need("Wily Newtfish")
    s = fresh()
    w = s.add_permanent(T.id_of("Wily Newtfish"), 0, base_loc(0))
    assert combat.might(s, T, w) == 4
    s.xp[0] = 1
    s.xp_gained_ply[0] = int(s.ply)
    assert combat.might(s, T, w) == 5 and combat.perm_kw(s, T, w, "Ganking")
    s.ply += 1
    assert combat.might(s, T, w) == 4, "FAQ #10777 -- 'this turn'"


@case(11108, "Lillia - Fae Fawn leaving her battlefield keeps it through her Sprite")
def _():
    need("Lillia - Fae Fawn")
    s = fresh()
    s.bf_ctrl[0] = 0
    li = s.add_permanent(T.id_of("Lillia - Fae Fawn"), 0, bf_loc(0), ready=True)
    rsv.resolve(s, T, V1, SPECS["Flash"], 0, [li, -1], -1, True)
    A._settle(s, T, V1)
    run(s)
    assert int(s.bf_ctrl[0]) == 0 and tokens(s, 0, bf_loc(0)), (
        "the Chain was open, so control was never lost; the Sprite holds it")


@case(11109, "Repulse cannot answer a repeated Bellows Breath choosing several friends")
def _():
    need("Repulse", "Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")])
    give(s, 1, "Repulse")
    s.bf_ctrl[0] = 1
    a = body(s, 1, base_loc(1), 3)
    b = body(s, 1, base_loc(1), 3)
    c = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Bellows Breath", a, b, -1, repeat=True)
    run(s, picking(c, -1), stop=lambda s: s.pend_slot < 0 and not chain_mod.decision_open(s))
    pass_priority_to(s, 1)
    item = top_uid(s)
    ok = False
    if "Repulse" in hand_plays(s, 1):
        act(s, A.A_PLAY, hand_index(s, 1, "Repulse"), 1)
        legal = A.legal_actions(s, T, V1, 1)
        if any(x.kind == A.A_TARGET and x.arg == c for x in legal):
            choose(s, c)
            ok = any(x.kind == A.A_TARGET and x.arg == item
                     for x in A.legal_actions(s, T, V1, 1))
    assert not ok, "FAQ #9655 -- it chooses more than that one friendly unit"


@case(11119, "Kha'Zix - Voidreaver gains no XP conquering an empty battlefield")
def _():
    need("Kha'Zix - Voidreaver")
    s = fresh()
    s.legend[0], s.legend_ready[0] = T.id_of("Kha'Zix - Voidreaver"), 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    fight(s)
    assert int(s.bf_ctrl[0]) == 0 and int(s.xp[0]) == 0, "no combat, so no win"


@case(11120, "Allay's granted Deflect adds to a unit's own Deflect")
def _():
    need("Allay, Eager Admirer", "Commander Ledros")
    s = fresh()
    s.add_permanent(T.id_of("Allay, Eager Admirer"), 0, bf_loc(0))
    led = s.add_permanent(T.id_of("Commander Ledros"), 0, bf_loc(0))
    assert combat.perm_kw(s, T, led, "Deflect") == 2, (
        f"809.2 -- summed: {combat.perm_kw(s, T, led, 'Deflect')}")


@case(11128, "Not So Fast counters Elder Dragon's whole play effect")
def _():
    need("Elder Dragon", "Not So Fast")
    s = fresh(hand=[T.id_of("Elder Dragon")])
    give(s, 1, "Not So Fast")
    a = body(s, 1, bf_loc(0), 3)
    b = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Elder Dragon", base_loc(0))
    run(s, picking(a, b), stop=lambda s: s.n_chain and s.pend_slot < 0
        and not chain_mod.decision_open(s))
    pass_priority_to(s, 1)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert alive(s, a) and alive(s, b)


@case(11129, "Karthus doubles Ruined Rex's Deathknell as two separate Chain items")
def _():
    need("Karthus - Eternal", "Ruined Rex")
    s = fresh()
    s.add_permanent(T.id_of("Karthus - Eternal"), 0, base_loc(0))
    rex = s.add_permanent(T.id_of("Ruined Rex"), 0, base_loc(0))
    body(s, 1, base_loc(1), 9)
    combat.destroy(s, T, rex)
    A._settle(s, T, V1)
    run(s, picking(), stop=lambda s: s.n_chain >= 2 or (s.n_chain and s.pend_slot < 0
                                                        and s.n_trig == 0))
    rex_items = [n for n in chain_names(s) if n == "Ruined Rex"]
    assert len(rex_items) + int(s.n_trig) >= 2, (
        f"FAQ #10983 -- two instances: chain {chain_names(s)}, queued {int(s.n_trig)}")


@case(11141, "Irelia at Abandoned Hall: En Garde +1+1, her trigger twice, the Hall's +1 = 9")
def _():
    need("Irelia, Fervent", "En Garde", "Abandoned Hall")
    s = fresh(hand=[T.id_of("En Garde")])
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    ire = s.add_permanent(T.id_of("Irelia, Fervent"), 0, bf_loc(0))
    base = combat.might(s, T, ire)
    cast(s, 0, "En Garde", ire)
    run(s, picking(ire))
    assert combat.might(s, T, ire) == base + 5, (
        f"FAQ #10297 -- the Hall chooses her too: {combat.might(s, T, ire)} vs base {base}")


@case(11147, "damage in a Non-Combat Showdown is not healed when it closes")
def _():
    s = fresh()
    s.hand[1, 0], s.n_hand[1] = T.id_of("Smoke Screen"), 1
    u = body(s, 0, base_loc(0), 5, ready=True)
    attack(s, 0, 0, u)
    combat.mark_damage(s, T, u, 3, by_seat=1)
    fight(s)
    assert int(s.bf_ctrl[0]) == 0 and int(s.perms[u, P_DMG]) == 3, (
        "only a Combat Cleanup heals")


@case(11148, "Deadly Flourish loses its target to Hidden Blade: no Gold")
def _():
    need("Deadly Flourish", "Hidden Blade")
    s = fresh()
    u = body(s, 1, bf_loc(0), 3)
    combat.destroy(s, T, u)                         # Hidden Blade resolved first
    rsv.resolve(s, T, V1, SPECS["Deadly Flourish"], 0, [u], -1, True)
    A._settle(s, T, V1)
    run(s)
    assert not [i for i in tokens(s, 0) if T.names[int(s.perms[i, P_CARD])].startswith("Gold")]


@case(11150, "Beast Below with no other friendly unit: played, trigger never goes on")
def _():
    need("Beast Below")
    s = fresh(hand=[T.id_of("Beast Below")])
    s.runes_ready[:, :] = 9
    foe = body(s, 1, base_loc(1), 3)
    assert "Beast Below" in hand_plays(s, 0)
    cast(s, 0, "Beast Below", base_loc(0))
    run(s)
    assert perm_of(s, "Beast Below") and alive(s, foe)


@case(11152, "Lotus Trap played after a damage spell still doubles it")
def _():
    need("Lotus Trap", "Void Seeker")
    s = fresh(hand=[T.id_of("Void Seeker")])
    give(s, 1, "Lotus Trap")
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Void Seeker", u)
    cast(s, 1, "Lotus Trap", u)
    run(s)
    assert int(s.perms[u, P_DMG]) == 8


@case(11158, "a Fizz-played spell countered by Abandon is recycled, not returned")
def _():
    need("Fizz - Trickster", "Abandon", "Discipline")
    s = fresh(hand=[T.id_of("Fizz - Trickster")])
    give(s, 1, "Abandon")
    s.trash[0, 0], s.n_trash[0] = T.id_of("Discipline"), 1
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Fizz - Trickster", base_loc(0))
    from rl.engine.effects import pack_trash
    run(s, picking(pack_trash(0, T.id_of("Discipline")), u),
        stop=lambda s: s.n_chain and chain_names(s)[-1] == "Discipline"
        and s.pend_slot < 0 and not chain_mod.decision_open(s))
    assert chain_names(s)[-1] == "Discipline", chain_names(s)
    cast(s, 1, "Abandon", top_uid(s))
    run(s)
    assert T.id_of("Discipline") not in list(s.hand[0, :int(s.n_hand[0])]), "not to hand"
    assert T.id_of("Discipline") in list(s.deck[0]), "recycled"


@case(11165, "Undercover Agent's discard comes too late to save a lethally damaged Jinx")
def _():
    need("Undercover Agent", "Jinx - Rebel")
    s = fresh(hand=[VANILLA, VANILLA])
    ua = s.add_permanent(T.id_of("Undercover Agent"), 0, bf_loc(0))
    jx = s.add_permanent(T.id_of("Jinx - Rebel"), 0, bf_loc(0))
    s.perms[ua, P_DMG] = 5
    s.perms[jx, P_DMG] = 5
    combat.enforce_lethal(s, T)
    A._settle(s, T, V1)
    run(s, picking())
    assert not perm_of(s, "Jinx - Rebel"), "both die in the same check"


@case(11169, "a Defied Discipline still chose Irelia: she keeps her +1")
def _():
    need("Irelia, Fervent", "Discipline", "Defy")
    s = fresh(hand=[T.id_of("Discipline")])
    give(s, 1, "Defy")
    ire = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0))
    base = combat.might(s, T, ire)
    cast(s, 0, "Discipline", ire)
    item = next(k for k in range(s.n_chain) if chain_names(s)[k] == "Discipline")
    cast(s, 1, "Defy", int(s.chain[item, C_UID]))
    run(s)
    assert combat.might(s, T, ire) == base + 1, "her trigger was already on the Chain"


@case(11171, "Unsung Hero's Deathknell uses its Might at death")
def _():
    need("Unsung Hero")
    s = fresh()
    h = s.add_permanent(T.id_of("Unsung Hero"), 0, base_loc(0))
    s.base_might_ply[h], s.base_might_val[h] = int(s.ply), 6
    combat.destroy(s, T, h)
    A._settle(s, T, V1)
    run(s)
    assert int(s.n_hand[0]) == 2, "808.1.d.3 -- it was Mighty when it died"
