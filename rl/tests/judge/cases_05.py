"""RiftJudge batch 5 -- unused questions from 11180-11375."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.engine.state import C_UID, F_BUFFED


def to_trigger(s, name):
    """Advance until `name`'s ability is the newest item on the Chain."""
    run(s, picking(), stop=lambda s: s.n_chain and chain_names(s)[-1] == name
        and s.pend_slot < 0 and s.pend_may < 0 and not chain_mod.decision_open(s))
    assert s.n_chain and chain_names(s)[-1] == name, chain_names(s)


@case(11183, "Azir - Sovereign bounced in answer: his 'this battlefield' pulls no tokens")
def _():
    need("Azir - Sovereign", "Star-Crossed", "Sprite Call")
    s = fresh()
    give(s, 1, "Star-Crossed")
    s.bf_ctrl[0] = 1
    theirs = body(s, 1, bf_loc(0), 1)
    tok = tokens(s)
    rsv.resolve(s, T, V1, SPECS["Sprite Call"], 0, [base_loc(0)], -1, True)
    A._settle(s, T, V1)
    tok = tokens(s, 0)[0]
    az = s.add_permanent(T.id_of("Azir - Sovereign"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, az)
    run(s, picking(tok), stop=lambda s: s.n_chain and chain_names(s)[-1].startswith("Azir")
        and s.pend_slot < 0 and s.pend_may < 0)
    pass_priority_to(s, 1)
    cast(s, 1, "Star-Crossed", theirs, az)
    run(s, picking(tok))
    assert int(s.perms[tok, P_LOC]) == base_loc(0), "FAQ #11149 -- the ability whiffs"


@case(11188, "Tideturner stunned by Vex stays put; the other unit still moves")
def _():
    need("Tideturner", "Vex - Apathetic")
    # Tideturner's controller is the turn player, so their trigger is placed
    # first and Vex's resolves first (383.3.d) -- the case the ruling covers.
    s = fresh(seat=0)
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    body(s, 0, bf_loc(0), 3)
    other = body(s, 0, base_loc(0), 3)
    fd = list(fd_slots(0))[0]
    s.fd_owner[fd], s.fd_card[fd], s.fd_ply[fd] = 0, T.id_of("Tideturner"), -5
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(other))
    tt = perm_of(s, "Tideturner")[0]
    assert s.has_flag(tt, F_STUNNED), "Vex stunned it"
    assert int(s.perms[tt, P_LOC]) == bf_loc(0), "'can't move it this turn'"
    assert int(s.perms[other, P_LOC]) == bf_loc(0), "FAQ #10318 -- the other half moves"


@case(11205, "Not So Fast counters Harnessed Dragon's 'kill an enemy unit'")
def _():
    need("Harnessed Dragon", "Not So Fast")
    s = fresh(hand=[T.id_of("Harnessed Dragon")])
    s.runes_ready[:, :] = 9
    give(s, 1, "Not So Fast")
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Harnessed Dragon", base_loc(0))
    run(s, picking(foe), stop=lambda s: s.n_chain and s.pend_slot < 0
        and not chain_mod.decision_open(s))
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert alive(s, foe)


@case(11220, "Defy reads Call to Glory's printed cost, even when the buff paid for it")
def _():
    need("Defy", "Call to Glory")
    s = fresh(hand=[T.id_of("Call to Glory")])
    give(s, 1, "Defy")
    u = body(s, 0, base_loc(0), 3)
    s.set_flag(u, F_BUFFED)
    act(s, A.A_PLAY_REPEAT, 0, 0)
    run(s, picking(u), stop=lambda s: s.n_chain and s.pend_slot < 0
        and not chain_mod.decision_open(s) and s.pend_cost_kill < 0)
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1), "3 Energy printed <= 4"


@case(11228, "a Defied Thrill of the Hunt banishes nothing -- the banish is its effect")
def _():
    need("Thrill of the Hunt", "Defy")
    s = fresh(hand=[T.id_of("Thrill of the Hunt")])
    give(s, 1, "Defy")
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Thrill of the Hunt", u, bf_loc(0))
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert alive(s, u) and int(s.n_banished[0]) == 0


