"""RiftJudge batch 37 -- unused questions from 8848-8912."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8912, "Azir cannot swap a unit out of Vilemaw's Lair")
def _():
    need("Azir - Ascendant", "Vilemaw's Lair")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    az = s.add_permanent(T.id_of("Azir - Ascendant"), 0, base_loc(0), ready=True)
    stuck = body(s, 0, bf_loc(0), 3)
    act(s, A.A_ACTIVATE, az, 0)
    run(s, picking(stuck))
    assert int(s.perms[stuck, P_LOC]) == bf_loc(0), "'can't' beats a swap"


@case(8911, "a hidden card keeps its battlefield on a later turn")
def _():
    need("Hidden Blade")
    s = fresh(runes=9)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    slot = hidden_at(s, 0, 0, "Hidden Blade")
    body(s, 0, bf_loc(0), 3)          # keeps the battlefield his across the turn
    _next_own_turn(s)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    here = body(s, 1, bf_loc(0), 3)
    away = body(s, 1, bf_loc(1), 3)
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    offered = targets_offered(s, 0)
    assert here in offered and away not in offered, "737.1.d.2 outlives the turn"


@case(8910, "Not So Fast cannot answer Cull the Weak")
def _():
    need("Cull the Weak", "Not So Fast")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=9)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 9
    body(s, 1, base_loc(1), 3)
    body(s, 0, base_loc(0), 3)
    cast(s, 0, "Cull the Weak")
    assert "Not So Fast" not in hand_plays(s, 1)


@case(8909, "Brynhir stops cards being played, not a Deathknell")
def _():
    need("Brynhir Thundersong", "Ferrous Forerunner", "Cull the Weak")
    s = fresh(hand=[T.id_of("Brynhir Thundersong"), T.id_of("Cull the Weak")],
              runes=14)
    ff = s.add_permanent(T.id_of("Ferrous Forerunner"), 1, base_loc(1), ready=True)
    body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Brynhir Thundersong"), 0)
    choose(s, base_loc(0))
    run(s)
    cast(s, 0, "Cull the Weak")
    run(s, picking(ff))
    assert not alive(s, ff)
    assert len(tokens(s, 1)) == 2, "an effect is not the player playing a card"


@case(8908, "a hidden Facebreaker needs a unit of each side there")
def _():
    need("Facebreaker")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 0
    slot = hidden_at(s, 0, 0, "Facebreaker")
    foe = body(s, 1, bf_loc(0), 3)
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_PLAY_HIDDEN and a.arg == slot], "no friend there"
    mine = body(s, 0, bf_loc(0), 3)
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    run(s, picks(mine, foe))
    assert s.has_flag(mine, F_STUNNED) and s.has_flag(foe, F_STUNNED)


@case(8905, "Piercing Light needs a unit at a battlefield, not just at base")
def _():
    need("Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=9)
    body(s, 1, base_loc(1), 3)
    assert "Piercing Light" not in hand_plays(s, 0), "the first half is mandatory"
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(0), 3)
    assert "Piercing Light" in hand_plays(s, 0)


@case(8901, "Challenge is not combat, so nothing heals afterwards")
def _():
    need("Challenge")
    s = fresh(hand=[T.id_of("Challenge")], runes=9)
    mine = body(s, 0, base_loc(0), 5)
    theirs = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Challenge", mine, theirs)
    run(s)
    assert int(s.perms[theirs, P_DMG]) == 5, "the damage stays marked"
    assert not alive(s, mine), "and 9 back was lethal"


@case(8898, "Aphelios may buff himself off his own Equipment trigger")
def _():
    need("Aphelios - Exalted", "Warmog's Armor")
    s = fresh(runes=9)
    ap = s.add_permanent(T.id_of("Aphelios - Exalted"), 0, base_loc(0), ready=True)
    g = s.add_permanent(T.id_of("Warmog's Armor"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, ap)
    run(s, picking(2, ap))
    assert s.has_flag(ap, F_BUFFED), "702.2.a: a friendly unit includes him"


@case(8895, "a unit bounced in answer to its own play trigger still draws")
def _():
    need("Lecturing Yordle", "Gust")
    s = fresh(hand=[T.id_of("Lecturing Yordle")], runes=9)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[0] = 0
    before = int(s.n_hand[0])
    act(s, A.A_PLAY, hand_index(s, 0, "Lecturing Yordle"), 0)
    choose(s, bf_loc(0))
    ly = perm_of(s, "Lecturing Yordle", 0)[0]
    cast(s, 1, "Gust", ly)
    run(s)
    assert not alive(s, ly), "it went back to hand"
    assert int(s.n_hand[0]) == before - 1 + 1 + 1, "played, drawn, returned"


@case(8890, "Brynhir stops a hidden card too: playing it is playing a card")
def _():
    need("Brynhir Thundersong", "Edge of Night")
    s = fresh(hand=[T.id_of("Brynhir Thundersong")], runes=14)
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(0), 3)
    slot = hidden_at(s, 1, 0, "Edge of Night")
    act(s, A.A_PLAY, hand_index(s, 0, "Brynhir Thundersong"), 0)
    choose(s, base_loc(0))
    run(s)
    assert not [a for a in A.legal_actions(s, T, V1, 1)
                if a.kind == A.A_PLAY_HIDDEN and a.arg == slot]


@case(8889, "with two death replacements available, the controller picks")
def _():
    need("Guardian Angel", "Zhonya's Hourglass", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=9)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 1, bf_loc(0))
    s.active = s.priority = 1
    act(s, A.A_ACTIVATE, ga, 1)
    choose(s, u)
    run(s)
    s.active = s.priority = 0
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u), "one of the two saved it"
    assert alive(s, z) != alive(s, ga), "and only one of them was spent"


@case(8888, "Forge of the Future's ability is not usable on the enemy turn")
def _():
    need("Forge of the Future")
    s = fresh(runes=9)
    fo = s.add_permanent(T.id_of("Forge of the Future"), 0, base_loc(0))
    s.trash[0, 0] = VANILLA
    s.n_trash[0] = 1
    assert [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
    s.ply += 1
    s.active = s.priority = 1
    assert not [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE], \
        "374: an activated ability waits for your own turn"
    assert fo >= 0


@case(8886, "En Garde's second +1 asks whether the unit is alone there")
def _():
    need("En Garde")

    def pumped(alone):
        s = fresh(runes=9)
        give(s, 0, "En Garde")
        s.bf_ctrl[0] = 0
        u = body(s, 0, bf_loc(0), 3)
        if not alone:
            body(s, 0, bf_loc(0), 3)
        cast(s, 0, "En Garde", u)
        run(s)
        return combat.might(s, T, u)

    assert pumped(True) == 5 and pumped(False) == 4


@case(8880, "a move to base counts toward Yasuo, Windrider's third move")
def _():
    need("Yasuo - Windrider", "Ride The Wind")
    s = fresh(runes=12)
    give(s, 0, "Ride The Wind", "Ride The Wind", "Ride The Wind")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)                     # holds the battlefield all along
    ya = s.add_permanent(T.id_of("Yasuo - Windrider"), 0, base_loc(0), ready=True)
    for dest in (bf_loc(0), base_loc(0), bf_loc(0)):
        cast(s, 0, "Ride The Wind", ya, dest)
        run(s)
        assert int(s.perms[ya, P_LOC]) == dest
    assert int(s.points[0]) == 1, "407.1: base is a location like any other"


@case(8875, "Fight or Flight sends a unit home without exhausting it")
def _():
    need("Fight or Flight")
    s = fresh(hand=[T.id_of("Fight or Flight")], runes=9)
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3, ready=True)
    cast(s, 0, "Fight or Flight", u)
    run(s)
    assert int(s.perms[u, P_LOC]) == base_loc(0) and int(s.perms[u, P_READY]) == 1


@case(8873, "an alternate score can be the eighth point")
def _():
    need("Yasuo - Windrider", "Ride The Wind")
    s = fresh(runes=12)
    give(s, 0, "Ride The Wind", "Ride The Wind", "Ride The Wind")
    s.points[0] = 7
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    ya = s.add_permanent(T.id_of("Yasuo - Windrider"), 0, base_loc(0), ready=True)
    for dest in (bf_loc(0), base_loc(0), bf_loc(0)):
        cast(s, 0, "Ride The Wind", ya, dest)
        run(s)
    assert int(s.points[0]) == 8, "448.1.a.1 beholds only Conquer and Hold"


@case(8869, "Altar of Memories sees a token unit die")
def _():
    need("Altar of Memories", "Sprite Call", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=12)
    al = s.add_permanent(T.id_of("Altar of Memories"), 0, base_loc(0), ready=True)
    tok = _sprite_at(s, 0, 0)
    before = int(s.n_hand[0])
    cast(s, 0, "Hidden Blade", tok)
    run(s, picking(0))
    assert not alive(s, tok)
    assert int(s.perms[al, P_READY]) == 0, "179.1.d: a token unit is a unit"
    assert int(s.n_hand[0]) >= before - 1


@case(8853, "Unchecked Power chooses nothing, so Not So Fast misses it")
def _():
    need("Unchecked Power", "Not So Fast")
    s = fresh(hand=[T.id_of("Unchecked Power")], runes=16)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3, ready=True)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Unchecked Power")
    assert "Not So Fast" not in hand_plays(s, 1), "352.10.d"
    run(s)
    assert not alive(s, mine), "12 to ALL units at battlefields"
    assert alive(s, theirs), "a base is not a battlefield"


@case(8850, "Sun Disc reads [Legion] as you exhaust it")
def _():
    need("Sun Disc", "Determined Sentry")
    from rl.engine.state import P_ARRIVED
    s = fresh(hand=[T.id_of("Determined Sentry")], runes=9)
    sd = s.add_permanent(T.id_of("Sun Disc"), 0, base_loc(0), ready=True)
    s.perms[sd, P_ARRIVED] = -1
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE], "nothing played yet, so no [Legion]"
    s.cards_played[0] = 1
    act(s, A.A_ACTIVATE, sd, 0)
    run(s)
    act(s, A.A_PLAY, hand_index(s, 0, "Determined Sentry"), 0)
    choose(s, base_loc(0))
    run(s)
    ds = perm_of(s, "Determined Sentry", 0)[0]
    assert int(s.perms[ds, P_READY]) == 1, "the effect was banked at activation"


@case(8871, "Yasuo, Remorseful's attack trigger opens a Reaction-only chain")
def _():
    need("Yasuo - Remorseful", "Rune Prison", "Smoke Screen")
    s = fresh(runes=14)
    give(s, 1, "Rune Prison", "Smoke Screen")
    s.runes_ready[1, :] = 14
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, ya)
    foe = perm_of(s, "Shipyard Skulker", 1)[0]
    choose(s, foe)
    pass_priority_to(s, 1)
    plays = hand_plays(s, 1)
    assert "Smoke Screen" in plays, "a Reaction answers the initial chain"
    assert "Rune Prison" not in plays, "an [Action] waits for the open state"


@case(8852, "a unit from Glasc Mixologist's Deathknell joins that battlefield")
def _():
    need("Glasc Mixologist", "Determined Sentry")
    s = fresh(runes=12)
    s.bf_ctrl[0] = 0
    gm = s.add_permanent(T.id_of("Glasc Mixologist"), 0, bf_loc(0), ready=True)
    s.trash[0, 0] = T.id_of("Determined Sentry")
    s.n_trash[0] = 1
    s.ply += 1                        # a base Might override is stamped per ply
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    run(s, picking(pack_trash(0, T.id_of("Determined Sentry")), bf_loc(0)),
        limit=80)
    assert not alive(s, gm)
    back = perm_of(s, "Determined Sentry", 0)
    assert back, "the Deathknell replayed it"


@case(8878, "Draven, Vanquisher asks for his rune as the trigger resolves")
def _():
    need("Draven - Vanquisher")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 1
    dv = s.add_permanent(T.id_of("Draven - Vanquisher"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, dv)
    before = runes(s, 0)
    run(s, picking(accept=False), limit=8)
    assert combat.might(s, T, dv) == 4 and runes(s, 0) == before, \
        "declining on resolution costs nothing"


@case(8893, "Bullet Time's amount is chosen while it resolves")
def _():
    need("Bullet Time", "Defy")
    s = fresh(hand=[T.id_of("Bullet Time")], runes=12)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    before = runes(s, 0)
    cast(s, 0, "Bullet Time", bf_loc(0))
    assert runes(s, 0) == before, "1 energy exhausts a rune, it recycles none"
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1), "and it is still a 1-cost spell to answer"
    run(s, picking(3))
    assert not alive(s, u)


@case(8881, "Fiora's [Mighty] trigger is answered now or not at all")
def _():
    need("Fiora - Grand Duelist", "Defiant Dance")
    s = fresh(hand=[T.id_of("Defiant Dance")], runes=9)
    s.legend[0], s.legend_ready[0] = T.id_of("Fiora - Grand Duelist"), 1
    u = body(s, 0, base_loc(0), 4)
    spare = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Defiant Dance", u, spare)
    # Her "you may exhaust me" is offered as the trigger goes on the Chain
    # (402.1) -- and DECLINED here, which is the whole question: the player who
    # forgot cannot come back to it. (This case used to pass because the trigger
    # never fired at all: the scan's watcher gate did not know a legend could be
    # watching. See #6308.)
    run(s, picking(-1, accept=False))
    assert combat.might(s, T, u) == 6, "the pump made him Mighty"
    assert int(s.legend_ready[0]) == 1, "the window closed unused"
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE], "and does not come back"
    _next_own_turn(s)
    assert int(s.legend_ready[0]) == 1 and not [
        a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE], \
        "402.1.a: declining removed it from the Chain, and a later turn is too late"
