"""RiftJudge batch 7 -- unused questions from 11581-11770."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_05 import to_trigger
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import C_UID, F_BUFFED, F_EMPOWERED, P_ATTACHED_TO, P_EMPOWER


@case(11584, "Defy cannot choose Lilting Lullaby: 2 Power is over its limit")
def _():
    need("Defy", "Lilting Lullaby")
    s = fresh(hand=[T.id_of("Lilting Lullaby")])
    give(s, 1, "Defy")
    sp = T.id_of("Discipline")
    s.hand[0, 1], s.n_hand[0] = sp, 2
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    cast(s, 0, "Lilting Lullaby", top_uid(s))
    pass_priority_to(s, 1)
    lull = top_uid(s)
    act(s, A.A_PLAY, hand_index(s, 1, "Defy"), 1) if "Defy" in hand_plays(s, 1) else None
    offered = {a.arg for a in A.legal_actions(s, T, V1, 1) if a.kind == A.A_TARGET}
    assert lull not in offered, offered


@case(11586, "Smoke Screen on a unit already killed for Sacrifice changes nothing")
def _():
    need("Sacrifice", "Smoke Screen")
    s = fresh(hand=[T.id_of("Sacrifice")])
    rune_deck(s)
    give(s, 1, "Smoke Screen")
    vi = body(s, 0, base_loc(0), 5)
    act(s, A.A_PLAY, 0, 0)
    choose(s, vi)
    assert not alive(s, vi), "357 -- paid before anyone can respond"
    pass_priority_to(s, 1)
    assert not ({vi} & {a.arg for a in A.legal_actions(s, T, V1, 1)}), "no target left"
    run(s)
    assert int(s.n_hand[0]) == 2, "Draw 2 still happens"


@case(11590, "Teemo's defend trigger resolves before the attacker may play an [Action]")
def _():
    need("Teemo - Strategist", "Punch First")
    s = fresh(hand=[T.id_of("Punch First")])
    s.bf_ctrl[0] = 1
    s.add_permanent(T.id_of("Teemo - Strategist"), 1, bf_loc(0))
    a = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, a)
    run(s, picking(a), stop=lambda s: s.n_chain and chain_names(s)[-1].startswith("Teemo")
        and s.pend_slot < 0)
    assert chain_names(s) and chain_names(s)[-1].startswith("Teemo")
    pass_priority_to(s, 0)
    assert "Punch First" not in hand_plays(s, 0), "309.1.a -- Closed State"


@case(11594, "Cull the Weak makes you kill your Ruin Runner -- you are the one choosing")
def _():
    need("Cull the Weak", "Ruin Runner")
    s = fresh(hand=[T.id_of("Cull the Weak")])
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1))
    body(s, 0, base_loc(0), 3)
    cast(s, 0, "Cull the Weak")
    run(s, picking(rr))
    assert not alive(s, rr)


@case(11595, "Thrill of the Hunt in answer to Cull the Weak does not dodge it")
def _():
    need("Cull the Weak", "Thrill of the Hunt")
    s = fresh(hand=[T.id_of("Cull the Weak")])
    give(s, 1, "Thrill of the Hunt")
    body(s, 0, base_loc(0), 3)
    u = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Cull the Weak")
    cast(s, 1, "Thrill of the Hunt", u, bf_loc(0))
    run(s, picking())
    assert len(units(s, 1)) == 0, "the replayed unit is still theirs to kill"


@case(11596, "Kinkou Initiate's 'draw 1 if...' is part of the effect: the trigger goes on anyway")
def _():
    need("Kinkou Initiate")
    s = fresh(hand=[T.id_of("Kinkou Initiate")])
    body(s, 0, base_loc(0), 4)
    cast(s, 0, "Kinkou Initiate", base_loc(0))
    A._settle(s, T, V1)
    assert "Kinkou Initiate" in chain_names(s), "383.2.a.1 -- not immediately after the Condition"


@case(11598, "Skyfall of Areion makes Trinity Force's hold effects conquer effects: they stack")
def _():
    need("Skyfall of Areion", "Trinity Force")
    s = fresh()
    u = body(s, 0, base_loc(0), 3, ready=True)
    for n in ("Trinity Force", "Trinity Force", "Skyfall of Areion"):
        g = s.add_permanent(T.id_of(n), 0, base_loc(0))
        s.attach(g, u)
    attack(s, 0, 0, u)
    fight(s)
    run(s)
    assert int(s.points[0]) == 3, f"1 conquer + 2 Trinity Forces: {int(s.points[0])}"


@case(11601, "Lux's legend draws for Falling Comet even when its target was Retreated")
def _():
    need("Lux - Lady of Luminosity", "Falling Comet")
    s = fresh(hand=[T.id_of("Falling Comet")])
    s.legend[0], s.legend_ready[0] = T.id_of("Lux - Lady of Luminosity"), 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Falling Comet", u)
    combat.return_to_hand(s, T, u)                 # the Retreat
    run(s)
    assert int(s.n_hand[0]) == 1, "359.3.e.10 -- it resolved, so it was played"


@case(11602, "Kai'Sa - Evolutionary reads Drag Under's printed Energy")
def _():
    need("Kai'Sa - Evolutionary", "Drag Under")
    from rl.engine.effects import pack_trash
    s = fresh()
    s.points[0] = 4
    s.trash[0, 0], s.n_trash[0] = T.id_of("Drag Under"), 1
    k = s.add_permanent(T.id_of("Kai'Sa - Evolutionary"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, k)
    offered = set()
    for _ in range(20):
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        offered |= {a.arg for a in legal if a.kind == A.A_TARGET}
        if not legal or (s.showdown_bf < 0 and not s.n_chain and not s.n_trig):
            break
        A.apply(s, T, V1, next((a for a in legal if a.kind in (A.A_ACCEPT, A.A_ORDER, A.A_PASS)), legal[0]))
    assert pack_trash(0, T.id_of("Drag Under")) not in offered


@case(11607, "Flame Chompers killed is not discarded: no play offer")
def _():
    need("Flame Chompers")
    s = fresh()
    fc = s.add_permanent(T.id_of("Flame Chompers"), 0, base_loc(0))
    combat.destroy(s, T, fc)
    A._settle(s, T, V1)
    assert s.n_chain == 0 and s.n_trig == 0 and s.pend_may < 0


@case(11609, "Smoke Screen on Baited Hook's target lowers what it can find")
def _():
    need("Baited Hook", "Smoke Screen")
    s = fresh()
    s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 5)
    s.deck[0, :5] = [T.id_of("Commander Ledros")] * 5     # 8 Might each
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, u)
    rsv.resolve(s, T, V1, SPECS["Smoke Screen"], 1, [u], -1, True)
    run(s, picking())
    assert combat.might(s, T, u) == 1 or not alive(s, u)
    assert not perm_of(s, "Commander Ledros"), "Might 1 + 1 cannot reach an 8"


@case(11617, "targeting Svellsongur on Ornn pays no Deflect: the gear has none")
def _():
    need("Svellsongur", "Ornn - Forge God", "Salvage")
    s = fresh(hand=[T.id_of("Salvage")])
    o = s.add_permanent(T.id_of("Ornn - Forge God"), 1, base_loc(1))
    sv = s.add_permanent(T.id_of("Svellsongur"), 1, base_loc(1))
    s.attach(sv, o)
    before = runes(s, 0)
    cast(s, 0, "Salvage", sv)
    run(s)
    assert not alive(s, sv) and before - runes(s, 0) == int(T.power[T.id_of("Salvage")])


@case(11626, "Darius - Trifarian readies only once the second card resolves")
def _():
    need("Darius - Trifarian", "Discipline")
    s = fresh(hand=[T.id_of("Darius - Trifarian"), T.id_of("Discipline")])
    cast(s, 0, "Darius - Trifarian", base_loc(0))
    run(s)
    d = perm_of(s, "Darius - Trifarian")[0]
    cast(s, 0, "Discipline", d)
    A._settle(s, T, V1)
    assert int(s.perms[d, P_READY]) == 0, "419.4.a -- not while Discipline is on the Chain"
    run(s)
    assert int(s.perms[d, P_READY]) == 1


@case(11639, "hiding a card is not playing it: Ravenbloom Student stays put")
def _():
    need("Ravenbloom Student", "Back Off")
    s = fresh(hand=[T.id_of("Back Off")])
    s.bf_ctrl[0] = 0
    st = s.add_permanent(T.id_of("Ravenbloom Student"), 0, bf_loc(0))
    hides = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_HIDE]
    assert hides
    A.apply(s, T, V1, hides[0])
    act(s, A.A_HIDE_AT, None, 0)
    run(s)
    assert combat.might(s, T, st) == 2


@case(11643, "Tideturner cannot choose a unit at its own location")
def _():
    need("Tideturner")
    s = fresh()
    s.bf_ctrl[0] = 0
    same = body(s, 0, bf_loc(0), 3)
    other = body(s, 0, base_loc(0), 3)
    hidden_at(s, 0, 0, "Tideturner")
    act(s, A.A_PLAY_HIDDEN, None, 0)
    offered = targets_offered(s)
    assert other in offered and same not in offered, offered


@case(11659, "Fiora - Peerless at negative Might does not double: +(-1) becomes +0")
def _():
    need("Fiora - Peerless", "Eclipse")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 0, bf_loc(0))
    rsv.resolve(s, T, V1, SPECS["Eclipse"], 1, [fi], -1, True)       # 3 - 4
    run(s, picking(accept=False))                                     # the Predict look
    from rl.engine.state import P_MIGHT_MOD
    assert int(s.perms[fi, P_MIGHT_MOD]) == -4 and combat.might(s, T, fi) == 0
    a = body(s, 1, base_loc(1), 1, ready=True)
    attack(s, 1, 0, a)
    run(s, stop=lambda s: s.n_chain == 0 and s.n_trig == 0 and s.showdown_bf >= 0
        and int(s.priority) >= 0)
    assert combat.might(s, T, fi) == 0 and int(s.combat_might_val[fi]) <= 0, (
        f"477.3.c: {combat.might(s, T, fi)} / {int(s.combat_might_val[fi])}")
    s.perms[fi, P_MIGHT_MOD] = 0                  # lift the -4: still no doubling bonus
    assert combat.might(s, T, fi) <= 3


@case(11669, "Astral Heron's discount does not apply to hiding a card")
def _():
    need("Astral Heron", "Back Off")
    s = fresh(hand=[T.id_of("Back Off")])
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    s.next_discount[0, :] = 2
    s.runes_ready[:, :] = 0
    s.runes_ready[0, 0] = 1
    hides = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_HIDE]
    assert hides, "hiding costs [A]: one rune pays it"
    A.apply(s, T, V1, hides[0])
    act(s, A.A_HIDE_AT, None, 0)
    assert int(s.next_discount[0].sum()) == 4, "811.1.c.1 -- hiding is not playing"


@case(11670, "Astral Heron's discount also covers a Repeat cost")
def _():
    need("Astral Heron", "Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")])
    s.next_discount[0, :] = 2
    u = body(s, 1, base_loc(1), 9)
    before = runes(s, 0)
    ready = int(s.runes_ready[0].sum())
    cast(s, 0, "Bellows Breath", u, -1, -1, repeat=True)
    run(s, picking(u, -1))
    assert runes(s, 0) == before and int(s.runes_ready[0].sum()) == ready, (
        "1+1 base and 1+1 Repeat, all taken by [2][A][A]")


@case(11673, "Temporal Breach at Rockfall Path: the unit stays banished")
def _():
    need("Temporal Breach", "Rockfall Path")
    s = fresh()
    s.bf_card[0] = T.id_of("Rockfall Path")
    u = body(s, 0, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Temporal Breach"], 0, [u], -1, True)
    run(s)
    assert not perm_of(s, "Shipyard Skulker") and int(s.n_banished[0]) == 1


@case(11675, "Alpha Strike's damage is its unit's Might at resolution")
def _():
    need("Alpha Strike", "Discipline")
    s = fresh(hand=[T.id_of("Alpha Strike")])
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 2)
    foe = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Alpha Strike", mine)
    rsv.resolve(s, T, V1, SPECS["Discipline"], 0, [mine], -1, True)
    run(s, picking(foe))
    assert int(s.perms[foe, P_DMG]) == 4, f"359.3.f.2: {int(s.perms[foe, P_DMG])}"


@case(11682, "Shuriken Flip is playable with no enemy at a battlefield")
def _():
    need("Shuriken Flip")
    s = fresh(hand=[T.id_of("Shuriken Flip")])
    body(s, 0, base_loc(0), 3)
    assert "Shuriken Flip" in hand_plays(s, 0), "'up to one'"


@case(11683, "a second Astral Heron played to Star Spring triggers with the first")
def _():
    need("Astral Heron")
    s = fresh(hand=[T.id_of("Astral Heron")])
    s.runes_ready[:, :] = 9
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    cast(s, 0, "Astral Heron", bf_loc(0))
    run(s)
    assert int(s.next_discount[0, 0]) == 4


@case(11685, "Defy counters a Flow-played Shadow Dash: it reads the printed cost")
def _():
    need("Defy", "Shadow Dash")
    s = fresh()
    s.runes_ready[:, :] = 9
    s.trash[0, 0], s.n_trash[0] = T.id_of("Shadow Dash"), 1
    give(s, 1, "Defy")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    flows = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_FLOW]
    assert flows
    A.apply(s, T, V1, flows[0])
    run(s, picking(foe, bf_loc(0)), stop=lambda s: s.n_chain and s.pend_slot < 0
        and not chain_mod.decision_open(s))
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1)


@case(11688, "a spell countered by Riposte is no first card for Astral Heron")
def _():
    need("Astral Heron", "Riposte", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")])
    give(s, 1, "Riposte")
    s.bf_ctrl[0] = 0
    her = s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Discipline", her)
    cast(s, 1, "Riposte", theirs, top_uid(s))
    run(s)
    assert int(s.next_discount[0].sum()) == 0


@case(11691, "Sprite Queen makes a Sprite at the start of each Beginning Phase")
def _():
    need("Sprite Queen")
    s = fresh()
    rune_deck(s)
    s.add_permanent(T.id_of("Sprite Queen"), 0, base_loc(0))
    _next_own_turn(s)
    run(s)
    assert len(tokens(s, 0)) == 1


@case(11696, "Overzealous Fan cannot move an attacker off Vilemaw's Lair")
def _():
    need("Overzealous Fan", "Vilemaw's Lair")
    s = fresh()
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 1
    fan = s.add_permanent(T.id_of("Overzealous Fan"), 1, bf_loc(0))
    body(s, 1, bf_loc(0), 3)
    a = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, a)
    run(s, picking(a), stop=lambda s: not alive(s, fan))
    assert int(s.perms[a, P_LOC]) == bf_loc(0)


@case(11697, "Salvage on a gear attached to a Deflect unit pays no Deflect")
def _():
    need("Salvage", "Long Sword", "Commander Ledros")
    s = fresh(hand=[T.id_of("Salvage")])
    led = s.add_permanent(T.id_of("Commander Ledros"), 1, base_loc(1))
    sw = s.add_permanent(T.id_of("Long Sword"), 1, base_loc(1))
    s.attach(sw, led)
    before = runes(s, 0)
    cast(s, 0, "Salvage", sw)
    run(s)
    assert not alive(s, sw) and before - runes(s, 0) == int(T.power[T.id_of("Salvage")])


@case(11705, "Call to Battle can only send a unit to a battlefield you control")
def _():
    need("Call to Battle")
    s = fresh()
    s.bf_ctrl[0] = 1
    s.bf_ctrl[1] = 0
    body(s, 1, bf_loc(0), 3)
    body(s, 0, bf_loc(1), 3)
    spec = SPECS["Call to Battle"]
    locs = set(rsv.legal_targets(s, T, spec, 1, 0, [body(s, 0, base_loc(0), 2)], -1)) \
        if spec.n_targets > 1 else set()
    assert bf_loc(1) in locs and bf_loc(0) not in locs, locs


@case(11708, "Emperor's Dais returning a Reflection still gives the Sand Soldier")
def _():
    need("Emperor's Dais", "Mirror Image")
    s = fresh()
    s.bf_card[0] = T.id_of("Emperor's Dais")
    u = body(s, 1, base_loc(1), 3)
    rsv.resolve(s, T, V1, SPECS["Mirror Image"], 0, [u], -1, True)
    A._settle(s, T, V1)
    ref = tokens(s, 0)[0]
    s.perms[ref, P_READY] = 1
    attack(s, 0, 0, ref)
    run(s, picking(ref))
    toks = [T.names[int(s.perms[i, P_CARD])] for i in tokens(s, 0)]
    assert not alive(s, ref) and "Sand Soldier" in toks and int(s.n_hand[0]) == 0, toks


@case(11710, "a Cleave stolen by Rebuttal is not your second card for Darius")
def _():
    need("Rebuttal", "Cleave", "Darius - Trifarian")
    s = fresh(hand=[T.id_of("Darius - Trifarian"), T.id_of("Cleave")])
    give(s, 1, "Rebuttal")
    cast(s, 0, "Darius - Trifarian", base_loc(0))
    run(s)
    d = perm_of(s, "Darius - Trifarian")[0]
    cast(s, 0, "Cleave", d)
    cast(s, 1, "Rebuttal", top_uid(s))
    run(s, picking(d))
    assert int(s.perms[d, P_READY]) == 0, "FAQ #6678"


@case(11712, "returning a token from Ripper's Bay still triggers the Bay")
def _():
    need("Ripper's Bay", "Gust", "Sprite Call")
    s = fresh()
    rune_deck(s)
    s.bf_card[0] = T.id_of("Ripper's Bay")
    spr = _sprite_at(s, 0, 0)
    rsv.resolve(s, T, V1, SPECS["Gust"], 1, [spr], -1, True)
    A._settle(s, T, V1)
    offered = any(a.kind == A.A_ACCEPT for a in A.legal_actions(s, T, V1, A.acting_seat(s)))
    assert offered, "the zone change fired it before the token ceased to exist"
    before, ready = runes(s, 0), int(s.runes_ready[0].sum())
    run(s, picking())
    assert runes(s, 0) == before + 1 and int(s.runes_ready[0].sum()) == ready - 1


@case(11713, "Astral Heron's discount ends with the turn")
def _():
    need("Astral Heron", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")])
    s.bf_ctrl[0] = 0
    her = s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    cast(s, 0, "Discipline", her)
    run(s)
    assert int(s.next_discount[0].sum()) > 0
    act(s, A.A_END_TURN, None, 0)
    run(s)
    assert int(s.next_discount[0].sum()) == 0, "errata: 'the next card you play THIS TURN'"


@case(11719, "Flurry of Feathers' Birds still land where Gust emptied the battlefield")
def _():
    need("Flurry of Feathers", "Gust")
    s = fresh(hand=[T.id_of("Flurry of Feathers")])
    give(s, 1, "Gust")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    act(s, A.A_PLAY, 0, 0)
    run(s, picking(1, bf_loc(0)), stop=lambda s: s.n_chain and s.pend_slot < 0
        and not chain_mod.decision_open(s))
    cast(s, 1, "Gust", u)
    run(s, picking(bf_loc(0)))
    assert len(tokens(s, 0, bf_loc(0))) == 4 and int(s.bf_ctrl[0]) == 0


@case(11722, "Defy against an empowered Mel's spell: playable, but it counters nothing")
def _():
    need("Defy", "Mel, Newly Awakened", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")])
    give(s, 1, "Defy")
    mel = s.add_permanent(T.id_of("Mel, Newly Awakened"), 0, base_loc(0))
    s.set_flag(mel, F_EMPOWERED)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1), "can't be countered is not untargetable"
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert combat.might(s, T, u) == 5


@case(11725, "Not So Fast counters Janna's play trigger that chose your unit")
def _():
    need("Not So Fast", "Janna - Savior")
    s = fresh(seat=1)
    give(s, 0, "Janna - Savior")
    s.hand[1, 0], s.n_hand[1] = T.id_of("Not So Fast"), 1
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    a = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, a)
    pass_priority_to(s, 0)
    cast(s, 0, "Janna - Savior", bf_loc(0))
    run(s, picking(a), stop=lambda s: s.n_chain and chain_names(s)[-1].startswith("Janna")
        and s.pend_slot < 0)
    pass_priority_to(s, 1)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s, stop=lambda s: s.n_chain == 0 and s.n_trig == 0)
    assert int(s.perms[a, P_LOC]) == bf_loc(0)


@case(11726, "Mirror Image whose target left still makes a 0 Might Reflection with Temporary")
def _():
    need("Mirror Image")
    s = fresh()
    u = body(s, 1, base_loc(1), 3)
    combat.return_to_hand(s, T, u)
    rsv.resolve(s, T, V1, SPECS["Mirror Image"], 0, [u], -1, True)
    A._settle(s, T, V1)
    ref = tokens(s, 0)
    assert ref and combat.might(s, T, ref[0]) == 0 and combat.perm_kw(s, T, ref[0], "Temporary")


@case(11729, "Heron at Star Spring bounced by the unit that triggered her: still discounts")
def _():
    need("Astral Heron", "Star Spring")
    s = fresh(hand=[VANILLA])
    s.bf_card[0] = T.id_of("Star Spring")
    s.bf_ctrl[0] = 0
    her = s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    cast(s, 0, "Shipyard Skulker", bf_loc(0))
    run(s, picking(her))
    assert int(s.perms[her, P_LOC]) == base_loc(0) and int(s.next_discount[0].sum()) > 0


@case(11732, "Star-Crossed on Baited Hook's target: the hook finds nothing to kill")
def _():
    need("Baited Hook", "Star-Crossed")
    s = fresh()
    s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 3)
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, u)
    combat.return_to_hand(s, T, u)
    run(s, picking())
    assert len(units(s, 0)) == 0 and int(s.n_banished[0]) == 0


@case(11734, "a unit played beside Baron is born Mighty: Fiora's legend does not trigger")
def _():
    need("Baron Nashor", "Fiora - Grand Duelist")
    s = fresh(hand=[VANILLA])
    s.legend[0], s.legend_ready[0] = T.id_of("Fiora - Grand Duelist"), 1
    s.add_permanent(T.id_of("Baron Nashor"), 0, base_loc(0))
    cast(s, 0, "Shipyard Skulker", base_loc(0))
    A._settle(s, T, V1)
    assert s.n_chain == 0 and s.n_trig == 0 and s.pend_may < 0


@case(11737, "Moonfall with an empowered Mel: the chosen unit -3, the rest -2")
def _():
    need("Moonfall", "Mel, Newly Awakened")
    s = fresh()
    s.bf_ctrl[0] = 0
    mel = s.add_permanent(T.id_of("Mel, Newly Awakened"), 0, base_loc(0))
    s.set_flag(mel, F_EMPOWERED)
    body(s, 0, bf_loc(0), 3)
    other = body(s, 1, bf_loc(0), 6)
    pulled = body(s, 1, bf_loc(1), 6)
    rsv.resolve(s, T, V1, SPECS["Moonfall"], 0, [bf_loc(0), pulled], -1, True)
    assert combat.might(s, T, pulled) == 3 and combat.might(s, T, other) == 4, (
        combat.might(s, T, pulled), combat.might(s, T, other))


@case(11742, "Abandon against an empowered Mel's spell: it just Predicts")
def _():
    need("Abandon", "Mel, Newly Awakened", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")])
    give(s, 1, "Abandon")
    mel = s.add_permanent(T.id_of("Mel, Newly Awakened"), 0, base_loc(0))
    s.set_flag(mel, F_EMPOWERED)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Abandon", top_uid(s))
    run(s, picking(accept=False))
    assert combat.might(s, T, u) == 5 and T.id_of("Discipline") not in list(s.hand[0, :int(s.n_hand[0])])


@case(11750, "Crumbling Sands counters the first of two spells played in succession")
def _():
    need("Crumbling Sands", "Discipline")
    s = fresh(hand=[T.id_of("Discipline"), T.id_of("Discipline")])
    give(s, 1, "Crumbling Sands")
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    first = top_uid(s)
    cast(s, 0, "Discipline", u)
    pass_priority_to(s, 1)
    act(s, A.A_PLAY, hand_index(s, 1, "Crumbling Sands"), 1)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 1) if a.kind == A.A_TARGET}
    assert first in offered, "419.4.b -- the second was finalized, so 'another spell'"


@case(11752, "disempowering Kayle, Justified removes one of her three")
def _():
    need("Kayle, Justified")
    s = fresh()
    k = s.add_permanent(T.id_of("Kayle, Justified"), 0, base_loc(0))
    s.perms[k, P_EMPOWER] = 3
    s.set_flag(k, F_EMPOWERED)
    assert s.empower_count(k) == 3, s.empower_count(k)
    s.disempower(k)
    assert s.empower_count(k) == 2


@case(11754, "Akali, Silent Flashed out of combat is untargetable: Star-Crossed misses her")
def _():
    need("Akali, Silent", "Star-Crossed", "Flash")
    s = fresh(hand=[T.id_of("Star-Crossed")])
    give(s, 1, "Flash")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    ak = s.add_permanent(T.id_of("Akali, Silent"), 1, base_loc(1), ready=True)
    attack(s, 1, 0, ak)
    run(s, stop=lambda s: s.showdown_bf >= 0 and s.n_chain == 0 and A.acting_seat(s) >= 0)
    assert combat.in_combat(s, ak)
    pass_priority_to(s, 0)
    cast(s, 0, "Star-Crossed", mine, ak)
    cast(s, 1, "Flash", ak, -1)
    run(s)
    assert alive(s, ak) and int(s.perms[ak, P_LOC]) == base_loc(1), "no longer a legal target"
    assert not alive(s, mine), "the friendly half still returns"


@case(11756, "Swain with only Patched Porobot and Stupefy: one card can cover two kinds")
def _():
    need("Swain, Visionary", "Patched Porobot")
    from rl.engine.state import PT_GEAR, PT_SPELL, PT_UNIT
    s = fresh()
    sw = s.add_permanent(T.id_of("Swain, Visionary"), 0, base_loc(0), ready=True)
    s.played_types[0] = PT_UNIT | PT_GEAR | PT_SPELL
    attack(s, 0, 0, sw)
    fight(s)
    run(s)
    assert int(s.points[0]) == 2


@case(11759, "Stupefy on a 1 Might empowered Gangplank gives no -Might, so no +3")
def _():
    need("Stupefy", "Gangplank, Naval")
    s = fresh()
    gp = s.add_permanent(T.id_of("Gangplank, Naval"), 0, base_loc(0))
    s.set_flag(gp, F_EMPOWERED)
    s.base_might_ply[gp], s.base_might_val[gp] = int(s.ply), 1
    rsv.resolve(s, T, V1, SPECS["Stupefy"], 1, [gp], -1, True)
    assert combat.might(s, T, gp) == 1, f"477.3.b snapshot to -0: {combat.might(s, T, gp)}"


@case(11760, "Akali, Deadly Weapon killed in answer: her move trigger still deals its damage")
def _():
    need("Akali, Deadly Weapon")
    s = fresh()
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 5)
    ak = s.add_permanent(T.id_of("Akali, Deadly Weapon"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, ak)
    run(s, picking(foe), stop=lambda s: s.n_chain and chain_names(s)[-1].startswith("Akali")
        and s.pend_slot < 0 and s.pend_may < 0)
    combat.destroy(s, T, ak)
    run(s, picking(foe))
    assert int(s.perms[foe, P_DMG]) >= 1 or not alive(s, foe), "implicit move ends survive"


@case(11764, "Perched Grimwyrm cannot be played to a battlefield you did not conquer")
def _():
    need("Perched Grimwyrm")
    s = fresh(hand=[T.id_of("Perched Grimwyrm")])
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    assert "Perched Grimwyrm" not in {T.names[int(s.hand[0, a.arg])] for a in
                                      A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY}


@case(11765, "Profiteer can disempower your own legend")
def _():
    need("Profiteer", "Ambessa - Matriarch of War", "Kayle, Justified")
    s = fresh(hand=[T.id_of("Profiteer")])
    s.legend[0], s.legend_ready[0] = T.id_of("Ambessa - Matriarch of War"), 1
    s.legend_emp[0] = 1
    k = s.add_permanent(T.id_of("Kayle, Justified"), 0, base_loc(0))
    from rl.engine.state import legend_src
    cast(s, 0, "Profiteer", base_loc(0))
    offered = []
    orig = rsv.resolve

    def spy(*a, **kw):
        log = orig(*a, **kw)
        offered.append(log.get("disempowered"))
        return log
    rsv.resolve = spy
    try:
        order = [legend_src(0), k]                 # slot 0 the legend, slot 1 Kayle

        def seq(s, who, legal):
            tg = [a for a in legal if a.kind == A.A_TARGET]
            if tg and order:
                want = order.pop(0)
                return next(a for a in tg if a.arg == want)
            return next((a for a in legal if a.kind == A.A_ACCEPT), None)
        run(s, seq)
    finally:
        rsv.resolve = orig
    assert legend_src(0) in offered and s.empower_count(k) == 1
    # ...and empowering Kayle is "empower something else": Ambessa re-empowers.
    assert int(s.legend_emp[0]) == 1


@case(11766, "Dragon Form under a Stupefy never passes through 5: no Fiora trigger")
def _():
    need("Dragon Form", "Stupefy", "Fiora - Grand Duelist")
    s = fresh()
    s.legend[0], s.legend_ready[0] = T.id_of("Fiora - Grand Duelist"), 1
    u = body(s, 0, base_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Stupefy"], 1, [u], -1, True)
    rsv.resolve(s, T, V1, SPECS["Dragon Form"], 0, [u], -1, True)
    A._settle(s, T, V1)
    assert combat.might(s, T, u) == 4 and s.n_chain == 0 and s.n_trig == 0


@case(11767, "Temporal Breach on a stolen unit at your base: it stays banished")
def _():
    need("Temporal Breach", "Hostile Takeover")
    s = fresh()
    u = body(s, 1, base_loc(0), 3)
    s.perms[u, P_CTRL] = 0                          # taken, and moved home
    rsv.resolve(s, T, V1, SPECS["Temporal Breach"], 0, [u], -1, True)
    run(s)
    assert not [i for i in units(s, 1) + units(s, 0)
                if T.names[int(s.perms[i, P_CARD])] == "Shipyard Skulker"], (
        "its owner cannot play it to another player's base")


@case(11770, "Imperial Decree's kill is a spell's kill: Immortal Phoenix may come back")
def _():
    need("Imperial Decree", "Immortal Phoenix", "Hextech Ray")
    s = fresh()
    s.trash[0, 0], s.n_trash[0] = T.id_of("Immortal Phoenix"), 1
    u = body(s, 1, bf_loc(0), 9)
    rsv.resolve(s, T, V1, SPECS["Imperial Decree"], 0, [], -1, True)
    from rl.engine import combat as C
    C.KILLER[:] = [0, True]
    try:
        rsv.resolve(s, T, V1, SPECS["Hextech Ray"], 0, [u], -1, True)
    finally:
        C.KILLER[:] = [-1, False]
    A._settle(s, T, V1)
    assert not alive(s, u)
    assert any(a.kind == A.A_ACCEPT for a in A.legal_actions(s, T, V1, 0)), "Phoenix offer"