@case(11230, "Ezreal, Prodigy makes Pyke's optional [Fury] cost free")
def _():
    need("Ezreal, Prodigy", "Pyke - Dockside Butcher")
    from rl.engine import actions as AA
    s = fresh()
    s.add_permanent(T.id_of("Ezreal, Prodigy"), 0, base_loc(0))
    pk = T.id_of("Pyke - Dockside Butcher")
    base = AA.optional_add_cost(T, pk)
    red = AA.reduced_add_cost(s, T, 0, base)
    assert base is not None and red is not None and sum(red) < sum(base), (
        f"'optional additional costs cost [A] less': {base} -> {red}")


@case(11231, "Thousand-Tailed Watcher bounced in answer: its -3 still resolves")
def _():
    need("Thousand-Tailed Watcher", "Star-Crossed")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")])
    s.runes_ready[:, :] = 9
    give(s, 1, "Star-Crossed")
    foe = body(s, 1, base_loc(1), 5)
    stayer = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Thousand-Tailed Watcher", base_loc(0))
    to_trigger(s, "Thousand-Tailed Watcher")
    w = perm_of(s, "Thousand-Tailed Watcher")[0]
    cast(s, 1, "Star-Crossed", foe, w)
    run(s)
    assert not perm_of(s, "Thousand-Tailed Watcher"), "bounced"
    assert combat.might(s, T, stayer) == 2, "FAQ #9750 -- the -3 still resolved"


@case(11239, "Janna moving Vi - Peacekeeper home: Vi's stun has no 'here'")
def _():
    need("Janna - Savior", "Vi - Peacekeeper")
    s = fresh(seat=1)
    give(s, 0, "Janna - Savior")
    s.bf_ctrl[0] = 0
    spr = body(s, 0, bf_loc(0), 3)
    vi = s.add_permanent(T.id_of("Vi - Peacekeeper"), 1, base_loc(1), ready=True)
    attack(s, 1, 0, vi)
    run(s, picking(spr), stop=lambda s: s.n_chain and chain_names(s)[-1].startswith("Vi")
        and s.pend_slot < 0)
    pass_priority_to(s, 0)
    cast(s, 0, "Janna - Savior", bf_loc(0))
    run(s, picking(vi, spr))
    assert int(s.perms[vi, P_LOC]) == base_loc(1), "Janna moved her"
    assert not s.has_flag(spr, F_STUNNED), "'an enemy unit HERE' -- nobody is"


@case(11241, "Riptide Rex's 6 outside combat is not healed before the next move")
def _():
    need("Riptide Rex")
    s = fresh(hand=[T.id_of("Riptide Rex")])
    s.runes_ready[:, :] = 9
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Riptide Rex", base_loc(0))
    run(s, picking(foe))
    assert int(s.perms[foe, P_DMG]) == 6
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    fight(s)
    assert not alive(s, foe), "6 still marked + 3 combat damage = lethal on a 9"


@case(11242, "Star-Crossed needs a friendly unit to be played")
def _():
    need("Star-Crossed")
    s = fresh(hand=[T.id_of("Star-Crossed")])
    body(s, 1, base_loc(1), 3)
    assert "Star-Crossed" not in hand_plays(s, 0)
    body(s, 0, base_loc(0), 3)
    assert "Star-Crossed" in hand_plays(s, 0)


@case(11249, "Baited Hook's target killed in response: no Might to measure, nothing played")
def _():
    need("Baited Hook")
    s = fresh()
    s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 3)
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, u)
    combat.destroy(s, T, u)                          # the response
    run(s, picking())
    assert len(units(s, 0)) == 0, "359.3.e.12"


@case(11250, "The Arena's Greatest triggers even when nobody controls it")
def _():
    need("The Arena's Greatest")
    s = fresh()
    rune_deck(s)
    s.bf_card[0] = T.id_of("The Arena's Greatest")
    assert int(s.bf_ctrl[0]) == -1, "uncontrolled"
    s.turn, s.ply, s.active = 1, 0, 0
    phases.start_turn(s, T, V1)
    A._settle(s, T, V1)
    run(s)
    assert int(s.points[0]) == 1, f"187.6.b -- the turn player controls it: {int(s.points[0])}"


