"""RiftJudge batch 23 -- unused questions from 10058-10165."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_NO_MOVE, P_ATTACHED_TO
from rl.engine.effects import ABILITIES, pack_trash


@case(10159, "a recalled Stellacorn Herder did not move: no draw")
def _():
    need("Stellacorn Herder", "Tactical Retreat")
    s = fresh(hand=[T.id_of("Tactical Retreat")], runes=9)
    s.bf_ctrl[0] = 0
    h = s.add_permanent(T.id_of("Stellacorn Herder"), 0, bf_loc(0))
    cast(s, 0, "Tactical Retreat", h)
    run(s)
    combat.destroy(s, T, h)
    run(s)
    assert alive(s, h) and int(s.perms[h, P_LOC]) == base_loc(0)
    assert int(s.n_hand[0]) == 0, "a recall is not a move"


@case(10155, "Blue Sentinel's own hold trigger fires an additional time")
def _():
    need("Blue Sentinel")
    s = fresh()
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Blue Sentinel"), 0, bf_loc(0))
    _next_own_turn(s)
    assert chain_names(s).count("Blue Sentinel") == 2, chain_names(s)


@case(10154, "two Zileans each add a copy: one token becomes three")
def _():
    need("Zilean - Time Mage", "Sprite Call")
    s = fresh(hand=[T.id_of("Sprite Call")], runes=9)
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Zilean - Time Mage"), 0, bf_loc(0))
    s.add_permanent(T.id_of("Zilean - Time Mage"), 0, bf_loc(0))
    cast(s, 0, "Sprite Call", bf_loc(0))
    run(s, picking(bf_loc(0)))
    assert len(tokens(s, 0)) == 3, len(tokens(s, 0))


@case(10150, "an Abandoned Defy may be played again at the same spell")
def _():
    need("Abandon", "Defy", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    give(s, 0, "Abandon")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    disc = top_uid(s)
    cast(s, 1, "Defy", disc)
    cast(s, 0, "Abandon", top_uid(s))
    run(s, picking(accept=False),
        stop=lambda s: A.acting_seat(s) == 1 and "Defy" in hand_plays(s, 1))
    assert T.id_of("Defy") in list(s.hand[1, :int(s.n_hand[1])])
    assert "Discipline" in chain_names(s), "and its old target is still there"


@case(10149, "Gentle Gemdragon may ready runes spent to play it")
def _():
    need("Gentle Gemdragon")
    s = fresh(hand=[T.id_of("Gentle Gemdragon")], runes=2)
    before = int(s.runes_ready[0].sum())
    cast(s, 0, "Gentle Gemdragon", base_loc(0))
    run(s, picking())
    assert int(s.runes_ready[0].sum()) == before - 8 + 2, int(s.runes_ready[0].sum())


@case(10143, "Heedless Resurrection can't choose the Phoenix it kills; the Phoenix may")
def _():
    need("Heedless Resurrection", "Immortal Phoenix")
    s = fresh(hand=[T.id_of("Heedless Resurrection")], runes=9)
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, base_loc(0))
    s.trash[0, 0], s.n_trash[0] = T.id_of("Determined Sentry"), 1
    act(s, A.A_PLAY, hand_index(s, 0, "Heedless Resurrection"), 0)
    choose(s, ph)
    # 355 step 2 chose targets before step 3 paid the kill: HR's slot never
    # sees the Phoenix...
    assert pack_trash(0, T.id_of("Immortal Phoenix")) not in targets_offered(s, 0)
    choose(s, pack_trash(0, T.id_of("Determined Sentry")))
    run(s, picking(base_loc(0)))
    assert perm_of(s, "Determined Sentry")
    # ...but its own trigger does: a spell's cost killed it (428.1.a.1) and it
    # entered the trash as that happened (383.2.c.1).
    assert perm_of(s, "Immortal Phoenix")


@case(10142, "a tie with Symbol of the Solari recalls every unit")
def _():
    need("Symbol of the Solari", "Back Off")
    s = fresh(hand=[T.id_of("Back Off")], runes=9)
    s.add_permanent(T.id_of("Symbol of the Solari"), 0, base_loc(0))
    s.bf_ctrl[0] = 1
    a = body(s, 0, base_loc(0), 6, ready=True)
    d = body(s, 1, bf_loc(0), 3)
    attack(s, 0, 0, a)
    pass_priority_to(s, 0)
    cast(s, 0, "Back Off", a)
    fight(s)
    assert alive(s, a) and alive(s, d)
    assert int(s.perms[a, P_LOC]) == base_loc(0)
    assert int(s.perms[d, P_LOC]) == base_loc(1), "ALL units, the defender too"


@case(10140, "Azir - Sovereign moves a Reflection token like any token unit")
def _():
    need("Azir - Sovereign", "Mirror Image")
    s = fresh(hand=[T.id_of("Mirror Image")], runes=12)
    az = s.add_permanent(T.id_of("Azir - Sovereign"), 0, base_loc(0), ready=True)
    u = s.add_permanent(T.id_of("Mindsplitter"), 0, base_loc(0))
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 12)
    cast(s, 0, "Mirror Image", u)
    run(s)
    tok = tokens(s, 0)[-1]
    attack(s, 0, 0, az)
    run(s, picks(tok), stop=lambda s: int(s.perms[tok, P_LOC]) == bf_loc(0))
    assert int(s.perms[tok, P_LOC]) == bf_loc(0)


@case(10139, "Arcane Shift needs a friendly unit to be played at all")
def _():
    need("Arcane Shift")
    s = fresh(hand=[T.id_of("Arcane Shift")], runes=9)
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(0), 3)
    assert "Arcane Shift" not in hand_plays(s, 0)
    body(s, 0, base_loc(0), 3)
    assert "Arcane Shift" in hand_plays(s, 0)


@case(10138, "Fiora - Victorious has [Shield] the moment she is Mighty")
def _():
    need("Fiora - Victorious", "Discipline")
    s = fresh(runes=9)
    fi = s.add_permanent(T.id_of("Fiora - Victorious"), 0, base_loc(0))
    assert not combat.perm_kw(s, T, fi, "Shield")
    rsv.resolve(s, T, V1, SPECS["Discipline"], 0, [fi], -1, True)
    assert combat.might(s, T, fi) >= 5 and combat.perm_kw(s, T, fi, "Shield")


@case(10134, "Defiant Dance's two units must be different")
def _():
    need("Defiant Dance")
    s = fresh(hand=[T.id_of("Defiant Dance")])
    u = body(s, 0, base_loc(0), 3)
    v = body(s, 1, base_loc(1), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Defiant Dance"), 0)
    choose(s, u)
    off = targets_offered(s, 0)
    assert u not in off and v in off, off


@case(10132, "Plundering Poro's Gold is a token, not a card: no [Legion]")
def _():
    need("Plundering Poro", "Noxus Hopeful")
    s = fresh(runes=9)
    pp = s.add_permanent(T.id_of("Plundering Poro"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, pp)
    run(s, picking())
    assert tokens(s, 0), "the Gold was played"
    assert int(s.cards_played[0]) == 0, "a token is not a card"


@case(10126, "Red Brambleback doubles a battlefield's own conquer effect")
def _():
    need("Red Brambleback", "Targon's Peak")
    s = fresh()
    s.bf_card[0] = T.id_of("Targon's Peak")
    rb = s.add_permanent(T.id_of("Red Brambleback"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, rb)
    run(s, picking(rb))
    assert int(s.pending_ready_runes[0]) == 4, int(s.pending_ready_runes[0])


@case(10119, "Singularity follows its target to base")
def _():
    need("Singularity", "Flash")
    s = fresh(hand=[T.id_of("Singularity")], runes=12)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Singularity", foe, -1)
    rsv.resolve(s, T, V1, SPECS["Flash"], 1, [foe, -1], -1, True)
    assert int(s.perms[foe, P_LOC]) == base_loc(1)
    run(s)
    assert not alive(s, foe), "no location clause, so no location to leave"


@case(10116, "Deathgrip needs two friendly units")
def _():
    need("Deathgrip")
    s = fresh(hand=[T.id_of("Deathgrip")])
    body(s, 0, base_loc(0), 3)
    assert "Deathgrip" not in hand_plays(s, 0)
    body(s, 0, base_loc(0), 3)
    assert "Deathgrip" in hand_plays(s, 0)


@case(10114, "Lotus Trap lets a 4 Might attacker kill a 7 Might Mindsplitter")
def _():
    need("Lotus Trap", "Mindsplitter", "Noxus Hopeful")
    s = fresh(runes=9)
    s.bf_ctrl[1] = 1
    nh = s.add_permanent(T.id_of("Noxus Hopeful"), 0, base_loc(0), ready=True)
    ms = s.add_permanent(T.id_of("Mindsplitter"), 1, bf_loc(0))
    rsv.resolve(s, T, V1, SPECS["Lotus Trap"], 0, [ms], -1, True)
    attack(s, 0, 0, nh)
    fight(s)
    assert not alive(s, ms), "4 doubled to 8"


@case(10111, "there is no window to act before an attack trigger exists")
def _():
    need("Ezreal - Dashing", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    s.bf_ctrl[0] = 1
    ez = s.add_permanent(T.id_of("Ezreal - Dashing"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, ez)
    assert chain_names(s) and chain_names(s)[0] == "Ezreal - Dashing", chain_names(s)


@case(10110, "Double Trouble with no unit revealed recycles all three")
def _():
    need("Double Trouble", "Discipline")
    s = fresh(hand=[T.id_of("Double Trouble")])
    spell = T.id_of("Discipline")
    s.deck[0, :3] = spell
    cast(s, 0, "Double Trouble")
    run(s, picking(accept=False))
    live = [int(c) for c in s.deck[0, int(s.deck_ptr[0]):int(s.n_deck[0])]]
    assert len(live) == 20 and int(s.n_hand[0]) == 0
    assert live[-3:] == [spell] * 3, "to the bottom, not back on top"
    assert live[0] != spell


@case(10109, "equipping gear to Irelia, Fervent chooses her: +1 Might")
def _():
    need("Irelia, Fervent", "Boots of Swiftness")
    s = fresh(runes=9)
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0))
    g = s.add_permanent(T.id_of("Boots of Swiftness"), 0, base_loc(0))
    base = combat.might(s, T, ir)
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, ir)
    run(s)
    assert int(s.perms[g, P_ATTACHED_TO]) == ir
    assert combat.might(s, T, ir) >= base + 1, (base, combat.might(s, T, ir))


@case(10105, "Abandon cannot be played with nothing on the Chain")
def _():
    need("Abandon")
    s = fresh(hand=[T.id_of("Abandon")])
    assert "Abandon" not in hand_plays(s, 0)


@case(10102, "Loyal Poro alone at a battlefield died alone, however many attacked")
def _():
    need("Loyal Poro")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    lp = s.add_permanent(T.id_of("Loyal Poro"), 0, bf_loc(0))
    a1 = body(s, 1, base_loc(1), 5, ready=True)
    a2 = body(s, 1, base_loc(1), 5, ready=True)
    attack(s, 1, 0, a1, a2)
    fight(s)
    assert not alive(s, lp) and int(s.n_hand[0]) == 0


@case(10101, "Irresistible Faefolk bringing an enemy along makes you the attacker")
def _():
    need("Irresistible Faefolk")
    s = fresh()
    fae = s.add_permanent(T.id_of("Irresistible Faefolk"), 0, base_loc(0), ready=True)
    foe = body(s, 1, base_loc(1), 3)
    give(s, 1, "Smoke Screen")                # keeps the combat open to look at
    s.runes_ready[1, :] = 6
    attack(s, 0, 0, fae)
    run(s, picks(foe), stop=lambda s: bool(s.showdown_combat))
    assert int(s.perms[foe, P_LOC]) == bf_loc(0)
    assert int(s.attacker) == 0, int(s.attacker)


@case(10096, "Tactical Retreat works on a unit already in base")
def _():
    need("Tactical Retreat")
    s = fresh(hand=[T.id_of("Tactical Retreat")])
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Tactical Retreat", u)
    run(s)
    combat.destroy(s, T, u)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_LOC]) == base_loc(0)


@case(10094, "a Star-Crossed whose shared target is gone still returns the other")
def _():
    need("Star-Crossed")
    s = fresh(hand=[T.id_of("Star-Crossed")], runes=9)
    give(s, 1, "Star-Crossed")
    s.runes_ready[1, :] = 9
    a = body(s, 0, base_loc(0), 3)
    b = body(s, 1, base_loc(1), 3)
    c = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Star-Crossed", a, b)
    cast(s, 1, "Star-Crossed", b, c)
    run(s)
    assert not alive(s, b) and not alive(s, c) and not alive(s, a)
    assert int(s.n_hand[0]) == 2 and int(s.n_hand[1]) == 1


@case(10085, "hidden Smoke and Mirrors may swap with a unit at another location")
def _():
    need("Smoke and Mirrors", "Sprite Call")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 0
    here = _sprite_at(s, 0, 0)
    there = body(s, 0, base_loc(0), 3)
    hidden_at(s, 0, 0, "Smoke and Mirrors")
    act(s, A.A_PLAY_HIDDEN, None, 0)
    choose(s, here)
    assert there in targets_offered(s, 0)
    choose(s, there)
    run(s)
    assert int(s.perms[here, P_LOC]) == base_loc(0)
    assert int(s.perms[there, P_LOC]) == bf_loc(0)


@case(10072, "Relentless Pursuit's move does not exhaust the unit")
def _():
    need("Relentless Pursuit")
    s = fresh(hand=[T.id_of("Relentless Pursuit")], runes=9)
    u = body(s, 0, base_loc(0), 3, ready=True)
    cast(s, 0, "Relentless Pursuit", u, bf_loc(0))
    run(s, picking(accept=False))
    assert int(s.perms[u, P_LOC]) == bf_loc(0) and int(s.perms[u, P_READY]) == 1


@case(10071, "with Elder Dragon a 2 Might attacker kills two defenders")
def _():
    need("Elder Dragon")
    s = fresh()
    s.add_permanent(T.id_of("Elder Dragon"), 0, base_loc(0))
    s.bf_ctrl[1] = 1
    a = body(s, 0, base_loc(0), 2, ready=True)
    d1 = body(s, 1, bf_loc(0), 5)
    d2 = body(s, 1, bf_loc(0), 5)
    attack(s, 0, 0, a)
    fight(s)
    assert not alive(s, d1) and not alive(s, d2)


@case(10066, "Ruined Rex's Deathknell is not optional")
def _():
    need("Ruined Rex")
    s = fresh()
    rex = s.add_permanent(T.id_of("Ruined Rex"), 0, base_loc(0))
    foe = body(s, 1, base_loc(1), 9)
    combat.destroy(s, T, rex)
    A._settle(s, T, V1)
    legal = {a.kind for a in A.legal_actions(s, T, V1, A.acting_seat(s))}
    assert A.A_DECLINE not in legal, legal
    run(s, picking(foe))
    assert int(s.perms[foe, P_DMG]) == 4


@case(10063, "Lilting Lullaby on the Chain has not stopped anyone yet")
def _():
    need("Hard Bargain", "Lilting Lullaby", "En Garde")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    give(s, 1, "Hard Bargain", "En Garde")
    give(s, 0, "Lilting Lullaby")
    body(s, 1, base_loc(1), 3)
    rsv_spell = body(s, 0, base_loc(0), 3)
    give(s, 0, "Discipline")
    # seat 1 answers seat 0's spell with Hard Bargain; seat 0 Lullabies it
    s.active = s.priority = 0
    cast(s, 0, "Discipline", rsv_spell)
    cast(s, 1, "Hard Bargain", top_uid(s))
    cast(s, 0, "Lilting Lullaby", top_uid(s))
    pass_priority_to(s, 1)
    assert "En Garde" in hand_plays(s, 1), hand_plays(s, 1)


@case(10059, "Star-Crossed on a Reflection copy of a Deathknell unit: no Deathknell")
def _():
    need("Star-Crossed", "Mirror Image", "Loyal Poro")
    s = fresh(hand=[T.id_of("Mirror Image")], runes=9)
    give(s, 1, "Star-Crossed")
    s.runes_ready[1, :] = 9
    lp = s.add_permanent(T.id_of("Loyal Poro"), 0, base_loc(0))
    cast(s, 0, "Mirror Image", lp)
    run(s)
    tok = tokens(s, 0)[-1]
    mine = body(s, 1, base_loc(1), 3)
    s.active = s.priority = 1
    cast(s, 1, "Star-Crossed", mine, tok)
    run(s)
    assert not alive(s, tok) and int(s.n_hand[0]) == 0, "returned, not killed"


@case(10058, "Sacrifice on Star-Crossed's friendly target: the enemy still goes")
def _():
    need("Star-Crossed", "Sacrifice")
    s = fresh(hand=[T.id_of("Star-Crossed")], runes=9)
    give(s, 1, "Sacrifice")
    s.runes_ready[1, :] = 9
    rune_deck(s)
    mine = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Star-Crossed", mine, theirs)
    cast(s, 1, "Sacrifice", theirs)
    run(s)
    assert not alive(s, theirs) and not alive(s, mine)
    assert T.id_of("Shipyard Skulker") in list(s.hand[0, :int(s.n_hand[0])])
