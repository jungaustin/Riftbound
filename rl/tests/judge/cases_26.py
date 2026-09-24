"""RiftJudge batch 26 -- unused questions from 9814-9891."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_NO_MOVE, P_ATTACHED_TO
from rl.engine.effects import ABILITIES, pack_trash


@case(9891, "Heedless Resurrection names its trash unit as it is played")
def _():
    need("Heedless Resurrection", "Determined Sentry")
    s = fresh(hand=[T.id_of("Heedless Resurrection")], runes=9)
    k = body(s, 0, base_loc(0), 3)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Determined Sentry"), 1
    act(s, A.A_PLAY, hand_index(s, 0, "Heedless Resurrection"), 0)
    choose(s, k)
    assert pack_trash(0, T.id_of("Determined Sentry")) in targets_offered(s, 0)
    choose(s, pack_trash(0, T.id_of("Determined Sentry")))
    assert "Heedless Resurrection" in chain_names(s)
    assert not perm_of(s, "Determined Sentry"), "chosen now, played on resolution"


@case(9890, "Karthus doubles Soaring Scout's Deathknell when Falling Star kills both")
def _():
    need("Falling Star", "Karthus - Eternal", "Soaring Scout")
    s = fresh(hand=[T.id_of("Falling Star")], runes=9)
    rune_deck(s)
    ka = s.add_permanent(T.id_of("Karthus - Eternal"), 1, base_loc(1))
    sc = s.add_permanent(T.id_of("Soaring Scout"), 1, base_loc(1))
    before = runes(s, 1)
    cast(s, 0, "Falling Star", ka, sc)
    run(s)
    assert not alive(s, ka) and not alive(s, sc)
    assert runes(s, 1) == before + 2, runes(s, 1) - before


@case(9889, "Beast Below may be played with no other friendly unit")
def _():
    need("Beast Below")
    s = fresh(hand=[T.id_of("Beast Below")], runes=12)
    foe = body(s, 1, base_loc(1), 3)
    assert "Beast Below" in hand_plays(s, 0)
    cast(s, 0, "Beast Below", base_loc(0))
    run(s, picking(foe))
    bb = perm_of(s, "Beast Below")
    assert bb, "it stays: 'another friendly unit' simply isn't there"


@case(9885, "Piercing Light's second target may be skipped")
def _():
    need("Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=9)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Piercing Light", u, -1)
    run(s)
    assert int(s.perms[u, P_DMG]) == 2


@case(9882, "Frozen Fortress kills before the Scoring Step: no hold point")
def _():
    need("Frozen Fortress")
    s = fresh()
    s.bf_card[0] = T.id_of("Frozen Fortress")
    s.bf_ctrl[0] = 0
    u = s.add_permanent(T.id_of("Determined Sentry"), 0, bf_loc(0))
    _next_own_turn(s)
    run(s, picking())
    assert not alive(s, u) and int(s.points[0]) == 0


@case(9880, "Void Assault whose friendly unit was Retreated still moves the enemy")
def _():
    need("Void Assault", "Retreat")
    s = fresh(hand=[T.id_of("Void Assault")], runes=9)
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 9
    rune_deck(s)
    s.bf_ctrl[0] = 0
    mine = body(s, 0, base_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    theirs_retreat = body(s, 1, base_loc(1), 2)
    cast(s, 0, "Void Assault", mine, bf_loc(0), foe, bf_loc(0))
    rsv.resolve(s, T, V1, SPECS["Retreat"], 0, [mine], -1, True)
    run(s)
    assert not alive(s, mine)
    assert int(s.perms[foe, P_LOC]) == bf_loc(0), "do as much as you can"


@case(9878, "units do not heal when a non-combat showdown ends")
def _():
    need("Challenge")
    s = fresh(hand=[T.id_of("Challenge")], runes=9)
    give(s, 1, "Smoke Screen")
    a = body(s, 0, base_loc(0), 5, ready=True)
    foe = body(s, 1, base_loc(1), 1)
    attack(s, 0, 0, a)
    assert int(s.showdown_bf) == 0 and not s.showdown_combat
    rsv.resolve(s, T, V1, SPECS["Challenge"], 0, [a, foe], -1, True)
    assert int(s.perms[a, P_DMG]) == 1
    fight(s)
    assert int(s.showdown_bf) < 0 and int(s.perms[a, P_DMG]) == 1


@case(9877, "Rengar answering a move is a defender, so Master Yi pumps him")
def _():
    need("Master Yi - Wuju Bladesman", "Rengar, Trophy Hunter")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    s.legend[0], s.legend_ready[0] = T.id_of("Master Yi - Wuju Bladesman"), 1
    give(s, 0, "Rengar, Trophy Hunter")
    give(s, 1, "Smoke Screen")
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    cast(s, 0, "Rengar, Trophy Hunter", bf_loc(0))
    run(s, stop=lambda s: bool(s.showdown_combat) and bool(perm_of(s, "Rengar, Trophy Hunter")))
    rg = perm_of(s, "Rengar, Trophy Hunter")[0]
    assert combat.might(s, T, rg) == 8, combat.might(s, T, rg)


@case(9873, "Rengar legend's +1 may resolve before Kinkou Initiate's check")
def _():
    need("Kinkou Initiate", "Rengar - Pridestalker")
    s = fresh(hand=[T.id_of("Kinkou Initiate")], runes=9)
    s.legend[0], s.legend_ready[0] = T.id_of("Rengar - Pridestalker"), 1
    u = body(s, 0, base_loc(0), 4)
    cast(s, 0, "Kinkou Initiate", base_loc(0))
    A._settle(s, T, V1)
    # Kinkou placed FIRST, so the legend's trigger (placed last) resolves first
    ki = perm_of(s, "Kinkou Initiate")[0]
    act(s, A.A_ORDER, next(a.arg for a in A.legal_actions(s, T, V1, 0)
                           if a.kind == A.A_ORDER and int(s.trig[a.arg, 1]) == ki), 0)
    run(s, picking(u), stop=lambda s: s.n_chain == 0 and s.n_trig == 0)
    assert combat.might(s, T, u) == 5 and int(s.n_hand[0]) == 1


@case(9872, "Soraka - Wanderer saves a [Temporary] unit")
def _():
    need("Soraka - Wanderer", "Sprite Call")
    s = fresh()
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Soraka - Wanderer"), 0, bf_loc(0))
    sprite = _sprite_at(s, 0, 0)
    _next_own_turn(s)
    run(s, picking())
    assert alive(s, sprite) and int(s.perms[sprite, P_LOC]) == base_loc(0)


@case(9870, "Thrill of the Hunt sheds a unit's Might reduction")
def _():
    need("Thrill of the Hunt", "Frigid Touch")
    s = fresh(hand=[T.id_of("Thrill of the Hunt")], runes=9)
    s.bf_ctrl[0] = 0
    u = s.add_permanent(T.id_of("Mindsplitter"), 0, bf_loc(0))
    rsv.resolve(s, T, V1, SPECS["Frigid Touch"], 1, [u], -1, True)
    assert combat.might(s, T, u) == 5
    cast(s, 0, "Thrill of the Hunt", u)
    run(s, picking(bf_loc(0)))
    ms = perm_of(s, "Mindsplitter", 0)
    assert ms and combat.might(s, T, ms[0]) == 7


@case(9867, "the Baron Pit stays when Baron Nashor dies")
def _():
    need("Baron Nashor")
    s = fresh(hand=[T.id_of("Baron Nashor")], runes=12)
    cast(s, 0, "Baron Nashor", base_loc(0))
    run(s, picking())
    combat.destroy(s, T, perm_of(s, "Baron Nashor")[0])
    run(s)
    assert any(int(c) == T.id_of("Baron Pit") for c in s.bf_card)


@case(9864, "a stolen Ferrous Forerunner's Mechs are its controller's")
def _():
    need("Conscription", "Ferrous Forerunner")
    s = fresh(hand=[T.id_of("Conscription")], runes=9)
    s.xp[0] = 5
    s.bf_ctrl[1] = 1
    ff = s.add_permanent(T.id_of("Ferrous Forerunner"), 1, bf_loc(0))
    act(s, A.A_PLAY_REPEAT, hand_index(s, 0, "Conscription"), 0)
    choose(s, ff)
    run(s)
    assert int(s.perms[ff, P_CTRL]) == 0
    combat.destroy(s, T, ff)
    run(s)
    assert len(tokens(s, 0, base_loc(0))) == 2 and not tokens(s, 1)


@case(9862, "Commander Ledros may be played where its only killed unit stood")
def _():
    need("Commander Ledros")
    s = fresh(hand=[T.id_of("Commander Ledros")], runes=9)
    s.bf_ctrl[0] = 0
    lone = body(s, 0, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Commander Ledros"), 0)
    choose(s, lone)                          # its only other unit: no more to kill
    assert int(s.bf_ctrl[0]) == 0
    choose(s, bf_loc(0))
    cl = perm_of(s, "Commander Ledros")
    assert cl and int(s.perms[cl[0], P_LOC]) == bf_loc(0) and not alive(s, lone)


@case(9861, "a Defy can itself be Defied")
def _():
    need("Defy", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    give(s, 0, "Defy")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Defy", top_uid(s))
    cast(s, 0, "Defy", top_uid(s))
    run(s)
    assert combat.might(s, T, u) == 5


@case(9860, "Dazzling Aurora finding no unit is not a Burn Out")
def _():
    need("Dazzling Aurora", "Discipline")
    s = fresh(runes=9)
    s.add_permanent(T.id_of("Dazzling Aurora"), 0, base_loc(0))
    s.deck[0, :20] = T.id_of("Discipline")
    act(s, A.A_END_TURN, None, 0)
    run(s)
    assert int(s.points[1]) == 0, "no Burn Out point for the opponent"


@case(9858, "Accelerate from Rek'Sai, Breacher still has to be paid")
def _():
    need("Rek'Sai - Breacher", "Glasc Mixologist", "Determined Sentry")
    s = fresh()
    s.add_permanent(T.id_of("Rek'Sai - Breacher"), 0, base_loc(0))
    g = s.add_permanent(T.id_of("Glasc Mixologist"), 0, base_loc(0))
    s.trash[0, 0], s.n_trash[0] = T.id_of("Determined Sentry"), 1
    s.runes_ready[0, :] = 0
    combat.destroy(s, T, g)
    run(s, picking(pack_trash(0, T.id_of("Determined Sentry")), base_loc(0)))
    ds = perm_of(s, "Determined Sentry")
    assert ds and int(s.perms[ds[0], P_READY]) == 0, "no runes, so no Accelerate"


@case(9855, "Ezreal, Prodigy does not discount Diana - Lunari's trigger")
def _():
    need("Ezreal, Prodigy", "Diana - Lunari")
    s = fresh(seat=1)
    s.runes_ready[0, :] = 0
    s.add_permanent(T.id_of("Ezreal, Prodigy"), 0, base_loc(0))
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Diana - Lunari"), 0, bf_loc(0))
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    assert A.A_ACCEPT not in {a.kind for a in A.legal_actions(s, T, V1, 0)}, \
        "{1 energy} is still owed and there is none"


@case(9854, "Hostile Takeover can take a token unit")
def _():
    need("Hostile Takeover", "Sprite Call")
    s = fresh(hand=[T.id_of("Hostile Takeover")], runes=9)
    tok = _sprite_at(s, 1, 0)
    s.active = s.priority = 0
    cast(s, 0, "Hostile Takeover", tok)
    run(s, picking())
    assert int(s.perms[tok, P_CTRL]) == 0


@case(9844, "Vex - Cheerless and Find Your Center stack to {1 energy}")
def _():
    need("Find Your Center", "Vex - Cheerless")
    s = fresh(hand=[T.id_of("Find Your Center")], runes=9)
    s.points[1] = 6
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    vx = s.add_permanent(T.id_of("Vex - Cheerless"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, vx)
    run(s, stop=lambda s: bool(s.showdown_combat) and A.acting_seat(s) == 0)
    s.runes_ready[0, :] = 0
    s.runes_ready[0, 0] = 1
    assert "Find Your Center" in hand_plays(s, 0), "3 - 2 - 1, minimum 1"


@case(9843, "Charm can move an enemy from one battlefield to one you control")
def _():
    need("Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=9)
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    body(s, 0, bf_loc(0), 3)
    foe = body(s, 1, bf_loc(1), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Charm"), 0)
    choose(s, foe)
    assert bf_loc(0) in targets_offered(s, 0)


@case(9841, "Lonely Poro's 'alone' is read at its death")
def _():
    need("Lonely Poro", "Vi - Peacekeeper")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 0
    lp = s.add_permanent(T.id_of("Lonely Poro"), 0, bf_loc(0))
    give(s, 0, "Vi - Peacekeeper")
    combat.destroy(s, T, lp)
    A._settle(s, T, V1)
    assert "Lonely Poro" in chain_names(s)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)                 # an Ambush in answer
    run(s)
    assert int(s.n_hand[0]) == 2, "Vi, and the Poro's card"


@case(9829, "Acceptable Losses needs no gear of your own")
def _():
    need("Acceptable Losses", "Warmog's Armor")
    s = fresh(hand=[T.id_of("Acceptable Losses")], runes=9)
    g = s.add_permanent(T.id_of("Warmog's Armor"), 1, base_loc(1))
    assert "Acceptable Losses" in hand_plays(s, 0)
    cast(s, 0, "Acceptable Losses")
    run(s, picking(g))
    assert not alive(s, g)


@case(9822, "Cull the Weak is main speed: not playable in combat")
def _():
    need("Cull the Weak")
    s = fresh(runes=9)
    give(s, 0, "Cull the Weak")
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    a = body(s, 0, base_loc(0), 3, ready=True)
    body(s, 1, bf_loc(0), 3)
    attack(s, 0, 0, a)
    run(s, stop=lambda s: bool(s.showdown_combat) and A.acting_seat(s) == 0)
    assert "Cull the Weak" not in hand_plays(s, 0)


@case(9815, "Sunken Temple wants a Mighty unit among those conquering")
def _():
    need("Sunken Temple", "Noxus Hopeful")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Sunken Temple")
    nh = s.add_permanent(T.id_of("Noxus Hopeful"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, nh)
    run(s, picking())
    assert int(s.bf_ctrl[0]) == 0 and int(s.n_hand[0]) == 0, "4 Might is not Mighty"


@case(9814, "Emperor's Divide's move does not exhaust")
def _():
    need("Emperor's Divide")
    s = fresh(hand=[T.id_of("Emperor's Divide")], runes=9)
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3, ready=True)
    cast(s, 0, "Emperor's Divide", u)
    run(s)
    assert int(s.perms[u, P_LOC]) == base_loc(0) and int(s.perms[u, P_READY]) == 1