@case(11255, "Kato the Arm cannot pick himself: 'another friendly unit'")
def _():
    need("Kato the Arm")
    s = fresh()
    k = s.add_permanent(T.id_of("Kato the Arm"), 0, base_loc(0), ready=True)
    pal = body(s, 0, base_loc(0), 2)
    attack(s, 0, 0, k)
    offered = set()
    for _ in range(10):
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who)
        tg = {a.arg for a in legal if a.kind == A.A_TARGET}
        if tg:
            offered = tg
            break
        pick = next((a for a in legal if a.kind in (A.A_ACCEPT, A.A_ORDER, A.A_PASS)), None)
        if pick is None:
            break
        A.apply(s, T, V1, pick)
    assert pal in offered and k not in offered, offered


@case(11258, "Traveling Merchant Gusted in answer still discards and draws")
def _():
    need("Traveling Merchant", "Gust")
    s = fresh(hand=[VANILLA])
    give(s, 1, "Gust")
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, tm)
    to_trigger(s, "Traveling Merchant")
    cast(s, 1, "Gust", tm)
    hand = int(s.n_hand[0])
    run(s, picking(0))
    assert int(s.n_trash[0]) >= 1, "discarded 1"
    assert int(s.n_hand[0]) == hand + 1, "Merchant back, -1 discard, +1 draw"


@case(11261, "Stupefy's target Thrilled away: no -1, still draws")
def _():
    need("Stupefy", "Thrill of the Hunt")
    s = fresh()
    u = body(s, 1, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Thrill of the Hunt"], 1, [u, bf_loc(1)], -1, True)
    A._settle(s, T, V1)
    run(s)
    new = units(s, 1)[0]
    rsv.resolve(s, T, V1, SPECS["Stupefy"], 0, [u], -1, True)
    assert combat.might(s, T, new) == 3 and int(s.n_hand[0]) == 1


@case(11276, "a Flurry of Blades may answer the Lilting Lullaby countering the first")
def _():
    need("Flurry of Blades", "Lilting Lullaby")
    s = fresh(hand=[T.id_of("Flurry of Blades"), T.id_of("Flurry of Blades")])
    give(s, 1, "Lilting Lullaby")
    cast(s, 0, "Flurry of Blades")
    cast(s, 1, "Lilting Lullaby", top_uid(s))
    pass_priority_to(s, 0)
    assert "Flurry of Blades" in hand_plays(s, 0), "both are [Reaction]"


@case(11280, "Abandoned Hall: the countered spell gives nothing, the counterspell does")
def _():
    need("Abandoned Hall", "Discipline", "Defy")
    s = fresh(hand=[T.id_of("Discipline")])
    give(s, 1, "Defy")
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    s.add_permanent(T.id_of("Soaring Scout"), 1, bf_loc(1))
    theirs = body(s, 1, bf_loc(0), 3)
    s.showdown_bf, s.showdown_combat = 0, 1
    cast(s, 0, "Discipline", mine)
    cast(s, 1, "Defy", top_uid(s))
    run(s, picking(mine, theirs))
    assert combat.might(s, T, mine) == 3, "425.1.b -- Discipline was never played"
    assert combat.might(s, T, theirs) == 4, "Defy was, so its player may take +1"


@case(11287, "Hidden Blade on a Guardian Angel unit: saved, and its controller draws 2")
def _():
    need("Hidden Blade", "Guardian Angel")
    s = fresh()
    u = body(s, 1, bf_loc(0), 3)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 1, bf_loc(0))
    s.attach(ga, u)
    rsv.resolve(s, T, V1, SPECS["Hidden Blade"], 0, [u], -1, True)
    assert alive(s, u) and int(s.n_hand[1]) == 2


@case(11294, "Icathian Rain is one spell: Ravenbloom Student +1")
def _():
    need("Icathian Rain", "Ravenbloom Student")
    s = fresh(hand=[T.id_of("Icathian Rain")])
    s.runes_ready[:, :] = 9
    st = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0))
    foe = body(s, 1, base_loc(1), 20)
    act(s, A.A_PLAY, 0, 0)
    run(s, picking(foe))
    assert int(s.perms[foe, P_DMG]) == 12 and combat.might(s, T, st) == 3


