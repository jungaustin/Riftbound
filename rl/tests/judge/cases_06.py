"""RiftJudge batch 6 -- unused questions from 11378-11578."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_05 import to_trigger
from rl.engine.state import C_UID, F_BUFFED


def hidden_at(s, seat, bf, name, slot=0):
    fd = list(fd_slots(bf))[slot]
    s.fd_owner[fd], s.fd_card[fd], s.fd_ply[fd] = seat, T.id_of(name), -5
    return fd


def targets_offered(s, seat=None, limit=12):
    """Walk ACCEPT/ORDER/PASS until a target choice opens; return its options."""
    for _ in range(limit):
        who = A.acting_seat(s) if seat is None else seat
        legal = A.legal_actions(s, T, V1, who)
        tg = {a.arg for a in legal if a.kind == A.A_TARGET}
        if tg:
            return tg
        pick = next((a for a in legal if a.kind in (A.A_ACCEPT, A.A_ORDER, A.A_PASS)), None)
        if pick is None:
            return set()
        A.apply(s, T, V1, pick)
    return set()


@case(11378, "Viktor - Leader dying with the others sees no death: no Recruits")
def _():
    need("Viktor - Leader")
    s = fresh()
    vik = s.add_permanent(T.id_of("Viktor - Leader"), 0, base_loc(0))
    others = [body(s, 0, base_loc(0), 1) for _ in range(2)]
    for i in [vik] + others:
        s.perms[i, P_DMG] = 9
    combat.enforce_lethal(s, T)
    A._settle(s, T, V1)
    run(s)
    assert not tokens(s, 0), "383.2.c.2"


@case(11379, "Falling Star choosing Deflect Irelia twice pays Deflect twice")
def _():
    need("Falling Star", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("Falling Star")])
    ire = s.add_permanent(T.id_of("Irelia, Fervent"), 1, base_loc(1))
    s.base_might_ply[ire], s.base_might_val[ire] = int(s.ply), 20
    before = runes(s, 0)
    cast(s, 0, "Falling Star", ire, ire)
    run(s)
    spent = before - runes(s, 0)
    assert spent == int(T.power[T.id_of("Falling Star")]) + 2, f"809.1.c per choice: {spent}"


@case(11385, "Fiora - Peerless keeps her doubling when an Ambush unit joins")
def _():
    need("Fiora - Peerless", "Kha'Zix - Mutating Horror")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 0, bf_loc(0))
    give(s, 0, "Kha'Zix - Mutating Horror")
    a = body(s, 1, base_loc(1), 2, ready=True)
    attack(s, 1, 0, a)
    run(s, stop=lambda s: s.n_chain and chain_names(s)[-1] == "Fiora - Peerless"
        and int(s.priority) == 0)
    pass_priority_to(s, 0)
    act(s, A.A_PLAY, hand_index(s, 0, "Kha'Zix - Mutating Horror"), 0)
    choose(s, bf_loc(0))
    run(s, stop=lambda s: s.showdown_bf >= 0 and s.n_chain == 0 and s.n_trig == 0
        and combat.might(s, T, fi) != 3)
    assert combat.might(s, T, fi) == 6, f"checked at designation: {combat.might(s, T, fi)}"


@case(11389, "Overzealous Fan's move resolves first: Vi - Peacekeeper's stun finds no 'here'")
def _():
    need("Overzealous Fan", "Vi - Peacekeeper")
    s = fresh()
    s.bf_ctrl[0] = 1
    fan = s.add_permanent(T.id_of("Overzealous Fan"), 1, bf_loc(0))
    other = body(s, 1, bf_loc(0), 3)
    vi = s.add_permanent(T.id_of("Vi - Peacekeeper"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, vi)
    run(s, picking(vi, other))
    assert int(s.perms[vi, P_LOC]) == base_loc(0), "the Fan sent Vi home"
    assert not s.has_flag(other, F_STUNNED), "then Vi's trigger had no 'here'"


@case(11402, "Charm moves a unit out of Vilemaw's Lair to another battlefield, never to base")
def _():
    need("Charm", "Vilemaw's Lair")
    s = fresh()
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[1] = 0
    u = body(s, 1, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Charm"], 0, [u, base_loc(1)], -1, True)
    assert int(s.perms[u, P_LOC]) == bf_loc(0), "not to base"
    rsv.resolve(s, T, V1, SPECS["Charm"], 0, [u, bf_loc(1)], -1, True)
    assert int(s.perms[u, P_LOC]) == bf_loc(1), "to another battlefield is fine"


@case(11405, "Guardian Angel's recall keeps Switcheroo's modifier; the Angel's +1 goes")
def _():
    need("Switcheroo", "Guardian Angel")
    s = fresh()
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 2)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 0, bf_loc(0))
    s.attach(ga, u)
    big = body(s, 1, bf_loc(0), 7)
    rsv.resolve(s, T, V1, SPECS["Switcheroo"], 0, [u, big], -1, True)
    assert combat.might(s, T, u) == 7 and combat.might(s, T, big) == 3
    s.perms[u, P_DMG] = 9
    combat.enforce_lethal(s, T)
    assert alive(s, u) and int(s.perms[u, P_LOC]) == base_loc(0)
    assert combat.might(s, T, u) == 6, f"FAQ #9335 -- +4 stays, -1 Angel: {combat.might(s, T, u)}"


@case(11409, "a token banished by The Zero Drive is gone for good")
def _():
    need("The Zero Drive", "Sprite Call")
    s = fresh()
    spr = _sprite_at(s, 0, 0)
    combat.banish(s, T, spr)
    assert int(s.n_banished[0]) == 0, "183.1 -- nothing to play back later"


@case(11415, "Ride the Wind onto an uncontrolled Abandoned Hall: the mover may take +1")
def _():
    need("Ride The Wind", "Abandoned Hall")
    s = fresh(hand=[T.id_of("Ride The Wind")])
    s.bf_card[0] = T.id_of("Abandoned Hall")
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Ride The Wind", u, bf_loc(0))
    run(s, picking(u), stop=lambda s: s.showdown_bf >= 0 and s.n_chain == 0
        and s.n_trig == 0 and s.pend_slot < 0 and s.pend_may < 0)
    assert combat.might(s, T, u) == 4


@case(11416, "Zhonya's saves a friendly unit wherever it dies")
def _():
    need("Zhonya's Hourglass")
    s = fresh()
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    s.death_guard[0] = z
    u = body(s, 0, bf_loc(1), 3)
    s.perms[u, P_DMG] = 3
    combat.enforce_lethal(s, T)
    assert alive(s, u) and int(s.perms[u, P_LOC]) == base_loc(0)


@case(11417, "Ahri - Alluring's hold point can be the winning point")
def _():
    need("Ahri - Alluring")
    s = fresh()
    V = V1
    s.points[0] = 5
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    s.add_permanent(T.id_of("Ahri - Alluring"), 0, bf_loc(0))
    body(s, 0, bf_loc(1), 3)
    phases.score_holds(s, V, T)
    A._settle(s, T, V)
    run(s)
    assert int(s.points[0]) >= 8 and int(s.winner) == 0, (
        f"points {int(s.points[0])} winner {int(s.winner)}")


@case(11419, "Star Spring cannot move Determined Sentry to base")
def _():
    need("Star Spring", "Determined Sentry")
    s = fresh(hand=[VANILLA])
    s.bf_card[0] = T.id_of("Star Spring")
    s.bf_ctrl[0] = 0
    ds = s.add_permanent(T.id_of("Determined Sentry"), 0, bf_loc(0))
    cast(s, 0, "Shipyard Skulker", bf_loc(0))
    run(s, picking(ds))
    assert int(s.perms[ds, P_LOC]) == bf_loc(0), "Can't beats can"


@case(11425, "The List's activation is not 'a spell or unit ability' for Ezreal's legend")
def _():
    need("The List", "Ezreal - Prodigal Explorer", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")])
    s.legend[0], s.legend_ready[0] = T.id_of("Ezreal - Prodigal Explorer"), 1
    lst = s.add_permanent(T.id_of("The List"), 0, base_loc(0), ready=True)
    foe = body(s, 1, base_loc(1), 3)
    # One real spell choice of an enemy, then The List's gear ability on another.
    cast(s, 0, "Discipline", foe)
    run(s)
    acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE
            and not A.is_legend_activate(a.arg)]
    for a in acts:
        A.apply(s, T, V1, a)
        run(s, picking(foe))
    leg = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE
           and A.is_legend_activate(a.arg)]
    assert not leg, "FAQ #11001 -- only one choice came from a spell or unit ability"


@case(11426, "Moonfall cannot 'move' a unit already at the chosen battlefield")
def _():
    need("Moonfall")
    s = fresh()
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    there = body(s, 1, bf_loc(0), 5)
    away = body(s, 1, bf_loc(1), 5)
    spec = SPECS["Moonfall"]
    opts = set(rsv.legal_targets(s, T, spec, 1, 0, [bf_loc(0)], -1))
    assert away in opts and there not in opts, opts


@case(11452, "Not So Fast cannot counter Defy -- Defy chooses a spell, not a unit")
def _():
    need("Not So Fast", "Defy", "Discipline")
    s = fresh(hand=[T.id_of("Not So Fast"), T.id_of("Discipline")])
    give(s, 1, "Defy")
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Defy", top_uid(s))
    defy = top_uid(s)
    pass_priority_to(s, 0)
    if "Not So Fast" in hand_plays(s, 0):
        act(s, A.A_PLAY, hand_index(s, 0, "Not So Fast"), 0)
        offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
        assert defy not in offered, offered


@case(11454, "Allay grants Ornn another Deflect: 2 + 1 = 3")
def _():
    need("Allay, Eager Admirer", "Ornn - Forge God")
    s = fresh()
    s.add_permanent(T.id_of("Allay, Eager Admirer"), 0, bf_loc(0))
    o = s.add_permanent(T.id_of("Ornn - Forge God"), 0, bf_loc(0))
    assert combat.perm_kw(s, T, o, "Deflect") == 3


@case(11458, "Teemo - Strategist must choose an enemy unit when one is there")
def _():
    need("Teemo - Strategist")
    s = fresh(seat=1)
    s.hand[0, 0], s.n_hand[0] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Teemo - Strategist"), 0, bf_loc(0))
    a = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, a)
    for _ in range(8):
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who)
        if any(x.kind == A.A_TARGET for x in legal):
            assert all(x.arg >= 0 for x in legal if x.kind == A.A_TARGET), (
                "no 'up to': declining is not offered")
            return
        A.apply(s, T, V1, next((x for x in legal if x.kind in (A.A_ORDER, A.A_PASS)), legal[0]))
    raise AssertionError("Teemo never asked for a target")


@case(11462, "Cull the Weak's kill is not a 'choose': Spirit Wheel stays quiet")
def _():
    need("Cull the Weak", "Spirit Wheel")
    s = fresh(hand=[T.id_of("Cull the Weak")])
    s.add_permanent(T.id_of("Spirit Wheel"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 3)
    body(s, 1, base_loc(1), 3)
    cast(s, 0, "Cull the Weak")
    offers = 0
    for _ in range(12):
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        if not legal or (s.n_chain == 0 and s.n_trig == 0 and s.pend_may < 0
                         and not chain_mod.decision_open(s)):
            break
        if any(x.kind == A.A_ACCEPT for x in legal):
            offers += 1
        A.apply(s, T, V1, next((x for x in legal if x.kind in (A.A_TARGET, A.A_PICK)),
                               next((x for x in legal if x.kind in (A.A_DECLINE, A.A_PASS)),
                                    legal[0])))
    assert offers == 0 and not alive(s, u)


@case(11465, "a repeated Bellows Breath chooses enemies twice: Ezreal's legend unlocks")
def _():
    need("Bellows Breath", "Ezreal - Prodigal Explorer")
    s = fresh(hand=[T.id_of("Bellows Breath")])
    s.legend[0], s.legend_ready[0] = T.id_of("Ezreal - Prodigal Explorer"), 1
    f = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Bellows Breath", f, -1, -1, repeat=True)
    run(s, picking(f, -1))
    acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE
            and A.is_legend_activate(a.arg)]
    assert acts, f"820.2 -- two choices of an enemy: chose {int(s.chose_enemy_n[0])}"


@case(11466, "Darius - Trifarian played fifth does not ready")
def _():
    need("Darius - Trifarian")
    s = fresh(hand=[T.id_of("Darius - Trifarian")])
    s.cards_played[0] = s.cards_completed[0] = 4
    cast(s, 0, "Darius - Trifarian", base_loc(0))
    run(s)
    d = perm_of(s, "Darius - Trifarian")[0]
    assert int(s.perms[d, P_READY]) == 0 and combat.might(s, T, d) == 5


@case(11467, "Blue Sentinel at Grove of the God-Willow draws two")
def _():
    need("Blue Sentinel", "Grove of the God-Willow")
    s = fresh()
    s.bf_card[0] = T.id_of("Grove of the God-Willow")
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Blue Sentinel"), 0, bf_loc(0))
    phases.score_holds(s, V1, T)
    A._settle(s, T, V1)
    run(s)
    assert int(s.n_hand[0]) == 2


@case(11472, "Heedless Resurrection cannot bring back the unit it killed as its cost")
def _():
    need("Heedless Resurrection", "Soaring Scout")
    from rl.engine.effects import pack_trash
    s = fresh(hand=[T.id_of("Heedless Resurrection")])
    s.trash[0, 0], s.n_trash[0] = T.id_of("Soaring Scout"), 1
    u = body(s, 0, base_loc(0), 3)                 # a Skulker, 2 Energy
    act(s, A.A_PLAY, 0, 0)
    choose(s, u)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert pack_trash(0, T.id_of("Soaring Scout")) in offered, offered
    assert pack_trash(0, VANILLA) not in offered, (
        f"targets are chosen before the cost is paid: {offered}")


@case(11475, "Vi - Peacekeeper ambushed into an ongoing combat attacks and stuns")
def _():
    need("Vi - Peacekeeper", "Rengar, Trophy Hunter")
    s = fresh()
    s.runes_ready[:, :] = 9
    s.bf_ctrl[0] = 1
    give(s, 0, "Vi - Peacekeeper")
    d = body(s, 1, bf_loc(0), 9)
    a = body(s, 0, base_loc(0), 3, ready=True)
    b = body(s, 0, base_loc(0), 1, ready=True)
    attack(s, 0, 0, a, b)
    pass_priority_to(s, 0)
    act(s, A.A_PLAY, hand_index(s, 0, "Vi - Peacekeeper"), 0)
    choose(s, bf_loc(0))
    run(s, picking(d), stop=lambda s: s.has_flag(d, F_STUNNED))
    assert s.has_flag(d, F_STUNNED), "323.2.a -- she inherits Attacker and triggers"


@case(11486, "Alpha Strike must give every chosen unit at least 1 damage")
def _():
    need("Alpha Strike")
    s = fresh(hand=[T.id_of("Alpha Strike")])
    mine = body(s, 0, bf_loc(0), 2)
    foes = [body(s, 1, bf_loc(0), 5) for _ in range(3)]
    s.bf_ctrl[0] = 0
    cast(s, 0, "Alpha Strike", mine)
    run(s, picking(*foes))
    hit = [f for f in foes if int(s.perms[f, P_DMG]) > 0]
    assert all(int(s.perms[f, P_DMG]) >= 1 for f in hit) and len(hit) <= 2, (
        f"355.14.g -- 2 Might reaches at most 2 units: {[int(s.perms[f, P_DMG]) for f in foes]}")


@case(11488, "Fiora - Peerless doubles her buffed Might: 3 + 1 buff -> 8")
def _():
    need("Fiora - Peerless")
    s = fresh(seat=1)
    s.hand[0, 0], s.n_hand[0] = T.id_of("Smoke Screen"), 1
    s.bf_ctrl[0] = 0
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 0, bf_loc(0))
    s.set_flag(fi, F_BUFFED)
    a = body(s, 1, base_loc(1), 2, ready=True)
    attack(s, 1, 0, a)
    run(s, stop=lambda s: combat.might(s, T, fi) == 8 or not alive(s, fi)
        or s.showdown_bf < 0)
    assert combat.might(s, T, fi) == 8


@case(11489, "Hard Bargain counters the spell: Ravenbloom Student gets nothing")
def _():
    need("Hard Bargain", "Ravenbloom Student", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")])
    give(s, 1, "Hard Bargain")
    st = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0))
    s.runes_ready[0, :] = 0
    s.runes_ready[0, 0] = 2
    cast(s, 0, "Discipline", st)
    cast(s, 1, "Hard Bargain", top_uid(s))
    run(s, picking(accept=False))
    assert combat.might(s, T, st) == 2, "419.4.a.1"


@case(11493, "a hidden Zhonya's flipped in answer to a Deathknell cannot save the dead Poro")
def _():
    need("Zhonya's Hourglass", "Lonely Poro")
    s = fresh()
    s.bf_ctrl[0] = 0
    poro = s.add_permanent(T.id_of("Lonely Poro"), 0, bf_loc(0))
    body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 0, "Zhonya's Hourglass")
    combat.destroy(s, T, poro)
    A._settle(s, T, V1)
    hid = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_HIDDEN]
    if hid:
        A.apply(s, T, V1, hid[0])
    run(s)
    assert not alive(s, poro) and not perm_of(s, "Lonely Poro")


@case(11495, "Flash in answer to Wages of Pain saves the unit at Forbidding Waste")
def _():
    need("Wages of Pain", "Flash", "Forbidding Waste")
    s = fresh(hand=[T.id_of("Wages of Pain")])
    give(s, 1, "Flash")
    s.bf_card[0] = T.id_of("Forbidding Waste")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 4)
    cast(s, 0, "Wages of Pain", u)
    cast(s, 1, "Flash", u, -1)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_LOC]) == base_loc(1)


@case(11502, "Fiora - Peerless facing two attackers never triggers, even if one leaves")
def _():
    need("Fiora - Peerless", "Star-Crossed")
    s = fresh(seat=1)
    give(s, 0, "Star-Crossed")
    s.bf_ctrl[0] = 0
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 0, bf_loc(0))
    a1 = body(s, 1, base_loc(1), 1, ready=True)
    a2 = body(s, 1, base_loc(1), 1, ready=True)
    attack(s, 1, 0, a1, a2)
    A._settle(s, T, V1)
    assert "Fiora - Peerless" not in chain_names(s), "two attackers: no trigger"
    combat.return_to_hand(s, T, a2)                # the Star-Crossed answer
    A._settle(s, T, V1)
    assert "Fiora - Peerless" not in chain_names(s) and s.n_trig == 0
    assert combat.might(s, T, fi) == 3, "no doubling ever arrives"


@case(11508, "Elder Dragon's play effect can choose an enemy unit in a base")
def _():
    need("Elder Dragon")
    s = fresh()
    foe = body(s, 1, base_loc(1), 3)
    ed = abilities_for(T, T.id_of("Elder Dragon"))[0]
    offered = set()
    for k in range(len(ed.targets)):
        offered |= set(rsv.legal_targets(s, T, ed, k, 0, [-1] * k, -1))
    assert foe in offered


@case(11520, "Not So Fast counters a Mirror Image that chose your unit")
def _():
    need("Not So Fast", "Mirror Image")
    s = fresh(hand=[T.id_of("Mirror Image")])
    give(s, 1, "Not So Fast")
    u = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Mirror Image", u)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert not tokens(s, 0)


@case(11521, "a Karthus played by the first Deathknell does not double the second")
def _():
    need("Glasc Mixologist", "Karthus - Eternal")
    s = fresh()
    s.bf_ctrl[0] = 0
    g1 = s.add_permanent(T.id_of("Glasc Mixologist"), 0, base_loc(0))
    g2 = s.add_permanent(T.id_of("Glasc Mixologist"), 0, base_loc(0))
    s.trash[0, 0], s.n_trash[0] = T.id_of("Karthus - Eternal"), 1
    for g in (g1, g2):
        s.perms[g, P_DMG] = 9
    combat.enforce_lethal(s, T)
    A._settle(s, T, V1)
    offers = 0
    for _ in range(30):
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        if not legal or (s.n_chain == 0 and s.n_trig == 0 and s.pend_may < 0
                         and s.pend_slot < 0 and not chain_mod.decision_open(s)):
            break
        if any(x.kind == A.A_ACCEPT for x in legal):
            offers += 1
        A.apply(s, T, V1, next((x for x in legal if x.kind in (A.A_ACCEPT, A.A_TARGET, A.A_PICK, A.A_PLAY_AT)
                                and x.arg != -1), next((x for x in legal if x.kind in (A.A_ORDER, A.A_PASS)), legal[0])))
    assert offers == 2, f"808.1.d.2 -- two Deathknells, not three: {offers}"


@case(11524, "Draven - Audacious conquering an empty battlefield scores 1, not 2")
def _():
    need("Draven - Audacious")
    s = fresh()
    d = s.add_permanent(T.id_of("Draven - Audacious"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, d)
    fight(s)
    run(s)
    assert int(s.points[0]) == 1


@case(11527, "a Defied Guards! costs no Order power: the ready payment is part of its effect")
def _():
    need("Guards!", "Defy")
    s = fresh(hand=[T.id_of("Guards!")])
    give(s, 1, "Defy")
    before = runes(s, 0)
    cast(s, 0, "Guards!", base_loc(0)) if SPECS["Guards!"].n_targets else cast(s, 0, "Guards!")
    after_cast = runes(s, 0)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert runes(s, 0) == after_cast and not tokens(s, 0)


@case(11528, "Gutter Palace wins on its trigger; a Gust in response is too late")
def _():
    need("Gutter Palace", "Gust")
    s = fresh(hand=[VANILLA] * 4)
    rune_deck(s)
    s.add_permanent(T.id_of("Gutter Palace"), 0, base_loc(0))
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    us = [body(s, 0, bf_loc(0), 3), body(s, 0, bf_loc(0), 3),
          body(s, 0, bf_loc(1), 3), body(s, 0, bf_loc(1), 3)]
    _next_own_turn(s)
    if s.n_chain:
        combat.return_to_hand(s, T, us[0])
        s.n_hand[0] -= 1
    run(s)
    assert int(s.winner) == 0, f"winner {int(s.winner)}"


@case(11537, "Faefolk pulls Sona onto Forbidding Waste: the lone defender takes -2")
def _():
    need("Irresistible Faefolk", "Forbidding Waste", "Sona, Harmonious")
    s = fresh()
    s.hand[1, 0], s.n_hand[1] = T.id_of("Smoke Screen"), 1
    s.bf_card[0] = T.id_of("Forbidding Waste")
    sona = s.add_permanent(T.id_of("Sona, Harmonious"), 1, base_loc(1))
    ff = s.add_permanent(T.id_of("Irresistible Faefolk"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, ff)
    run(s, picking(sona), stop=lambda s: s.showdown_bf >= 0 and s.showdown_combat
        and s.n_chain == 0 and s.n_trig == 0)
    assert int(s.attacker) == 0, "you applied Contested first"
    assert combat.might(s, T, sona) == 2 and combat.might(s, T, ff) == 1


@case(11555, "Fizz reads Drag Under's printed Energy, not a discounted one")
def _():
    need("Fizz - Trickster", "Drag Under")
    from rl.engine.effects import pack_trash
    s = fresh(hand=[T.id_of("Fizz - Trickster")])
    s.trash[0, 0], s.n_trash[0] = T.id_of("Drag Under"), 1
    body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Fizz - Trickster", base_loc(0))
    offered = targets_offered(s)
    assert pack_trash(0, T.id_of("Drag Under")) not in offered, offered


@case(11561, "Rengar ambushed onto a battlefield you contested: you stay the Attacker")
def _():
    need("Rengar, Trophy Hunter")
    s = fresh()
    give(s, 1, "Rengar, Trophy Hunter")
    s.runes_ready[:, :] = 9
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    pass_priority_to(s, 1)
    act(s, A.A_PLAY, hand_index(s, 1, "Rengar, Trophy Hunter"), 1)
    choose(s, bf_loc(0))
    run(s, stop=lambda s: s.showdown_combat and s.n_chain == 0 and s.n_trig == 0)
    assert int(s.attacker) == 0


@case(11562, "Azir - Sovereign pulls a ready token in and it stays ready")
def _():
    need("Azir - Sovereign", "Sprite Call")
    s = fresh()
    tok = _sprite_at(s, 0, 1)
    assert int(s.perms[tok, P_READY]) == 1
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 1)
    az = s.add_permanent(T.id_of("Azir - Sovereign"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, az)
    run(s, picking(tok), stop=lambda s: int(s.perms[tok, P_LOC]) == bf_loc(0))
    assert int(s.perms[tok, P_LOC]) == bf_loc(0) and int(s.perms[tok, P_READY]) == 1


@case(11563, "Ezreal - Dashing moved home by Janna deals no damage 'here'")
def _():
    need("Ezreal - Dashing", "Janna - Savior")
    s = fresh()
    give(s, 1, "Janna - Savior")
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 5)
    ez = s.add_permanent(T.id_of("Ezreal - Dashing"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, ez)
    run(s, stop=lambda s: s.n_chain and chain_names(s)[-1] == "Ezreal - Dashing"
        and s.pend_slot < 0 and not chain_mod.decision_open(s), limit=20)
    pass_priority_to(s, 1)
    cast(s, 1, "Janna - Savior", bf_loc(0))
    run(s, picking(ez, d))
    assert int(s.perms[d, P_DMG]) == 0


@case(11565, "Zilean doubles Mirror Image's Reflection")
def _():
    need("Zilean - Time Mage", "Mirror Image")
    s = fresh()
    s.add_permanent(T.id_of("Zilean - Time Mage"), 0, bf_loc(0))
    u = body(s, 1, base_loc(1), 3)
    rsv.resolve(s, T, V1, SPECS["Mirror Image"], 0, [u], -1, True)
    A._settle(s, T, V1)
    run(s, picking())
    assert len(tokens(s, 0)) == 2


@case(11567, "Diana - Lunari Gusted: her showdown trigger still resolves")
def _():
    need("Diana - Lunari", "Gust", "Discipline")
    s = fresh()
    give(s, 1, "Gust")
    s.deck[0, 0] = T.id_of("Discipline")
    di = s.add_permanent(T.id_of("Diana - Lunari"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, di)
    to_trigger(s, "Diana - Lunari")
    cast(s, 1, "Gust", di)
    hand = int(s.n_hand[0])
    run(s, picking())
    assert int(s.n_hand[0]) >= hand + 1, "the revealed spell was drawn"


@case(11571, "Acceptable Losses with no gear anywhere still resolves, doing nothing")
def _():
    need("Acceptable Losses")
    s = fresh(hand=[T.id_of("Acceptable Losses")])
    assert "Acceptable Losses" in hand_plays(s, 0)
    cast(s, 0, "Acceptable Losses")
    run(s)
    assert int(s.n_chain) == 0 and T.id_of("Acceptable Losses") in list(s.trash[0, :1])


@case(11572, "Pridestalker's +1 can resolve before Kinkou Initiate checks for the draw")
def _():
    need("Rengar - Pridestalker", "Kinkou Initiate")
    s = fresh(hand=[T.id_of("Kinkou Initiate")])
    s.legend[0], s.legend_ready[0] = T.id_of("Rengar - Pridestalker"), 1
    ally = body(s, 0, base_loc(0), 4)
    cast(s, 0, "Kinkou Initiate", base_loc(0))
    def pref(s, who, legal):
        orders = [a for a in legal if a.kind == A.A_ORDER]
        if orders:                          # Initiate placed first -> resolves last
            ki = [a for a in orders if int(s.trig[a.arg, 1]) >= 0
                  and T.names[int(s.perms[int(s.trig[a.arg, 1]), P_CARD])]
                  == "Kinkou Initiate"]
            return (ki or orders)[0]
        return picking(ally)(s, who, legal)
    run(s, pref)
    assert combat.might(s, T, ally) == 5 and int(s.n_hand[0]) == 1


@case(11577, "a hidden Stand United's buff bonus applies at every battlefield")
def _():
    need("Stand United")
    s = fresh()
    s.bf_ctrl[0] = 0
    a = body(s, 0, bf_loc(0), 3)
    b = body(s, 0, bf_loc(1), 3)
    s.set_flag(b, F_BUFFED)
    hidden_at(s, 0, 0, "Stand United")
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(a))
    assert combat.might(s, T, b) == 5, f"the bonus is global: {combat.might(s, T, b)}"


@case(11578, "LeBlanc - Everywhere At Once played after Temporary triggered saves nothing")
def _():
    need("LeBlanc - Everywhere At Once", "Sprite Call")
    s = fresh()
    rune_deck(s)
    spr = _sprite_at(s, 0, 0)
    give(s, 0, "LeBlanc - Everywhere At Once")
    _next_own_turn(s)
    assert s.n_chain >= 1, "Temporary is already on the Chain"
    lb = s.add_permanent(T.id_of("LeBlanc - Everywhere At Once"), 0, bf_loc(0))
    run(s)
    assert not alive(s, spr), "the trigger was already created"
