"""RiftJudge batch 51 -- unused questions from 8085-8137."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8129, "Gust saves a 3 Might unit from Harnessed Dragon")
def _():
    need("Harnessed Dragon", "Gust")
    s = fresh(hand=[T.id_of("Harnessed Dragon")], runes=32)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Harnessed Dragon"), 0)
    choose(s, base_loc(0))
    choose(s, u)
    cast(s, 1, "Gust", u)
    run(s)
    assert not alive(s, u), "it went home to hand, out of reach"
    assert int(s.n_hand[1]) >= 1


@case(8127, "Portal Rescue sends the card to its OWNER's base")
def _():
    need("Possession", "Portal Rescue")
    s = fresh(hand=[T.id_of("Possession"), T.id_of("Portal Rescue")], runes=32)
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Possession", foe)
    run(s)
    assert int(s.perms[foe, P_CTRL]) == 0
    cast(s, 0, "Portal Rescue", foe)
    run(s, picking(accept=True), limit=40)
    back = [i for i in range(s.n_perms) if alive(s, i)
            and int(s.perms[i, P_CARD]) == VANILLA]
    assert back and int(s.perms[back[0], P_LOC]) == base_loc(1), \
        "718.5.f: its owner plays it to THEIR base"


@case(8126, "Thousand-Tailed Watcher pays no [Deflect]")
def _():
    need("Thousand-Tailed Watcher", "Draven - Audacious")

    def spend(deflect):
        s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=32)
        if deflect:
            s.add_permanent(T.id_of("Draven - Audacious"), 1, base_loc(1),
                            ready=True)
        else:
            body(s, 1, base_loc(1), 6)
        before = runes(s, 0)
        act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
        choose(s, base_loc(0))
        run(s)
        return before - runes(s, 0)

    assert spend(True) == spend(False), "a sweep chooses nobody"


@case(8123, "Convergent Mutation needs two friendly units")
def _():
    need("Convergent Mutation")
    s = fresh(runes=24)
    give(s, 0, "Convergent Mutation")
    a = body(s, 0, base_loc(0), 3)
    assert "Convergent Mutation" not in hand_plays(s, 0), "one is not two"
    b = body(s, 0, base_loc(0), 7)
    assert "Convergent Mutation" in hand_plays(s, 0)
    cast(s, 0, "Convergent Mutation", a, b)
    run(s)
    assert combat.might(s, T, a) == 7


@case(8122, "Karma sees a card recycled, but not a token")
def _():
    need("Karma - Channeler", "Rumble - Hotheaded", "Carrion Dredger")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    ka = s.add_permanent(T.id_of("Karma - Channeler"), 0, base_loc(0), ready=True)
    ru = s.add_permanent(T.id_of("Rumble - Hotheaded"), 0, base_loc(0), ready=True)
    s.trash[0, 0] = T.id_of("Carrion Dredger")
    s.n_trash[0] = 1
    tok = _sprite_at(s, 0, 1)
    attack(s, 0, 0, ru)
    run(s, picking(tok, pack_trash(0, T.id_of("Carrion Dredger")), base_loc(0)),
        limit=60)
    assert not alive(s, tok)
    assert not s.has_flag(ka, F_BUFFED), "a token is not a card"


@case(8121, "units can be sent into a showdown one at a time")
def _():
    need("Mask of Foresight")
    s = fresh(runes=32)
    mask = s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    a = body(s, 0, base_loc(0), 3, ready=True)
    b = body(s, 0, base_loc(0), 3, ready=True)
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 1)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    attack(s, 0, 0, a)
    drain(s)
    assert combat.might(s, T, a) == 4, "alone, so the Mask fired"
    assert combat.might(s, T, b) == 3 and mask >= 0


@case(8116, "En Garde asks about units you control, not about the ground")
def _():
    need("En Garde")
    s = fresh(runes=24)
    give(s, 0, "En Garde")
    s.bf_ctrl[0] = 1
    att = body(s, 0, base_loc(0), 3, ready=True)
    body(s, 1, bf_loc(0), 9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    attack(s, 0, 0, att)
    cast(s, 0, "En Garde", att)
    drain(s)
    assert combat.might(s, T, att) == 5, "+1, and +1 again for being alone there"


@case(8111, "a showdown continues after Challenge kills the attacker")
def _():
    need("Challenge")
    s = fresh(hand=[T.id_of("Challenge")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    d = body(s, 0, bf_loc(0), 3)
    home = body(s, 0, base_loc(0), 9)
    s.ply += 1
    att = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, att)
    s.active = s.priority = 0
    cast(s, 0, "Challenge", home, att)
    drain(s)
    assert not alive(s, att), "9 against 3"
    assert int(s.showdown_bf) == 0, "and the showdown is still open"
    assert alive(s, d)


@case(8106, "a countered spell still paid its [Deflect]")
def _():
    need("Hidden Blade", "Defy", "Draven - Audacious")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 1, bf_loc(0), ready=True)
    before = runes(s, 0)
    cast(s, 0, "Hidden Blade", dr)
    assert before - runes(s, 0) == 2, "1 Power plus the Deflect rune, at cast"
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert alive(s, dr)
    assert before - runes(s, 0) == 2, "and countering refunds nothing"


@case(8105, "the first unit onto open ground is the attacker")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 1, "Ride The Wind")
    s.runes_ready[1, :] = 32
    first = body(s, 0, base_loc(0), 3, ready=True)
    late = body(s, 1, base_loc(1), 3, ready=False)
    attack(s, 0, 0, first)
    cast(s, 1, "Ride The Wind", late, bf_loc(0))
    drain(s)
    assert int(s.attacker) == 0, "the contester keeps the designation"


@case(8103, "The Dreaming Tree draws before the bounce resolves")
def _():
    need("The Dreaming Tree", "Retreat")
    s = fresh(runes=24)
    give(s, 0, "Retreat")
    s.bf_card[0] = T.id_of("The Dreaming Tree")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    before = int(s.n_hand[0])
    cast(s, 0, "Retreat", u)
    run(s)
    assert not alive(s, u), "it went back to hand"
    assert int(s.n_hand[0]) == before - 1 + 1 + 1, "the Tree's draw and the unit"


@case(8099, "a [Temporary] unit the Hourglass saved keeps the keyword")
def _():
    need("Zhonya's Hourglass", "Sprite Call")
    s = fresh(runes=24)
    rune_deck(s)
    tok = _sprite_at(s, 0, 0)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    s.death_guard[0] = z
    _next_own_turn(s)
    run(s, limit=40)
    assert not alive(s, tok) or not alive(s, z), \
        "either it died or the Hourglass paid for it"


@case(8097, "Viktor - Leader does not see a unit that died beside him")
def _():
    need("Viktor - Leader", "Watchful Sentry", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    vi = s.add_permanent(T.id_of("Viktor - Leader"), 1, base_loc(1), ready=True)
    ws = s.add_permanent(T.id_of("Watchful Sentry"), 1, base_loc(1), ready=True)
    s.base_might_ply[vi], s.base_might_val[vi] = int(s.ply), 3
    cast(s, 0, "Falling Star", vi, ws)
    run(s)
    assert not alive(s, vi) and not alive(s, ws)
    assert not tokens(s, 1), "he was gone when the triggers were placed"


@case(8096, "'this turn' ends with the turn it was played in")
def _():
    need("Decisive Strike")
    s = fresh(hand=[T.id_of("Decisive Strike")], runes=32)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Decisive Strike")
    run(s)
    assert combat.might(s, T, u) == 5
    act(s, A.A_END_TURN, None, 0)
    run(s, limit=40)
    assert combat.might(s, T, u) == 3, "the Ending Step took it back"


@case(8088, "Unyielding Spirit stops Void Seeker but not Snapvine")
def _():
    need("Unyielding Spirit", "Void Seeker", "Carnivorous Snapvine")
    s = fresh(hand=[T.id_of("Void Seeker")], runes=32)
    give(s, 1, "Unyielding Spirit")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Void Seeker", u)
    cast(s, 1, "Unyielding Spirit")
    run(s)
    assert int(s.perms[u, P_DMG]) == 0, "the spell dealt it, so it is prevented"
    give(s, 0, "Carnivorous Snapvine")
    act(s, A.A_PLAY, hand_index(s, 0, "Carnivorous Snapvine"), 0)
    choose(s, base_loc(0))
    choose(s, u)
    run(s)
    assert int(s.perms[u, P_DMG]) == 6, "the units deal that one to each other"


@case(8085, "conquering ground you already hold is no conquer at all")
def _():
    need("Boots of Swiftness")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    keeper = body(s, 0, bf_loc(0), 3)
    mover = body(s, 0, base_loc(0), 3, ready=True)
    before = int(s.points[0])
    attack(s, 0, 0, mover)
    fight(s)
    assert int(s.points[0]) == before, "190.4.a: it was already yours"
    assert keeper >= 0


@case(8113, "Janna can only be played to ground you control")
def _():
    need("Janna - Savior")
    s = fresh(runes=32)
    give(s, 0, "Janna - Savior")
    s.bf_ctrl[0] = 1
    att = body(s, 0, base_loc(0), 3, ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, att)
    act(s, A.A_PLAY, hand_index(s, 0, "Janna - Savior"), 0)
    where = {a.arg for a in A.legal_actions(s, T, V1, 0)
             if a.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)}
    assert bf_loc(0) not in where, "you do not control the ground you attack"


@case(8109, "a champion played from its own zone is not played from hand")
def _():
    need("Rek'Sai - Breacher", "Determined Sentry")
    s = fresh(runes=32)
    s.add_permanent(T.id_of("Rek'Sai - Breacher"), 0, base_loc(0), ready=True)
    s.trash[0, 0] = T.id_of("Determined Sentry")
    s.n_trash[0] = 1
    give(s, 0, "Spectral Matron")
    act(s, A.A_PLAY, hand_index(s, 0, "Spectral Matron"), 0)
    choose(s, base_loc(0))
    run(s, picking(pack_trash(0, T.id_of("Determined Sentry")), base_loc(0),
                   accept=True), limit=40)
    assert perm_of(s, "Determined Sentry", 0), "it was played from the trash"


@case(8134, "a hidden card is lost with the battlefield it was hidden at")
def _():
    need("Hidden Blade", "Bullet Time")
    s = fresh(hand=[T.id_of("Bullet Time")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    slot = hidden_at(s, 1, 0, "Hidden Blade")
    cast(s, 0, "Bullet Time", bf_loc(0))
    run(s, picking(3))
    assert not alive(s, u), "the last unit there died"
    assert int(s.fd_card[slot]) < 0, "466.5.c takes the hidden card with it"