@case(11312, "Janna sends Atakhan home before 'the defender must kill' resolves")
def _():
    need("Atakhan", "Janna - Savior")
    s = fresh(seat=1)
    give(s, 0, "Janna - Savior")
    s.bf_ctrl[0] = 0
    d = body(s, 0, bf_loc(0), 3)
    at = s.add_permanent(T.id_of("Atakhan"), 1, base_loc(1), ready=True)
    attack(s, 1, 0, at)
    run(s, stop=lambda s: s.n_chain and chain_names(s)[-1] == "Atakhan" and s.pend_slot < 0)
    pass_priority_to(s, 0)
    cast(s, 0, "Janna - Savior", bf_loc(0))
    run(s, picking(at))
    assert alive(s, d), "'here' is his base now, where you have no units"


@case(11314, "Vex - Apathetic stuns a Deflect unit without paying -- it chooses nothing")
def _():
    need("Vex - Apathetic", "Commander Ledros")
    s = fresh(seat=1, hand=[])
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Vex - Apathetic"), 0, bf_loc(0))
    s.hand[1, 0], s.n_hand[1] = T.id_of("Commander Ledros"), 1
    s.runes_ready[:, :] = 9
    before = runes(s, 0)
    act(s, A.A_PLAY, 0, 1)
    act(s, A.A_DECLINE, None, 1)                   # kill nothing for a discount
    act(s, A.A_PLAY_AT, base_loc(1), 1)
    run(s)
    led = perm_of(s, "Commander Ledros")
    assert led and s.has_flag(led[0], F_STUNNED), "stunned on arrival"
    assert runes(s, 0) == before, "355.10.d -- no Deflect: nothing was chosen"


@case(11315, "Gust returns a token, which then ceases to exist")
def _():
    need("Gust", "Sprite Call")
    s = fresh()
    spr = _sprite_at(s, 0, 0)
    rsv.resolve(s, T, V1, SPECS["Gust"], 1, [spr], -1, True)
    assert not alive(s, spr) and int(s.n_hand[0]) == 0


@case(11332, "Challenge is not combat: Fiora - Peerless does not trigger")
def _():
    need("Challenge", "Fiora - Peerless")
    s = fresh()
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 0, base_loc(0))
    foe = body(s, 1, base_loc(1), 2)
    rsv.resolve(s, T, V1, SPECS["Challenge"], 0, [fi, foe], -1, True)
    A._settle(s, T, V1)
    assert s.n_chain == 0 and s.n_trig == 0 and combat.might(s, T, fi) == 3


@case(11338, "Rengar, Trophy Hunter cannot be played to Rockfall Path")
def _():
    need("Rengar, Trophy Hunter", "Rockfall Path")
    s = fresh(seat=1)
    s.bf_card[0] = T.id_of("Rockfall Path")
    s.hand[0, 0], s.n_hand[0] = T.id_of("Rengar, Trophy Hunter"), 1
    body(s, 1, bf_loc(0), 2)
    body(s, 0, bf_loc(1), 2)
    s.showdown_bf, s.priority = 0, 0
    assert not A.ambush_playable(s, T, V1, 0) or bf_loc(0) not in [
        a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT_FAST], (
        "Can't beats can")


@case(11340, "Eye of the Herald's unit killed in answer: no Recruit")
def _():
    need("Eye of the Herald", "Hidden Blade")
    s = fresh()
    u = body(s, 0, base_loc(0), 3, ready=True)
    g = s.add_permanent(T.id_of("Eye of the Herald"), 0, base_loc(0))
    s.attach(g, u)
    attack(s, 0, 0, u)
    run(s, stop=lambda s: s.n_chain > 0 and s.pend_slot < 0)
    combat.destroy(s, T, u)
    run(s)
    assert not [i for i in tokens(s, 0) if "Recruit" in T.names[int(s.perms[i, P_CARD])]]


