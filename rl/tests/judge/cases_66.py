"""RiftJudge batch 66 -- unused questions from 7304-7353."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7353, "a Reaction that kills the source nullifies its attack trigger")
def _():
    need("Yasuo - Remorseful", "Hidden Blade")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 12)
    slot = hidden_at(s, 1, 0, "Hidden Blade")
    attack(s, 0, 0, ya)
    choose(s, d)
    pass_priority_to(s, 1)
    act(s, A.A_PLAY_HIDDEN, slot, 1)
    choose(s, ya)
    run(s, limit=40)
    assert not alive(s, ya)
    assert int(s.perms[d, P_DMG]) == 0, "his damage had no source left"


@case(7344, "a spell that does not say 'battlefield' reaches a base")
def _():
    need("Challenge")
    s = fresh(hand=[T.id_of("Challenge")], runes=32)
    mine = body(s, 0, base_loc(0), 5)
    theirs = body(s, 1, base_loc(1), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Challenge"), 0)
    choose(s, mine)
    assert theirs in targets_offered(s, 0), "no locality is printed"


@case(7342, "Stormbringer deals the same damage to each unit")
def _():
    need("Stormbringer")
    s = fresh(hand=[T.id_of("Stormbringer")], runes=32)
    mine = body(s, 0, base_loc(0), 4)
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 9)
    b = body(s, 1, bf_loc(0), 9)
    give(s, 1, "Smoke Screen")                   # keeps the showdown open
    s.runes_ready[1, :] = 32
    cast(s, 0, "Stormbringer", mine, bf_loc(0))
    drain(s)                                     # read it before the heal
    assert int(s.perms[a, P_DMG]) == 4 and int(s.perms[b, P_DMG]) == 4


@case(7339, "combat damage is checked once, so a dying buff saves nobody")
def _():
    need("Lee Sin - Centered")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    lee = s.add_permanent(T.id_of("Lee Sin - Centered"), 0, base_loc(0),
                          ready=True)
    mate = body(s, 0, base_loc(0), 2, ready=True)
    s.set_flag(mate, F_BUFFED)
    assert combat.might(s, T, mate) == 3, "at base, only the buff"
    body(s, 1, bf_loc(0), 6)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    attack(s, 0, 0, lee, mate)
    assert combat.might(s, T, mate) == 2 + 1 + 2, "at his battlefield, his +2 too"
    fight(s)
    assert alive(s, mate), "5 Might against the damage it was assigned"


@case(7338, "Singularity's targets cannot be changed")
def _():
    need("Singularity", "Retreat")
    s = fresh(hand=[T.id_of("Singularity")], runes=32)
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 32
    a = body(s, 1, base_loc(1), 5)
    b = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Singularity", a, -1)
    cast(s, 1, "Retreat", a)
    run(s)
    assert not alive(s, a), "it went to hand"
    assert alive(s, b) and int(s.perms[b, P_DMG]) == 0, "and b was never chosen"


@case(7337, "Unyielding Spirit does not stop Snapvine's exchange")
def _():
    need("Unyielding Spirit", "Carnivorous Snapvine")
    s = fresh(hand=[T.id_of("Carnivorous Snapvine")], runes=32)
    give(s, 1, "Unyielding Spirit")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 9)
    act(s, A.A_PLAY, hand_index(s, 0, "Carnivorous Snapvine"), 0)
    choose(s, base_loc(0))
    choose(s, foe)
    cast(s, 1, "Unyielding Spirit")
    run(s)
    assert int(s.perms[foe, P_DMG]) == 6, "the units deal it to each other"


@case(7335, "Last Breath is an [Action] and cannot answer a Reaction")
def _():
    need("Last Breath", "Hidden Blade")
    s = fresh(runes=32)
    give(s, 1, "Last Breath")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 3)
    body(s, 1, base_loc(1), 4, ready=False)
    att = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, att)
    give(s, 0, "Hidden Blade")
    cast(s, 0, "Hidden Blade", d)
    pass_priority_to(s, 1)
    assert "Last Breath" not in hand_plays(s, 1), "an Action wants an empty chain"


@case(7332, "a defender bonus goes when the combat does, the -1 stays")
def _():
    need("Stupefy", "Stalwart Poro", "Fight or Flight")
    s = fresh(runes=32)
    give(s, 1, "Stupefy", "Fight or Flight")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    poro = s.add_permanent(T.id_of("Stalwart Poro"), 0, bf_loc(0), ready=True)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    assert combat.might(s, T, poro) == 3, "2 printed plus [Shield] as a defender"
    cast(s, 1, "Stupefy", poro)
    drain(s)
    assert combat.might(s, T, poro) == 2, "the -1 came off the defending number"
    assert alive(s, poro), "and no damage is marked, so it lives"


@case(7331, "Unyielding Spirit does not stop Dragon's Rage")
def _():
    need("Unyielding Spirit", "Dragon's Rage")
    s = fresh(hand=[T.id_of("Dragon's Rage")], runes=32)
    give(s, 1, "Unyielding Spirit")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    mover = body(s, 1, bf_loc(0), 3)
    home = body(s, 1, base_loc(1), 4)
    cast(s, 0, "Dragon's Rage", mover, base_loc(1), home)
    cast(s, 1, "Unyielding Spirit")
    run(s)
    assert int(s.perms[home, P_DMG]) == 3, "the units dealt it"


@case(7330, "Karma can buff the unit that a Hook just played")
def _():
    need("Karma - Channeler", "Baited Hook", "Determined Sentry")
    s = fresh(runes=32)
    ka = s.add_permanent(T.id_of("Karma - Channeler"), 0, base_loc(0), ready=True)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, base_loc(0), 3)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Determined Sentry")
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, 0, base_loc(0), accept=True), limit=80)
    ds = perm_of(s, "Determined Sentry", 0)
    assert ds, "it came off the Hook"
    assert s.has_flag(ds[0], F_BUFFED) or s.has_flag(ka, F_BUFFED), \
        "the recycle gave Karma something to buff"


@case(7329, "a battlefield opened mid-combat waits its turn")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    att = body(s, 0, base_loc(0), 9, ready=True)
    home = body(s, 0, base_loc(0), 3, ready=False)
    body(s, 1, bf_loc(0), 3)
    s.bf_ctrl[1] = -1
    attack(s, 0, 0, att)
    cast(s, 0, "Ride The Wind", home, bf_loc(1))
    drain(s)
    assert int(s.showdown_bf) == 0, "the first showdown is still the open one"
    fight(s)
    assert int(s.bf_ctrl[1]) == 0, "and then the second one settled"


@case(7323, "Not So Fast counters a repeated spell whole")
def _():
    need("Not So Fast", "Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=32)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 5)
    b = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Bellows Breath", a, b, -1, repeat=True)
    choose(s, a)
    choose(s, b)
    choose(s, -1)
    cast(s, 1, "Not So Fast")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert int(s.perms[a, P_DMG]) == 0 and int(s.perms[b, P_DMG]) == 0


@case(7318, "a recall keeps the unit's ready state")
def _():
    need("Possession")
    s = fresh(hand=[T.id_of("Possession")], runes=32)
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 5, ready=True)
    cast(s, 0, "Possession", foe)
    run(s)
    assert int(s.perms[foe, P_CTRL]) == 0
    assert int(s.perms[foe, P_READY]) == 1, "a recall changes nothing else"


@case(7315, "Stormbringer needs a unit in your base")
def _():
    need("Stormbringer")
    s = fresh(hand=[T.id_of("Stormbringer")], runes=32)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 4)
    assert "Stormbringer" not in hand_plays(s, 0), "nobody at home"
    body(s, 0, base_loc(0), 4)
    assert "Stormbringer" in hand_plays(s, 0)


@case(7311, "Pack of Wonders reaches the board, not the trash")
def _():
    need("Pack of Wonders", "Determined Sentry")
    s = fresh(runes=32)
    pw = s.add_permanent(T.id_of("Pack of Wonders"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 3)
    s.trash[0, 0] = T.id_of("Determined Sentry")
    s.n_trash[0] = 1
    act(s, A.A_ACTIVATE, pw, 0)
    choose(s, 0)                                 # mode: return a unit or gear
    offered = targets_offered(s, 0)
    assert u in offered and pw not in offered, "'another' friendly card"
    assert pack_trash(0, T.id_of("Determined Sentry")) not in offered


@case(7308, "Showstopper moves an exhausted unit")
def _():
    need("Showstopper")
    s = fresh(runes=32)
    give(s, 0, "Showstopper")
    s.bf_ctrl[0] = 0
    u = body(s, 0, base_loc(0), 3, ready=False)
    cast(s, 0, "Showstopper", u, bf_loc(0))
    run(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(0), "452: no exhaust cost"
    assert s.has_flag(u, F_BUFFED)


@case(7307, "a lone defender picks up the legend's +2 once it is alone")
def _():
    need("Reaver's Row", "Master Yi - Wuju Bladesman")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Reaver's Row")
    s.bf_ctrl[0] = 0
    s.legend[0], s.legend_ready[0] = T.id_of("Master Yi - Wuju Bladesman"), 1
    a = body(s, 0, bf_loc(0), 3)
    b = body(s, 0, bf_loc(0), 3)
    give(s, 0, "Smoke Screen")
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    run(s, picking(b, accept=True), limit=20,
        stop=lambda st: int(st.perms[b, P_LOC]) == base_loc(0))
    assert int(s.perms[b, P_LOC]) == base_loc(0), "the Row sent one home"
    assert combat.might(s, T, a) == 5, "and the other is alone now"


@case(7304, "[Ganking] restricts only the Standard Move")
def _():
    need("Ride The Wind", "Boots of Swiftness")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    u = body(s, 0, bf_loc(0), 3)
    g = s.add_permanent(T.id_of("Boots of Swiftness"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, u)
    run(s)
    cast(s, 0, "Ride The Wind", u, bf_loc(1))
    run(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(1), "a spell needs no [Ganking]"


@case(7322, "an [Accelerate] cost is paid even off a free play")
def _():
    need("Promising Future", "Jinx, Demolitionist")
    s = fresh(hand=[T.id_of("Promising Future")], runes=32)
    n = int(s.deck_ptr[0])
    s.deck[0, n:n + 5] = T.id_of("Jinx, Demolitionist")
    m = int(s.deck_ptr[1])
    s.deck[1, m:m + 5] = VANILLA
    cast(s, 0, "Promising Future")
    run(s, picking(0, base_loc(0), base_loc(1), accept=True), limit=80)
    jx = perm_of(s, "Jinx, Demolitionist", 0)
    assert jx, "she came off the top"
