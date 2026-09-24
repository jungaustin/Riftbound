"""RiftJudge batch 70 -- unused questions from 7104-7153."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7153, "Blind Fury plays their card for no cost at all")
def _():
    need("Blind Fury", "Riptide Rex")
    s = fresh(hand=[T.id_of("Blind Fury")], runes=32)
    n = int(s.deck_ptr[1])
    s.deck[1, n] = T.id_of("Riptide Rex")
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(1), 9)
    before = runes(s, 0)
    cast(s, 0, "Blind Fury")
    run(s, picking(T.id_of("Riptide Rex"), base_loc(0), accept=True), limit=60)
    assert before - runes(s, 0) == 2, "only Blind Fury's own Power"


@case(7148, "Disintegrate draws when its damage kills the unit")
def _():
    need("Disintegrate")
    s = fresh(hand=[T.id_of("Disintegrate")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    before = int(s.n_hand[0])
    cast(s, 0, "Disintegrate", u)
    run(s, picking(accept=True))
    assert not alive(s, u)
    assert int(s.n_hand[0]) == before - 1 + 1, "the reflexive draw arrived"


@case(7145, "Vengeance chooses, Cull the Weak does not")
def _():
    need("Vengeance", "Cull the Weak")
    s = fresh(hand=[T.id_of("Vengeance"), T.id_of("Cull the Weak")], runes=32)
    foe = body(s, 1, base_loc(1), 9)
    act(s, A.A_PLAY, hand_index(s, 0, "Vengeance"), 0)
    assert foe in targets_offered(s, 0), "it names its unit at cast"
    choose(s, foe)
    run(s)
    assert not alive(s, foe)


@case(7138, "both players may score the same battlefield in a turn cycle")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    _next_own_turn(s)
    run(s, limit=40)
    assert int(s.points[0]) == 1, "his Hold"
    s.ply += 1
    s.active = s.priority = 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    fight(s)
    assert int(s.points[1]) == 1, "and their conquer on their own turn"


@case(7137, "a facedown card is not a spell, so Defy cannot name it")
def _():
    need("Zhonya's Hourglass", "Defy")
    s = fresh(runes=32)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    slot = hidden_at(s, 0, 0, "Zhonya's Hourglass")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    assert perm_of(s, "Zhonya's Hourglass", 0), "it is a gear, and already down"
    assert "Defy" not in hand_plays(s, 1)


@case(7134, "Traveling Merchant triggers for each move")
def _():
    need("Traveling Merchant", "Ride The Wind", "Fight or Flight")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    give(s, 1, "Fight or Flight")
    s.runes_ready[1, :] = 32
    give(s, 0, "Smoke Screen", "Smoke Screen")
    s.bf_ctrl[0] = 0
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, base_loc(0), ready=True)
    before = int(s.n_hand[0])
    cast(s, 0, "Ride The Wind", tm, bf_loc(0))
    run(s, picking(0), limit=40)
    assert int(s.perms[tm, P_LOC]) == bf_loc(0)
    assert int(s.n_hand[0]) == before - 1, "one discard, one draw, and the spell gone"


@case(7133, "Defy cannot be played into an empty chain")
def _():
    need("Defy")
    s = fresh(runes=32)
    give(s, 0, "Defy")
    body(s, 0, base_loc(0), 3)
    assert "Defy" not in hand_plays(s, 0), "355.8: nothing to counter"


@case(7131, "a countered Cleave never readies Darius")
def _():
    need("Cleave", "Defy", "Darius - Trifarian")
    s = fresh(runes=32)
    give(s, 1, "Cleave")
    give(s, 0, "Defy")
    s.runes_ready[1, :] = 32
    dar = s.add_permanent(T.id_of("Darius - Trifarian"), 0, base_loc(0),
                          ready=False)
    s.ply += 1
    s.active = s.priority = 1
    cast(s, 1, "Cleave", dar)
    cast(s, 0, "Defy")
    choose(s, sorted(targets_offered(s, 0))[0])
    run(s)
    assert int(s.perms[dar, P_READY]) == 0


@case(7129, "a passive that wants 'alone' switches on when the ally dies")
def _():
    need("Master Yi - Wuju Bladesman", "Void Seeker")
    s = fresh(hand=[T.id_of("Void Seeker")], runes=32)
    s.legend[1], s.legend_ready[1] = T.id_of("Master Yi - Wuju Bladesman"), 1
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 3)
    b = body(s, 1, bf_loc(0), 9)
    att = body(s, 0, base_loc(0), 3, ready=True)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    attack(s, 0, 0, att)
    assert combat.might(s, T, b) == 9, "two defenders, so no bonus"
    cast(s, 0, "Void Seeker", a)
    drain(s)
    assert not alive(s, a)
    assert combat.might(s, T, b) == 11, "alone now, so his +2 is on"


@case(7128, "a hidden Hidden Blade reaches only its own battlefield")
def _():
    need("Hidden Blade")
    s = fresh(runes=32)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    here = body(s, 1, bf_loc(0), 3)
    away = body(s, 1, bf_loc(1), 3)
    slot = hidden_at(s, 0, 0, "Hidden Blade")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    offered = targets_offered(s, 0)
    assert here in offered and away not in offered


@case(7125, "Teemo's ability pays [Deflect] once")
def _():
    need("Teemo - Strategist", "Draven - Audacious")

    def spend(deflect):
        s = fresh(runes=32)
        s.bf_ctrl[0] = 0
        body(s, 0, bf_loc(0), 3)
        s.add_permanent(T.id_of("Teemo - Strategist"), 0, bf_loc(0), ready=True)
        n = int(s.deck_ptr[0])
        s.deck[0, n:n + 5] = T.id_of("Hidden Blade")
        s.ply += 1
        if deflect:
            foe = s.add_permanent(T.id_of("Draven - Audacious"), 1, base_loc(1),
                                  ready=True)
        else:
            foe = body(s, 1, base_loc(1), 9, ready=True)
        attack(s, 1, 0, foe)
        before = runes(s, 0)
        choose(s, foe)
        drain(s)
        return before - runes(s, 0), int(s.perms[foe, P_DMG])

    a_spend, a_dmg = spend(False)
    b_spend, b_dmg = spend(True)
    assert a_dmg == b_dmg == 5, "five [Hidden] cards revealed"
    assert b_spend == a_spend + 1, "one choice, one rune"


@case(7123, "conquering empty ground designates nobody")
def _():
    need("Cleave")
    s = fresh(runes=32)
    give(s, 0, "Cleave")
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    cast(s, 0, "Cleave", u)
    drain(s)
    assert combat.might(s, T, u) == 3, "no Attacker designation, no [Assault]"


@case(7120, "a free play still offers [Accelerate]")
def _():
    need("Baited Hook", "Jinx, Demolitionist")
    s = fresh(runes=32)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, base_loc(0), 3)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Jinx, Demolitionist")
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, 0, base_loc(0), accept=True), limit=60)
    assert perm_of(s, "Jinx, Demolitionist", 0)


@case(7116, "Solari Shieldbearer may stun itself")
def _():
    need("Solari Shieldbearer")
    s = fresh(hand=[T.id_of("Solari Shieldbearer")], runes=32)
    act(s, A.A_PLAY, hand_index(s, 0, "Solari Shieldbearer"), 0)
    choose(s, base_loc(0))
    sb = perm_of(s, "Solari Shieldbearer", 0)[0]
    assert sb in targets_offered(s, 0), "'a unit' includes himself"
    choose(s, sb)
    run(s)
    assert s.has_flag(sb, F_STUNNED)


@case(7115, "Soulgorger played from the trash still triggers")
def _():
    need("Soulgorger", "The Harrowing", "Determined Sentry")
    s = fresh(hand=[T.id_of("The Harrowing")], runes=32)
    s.trash[0, 0] = T.id_of("Soulgorger")
    s.trash[0, 1] = T.id_of("Determined Sentry")
    s.n_trash[0] = 2
    cast(s, 0, "The Harrowing")
    run(s, picking(pack_trash(0, T.id_of("Soulgorger")), base_loc(0),
                   pack_trash(0, T.id_of("Determined Sentry")), accept=True),
        limit=80)
    assert perm_of(s, "Soulgorger", 0), "he came out of the trash"
    assert perm_of(s, "Determined Sentry", 0), "and his own trigger brought a friend"


@case(7114, "Brynhir stops a hidden card as much as a hand card")
def _():
    need("Brynhir Thundersong", "Hidden Blade")
    s = fresh(hand=[T.id_of("Brynhir Thundersong")], runes=32)
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(0), 3)
    slot = hidden_at(s, 1, 0, "Hidden Blade")
    act(s, A.A_PLAY, hand_index(s, 0, "Brynhir Thundersong"), 0)
    choose(s, base_loc(0))
    run(s)
    assert not [a for a in A.legal_actions(s, T, V1, 1)
                if a.kind == A.A_PLAY_HIDDEN and a.arg == slot]


@case(7113, "a stolen unit's Deathknell is yours, and so is the draw")
def _():
    need("Hostile Takeover", "Ferrous Forerunner", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hostile Takeover"), T.id_of("Hidden Blade")],
              runes=32)
    s.bf_ctrl[0] = 1
    ff = s.add_permanent(T.id_of("Ferrous Forerunner"), 1, bf_loc(0), ready=True)
    cast(s, 0, "Hostile Takeover", ff)
    run(s)
    assert int(s.perms[ff, P_CTRL]) == 0
    before = int(s.n_hand[0])
    cast(s, 0, "Hidden Blade", ff)
    run(s, picking(accept=True), limit=40)
    assert not alive(s, ff)
    assert len(tokens(s, 0)) == 2, "his Deathknell paid you"
    assert int(s.n_hand[0]) == before - 1 + 2, "and so did Hidden Blade"


@case(7109, "Taric's Shield holds through the damage assignment")
def _():
    need("Taric - Protector", "Stalwart Poro")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    ta = s.add_permanent(T.id_of("Taric - Protector"), 0, bf_loc(0), ready=True)
    poro = s.add_permanent(T.id_of("Stalwart Poro"), 0, bf_loc(0), ready=True)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 5, ready=True)
    attack(s, 1, 0, foe)
    fight(s)
    assert alive(s, poro), "4 Might while Taric stood, and the damage was assigned"


@case(7105, "Singularity may choose nothing at all")
def _():
    need("Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=32)
    mine = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Singularity", -1, -1)
    run(s)
    assert alive(s, mine), "'up to two' can be none"


@case(7104, "a Shield that ends leaves the unit at its own Might")
def _():
    need("Fortified Position", "Stalwart Poro")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Fortified Position")
    s.bf_ctrl[0] = 0
    poro = s.add_permanent(T.id_of("Stalwart Poro"), 0, bf_loc(0), ready=True)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 1, ready=True)
    attack(s, 1, 0, foe)
    run(s, picking(poro, accept=True), limit=40)
    assert alive(s, poro), "it survived the combat"
    assert combat.might(s, T, poro) == 2, "and is its printed Might again"