@case(11341, "Gearhead doubles Brutalizer's printed +1 only: 3 + 2 + 2 = 7")
def _():
    need("Gearhead", "Brutalizer")
    s = fresh()
    gh = s.add_permanent(T.id_of("Gearhead"), 0, base_loc(0))
    br = s.add_permanent(T.id_of("Brutalizer"), 0, base_loc(0))
    s.attach(br, gh)
    assert combat.might(s, T, gh) == 7, f"got {combat.might(s, T, gh)}"


@case(11342, "En Garde on a lone unit at Abandoned Hall: +2, then the Hall's +1")
def _():
    need("En Garde", "Abandoned Hall")
    s = fresh(hand=[T.id_of("En Garde")])
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "En Garde", u)
    run(s, picking(u))
    assert combat.might(s, T, u) == 6


@case(11345, "Vi - Peacekeeper's attack stun cannot choose Baron Nashor")
def _():
    need("Vi - Peacekeeper", "Baron Nashor")
    s = fresh()
    s.bf_ctrl[0] = 1
    baron = s.add_permanent(T.id_of("Baron Nashor"), 1, bf_loc(0))
    vi = s.add_permanent(T.id_of("Vi - Peacekeeper"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, vi)
    offered = set()
    for _ in range(8):
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who)
        offered |= {a.arg for a in legal if a.kind == A.A_TARGET}
        if offered or not legal:
            break
        A.apply(s, T, V1, next((a for a in legal if a.kind in (A.A_ORDER, A.A_PASS)), legal[0]))
    assert baron not in offered and not s.has_flag(baron, F_STUNNED)


@case(11348, "Void Assault into a battlefield you don't control: you are the attacker")
def _():
    need("Void Assault")
    s = fresh()
    s.hand[1, 0], s.n_hand[1] = T.id_of("Smoke Screen"), 1
    mine = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 3)
    rsv.resolve(s, T, V1, SPECS["Void Assault"], 0,
                [mine, bf_loc(0), theirs, bf_loc(0)][:SPECS["Void Assault"].n_targets],
                -1, True)
    A._settle(s, T, V1)
    assert s.showdown_bf == 0 and int(s.attacker) == 0


@case(11350, "Rally the Troops buffs Recruit tokens played this turn")
def _():
    need("Rally the Troops", "Vanguard Captain")
    s = fresh()
    rsv.resolve(s, T, V1, SPECS["Rally the Troops"], 0, [], -1, True,
                card=T.id_of("Rally the Troops"))
    s.cards_played[0] = 1
    cap = s.add_permanent(T.id_of("Vanguard Captain"), 0, base_loc(0))
    spec = abilities_for(T, T.id_of("Vanguard Captain"))[0]
    from rl.engine.state import F_LEGION
    s.set_flag(cap, F_LEGION)
    rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=cap)
    A._settle(s, T, V1)
    run(s)
    recs = [i for i in tokens(s, 0) if "Recruit" in T.names[int(s.perms[i, P_CARD])]]
    assert recs and all(s.has_flag(i, F_BUFFED) for i in recs)


@case(11352, "Blighted Battleaxe's 4 is healed in the same turn's Expiration Step")
def _():
    need("Blighted Battleaxe")
    s = fresh()
    u = body(s, 0, base_loc(0), 20)
    ax = s.add_permanent(T.id_of("Blighted Battleaxe"), 0, base_loc(0))
    s.attach(ax, u)
    act(s, A.A_END_TURN, None, 0)
    run(s)
    uu = [i for i in units(s, 0)]
    assert uu and int(s.perms[uu[0], P_DMG]) == 0


@case(11353, "a repeated Frigid Touch on Fiora - Victorious pays Deflect twice")
def _():
    need("Frigid Touch", "Fiora - Victorious", "B.F. Sword")
    s = fresh(hand=[T.id_of("Frigid Touch")])
    fi = s.add_permanent(T.id_of("Fiora - Victorious"), 1, base_loc(1))
    sw = s.add_permanent(T.id_of("B.F. Sword"), 1, base_loc(1))
    s.attach(sw, fi)
    assert combat.perm_kw(s, T, fi, "Deflect")
    before = runes(s, 0)
    cast(s, 0, "Frigid Touch", fi, repeat=True)
    run(s, picking(fi))
    assert before - runes(s, 0) == 2, f"both chosen while Mighty: {before - runes(s, 0)}"


