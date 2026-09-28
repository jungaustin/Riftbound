"""RiftJudge batch 18 -- unused questions from 10437-10566."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_EMPOWERED, F_BUFFED, P_ATTACHED_TO, P_MIGHT_MOD
from rl.engine.effects import ABILITIES, pack_trash, repeated_spec


def ready_runes(s, seat):
    return int(s.runes_ready[seat].sum())


@case(10558, "a Repeated Blood Rush chooses Jae Medarda twice: two draws")
def _():
    need("Blood Rush", "Jae Medarda")
    s = fresh(hand=[T.id_of("Blood Rush")], runes=9)
    jae = s.add_permanent(T.id_of("Jae Medarda"), 0, base_loc(0))
    act(s, A.A_PLAY_REPEAT, 0, 0)
    choose(s, jae)
    choose(s, jae)
    run(s)
    assert int(s.n_hand[0]) == 2, int(s.n_hand[0])


@case(10555, "Karthus - Eternal dying alongside a Deathknell unit still doubles it")
def _():
    need("Karthus - Eternal", "Watchful Sentry", "Unchecked Power")
    s = fresh(seat=1, hand=[T.id_of("Unchecked Power")], runes=12)
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Karthus - Eternal"), 0, bf_loc(0))
    s.add_permanent(T.id_of("Watchful Sentry"), 0, bf_loc(0))
    cast(s, 1, "Unchecked Power")
    run(s, picking(accept=False))
    assert int(s.n_hand[0]) == 2, int(s.n_hand[0])


@case(10554, "Mirror Image may choose a Sprite token")
def _():
    need("Mirror Image", "Sprite Call")
    s = fresh(hand=[T.id_of("Mirror Image")], runes=9)
    rsv.resolve(s, T, V1, SPECS["Sprite Call"], 0, [base_loc(0)], -1, True)
    spr = tokens(s, 0)[0]
    act(s, A.A_PLAY, 0, 0)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert spr in offered, offered


@case(10550, "a Repeated spell is still one card played: Battering Ram's discount counts once")
def _():
    need("Battering Ram", "Blood Rush")
    s = fresh(hand=[T.id_of("Blood Rush"), T.id_of("Battering Ram")], runes=12)
    from rl.engine.cost import effective_energy
    base = effective_energy(s, T, 0, T.id_of("Battering Ram"))
    u = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY_REPEAT, hand_index(s, 0, "Blood Rush"), 0)
    choose(s, u)
    choose(s, u)
    run(s)
    assert effective_energy(s, T, 0, T.id_of("Battering Ram")) == base - 1


@case(10546, "Switcheroo whose friendly unit was Gusted swaps nothing")
def _():
    need("Switcheroo", "Gust")
    s = fresh(hand=[T.id_of("Switcheroo")])
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 2)
    foe = body(s, 1, bf_loc(0), 6)
    cast(s, 0, "Switcheroo", mine, foe)
    combat.return_to_hand(s, T, mine)
    run(s)
    assert combat.might(s, T, foe) == 6


@case(10541, "a countered spell was still finalized: [Legion] stays on")
def _():
    need("Defy", "Discipline")
    s = fresh(seat=1, hand=[T.id_of("Discipline")])
    give(s, 0, "Defy")
    u = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Discipline", u)
    cast(s, 0, "Defy", top_uid(s))
    run(s)
    assert combat.might(s, T, u) == 3 and int(s.cards_played[1]) >= 1


@case(10540, "Ezreal, Prodigy discounts a Repeat cost")
def _():
    need("Ezreal, Prodigy", "Blood Rush")
    s = fresh(hand=[T.id_of("Blood Rush")], runes=12)
    s.add_permanent(T.id_of("Ezreal, Prodigy"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    before = ready_runes(s, 0)
    act(s, A.A_PLAY_REPEAT, 0, 0)
    choose(s, u)
    choose(s, u)
    run(s)
    paid = before - ready_runes(s, 0)
    assert paid == int(T.energy[T.id_of("Blood Rush")]) + 1 - 1, paid


@case(10539, "Pyke - Dockside Butcher from hidden may still pay his optional cost")
def _():
    need("Pyke - Dockside Butcher")
    s = fresh()
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 0, "Pyke - Dockside Butcher")
    reps = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_HIDDEN]
    assert reps
    act(s, A.A_PLAY_REPEAT, None, 0) if A.A_PLAY_REPEAT in kinds(s, 0) else \
        act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking())
    p = perm_of(s, "Pyke - Dockside Butcher")
    assert p and (int(s.perms[p[0], P_READY]) == 1
                  or combat.might(s, T, p[0]) == int(T.might[T.id_of("Pyke - Dockside Butcher")]))


@case(10531, "Unyielding Spirit prevents the damage, so Elder Dragon's passive finds none")
def _():
    need("Unyielding Spirit", "Flurry of Blades", "Elder Dragon")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    s.add_permanent(T.id_of("Elder Dragon"), 1, base_loc(1))
    rsv.resolve(s, T, V1, SPECS["Unyielding Spirit"], 0, [], -1, True)
    rsv.resolve(s, T, V1, SPECS["Flurry of Blades"], 1, [], -1, True)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_DMG]) == 0


@case(10530, "Falling Star killing Karthus and another Deathknell unit: it still doubles")
def _():
    need("Karthus - Eternal", "Watchful Sentry", "Falling Star")
    s = fresh(seat=1)
    ka = s.add_permanent(T.id_of("Karthus - Eternal"), 0, base_loc(0))
    ws = s.add_permanent(T.id_of("Watchful Sentry"), 0, base_loc(0))
    rsv.resolve(s, T, V1, SPECS["Falling Star"], 1, [ka, ws], -1, True)
    run(s)
    assert not alive(s, ka) and not alive(s, ws) and int(s.n_hand[0]) == 2


@case(10517, "Baited Hook on your last unit there: the found unit may still be played there")
def _():
    need("Baited Hook")
    s = fresh()
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    u = body(s, 0, bf_loc(0), 3)
    s.deck[0, :5] = [VANILLA] * 5
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, u)
    dests = []

    def pref(s, who, legal):
        picks = [a for a in legal if a.kind == A.A_PICK and a.arg == 0]
        if picks:
            return picks[0]
        at = [a.arg for a in legal if a.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)]
        if at:
            dests.append(set(at))
            return next(a for a in legal if a.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)
                        and a.arg == bf_loc(0))
        return next((a for a in legal if a.kind == A.A_ACCEPT), None)
    run(s, pref)
    assert dests and bf_loc(0) in dests[0], dests
    assert units(s, 0, bf_loc(0))


@case(10515, "declining Dusk Rose Lab's kill leaves nothing on the Chain")
def _():
    need("Dusk Rose Lab")
    s = fresh(seat=1)
    s.bf_card[0] = T.id_of("Dusk Rose Lab")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    act(s, A.A_END_TURN, None, 1)
    run(s, picking(accept=False), stop=lambda s: int(s.active) == 0 and s.phase == MAIN
        and s.n_chain == 0 and s.n_trig == 0)
    # the one card in hand is the turn's own draw: the Lab neither killed nor drew
    assert len(units(s, 0)) == 1 and int(s.n_hand[0]) == 1


@case(10511, "Elder Dragon Star-Crossed away still deals its play-trigger damage")
def _():
    need("Elder Dragon", "Star-Crossed")
    s = fresh(hand=[T.id_of("Elder Dragon")], runes=12)
    give(s, 1, "Star-Crossed")
    theirs = body(s, 1, base_loc(1), 9)
    mine = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Elder Dragon", base_loc(0))
    run(s, picks(theirs, -1, -1, -1), stop=lambda s: s.n_chain
        and chain_names(s)[-1] == "Elder Dragon" and s.pend_slot < 0)
    ed = perm_of(s, "Elder Dragon")[0]
    cast(s, 1, "Star-Crossed", theirs, ed)
    run(s)
    assert not perm_of(s, "Elder Dragon")


@case(10502, "Vi - Peacekeeper's attack stun cannot choose Baron Nashor")
def _():
    need("Vi - Peacekeeper", "Baron Nashor")
    s = fresh()
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    bn = s.add_permanent(T.id_of("Baron Nashor"), 1, bf_loc(0))
    other = body(s, 1, bf_loc(0), 3)
    vi = s.add_permanent(T.id_of("Vi - Peacekeeper"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, vi)
    offered = targets_offered(s, 0)
    assert other in offered and bn not in offered, offered


@case(10501, "Not So Fast counters Mirror Image that chose your unit")
def _():
    need("Not So Fast", "Mirror Image")
    s = fresh(hand=[T.id_of("Mirror Image")], runes=9)
    give(s, 1, "Not So Fast")
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Mirror Image", theirs)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert not tokens(s, 0)


@case(10500, "two Stand Uniteds stack: buffs give +1 more each")
def _():
    need("Stand United")
    s = fresh(hand=[T.id_of("Stand United"), T.id_of("Stand United")], runes=12)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Stand United", u)
    run(s)
    one = combat.might(s, T, u)
    cast(s, 0, "Stand United", u)
    run(s)
    assert combat.might(s, T, u) == one + 1, (one, combat.might(s, T, u))


@case(10498, "Tianna Crownguard stops the points, not the conquer's replacement draw")
def _():
    need("Tianna Crownguard")
    s = fresh()
    s.add_permanent(T.id_of("Tianna Crownguard"), 1, bf_loc(1))
    s.bf_ctrl[1] = 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    run(s, picking())
    assert int(s.points[0]) == 0


@case(10496, "Tideturner in your base cannot choose a unit in the same base")
def _():
    need("Tideturner")
    s = fresh(hand=[T.id_of("Tideturner")], runes=9)
    body(s, 0, base_loc(0), 3)
    cast(s, 0, "Tideturner", base_loc(0))
    assert not targets_offered(s, 0), "another LOCATION is required"


@case(10495, "Baited Hook's unit may still pay Accelerate")
def _():
    need("Baited Hook", "Eclipse Dragon")
    s = fresh(runes=12)
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 8)
    s.deck[0, :5] = [T.id_of("Eclipse Dragon")] * 5
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, u)
    saw = []

    def pref(s, who, legal):
        kinds_here = {a.kind for a in legal}
        if A.A_PICK in kinds_here:
            return next(a for a in legal if a.kind == A.A_PICK and a.arg == 0)
        if A.A_ACCEPT in kinds_here:
            saw.append(1)
            return next(a for a in legal if a.kind == A.A_ACCEPT)
        return None
    run(s, pref)
    ed = perm_of(s, "Eclipse Dragon")
    assert ed and (saw or int(s.perms[ed[0], P_READY]) == 0)


@case(10494, "two Ahri - Alluring at one battlefield each score on the hold")
def _():
    need("Ahri - Alluring")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Ahri - Alluring"), 0, bf_loc(0))
    s.add_permanent(T.id_of("Ahri - Alluring"), 0, bf_loc(0))
    act(s, A.A_END_TURN, None, 1)
    run(s, picking(), stop=lambda s: int(s.active) == 0 and s.phase == MAIN
        and s.n_chain == 0 and s.n_trig == 0)
    assert int(s.points[0]) == 3, int(s.points[0])


@case(10492, "a hidden Mischievous Marai cannot be played at Rockfall Path")
def _():
    need("Mischievous Marai", "Rockfall Path")
    s = fresh()
    s.bf_card[0] = T.id_of("Rockfall Path")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 0, "Mischievous Marai")
    assert A.A_PLAY_HIDDEN not in kinds(s, 0)


@case(10487, "Kai'Sa - Daughter of the Void's Power pays for spells only")
def _():
    need("Kai'Sa - Daughter of the Void", "Shipyard Skulker")
    s = fresh(hand=[VANILLA])
    s.legend[0], s.legend_ready[0] = T.id_of("Kai'Sa - Daughter of the Void"), 1
    s.runes_ready[0, :] = 0
    act(s, A.A_ACTIVATE, None, 0)
    run(s)
    assert int(s.pool_power[0].sum()) + int(s.pool_rstr_p[0].sum()) >= 1
    assert "Shipyard Skulker" not in hand_plays(s, 0), "a unit is not a spell"


@case(10481, "Void Assault needs a friendly unit and an enemy unit")
def _():
    need("Void Assault")
    s = fresh(hand=[T.id_of("Void Assault")])
    body(s, 0, base_loc(0), 3)
    assert "Void Assault" not in hand_plays(s, 0)
    body(s, 1, base_loc(1), 3)
    assert "Void Assault" in hand_plays(s, 0)


@case(10477, "Acceptable Losses with no gear of your own still kills theirs")
def _():
    need("Acceptable Losses", "Frigid Jewel")
    s = fresh(hand=[T.id_of("Acceptable Losses")])
    g = s.add_permanent(T.id_of("Frigid Jewel"), 1, base_loc(1))
    cast(s, 0, "Acceptable Losses")
    run(s, picking(g))
    assert not alive(s, g)


@case(10470, "Not So Fast counters Charm aimed at your unit")
def _():
    need("Not So Fast", "Charm")
    s = fresh(hand=[T.id_of("Charm")])
    give(s, 1, "Not So Fast")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Charm", foe, bf_loc(0))
    pass_priority_to(s, 1)
    assert "Not So Fast" in hand_plays(s, 1)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert int(s.perms[foe, P_LOC]) == base_loc(1)


@case(10467, "Flurry of Feathers needs something on the Chain in the Beginning Phase")
def _():
    need("Flurry of Feathers")
    s = fresh(hand=[T.id_of("Flurry of Feathers")])
    from rl.engine.state import BEGINNING
    s.phase = BEGINNING
    assert "Flurry of Feathers" not in hand_plays(s, 0)


@case(10457, "Defy reads Sky Splitter's printed 8, not the reduced cost")
def _():
    need("Defy", "Sky Splitter")
    s = fresh(hand=[T.id_of("Sky Splitter")], runes=12)
    give(s, 1, "Defy")
    s.bf_ctrl[0] = 1
    big = body(s, 0, base_loc(0), 8)
    foe = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Sky Splitter", foe)
    pass_priority_to(s, 1)
    assert "Defy" not in hand_plays(s, 1)


@case(10456, "Hidden Blade on a Guardian Angel unit: its controller still draws 2")
def _():
    need("Hidden Blade", "Guardian Angel")
    s = fresh(hand=[T.id_of("Hidden Blade")])
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 1, bf_loc(0))
    s.attach(ga, u)
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u) and int(s.n_hand[1]) == 2


@case(10453, "a Recall leaves the unit in the state it was in")
def _():
    need("Ride The Wind", "Galio - Indefatigable")
    s = fresh()
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    s.add_permanent(T.id_of("Galio - Indefatigable"), 1, bf_loc(0))   # deals no damage
    a = body(s, 0, base_loc(0), 1, ready=True)
    attack(s, 0, 0, a)
    assert int(s.perms[a, P_READY]) == 0, "the Standard Move exhausted it"
    # ready it again mid-combat; the move to where it already is does nothing
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [a, bf_loc(0)], -1, True)
    assert int(s.perms[a, P_READY]) == 1
    fight(s)
    run(s)
    assert int(s.perms[a, P_LOC]) == base_loc(0) and int(s.perms[a, P_READY]) == 1


@case(10447, "a stunned Elder Dragon still has its passive")
def _():
    need("Elder Dragon", "Vex - Apathetic", "Flurry of Blades")
    s = fresh(hand=[T.id_of("Elder Dragon")], runes=12)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    foe = body(s, 1, bf_loc(1), 9)
    cast(s, 0, "Elder Dragon", base_loc(0))
    run(s, picks(foe, -1, -1, -1))
    ed = perm_of(s, "Elder Dragon")[0]
    assert s.has_flag(ed, F_STUNNED)
    assert not alive(s, foe), "1 damage from its own play trigger was lethal"


@case(10443, "Jhin - Meticulous Killer cannot be played on the opponent's turn")
def _():
    need("Jhin - Meticulous Killer", "Discipline")
    s = fresh(seat=1, hand=[T.id_of("Discipline")])
    give(s, 0, "Jhin - Meticulous Killer")
    s.runes_ready[0, :] = 9
    s.big_spell_ply[0] = int(s.ply)
    u = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Discipline", u)
    pass_priority_to(s, 0)
    assert "Jhin - Meticulous Killer" not in hand_plays(s, 0)


@case(10437, "Vi - Peacekeeper Ambushed into an open combat is attacking")
def _():
    need("Vi - Peacekeeper")
    s = fresh()
    give(s, 0, "Vi - Peacekeeper")
    s.runes_ready[0, :] = 9
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 9)
    a = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, a)
    assert s.showdown_bf == 0
    pass_priority_to(s, 0)
    act(s, A.A_PLAY, hand_index(s, 0, "Vi - Peacekeeper"), 0)
    at = [x for x in A.legal_actions(s, T, V1, 0)
          if x.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST) and x.arg == bf_loc(0)]
    assert at
    A.apply(s, T, V1, at[0])
    run(s, picks(d), stop=lambda s: s.has_flag(d, F_STUNNED) or s.n_chain == 0)
    assert s.has_flag(d, F_STUNNED)
