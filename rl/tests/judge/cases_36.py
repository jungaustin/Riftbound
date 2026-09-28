"""RiftJudge batch 36 -- unused questions from 8914-8968."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8968, "Not So Fast cannot answer King's Edict, which chooses nothing")
def _():
    need("King's Edict", "Not So Fast")
    s = fresh(hand=[T.id_of("King's Edict")], runes=14)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 9
    body(s, 1, base_loc(1), 3)
    cast(s, 0, "King's Edict")
    assert "Not So Fast" not in hand_plays(s, 1)


@case(8964, "Garbage Grabber needs the three cards its cost recycles")
def _():
    need("Garbage Grabber")
    s = fresh(runes=9)
    gg = s.add_permanent(T.id_of("Garbage Grabber"), 0, base_loc(0), ready=True)
    s.trash[0, :2] = VANILLA
    s.n_trash[0] = 2
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE and a.arg == gg], "403.3"
    s.trash[0, 2] = VANILLA
    s.n_trash[0] = 3
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_ACTIVATE and a.arg == gg]


@case(8957, "Hidden Blade whose target left the battlefield draws nobody cards")
def _():
    need("Hidden Blade", "Fight or Flight")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=9)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    slot = hidden_at(s, 1, 0, "Fight or Flight")
    before = int(s.n_hand[1])
    cast(s, 0, "Hidden Blade", u)
    pass_priority_to(s, 1)
    act(s, A.A_PLAY_HIDDEN, slot, 1)
    choose(s, u)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_LOC]) == base_loc(1)
    assert int(s.n_hand[1]) == before, "no kill, so no draw 2"


@case(8953, "[Deflect] does not cover the gear attached to the unit")
def _():
    need("Detonate", "Draven - Audacious", "B.F. Sword")

    def spend(deflect):
        s = fresh(hand=[T.id_of("Detonate")], runes=9)
        if deflect:
            u = s.add_permanent(T.id_of("Draven - Audacious"), 1, base_loc(1),
                                ready=True)
        else:
            u = body(s, 1, base_loc(1), 6)
        g = s.add_permanent(T.id_of("B.F. Sword"), 1, base_loc(1))
        s.perms[g, P_ATTACHED_TO] = u
        before = runes(s, 0)
        cast(s, 0, "Detonate", g)
        run(s)
        assert not alive(s, g)
        return before - runes(s, 0)

    assert spend(True) == spend(False), "the gear has its own properties (744)"


@case(8952, "Sacred Shears' [Deathknell] belongs to the unit wearing it")
def _():
    need("Sacred Shears", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=9)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    g = s.add_permanent(T.id_of("Sacred Shears"), 1, bf_loc(0))
    s.active = s.priority = 1
    act(s, A.A_ACTIVATE, g, 1)
    choose(s, u)
    run(s)
    s.active = s.priority = 0
    before = int(s.n_hand[1])
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert not alive(s, u)
    assert int(s.n_hand[1]) == before + 2 + 1, "Hidden Blade's 2 and the Shears' 1"


@case(8951, "a repeated Rocket Barrage is one lethal check, so one save")
def _():
    need("Rocket Barrage", "Zhonya's Hourglass")
    s = fresh(hand=[T.id_of("Rocket Barrage")], runes=14)
    u = body(s, 1, base_loc(1), 4)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Rocket Barrage", repeat=True)
    run(s, picks(0, u, 0, u))
    assert alive(s, u) and not alive(s, z), "8 damage, checked once"


@case(8945, "Ravenbloom Student gets nothing from a countered spell")
def _():
    need("Ravenbloom Student", "Bellows Breath", "Defy")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=9)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    rs = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0), ready=True)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Bellows Breath", u, -1, -1)
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert combat.might(s, T, rs) == 2, "419.4.a: it was never played"


@case(8944, "Relentless Pursuit carries a unit battlefield to battlefield")
def _():
    need("Relentless Pursuit")
    s = fresh(hand=[T.id_of("Relentless Pursuit")], runes=12)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    u = body(s, 0, bf_loc(0), 3, ready=True)
    cast(s, 0, "Relentless Pursuit", u, bf_loc(1))
    run(s, picking(-1))
    assert int(s.perms[u, P_LOC]) == bf_loc(1)


@case(8943, "Void Rush is the other card, so Vanguard Captain has [Legion]")
def _():
    need("Void Rush", "Vanguard Captain")
    s = fresh(hand=[T.id_of("Void Rush")], runes=12)
    s.bf_ctrl[0] = 0
    s.deck[0, int(s.deck_ptr[0])] = T.id_of("Vanguard Captain")
    cast(s, 0, "Void Rush")
    run(s, picking(T.id_of("Vanguard Captain"), 0, bf_loc(0)))
    cap = perm_of(s, "Vanguard Captain", 0)
    assert cap, "the Captain was played from the reveal"
    assert len(tokens(s, 0)) == 2, "[Legion] saw Void Rush itself"


@case(8941, "Captain Farron's [Assault] is 'here', so it ends at the border")
def _():
    need("Captain Farron")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 1
    cf = s.add_permanent(T.id_of("Captain Farron"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 3, ready=True)
    assert combat.might(s, T, u) == 3, "[Assault] only shows while attacking"
    attack(s, 0, 0, u)
    assert int(s.perms[cf, P_LOC]) == base_loc(0)
    assert combat.might(s, T, u) == 3, "it left Farron's location"


@case(8938, "Cull the Weak may be played with no units at all")
def _():
    need("Cull the Weak")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=9)
    theirs = body(s, 1, base_loc(1), 3)
    assert "Cull the Weak" in hand_plays(s, 0), "it chooses nothing on play"
    cast(s, 0, "Cull the Weak")
    run(s, picking(theirs))
    assert not alive(s, theirs)


@case(8934, "a repeated Bellows Breath may pick a different location")
def _():
    need("Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=14)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(0), 5)
    b = body(s, 1, bf_loc(1), 5)
    cast(s, 0, "Bellows Breath", a, -1, repeat=True)
    run(s, picks(b, -1))
    assert int(s.perms[a, P_DMG]) == 1 and int(s.perms[b, P_DMG]) == 1


@case(8933, "Emperor's Divide cannot pull units out of Vilemaw's Lair")
def _():
    need("Emperor's Divide", "Vilemaw's Lair")
    s = fresh(hand=[T.id_of("Emperor's Divide")], runes=9)
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    a = body(s, 0, bf_loc(0), 3)
    b = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Emperor's Divide")
    run(s, picks(a, b))
    assert int(s.perms[a, P_LOC]) == bf_loc(0)
    assert int(s.perms[b, P_LOC]) == bf_loc(0)


@case(8931, "a pump after Thousand-Tailed Watcher adds to the floored Might")
def _():
    need("Thousand-Tailed Watcher", "Defiant Dance")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher"), T.id_of("Defiant Dance")],
              runes=16)
    u = body(s, 1, base_loc(1), 2)
    spare = body(s, 1, base_loc(1), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    run(s)
    assert combat.might(s, T, u) == 1, "-3 to a minimum of 1"
    cast(s, 0, "Defiant Dance", u, spare)
    run(s)
    assert combat.might(s, T, u) == 3, "the floor bound its own modifier only"


@case(8930, "Imperial Decree's two kills beat one Guardian Angel")
def _():
    need("Imperial Decree", "Bellows Breath", "Guardian Angel")
    s = fresh(hand=[T.id_of("Imperial Decree"), T.id_of("Bellows Breath")],
              runes=16)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 9)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 1, bf_loc(0))
    s.perms[ga, P_ATTACHED_TO] = u
    s.death_guard[1] = ga
    cast(s, 0, "Imperial Decree")
    run(s)
    cast(s, 0, "Bellows Breath", u, -1, repeat=True)
    run(s, picks(u, -1))
    assert not alive(s, ga) and not alive(s, u), "two damage events, two kills"


@case(8919, "Emperor's Divide sends units home without exhausting them")
def _():
    need("Emperor's Divide")
    s = fresh(hand=[T.id_of("Emperor's Divide")], runes=9)
    s.bf_ctrl[0] = 0
    a = body(s, 0, bf_loc(0), 3, ready=True)
    b = body(s, 0, bf_loc(0), 3, ready=False)
    cast(s, 0, "Emperor's Divide")
    run(s, picks(a, b))
    assert int(s.perms[a, P_LOC]) == base_loc(0) and int(s.perms[a, P_READY]) == 1
    assert int(s.perms[b, P_READY]) == 0, "a move changes nothing else"


@case(8918, "Smoke Screen floors a unit at 1 Might, never 0")
def _():
    need("Smoke Screen")
    s = fresh(hand=[T.id_of("Smoke Screen")], runes=9)
    u = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Smoke Screen", u)
    run(s)
    assert combat.might(s, T, u) == 1 and alive(s, u)


@case(8916, "Forge of the Future's recycle picks the exact cards")
def _():
    need("Forge of the Future")
    s = fresh(runes=9)
    fo = s.add_permanent(T.id_of("Forge of the Future"), 0, base_loc(0))
    keep, take = T.id_of("Smoke Screen"), T.id_of("Defy")
    s.trash[1, 0], s.trash[1, 1] = keep, take
    s.n_trash[1] = 2
    act(s, A.A_ACTIVATE, None, 0)
    run(s, picking(pack_trash(1, take), -1))
    assert int(s.n_trash[1]) == 1 and int(s.trash[1, 0]) == keep


@case(8915, "two Reactions can answer one Singularity")
def _():
    need("Singularity", "Smoke Screen", "Defy")
    s = fresh(hand=[T.id_of("Singularity")], runes=14)
    give(s, 1, "Smoke Screen", "Defy")
    s.runes_ready[1, :] = 14
    u = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Singularity", u, -1)
    cast(s, 1, "Smoke Screen", u)
    assert "Defy" in hand_plays(s, 1), "the chain keeps taking answers"
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert alive(s, u)


@case(8914, "Angle Shot re-attaching a Spinning Axe keeps it off [Temporary]")
def _():
    need("Angle Shot", "Spinning Axe")
    s = fresh(runes=9)
    give(s, 0, "Angle Shot")
    ax = s.add_permanent(T.id_of("Spinning Axe"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3, ready=True)
    cast(s, 0, "Angle Shot", u, ax)
    run(s)
    assert int(s.perms[ax, P_ATTACHED_TO]) == u
    _next_own_turn(s)
    assert alive(s, ax), "[Temporary] only kills it while unattached"


@case(8926, "Retreat answers a [Temporary] kill and channels a rune exhausted")
def _():
    need("Sprite Call", "Retreat")
    s = fresh(runes=9)
    give(s, 0, "Retreat")
    rune_deck(s)
    tok = _sprite_at(s, 0, 0)
    before = runes(s, 0)
    _next_own_turn(s)
    plays = hand_plays(s, 0)
    assert "Retreat" in plays, "the Temporary trigger opened a window"
    cast(s, 0, "Retreat", tok)
    run(s)
    assert not alive(s, tok), "a token that leaves the board ceases to exist"
    assert runes(s, 0) > before, "the channelled rune arrived exhausted"


@case(8924, "Janna heals damage Falling Star already marked")
def _():
    need("Janna - Savior", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=12)
    give(s, 1, "Janna - Savior")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(0), 5)
    b = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Falling Star", a, b)
    run(s)
    assert int(s.perms[a, P_DMG]) == 3 and int(s.perms[b, P_DMG]) == 3
    s.active = s.priority = 1
    s.ply += 1
    act(s, A.A_PLAY, hand_index(s, 1, "Janna - Savior"), 1)
    choose(s, bf_loc(0))
    run(s, picking(-1))
    assert int(s.perms[a, P_DMG]) == 0 and int(s.perms[b, P_DMG]) == 0


@case(8921, "Counter Strike prevents only the next damage Falling Star deals")
def _():
    need("Counter Strike", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=12)
    give(s, 1, "Counter Strike")
    s.runes_ready[1, :] = 12
    u = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Falling Star", u, u)
    cast(s, 1, "Counter Strike", u)
    run(s)
    assert int(s.perms[u, P_DMG]) == 3, "one instance prevented, one not"


@case(8937, "Temporal Portal's [Repeat] costs what the spell costs")
def _():
    need("Temporal Portal", "Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=14)
    tp = s.add_permanent(T.id_of("Temporal Portal"), 0, base_loc(0), ready=True)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    act(s, A.A_ACTIVATE, tp, 0)
    run(s)
    before = runes(s, 0)
    cast(s, 0, "Bellows Breath", u, -1, repeat=True)
    run(s, picks(u, -1))
    assert int(s.perms[u, P_DMG]) == 2, "the granted Repeat ran"
    assert before - runes(s, 0) == 2, "1 Power for the spell, 1 for the Repeat"


@case(8956, "Ride the Wind can conquer on the opponent's turn")
def _():
    need("Ride The Wind")
    s = fresh(runes=9)
    give(s, 0, "Ride The Wind")
    u = body(s, 0, base_loc(0), 3, ready=False)
    s.bf_ctrl[1] = 0
    body(s, 0, bf_loc(1), 3)
    foe = body(s, 1, base_loc(1), 3, ready=True)
    s.ply += 1
    attack(s, 1, 1, foe)
    cast(s, 0, "Ride The Wind", u, bf_loc(0))
    fight(s)
    assert int(s.bf_ctrl[0]) == 0, "moving in conquered it"
    assert int(s.points[0]) >= 1