@case(11356, "Traveling Merchant with an empty hand still draws")
def _():
    need("Traveling Merchant")
    s = fresh()
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, tm)
    run(s)
    assert int(s.n_hand[0]) == 1


@case(11359, "Elder Dragon's play effect cannot choose Ruin Runner; the Watcher still shrinks it")
def _():
    need("Elder Dragon", "Ruin Runner", "Thousand-Tailed Watcher")
    s = fresh()
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, bf_loc(0))
    ed = abilities_for(T, T.id_of("Elder Dragon"))[0]
    for k in range(ed.n_targets if hasattr(ed, "n_targets") else len(ed.targets)):
        assert rr not in rsv.legal_targets(s, T, ed, k, 0, [-1] * k, -1)
    w = s.add_permanent(T.id_of("Thousand-Tailed Watcher"), 0, base_loc(0))
    rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Thousand-Tailed Watcher"))[0],
                0, [], -1, False, source=w)
    assert combat.might(s, T, rr) == 2, "#11360 -- no choosing, so it applies"


@case(11362, "a hidden Emperor's Divide saves units from Elder Dragon's play effect")
def _():
    need("Elder Dragon", "Emperor's Divide")
    s = fresh(hand=[T.id_of("Elder Dragon")])
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 3)
    fd = list(fd_slots(0))[0]
    s.fd_owner[fd], s.fd_card[fd], s.fd_ply[fd] = 1, T.id_of("Emperor's Divide"), -5
    cast(s, 0, "Elder Dragon", base_loc(0))
    run(s, picking(foe, -1), stop=lambda s: s.n_chain and s.pend_slot < 0
        and not chain_mod.decision_open(s))
    pass_priority_to(s, 1)
    act(s, A.A_PLAY_HIDDEN, None, 1)
    run(s, picking(foe, -1))
    assert alive(s, foe) and int(s.perms[foe, P_LOC]) == base_loc(1)


@case(11366, "Rengar played to answer a Gust on the last defender: non-combat, he conquers")
def _():
    need("Rengar, Trophy Hunter", "Gust")
    s = fresh()
    s.hand[1, 0], s.n_hand[1] = T.id_of("Gust"), 1
    give(s, 0, "Rengar, Trophy Hunter")
    s.runes_ready[:, :] = 9
    s.bf_ctrl[0] = 1
    theirs = body(s, 1, bf_loc(0), 2)
    body(s, 0, bf_loc(1), 2)
    s.bf_ctrl[1] = 0
    s.active = s.priority = 1
    cast(s, 1, "Gust", theirs)
    pass_priority_to(s, 0)
    assert A.ambush_playable(s, T, V1, 0)
    act(s, A.A_PLAY, hand_index(s, 0, "Rengar, Trophy Hunter"), 0)
    run(s, picking(bf_loc(0)))
    assert int(s.bf_ctrl[0]) == 0, "the Gust emptied it, Rengar took it"


@case(11367, "Long Sword must attach if you control a unit")
def _():
    need("Long Sword")
    s = fresh(hand=[T.id_of("Long Sword")])
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Long Sword", base_loc(0))
    run(s, picking(u))
    sw = perm_of(s, "Long Sword")[0]
    assert s.is_attached(sw), "Quick-Draw is not optional"


@case(11370, "Gust can return a Reflection whose copied Might is 3 or less")
def _():
    need("Gust", "Mirror Image")
    s = fresh()
    u = body(s, 1, base_loc(1))
    rsv.resolve(s, T, V1, SPECS["Mirror Image"], 0, [u], -1, True)
    A._settle(s, T, V1)
    ref = tokens(s, 0)[0]
    s.set_location(ref, bf_loc(0))
    assert ref in rsv.legal_targets(s, T, SPECS["Gust"], 0, 1, [], -1)
    rsv.resolve(s, T, V1, SPECS["Gust"], 1, [ref], -1, True)
    assert not alive(s, ref) and int(s.n_hand[0]) == 0, "#11371 -- still a token"
