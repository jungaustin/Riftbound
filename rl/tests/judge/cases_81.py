"""RiftJudge batch 81 -- unused questions from 6100-6393."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_STUNNED, P_READY


@case(6391, "'discard 1, then draw 1' draws with an empty hand")
def _():
    need("Traveling Merchant")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, base_loc(0), ready=True)
    assert int(s.n_hand[0]) == 0, "nothing to discard"
    act(s, A.A_DECLARE, bf_loc(0), 0)
    act(s, A.A_ADD, tm, 0)
    act(s, A.A_COMMIT, None, 0)
    run(s, picking(accept=True), limit=60)
    assert int(s.n_hand[0]) == 1, \
        "'then' is sequence, not condition: the draw is not owed the discard"


@case(6390, "the buff goes away after the damage, and that can be lethal")
def _():
    need("Lee Sin - Centered", "Flurry of Blades")
    s = fresh(runes=32)
    give(s, 1, "Flurry of Blades")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    lee = s.add_permanent(T.id_of("Lee Sin - Centered"), 0, bf_loc(0))
    ward = body(s, 0, bf_loc(0), 1)
    s.set_flag(ward, F_BUFFED)
    s.perms[lee, P_DMG] = 5                        # 6 Might: one more kills him
    s.perms[ward, P_DMG] = 1                       # 4 Might while he stands
    assert combat.might(s, T, ward) == 1 + 1 + 2, \
        "1 printed, +1 for its Buff, +2 from Lee Sin"
    s.active = s.priority = 1
    cast(s, 1, "Flurry of Blades")                 # 1 to everything at once
    run(s, limit=60)
    assert not alive(s, lee), "6 damage on 6 Might"
    assert not alive(s, ward), \
        "143.2.a: his +2 left with him, and 2 damage on a 2 Might unit is lethal"


@case(6385, "the unit that never left keeps the designation it was given")
def _():
    need("Mask of Foresight", "Flash")
    s = fresh(runes=32)
    give(s, 0, "Flash", "Discipline")
    s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    s.bf_ctrl[0] = 0
    s.ply += 1
    stays = body(s, 0, bf_loc(0), 6)
    goes = body(s, 0, bf_loc(0), 6)
    foe = body(s, 1, base_loc(1), 1, ready=True)
    attack(s, 1, 0, foe)
    drain(s)
    assert combat.might(s, T, stays) == 6, "two defenders: neither defended alone"
    pass_priority_to(s, 0)
    cast(s, 0, "Flash", goes)                      # the company goes home
    drain(s)
    assert int(s.perms[goes, P_LOC]) == base_loc(0), "it left"
    assert combat.might(s, T, stays) == 6, (
        "323.2: the one that stayed never gained a designation again, so the "
        "Mask's condition is never re-checked for it")


@case(6380, "whoever contested the battlefield is the attacker, whoever owns it is not")
def _():
    need("Charm")
    s = fresh(runes=32)
    give(s, 0, "Charm", "Discipline")
    s.bf_ctrl[0] = 0                               # my ground
    body(s, 0, bf_loc(0), 5)                       # my unit holding it
    theirs = body(s, 1, base_loc(1), 3, ready=True)
    cast(s, 0, "Charm", theirs, bf_loc(0))         # I drag THEIR unit in
    run(s, limit=40, stop=lambda st: int(st.showdown_bf) >= 0)
    assert int(s.showdown_bf) == 0 and int(s.showdown_combat), "a Combat here"
    assert int(s.attacker) == 1, \
        "459: their unit applied Contested, so THEY attack and I defend"


@case(6378, "both halves of Falling Star may name the same unit")
def _():
    need("Falling Star")
    s = fresh(runes=32)
    give(s, 0, "Falling Star")
    s.bf_ctrl[1] = 1
    victim = body(s, 1, bf_loc(1), 9)
    spare = body(s, 1, bf_loc(1), 9)
    cast(s, 0, "Falling Star", victim, victim)
    run(s, limit=60)
    assert int(s.perms[victim, P_DMG]) == 6, "3 and 3 into the same unit"
    assert int(s.perms[spare, P_DMG]) == 0, "and nothing spills onto the other"


@case(6375, "a unit killed by a spell is in the trash when its ability triggers")
def _():
    need("Immortal Phoenix", "Hidden Blade")
    s = fresh(runes=32)
    give(s, 0, "Hidden Blade")
    s.bf_ctrl[1] = 1
    s.bf_ctrl[0] = 0
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, bf_loc(0))
    cast(s, 0, "Hidden Blade", ph)
    run(s, limit=20, stop=lambda st: not alive(st, ph))
    assert not alive(s, ph), "their own spell killed it"
    assert T.id_of("Immortal Phoenix") in [
        int(s.trash[0, i]) for i in range(int(s.n_trash[0]))], \
        "808.1.d: it reaches the trash, and its offer reads it from there"


@case(6368, "'here' is nowhere once the unit has left")
def _():
    need("Yasuo - Remorseful", "Flash")
    s = fresh(runes=32)
    give(s, 0, "Flash")
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 9)
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    attack(s, 0, 1, ya)
    assert int(s.n_chain) >= 1 or int(s.n_trig) >= 1, "his attack trigger is queued"
    choose(s, foe) if int(s.pend_slot) >= 0 else None
    cast(s, 0, "Flash", ya)                        # ...and he goes home
    run(s, limit=80)
    assert int(s.perms[ya, P_LOC]) == base_loc(0), "he is at base"
    assert int(s.perms[foe, P_DMG]) == 0, \
        "359.3.f.3: 'an enemy unit HERE' cannot be read off a unit that is away"


@case(6367, "the end of one Combat heals every location, not just its own")
def _():
    need("Warwick - Hunter", "Flurry of Blades")
    s = fresh(runes=32)
    give(s, 0, "Flurry of Blades", "Discipline")
    s.bf_ctrl[0] = 1                               # their other ground
    s.bf_ctrl[1] = 1
    far = body(s, 1, bf_loc(0), 2)
    near = body(s, 1, bf_loc(1), 2)
    ww = s.add_permanent(T.id_of("Warwick - Hunter"), 0, base_loc(0), ready=True)
    cast(s, 0, "Flurry of Blades")                 # 1 damage everywhere
    drain(s)
    assert int(s.perms[far, P_DMG]) == 1, "the distant unit is marked too"
    attack(s, 0, 1, ww)
    fight(s, limit=100)
    assert not alive(s, near), "his attack trigger kills the damaged unit here"
    assert alive(s, far) and int(s.perms[far, P_DMG]) == 0, (
        "317.2.b/323.11: the Combat's end heals the whole board, so the other "
        "battlefield is clean before he could get there")


@case(6364, "a unit that leaves and walks back in is designated afresh")
def _():
    need("Mask of Foresight", "Flash", "Zenith Blade")
    s = fresh(runes=32)
    give(s, 0, "Flash", "Zenith Blade", "Discipline")
    s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    s.bf_ctrl[1] = 1
    s.ply += 1
    theirs = body(s, 1, bf_loc(1), 9)
    mine = body(s, 0, base_loc(0), 6, ready=True)
    attack(s, 0, 1, mine)
    drain(s)
    assert combat.might(s, T, mine) == 7, "attacking alone: the Mask pays +1"
    pass_priority_to(s, 0)
    cast(s, 0, "Flash", mine)                      # home, and out of the Combat
    drain(s)
    assert int(s.perms[mine, P_LOC]) == base_loc(0) and not int(s.desig[mine]), \
        "323.2.c: away from the battlefield, it loses the designation"
    pass_priority_to(s, 0)
    cast(s, 0, "Zenith Blade", theirs, mine)       # stun, and walk back in
    drain(s)
    assert int(s.perms[mine, P_LOC]) == bf_loc(1), "back in the fight"
    assert combat.might(s, T, mine) == 8, (
        "323.2.a designates it again, so 'when I attack' fires a second time "
        "(#6364; FAQ #6656 says the opposite and is rejected)")


@case(6363, "a banished unit comes back with no memory of the turn")
def _():
    need("Kayn - Unleashed", "Portal Rescue")
    s = fresh(runes=32)
    give(s, 0, "Portal Rescue")
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    kayn = s.add_permanent(T.id_of("Kayn - Unleashed"), 0, bf_loc(0), ready=True)
    s.move_ply[kayn] = int(s.ply)
    s.move_count[kayn] = 2                         # he has moved twice already
    cast(s, 0, "Portal Rescue", kayn)
    run(s, picking(accept=True), limit=80)
    back = perm_of(s, "Kayn - Unleashed", 0)
    assert back, "his owner played him straight back"
    assert not (int(s.move_ply[back[0]]) == int(s.ply)
                and int(s.move_count[back[0]]) >= 2), \
        "112.2: a new game object, with every temporary modifier and count gone"


@case(6358, "Defy reads the printed cost, not the one you would pay")
def _():
    need("Defy", "Sky Splitter")
    s = fresh(runes=32)
    give(s, 0, "Sky Splitter")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    big = body(s, 0, base_loc(0), 8, ready=True)   # its cost falls by 8
    foe = body(s, 1, bf_loc(1), 9)
    cast(s, 0, "Sky Splitter", foe)
    assert big >= 0
    pass_priority_to(s, 1)
    assert "Defy" not in hand_plays(s, 1), \
        "820.1: 'costs no more than {4 energy}' reads the {8 energy} printed on it"


@case(6351, "+1 Might from the ground can be what makes a unit [Mighty]")
def _():
    need("Trifarian War Camp", "Fiora - Peerless")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Trifarian War Camp")
    s.bf_ctrl[0] = 0
    base = body(s, 0, base_loc(0), 4)
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 0, bf_loc(0))
    assert combat.might(s, T, fi) == int(T.might[T.id_of("Fiora - Peerless")]) + 1
    assert combat.might(s, T, base) == 4, "the one in base gets nothing"
    if combat.might(s, T, fi) >= 5:
        assert combat.perm_kw(s, T, fi, "Ganking"), \
            "[Mighty] is read off effective Might, so the ground can grant it"
        assert combat.perm_kw(s, T, fi, "Shield") and \
            combat.perm_kw(s, T, fi, "Deflect"), "all three of them"


@case(6347, "one trigger or the other: a move and a flip are not both")
def _():
    need("Teemo - Strategist")
    s = fresh(runes=32)
    give(s, 1, "Discipline")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(1), 9)
    tm = s.add_permanent(T.id_of("Teemo - Strategist"), 0, base_loc(0), ready=True)
    attack(s, 0, 1, tm)
    # He is the ATTACKER here, and his trigger reads "when I DEFEND": one
    # designation, one condition, and this is not the one he wants.
    assert int(s.attacker) == 0
    assert not int(s.n_trig), "no defend trigger for an attacker"
    assert tm >= 0


@case(6346, "Challenge reaches any location; only a hidden card is pinned")
def _():
    need("Challenge")
    s = fresh(runes=32)
    give(s, 0, "Challenge")
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    mine_here = body(s, 0, bf_loc(0), 5)
    mine_base = body(s, 0, base_loc(0), 5)
    far = body(s, 1, base_loc(1), 3)
    near = body(s, 1, bf_loc(1), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Challenge"), 0)
    first = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert {mine_here, mine_base} <= first, \
        "'a friendly unit' says nothing about where"
    act(s, A.A_TARGET, mine_base, 0)
    second = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert {far, near} <= second, "and neither does 'an enemy unit'"


@case(6330, "floating Power pays a Power cost, so no rune is recycled")
def _():
    need("Hextech Ray")
    s = fresh(runes=32)
    give(s, 0, "Hextech Ray")
    s.legend[0], s.legend_ready[0] = T.id_of("Kai'Sa - Daughter of the Void"), 1
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 9)
    before = runes(s, 0)
    act(s, A.A_ACTIVATE, next(a.arg for a in A.legal_actions(s, T, V1, 0)
                              if a.kind == A.A_ACTIVATE), 0)
    run(s, picking(accept=True), limit=40)
    assert int(s.pool_rstr_p[0].sum()) >= 1, \
        "her [Add] floats {any rune} of Power, restricted to playing spells"
    cast(s, 0, "Hextech Ray", foe)
    run(s, limit=40)
    assert int(s.perms[foe, P_DMG]) == 3, "the Ray resolved"
    assert runes(s, 0) == before, \
        "164.2.b: the floating Power paid it, so no rune had to be recycled"


@case(6329, "two of the same unit are two abilities, and both apply")
def _():
    need("Ezreal, Prodigy", "Piercing Light")
    s = fresh(runes=32)
    pl = T.id_of("Piercing Light")
    printed = (int(T.repeat_energy[pl]), int(T.repeat_power[pl]))
    assert printed == (2, 1), f"[Repeat] {{2 energy}}{{Fury rune}} ({printed})"
    assert A.reduced_add_cost(s, T, 0, printed) == printed, "nobody to discount it"
    s.add_permanent(T.id_of("Ezreal, Prodigy"), 0, base_loc(0))
    assert A.reduced_add_cost(s, T, 0, printed) == (1, 1), "one copy: {1 energy} off"
    s.add_permanent(T.id_of("Ezreal, Prodigy"), 0, base_loc(0))
    assert A.reduced_add_cost(s, T, 0, printed) == (0, 1), \
        "103: no Legend Rule for a non-Unique unit, so the second copy applies too"


@case(6328, "a token arriving at a battlefield walks into the statics there")
def _():
    need("Noxian Drummer", "Trifarian War Camp", "Ahri - Nine-Tailed Fox")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Trifarian War Camp")
    s.bf_ctrl[0] = 1                               # THEIR ground, with Ahri
    s.legend[1] = T.id_of("Ahri - Nine-Tailed Fox")
    nd = s.add_permanent(T.id_of("Noxian Drummer"), 0, base_loc(0), ready=True)
    act(s, A.A_DECLARE, bf_loc(0), 0)
    act(s, A.A_ADD, nd, 0)
    act(s, A.A_COMMIT, None, 0)
    run(s, picking(accept=True), limit=80)
    toks = [i for i in tokens(s, 0) if int(s.perms[i, P_LOC]) == bf_loc(0)]
    assert toks, "his move trigger made a Recruit here"
    assert combat.might(s, T, toks[0]) == 1 + 1, \
        "1 printed, +1 from the ground it arrived on"


@case(6326, "a spell that cannot find its unit reads nothing off it")
def _():
    need("Challenge", "Shakedown")
    s = fresh(runes=32)
    give(s, 0, "Challenge")
    give(s, 1, "Shakedown")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    mine = body(s, 0, bf_loc(0), 5)
    theirs = body(s, 1, bf_loc(1), 4)
    cast(s, 0, "Challenge", mine, theirs)
    pass_priority_to(s, 1)
    cast(s, 1, "Shakedown", mine)                  # 6 into my 5 Might unit
    run(s, picking(accept=False), limit=80)
    assert not alive(s, mine), "it dies before Challenge resolves"
    assert alive(s, theirs) and int(s.perms[theirs, P_DMG]) == 0, \
        "359.3.e: no unit, no Might to read, so nothing is dealt either way"


@case(6324, "an ability names its target as it goes on the Chain")
def _():
    need("Gentlemen's Duel")
    s = fresh(runes=32)
    give(s, 0, "Gentlemen's Duel")
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    mine = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, bf_loc(1), 4)
    act(s, A.A_PLAY, hand_index(s, 0, "Gentlemen's Duel"), 0)
    asked = 0
    while int(s.pend_slot) >= 0 and asked < 4:
        want = (mine, theirs)[min(asked, 1)]
        act(s, A.A_TARGET, want, 0)
        asked += 1
    assert asked == 2, "both the friendly unit and the enemy one, before it resolves"
    assert int(s.n_chain) == 1 and int(s.pend_slot) < 0, \
        "355: the enemy named halfway through the text is still a finalization choice"
    run(s, limit=60)
    assert not alive(s, theirs), "6 into 4"
    assert alive(s, mine), "and 4 into a 6 Might unit is not lethal"


@case(6323, "an activated ability with no 'once each turn' may be used again")
def _():
    need("Vi, Destructive")
    s = fresh(runes=32)
    vi = s.add_permanent(T.id_of("Vi, Destructive"), 0, base_loc(0), ready=True)
    s.trash[0, 0] = T.id_of("Cleave")
    s.trash[0, 1] = T.id_of("Cleave")
    s.n_trash[0] = 2
    printed = int(T.might[T.id_of("Vi, Destructive")])
    act(s, A.A_ACTIVATE, None, 0)
    run(s, picking(accept=True), limit=40)
    assert combat.might(s, T, vi) == printed + 1, "one recycle, +1"
    assert A.A_ACTIVATE in kinds(s, 0), \
        "377: the cost is a recycle, not an Exhaust, and nothing says once"
    act(s, A.A_ACTIVATE, None, 0)
    run(s, picking(accept=True), limit=40)
    assert combat.might(s, T, vi) == printed + 2, "so a second recycle is a second +1"
