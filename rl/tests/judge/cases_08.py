"""RiftJudge batch 8 -- unused questions from 11771-12046."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_EMPOWERED, F_UNCHOOSABLE_TURN, P_EMPOWER, P_MIGHT_MOD
from rl.engine.effects import pack_trash


def ready_runes(s, seat):
    return int(s.runes_ready[seat].sum())


@case(11771, "Ride the Wind from Vilemaw's Lair to base: no move, but it still readies")
def _():
    need("Ride The Wind", "Vilemaw's Lair")
    s = fresh()
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [u, base_loc(0)], -1, True)
    assert int(s.perms[u, P_LOC]) == bf_loc(0) and int(s.perms[u, P_READY]) == 1


@case(11772, "Sigil of the Storm's recycle gives no Power")
def _():
    need("Sigil of the Storm")
    s = fresh()
    s.bf_card[0] = T.id_of("Sigil of the Storm")
    u = body(s, 0, base_loc(0), 3, ready=True)
    before = runes(s, 0)
    attack(s, 0, 0, u)
    run(s, picking())
    assert runes(s, 0) == before - 1, (before, runes(s, 0))
    assert int(s.pool_power[0].sum()) == 0


@case(11775, "Elder Dragon entering kills an enemy already holding its player's damage")
def _():
    need("Elder Dragon")
    s = fresh()
    mine = body(s, 1, base_loc(1), 3)
    s.perms[mine, P_DMG] = 1
    s.foe_dmg[mine] = 1                      # marked by seat 0
    theirs = body(s, 1, base_loc(1), 3)
    s.perms[theirs, P_DMG] = 1               # marked by its own side
    s.add_permanent(T.id_of("Elder Dragon"), 0, base_loc(0))
    combat.enforce_lethal(s, T)
    assert not alive(s, mine) and alive(s, theirs)


@case(11784, "Profiteer may empower the same unit it disempowers")
def _():
    need("Profiteer")
    s = fresh(hand=[T.id_of("Profiteer")])
    u = body(s, 0, base_loc(0), 3)
    s.set_flag(u, F_EMPOWERED)
    s.perms[u, P_EMPOWER] = 1
    cast(s, 0, "Profiteer", base_loc(0))
    offered = []
    for _ in range(8):
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who)
        tg = [a for a in legal if a.kind == A.A_TARGET]
        if tg:
            offered.append({a.arg for a in tg})
            A.apply(s, T, V1, next(a for a in tg if a.arg == u))
            continue
        pick = next((a for a in legal if a.kind in (A.A_ACCEPT, A.A_ORDER)), None)
        if pick is None:
            break
        A.apply(s, T, V1, pick)
    assert len(offered) == 2 and u in offered[1], offered
    run(s)
    assert s.empower_count(u) == 1


@case(11786, "Shuriken Flip moves a unit battlefield to battlefield without Ganking")
def _():
    need("Shuriken Flip")
    s = fresh(hand=[T.id_of("Shuriken Flip")])
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    act(s, A.A_PLAY, 0, 0)
    choose(s, -1)                                      # no enemy to damage
    choose(s, bf_loc(1))
    choose(s, u)
    run(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(1)


@case(11805, "Eclipse Dragon counts exhausted runes as runes you control")
def _():
    need("Eclipse Dragon", "Ride The Wind")
    for ready, spent, draws in ((3, 2, 0), (2, 2, 1)):
        s = fresh()
        s.runes_ready[0, :] = 0
        s.runes_ready[0, 0] = ready
        s.runes_spent[0, 0] = spent
        d = s.add_permanent(T.id_of("Eclipse Dragon"), 0, base_loc(0))
        rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [d, bf_loc(0)], -1, True)
        A._settle(s, T, V1)
        drain(s)
        assert int(s.n_hand[0]) == draws, (ready, spent, int(s.n_hand[0]))


@case(11808, "moving Whiteflame Protector is not playing it")
def _():
    need("Whiteflame Protector", "Ride The Wind")
    s = fresh()
    w = s.add_permanent(T.id_of("Whiteflame Protector"), 0, base_loc(0))
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [w, bf_loc(0)], -1, True)
    A._settle(s, T, V1)
    assert "Whiteflame Protector" not in chain_names(s) and s.pend_slot < 0


@case(11815, "Hidden Blade on Rift Herald: its controller draws 2 before the Deathknell")
def _():
    need("Hidden Blade", "Rift Herald")
    s = fresh(hand=[T.id_of("Hidden Blade")])
    h = s.add_permanent(T.id_of("Rift Herald"), 1, bf_loc(0))
    s.bf_ctrl[0] = 1
    cast(s, 0, "Hidden Blade", h)
    seen = []

    def watch(s):
        if "Rift Herald" in chain_names(s) or s.n_trig:
            seen.append(int(s.n_hand[1]))
        return False
    run(s, picking(accept=False), stop=watch)
    assert seen and seen[0] == 2, seen


@case(11816, "Akali, Silent at a battlefield out of combat: Falling Comet can't choose her")
def _():
    need("Akali, Silent", "Falling Comet")
    s = fresh(hand=[T.id_of("Falling Comet")])
    ak = s.add_permanent(T.id_of("Akali, Silent"), 1, bf_loc(0))
    other = body(s, 1, bf_loc(1), 3)
    act(s, A.A_PLAY, 0, 0)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert other in offered and ak not in offered, offered


@case(11818, "The List cannot choose Baron Nashor, even naming The Void")
def _():
    need("The List", "Baron Nashor")
    from rl.engine.effects import tag_vocab
    s = fresh()
    g = s.add_permanent(T.id_of("The List"), 0, base_loc(0), ready=True)
    s.named[g] = tag_vocab(T).index("The Void")
    s.add_permanent(T.id_of("Baron Nashor"), 1, base_loc(1))
    acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
    assert not acts, "no legal choice, so the ability cannot be activated"


@case(11819, "Otterpus in the trash replaces nothing: the conquer scores")
def _():
    need("Otterpus")
    for alive_otter, pts in ((True, 0), (False, 1)):
        s = fresh()
        s.turn = 1
        o = s.add_permanent(T.id_of("Otterpus"), 1, base_loc(1))
        if not alive_otter:
            combat.destroy(s, T, o)
            A._settle(s, T, V1)
        u = body(s, 0, base_loc(0), 3, ready=True)
        attack(s, 0, 0, u)
        run(s, picking())
        assert int(s.points[0]) == pts, (alive_otter, int(s.points[0]))


@case(11820, "Temporal Breach on a lone unit keeps the battlefield and its hidden card")
def _():
    need("Temporal Breach")
    s = fresh()
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    fd = hidden_at(s, 1, 0, "Back Off")
    rsv.resolve(s, T, V1, SPECS["Temporal Breach"], 0, [u], -1, True)
    run(s)
    assert int(s.bf_ctrl[0]) == 1 and int(s.fd_card[fd]) == T.id_of("Back Off")


@case(11830, "Twilight Reveler into an empty battlefield is no attack: nothing readies")
def _():
    need("Twilight Reveler")
    s = fresh()
    tr = s.add_permanent(T.id_of("Twilight Reveler"), 0, base_loc(0), ready=True)
    other = body(s, 0, base_loc(0), 3)
    attack(s, 0, 0, tr)
    run(s, picking(other))
    assert int(s.perms[other, P_READY]) == 0


@case(11832, "Tornado Warrior's empower still ends at end of turn after it dies")
def _():
    need("Tornado Warrior")
    s = fresh()
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 0, "Tornado Warrior")
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(u))
    assert s.empower_count(u) == 1, "a unit with no Empower text may be empowered"
    tw = perm_of(s, "Tornado Warrior")[0]
    combat.destroy(s, T, tw)
    run(s)
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(), stop=lambda s: int(s.active) == 1 and s.n_chain == 0 and s.n_trig == 0)
    sk = perm_of(s, "Shipyard Skulker")                 # rows compact at turn end
    assert len(sk) == 1 and s.empower_count(sk[0]) == 0


@case(11834, "Janna - Savior played to base on the opponent's turn still triggers")
def _():
    need("Janna - Savior", "Discipline")
    s = fresh(seat=1, hand=[T.id_of("Discipline")])
    give(s, 0, "Janna - Savior")
    theirs = body(s, 1, base_loc(1), 3)
    mine = body(s, 0, base_loc(0), 5)
    s.perms[mine, P_DMG] = 2
    cast(s, 1, "Discipline", theirs)
    cast(s, 0, "Janna - Savior", base_loc(0))
    run(s, picking())
    assert int(s.perms[mine, P_DMG]) == 0, "heal your units here"


@case(11836, "Irelia Flashed off Abandoned Hall: the Hall has no unit of hers to give +1")
def _():
    need("Abandoned Hall", "Flash", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("Flash")])
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, bf_loc(0))
    act(s, A.A_PLAY, 0, 0)
    choose(s, ir)
    choose(s, -1)
    run(s, picking(ir))
    # The ruling also says her own "when you choose me" never fires; that
    # contradicts #11860 (Flash DOES choose her, 355.10), so only the Hall's
    # half is asserted: 4 printed + 1 from being chosen, and no +1 from the Hall.
    assert int(s.perms[ir, P_LOC]) == base_loc(0) and combat.might(s, T, ir) == 5, \
        combat.might(s, T, ir)


@case(11843, "a stunned attacker at Vilemaw's Lair is still recalled to base")
def _():
    need("Vilemaw's Lair")
    s = fresh()
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 3)
    a = body(s, 0, base_loc(0), 5, ready=True)
    s.stun(a)
    attack(s, 0, 0, a)
    fight(s)
    run(s)
    assert alive(s, a) and alive(s, d) and int(s.perms[a, P_LOC]) == base_loc(0)


@case(11844, "Shadows of the Past returns units from both trashes to their owners")
def _():
    need("Shadows of the Past")
    s = fresh(hand=[T.id_of("Shadows of the Past")])
    s.trash[0, 0], s.n_trash[0] = VANILLA, 1
    other = T.id_of("Watchful Sentry")
    s.trash[1, 0], s.n_trash[1] = other, 1
    cast(s, 0, "Shadows of the Past", pack_trash(1, other), pack_trash(0, VANILLA))
    run(s)
    assert list(s.hand[1, :int(s.n_hand[1])]) == [other]
    assert list(s.hand[0, :int(s.n_hand[0])]) == [VANILLA]


@case(11851, "Star-Crossed whose enemy was Retreated still returns your unit")
def _():
    need("Star-Crossed")
    s = fresh(hand=[T.id_of("Star-Crossed")])
    mine = body(s, 0, base_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Star-Crossed", mine, foe)
    combat.return_to_hand(s, T, foe)
    run(s)
    assert not alive(s, mine) and int(s.n_hand[0]) == 1


@case(11854, "Tactical Retreat: the attacker deals full damage, is recalled, and does not conquer")
def _():
    need("Tactical Retreat")
    s = fresh()
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 3)
    a = body(s, 0, base_loc(0), 3, ready=True)
    rsv.resolve(s, T, V1, SPECS["Tactical Retreat"], 0, [a], -1, True)
    attack(s, 0, 0, a)
    fight(s)
    run(s)
    assert not alive(s, d) and alive(s, a) and int(s.perms[a, P_LOC]) == base_loc(0)
    assert int(s.points[0]) == 0


@case(11855, "Astral Heron's pending discount also pays an opponent's Deflect")
def _():
    need("Astral Heron", "Back Off", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("Back Off")])
    s.next_discount[0, :] = 2
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 1, base_loc(1))
    before = runes(s, 0)
    cast(s, 0, "Back Off", ir)
    run(s)
    assert runes(s, 0) == before, "no Power recycled for Deflect"


@case(11859, "a countered Flash is not played: Abandoned Hall gives nothing")
def _():
    need("Abandoned Hall", "Flash", "Crumbling Sands")
    s = fresh(hand=[T.id_of("Flash"), T.id_of("Discipline")])
    give(s, 1, "Crumbling Sands")
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    stay = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Discipline", stay)                     # Crumbling Sands needs another spell
    run(s, picking(stay))
    act(s, A.A_PLAY, hand_index(s, 0, "Flash"), 0)
    choose(s, u)
    choose(s, -1)                                      # "up to 2": just the one
    cast(s, 1, "Crumbling Sands", top_uid(s))
    run(s, picking(u))
    assert int(s.perms[u, P_LOC]) == bf_loc(0) and combat.might(s, T, u) == 3


@case(11860, "Irelia chosen by a Flash that is then countered keeps her +1")
def _():
    need("Irelia, Fervent", "Flash", "Defy")
    s = fresh(hand=[T.id_of("Flash")])
    give(s, 1, "Defy")
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, bf_loc(0))
    s.bf_ctrl[0] = 0
    act(s, A.A_PLAY, 0, 0)
    choose(s, ir)
    choose(s, -1)                                      # "up to 2": just the one
    run(s, stop=lambda s: s.n_chain and chain_names(s)[-1] == "Flash" and s.n_trig == 0
        and "Irelia, Fervent" not in chain_names(s))
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert int(s.perms[ir, P_LOC]) == bf_loc(0) and combat.might(s, T, ir) == 5


@case(11861, "Switcheroo on Irelia and Tasty Faefolk: her +1 first, then 6 and 5")
def _():
    need("Switcheroo", "Irelia, Fervent", "Tasty Faefolk")
    s = fresh(hand=[T.id_of("Switcheroo")])
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, bf_loc(0))
    tf = s.add_permanent(T.id_of("Tasty Faefolk"), 1, bf_loc(0))
    cast(s, 0, "Switcheroo", ir, tf)
    drain(s)
    assert combat.might(s, T, ir) == 6 and combat.might(s, T, tf) == 5, (
        combat.might(s, T, ir), combat.might(s, T, tf))


@case(11874, "Defy counters a Rebuttal aimed at your Discipline")
def _():
    need("Defy", "Rebuttal", "Discipline")
    s = fresh(hand=[T.id_of("Discipline"), T.id_of("Defy")])
    give(s, 1, "Rebuttal")
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    disc = top_uid(s)
    cast(s, 1, "Rebuttal", disc)
    cast(s, 0, "Defy", top_uid(s))
    run(s, picking(accept=False))
    assert combat.might(s, T, u) == 5 and int(s.n_hand[0]) == 1


@case(11877, "Forbidding Waste's -2 stops the moment a second defender arrives")
def _():
    need("Forbidding Waste")
    s = fresh()
    s.bf_card[0] = T.id_of("Forbidding Waste")
    s.bf_ctrl[0] = 1
    give(s, 1, "Smoke Screen")                        # keeps the showdown open
    d = body(s, 1, bf_loc(0), 4)
    a = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, a)
    assert s.showdown_bf == 0 and combat.might(s, T, d) == 2
    body(s, 1, bf_loc(0), 1)
    assert combat.might(s, T, d) == 4


@case(11882, "Shuriken Flip needs a friendly unit to move")
def _():
    need("Shuriken Flip")
    s = fresh(hand=[T.id_of("Shuriken Flip")])
    body(s, 1, bf_loc(0), 3)
    assert "Shuriken Flip" not in hand_plays(s, 0)


@case(11885, "Defy counters a Repeated Piercing Light: both executions")
def _():
    need("Defy", "Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=12)
    give(s, 1, "Defy")
    u = body(s, 1, bf_loc(0), 9)
    act(s, A.A_PLAY_REPEAT, 0, 0)
    for c in (u, -1, u, -1):                           # each execution: u, no second unit
        choose(s, c)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert int(s.perms[u, P_DMG]) == 0


@case(11894, "Blighted Battleaxe's 4 is not lethal while Punch First's +5 lasts")
def _():
    need("Blighted Battleaxe", "Punch First")
    s = fresh()
    u = body(s, 0, base_loc(0), 4)
    ax = s.add_permanent(T.id_of("Blighted Battleaxe"), 0, base_loc(0))
    s.attach(ax, u)
    rsv.resolve(s, T, V1, SPECS["Punch First"], 0, [u], -1, True)
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(), stop=lambda s: int(s.active) == 1)
    assert perm_of(s, "Shipyard Skulker"), "rows compact at turn end: look it up by name"


@case(11896, "Spoils of War costs 2 less once, however many enemies died")
def _():
    need("Spoils of War")
    for kills, cost in ((0, 4), (2, 2)):
        s = fresh(hand=[T.id_of("Spoils of War")])
        for _ in range(kills):
            combat.destroy(s, T, body(s, 1, base_loc(1), 3))
        A._settle(s, T, V1)
        before = ready_runes(s, 0)
        cast(s, 0, "Spoils of War")
        run(s)
        assert before - ready_runes(s, 0) == cost, (kills, before - ready_runes(s, 0))


@case(11901, "Ride the Wind readies a stunned unit but does not unstun it")
def _():
    need("Ride The Wind")
    s = fresh()
    u = body(s, 0, base_loc(0), 3)
    s.set_flag(u, F_STUNNED)
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [u, bf_loc(0)], -1, True)
    assert int(s.perms[u, P_READY]) == 1 and s.has_flag(u, F_STUNNED)


@case(11906, "Astral Heron at base when the first card is played: no discount later")
def _():
    need("Astral Heron")
    s = fresh(hand=[VANILLA])
    s.add_permanent(T.id_of("Astral Heron"), 0, base_loc(0))
    cast(s, 0, "Shipyard Skulker", base_loc(0))
    run(s)
    assert int(s.next_discount[0].sum()) == 0


@case(11907, "Vex - Apathetic stuns a Deflect unit without paying for Deflect")
def _():
    need("Vex - Apathetic", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("Irelia, Fervent")])
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    s.bf_ctrl[1] = 1
    before = runes(s, 1)
    cast(s, 0, "Irelia, Fervent", base_loc(0))
    run(s, picking())
    ir = perm_of(s, "Irelia, Fervent")[0]
    assert s.has_flag(ir, F_STUNNED) and runes(s, 1) == before


@case(11922, "Riposte counters Bone Skewer, which chooses no unit")
def _():
    need("Riposte", "Bone Skewer")
    s = fresh(hand=[T.id_of("Bone Skewer")])
    give(s, 1, "Riposte", "Shipyard Skulker")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 7)
    mine = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Bone Skewer", bf_loc(0))
    cast(s, 1, "Riposte", mine, top_uid(s))
    run(s, picking())
    assert combat.might(s, T, mine) == 3 + int(T.energy[T.id_of("Bone Skewer")])
    assert len(units(s, 1)) == 1, "no unit played from the revealed hand"


@case(11923, "Riposte needs a friendly unit to be played")
def _():
    need("Riposte", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")])
    give(s, 1, "Riposte")
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    pass_priority_to(s, 1)
    assert "Riposte" not in hand_plays(s, 1)


@case(11926, "Switcheroo cannot choose a Twilight Shrouded unit")
def _():
    need("Switcheroo")
    s = fresh(hand=[T.id_of("Switcheroo")])
    mine = body(s, 0, bf_loc(0), 3)
    a = body(s, 1, bf_loc(0), 5)
    b = body(s, 1, bf_loc(0), 6)
    s.set_flag(a, F_UNCHOOSABLE_TURN)
    act(s, A.A_PLAY, 0, 0)
    offered = {x.arg for x in A.legal_actions(s, T, V1, 0) if x.kind == A.A_TARGET}
    assert a not in offered and b in offered and mine in offered, offered


@case(11927, "Pickpocket can kill Seal of Discord: only Energy is compared")
def _():
    need("Pickpocket", "Seal of Discord")
    s = fresh(hand=[T.id_of("Pickpocket")])
    seal = s.add_permanent(T.id_of("Seal of Discord"), 1, base_loc(1))
    cast(s, 0, "Pickpocket", base_loc(0))
    assert seal in targets_offered(s, 0)


@case(11935, "Whirlwind lets the opponent return their own Baron Nashor")
def _():
    need("Whirlwind", "Baron Nashor")
    s = fresh(hand=[T.id_of("Whirlwind")])
    body(s, 0, base_loc(0), 3)
    bn = s.add_permanent(T.id_of("Baron Nashor"), 1, base_loc(1))
    cast(s, 0, "Whirlwind")
    run(s, picking(bn))
    assert not alive(s, bn), "the spell does not choose Baron; his controller does"


@case(11952, "Void Rush playing neither card draws both")
def _():
    need("Void Rush")
    s = fresh(hand=[T.id_of("Void Rush")])
    s.deck[0, :2] = [T.id_of("Watchful Sentry"), T.id_of("Discipline")]
    cast(s, 0, "Void Rush")

    def none(s, who, legal):
        return next((a for a in legal if a.kind in (A.A_PICK_NONE, A.A_DECLINE)), None)
    run(s, none)
    hand = sorted(T.names[int(c)] for c in s.hand[0, :int(s.n_hand[0])])
    assert hand == ["Discipline", "Watchful Sentry"], hand


@case(11966, "Frigid Touch Repeated with an empowered Mel: -3 twice")
def _():
    need("Frigid Touch", "Mel, Newly Awakened")
    s = fresh(hand=[T.id_of("Frigid Touch")], runes=12)
    mel = s.add_permanent(T.id_of("Mel, Newly Awakened"), 0, base_loc(0))
    s.set_flag(mel, F_EMPOWERED)
    u = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Frigid Touch", u, u, repeat=True)
    run(s)
    assert combat.might(s, T, u) == 3, combat.might(s, T, u)


@case(11967, "Mirror Image gives Temporary to the Reflection, not the chosen unit")
def _():
    need("Mirror Image")
    s = fresh()
    u = body(s, 1, base_loc(1), 3)
    rsv.resolve(s, T, V1, SPECS["Mirror Image"], 0, [u], -1, True)
    A._settle(s, T, V1)
    assert not combat.perm_kw(s, T, u, "Temporary")
    assert combat.perm_kw(s, T, tokens(s, 0)[0], "Temporary")


@case(11984, "Minotaur Reckoner stops Ride the Wind's move to base")
def _():
    need("Minotaur Reckoner", "Ride The Wind")
    s = fresh()
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Minotaur Reckoner"), 1, base_loc(1))
    u = body(s, 0, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [u, base_loc(0)], -1, True)
    assert int(s.perms[u, P_LOC]) == bf_loc(0) and int(s.perms[u, P_READY]) == 1


@case(11988, "Temporal Breach on a token: it ceases to exist and is not replayed")
def _():
    need("Temporal Breach", "Sprite Call")
    s = fresh()
    rsv.resolve(s, T, V1, SPECS["Sprite Call"], 0, [base_loc(0)], -1, True)
    tok = tokens(s, 0)[0]
    rsv.resolve(s, T, V1, SPECS["Temporal Breach"], 0, [tok], -1, True)
    run(s)
    assert not tokens(s, 0) and int(s.n_banished[0]) == 0


@case(11992, "a Reflection of a Dragon Formed Watchful Sentry has the printed 1 Might")
def _():
    need("Mirror Image", "Dragon Form", "Watchful Sentry")
    s = fresh()
    ws = s.add_permanent(T.id_of("Watchful Sentry"), 0, base_loc(0))
    rsv.resolve(s, T, V1, SPECS["Dragon Form"], 0, [ws], -1, True)
    rsv.resolve(s, T, V1, SPECS["Mirror Image"], 0, [ws], -1, True)
    A._settle(s, T, V1)
    assert combat.might(s, T, ws) == 5 and combat.might(s, T, tokens(s, 0)[0]) == 1


@case(11998, "a hidden Back Off cannot choose a unit at base")
def _():
    need("Back Off")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    jayce = body(s, 1, base_loc(1), 3)
    hidden_at(s, 0, 0, "Back Off")
    here = body(s, 0, bf_loc(0), 2)
    s.active, s.priority = 0, 0
    act(s, A.A_PLAY_HIDDEN, None, 0)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert jayce not in offered and here in offered, offered


@case(12012, "Unyielding Spirit prevents Glowstone's 5; Glowstone still dies")
def _():
    need("Glowstone", "Unyielding Spirit")
    s = fresh()
    gs = s.add_permanent(T.id_of("Glowstone"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Unyielding Spirit"], 0, [], -1, True)
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(), stop=lambda s: int(s.active) == 1)
    assert not perm_of(s, "Glowstone") and perm_of(s, "Shipyard Skulker")   # rows compacted


@case(12016, "Bellows Breath follows a unit Flashed to base")
def _():
    need("Bellows Breath", "Flash")
    s = fresh(hand=[T.id_of("Bellows Breath")])
    s.bf_ctrl[0] = 1
    r = body(s, 1, bf_loc(0), 3)
    act(s, A.A_PLAY, 0, 0)
    choose(s, r)
    while any(a.kind == A.A_PICK_NONE for a in A.legal_actions(s, T, V1, 0)):
        act(s, A.A_PICK_NONE, None, 0)
    rsv.resolve(s, T, V1, SPECS["Flash"], 1, [r, -1], -1, True)
    run(s)
    assert int(s.perms[r, P_LOC]) == base_loc(1) and int(s.perms[r, P_DMG]) == 1


@case(12020, "Sacrifice without a Mighty unit cannot be played")
def _():
    need("Sacrifice")
    s = fresh(hand=[T.id_of("Sacrifice")])
    body(s, 0, base_loc(0), 4)
    assert "Sacrifice" not in hand_plays(s, 0)


@case(12045, "Emperor's Divide moves units from only one battlefield")
def _():
    need("Emperor's Divide")
    s = fresh(hand=[T.id_of("Emperor's Divide")])
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    a = body(s, 0, bf_loc(0), 3)
    b = body(s, 0, bf_loc(1), 3)
    act(s, A.A_PLAY, 0, 0)
    choose(s, a)
    offered = {x.arg for x in A.legal_actions(s, T, V1, 0) if x.kind == A.A_TARGET}
    assert b not in offered


@case(12046, "Vi, Destructive activates as often as the trash can pay")
def _():
    need("Vi, Destructive")
    s = fresh()
    s.trash[0, :2], s.n_trash[0] = [VANILLA, VANILLA], 2
    vi = s.add_permanent(T.id_of("Vi, Destructive"), 0, base_loc(0))
    for _ in range(2):
        act(s, A.A_ACTIVATE, None, 0)
        run(s, picking(pack_trash(0, VANILLA)))
    assert combat.might(s, T, vi) == 5 and int(s.n_trash[0]) == 0
    assert not [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
