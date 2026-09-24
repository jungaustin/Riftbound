"""RiftJudge batch 32 -- unused questions from 9211-9348."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_NO_MOVE, P_ATTACHED_TO, C_UID
from rl.engine.effects import ABILITIES, pack_trash


@case(9348, "Rebuke returns the unit; its Equipment stays on the board")
def _():
    need("Rebuke", "Long Sword")
    s = fresh(hand=[T.id_of("Rebuke")], runes=9)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 3)
    ls = s.add_permanent(T.id_of("Long Sword"), 1, bf_loc(0))
    s.attach(ls, foe)
    cast(s, 0, "Rebuke", foe)
    run(s)
    assert not alive(s, foe) and alive(s, ls) and int(s.perms[ls, P_ATTACHED_TO]) < 0


@case(9345, "Keeper's Verdict on a token: it ceases to exist")
def _():
    need("Keeper's Verdict", "Sprite Call")
    s = fresh(hand=[T.id_of("Keeper's Verdict")], runes=9)
    tok = _sprite_at(s, 1, 0)
    s.active = s.priority = 0
    n = int(s.n_deck[1]) - int(s.deck_ptr[1])
    cast(s, 0, "Keeper's Verdict", tok)
    run(s, picking())
    assert not alive(s, tok)
    assert int(s.n_deck[1]) - int(s.deck_ptr[1]) == n, "no card joined the deck"


@case(9344, "Wages of Pain's Gold arrives even if a reaction killed the target")
def _():
    need("Wages of Pain")
    s = fresh(hand=[T.id_of("Wages of Pain")], runes=9)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Wages of Pain", foe)
    combat.destroy(s, T, foe)
    run(s)
    assert tokens(s, 0)


@case(9341, "repeated Bellows Breath: units Flashed to base are still hit")
def _():
    need("Bellows Breath", "Flash")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=9)
    give(s, 1, "Flash")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[0] = s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(0), 1)
    b = body(s, 1, bf_loc(1), 1)
    cast(s, 0, "Bellows Breath", a, -1, -1, b, -1, -1, repeat=True)
    cast(s, 1, "Flash", a, b)
    run(s)
    assert not alive(s, a) and not alive(s, b), "each execution's lone target is still together with itself"


@case(9338, "[Tank] means nothing to Falling Comet")
def _():
    need("Falling Comet", "Taric - Protector")
    s = fresh(hand=[T.id_of("Falling Comet")], runes=9)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Taric - Protector"), 1, bf_loc(0))
    other = body(s, 1, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Falling Comet"), 0)
    assert other in targets_offered(s, 0)


@case(9337, "Back-Alley Bar's +1 chooses nobody: Irelia's legend doesn't see it")
def _():
    need("Back-Alley Bar", "Irelia - Blade Dancer", "Ride The Wind")
    s = fresh(hand=[T.id_of("Ride The Wind")], runes=9)
    s.legend[0], s.legend_ready[0] = T.id_of("Irelia - Blade Dancer"), 0
    s.bf_card[0] = T.id_of("Back-Alley Bar")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [u, bf_loc(1)], -1, True)
    A._settle(s, T, V1)
    names = chain_names(s)
    assert names.count("Irelia - Blade Dancer") == 0, names


@case(9328, "a repeated Hard Bargain may name the same spell twice")
def _():
    need("Hard Bargain", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    give(s, 1, "Hard Bargain")
    s.runes_ready[1, :] = 9
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    disc = top_uid(s)
    pass_priority_to(s, 1)
    act(s, A.A_PLAY_REPEAT, hand_index(s, 1, "Hard Bargain"), 1)
    choose(s, disc)
    assert disc in targets_offered(s, 1)


@case(9320, "the spell Fizz replays may choose Fizz himself")
def _():
    need("Fizz - Trickster", "Discipline")
    s = fresh(hand=[T.id_of("Fizz - Trickster")], runes=12)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Discipline"), 1
    cast(s, 0, "Fizz - Trickster", base_loc(0))
    fz = perm_of(s, "Fizz - Trickster")[0]
    run(s, picks(pack_trash(0, T.id_of("Discipline")), fz))
    assert combat.might(s, T, fz) == 5


@case(9317, "Karthus dying beside a Deathknell unit still doubles it")
def _():
    need("Karthus - Eternal", "Soaring Scout", "Falling Star")
    s = fresh()
    rune_deck(s)
    ka = s.add_permanent(T.id_of("Karthus - Eternal"), 0, base_loc(0))
    sc = s.add_permanent(T.id_of("Soaring Scout"), 0, base_loc(0))
    before = runes(s, 0)
    # one resolution, both lethal: they die together in the Cleanup after it
    rsv.resolve(s, T, V1, SPECS["Falling Star"], 1, [ka, sc], -1, True)
    run(s)
    assert not alive(s, ka) and not alive(s, sc)
    assert runes(s, 0) == before + 2


@case(9314, "Glasc dying while conquering can't revive onto that battlefield")
def _():
    need("Glasc Mixologist", "Determined Sentry")
    s = fresh(runes=9)
    g = s.add_permanent(T.id_of("Glasc Mixologist"), 0, base_loc(0), ready=True)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Determined Sentry"), 1
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 6
    attack(s, 0, 0, g)
    combat.destroy(s, T, g)                  # the Hidden Blade
    seen = set()

    def pref(s, who, legal):
        seen.update(a.arg for a in legal if a.kind in (A.A_TARGET, A.A_PLAY_AT))
        return picking(pack_trash(0, T.id_of("Determined Sentry")), base_loc(0))(s, who, legal)
    run(s, pref)
    assert bf_loc(0) not in seen, seen


@case(9313, "Switcheroo cannot choose Ruin Runner")
def _():
    need("Switcheroo", "Ruin Runner")
    s = fresh(hand=[T.id_of("Switcheroo")], runes=9)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, bf_loc(0))
    assert "Switcheroo" not in hand_plays(s, 0), "the only other unit there is Ruin Runner"
    body(s, 1, bf_loc(0), 2)
    act(s, A.A_PLAY, hand_index(s, 0, "Switcheroo"), 0)
    assert rr not in targets_offered(s, 0)


@case(9310, "Fox-Fire chooses its units, so Ruin Runner is out")
def _():
    need("Fox-Fire", "Ruin Runner")
    s = fresh(hand=[T.id_of("Fox-Fire")], runes=9)
    s.bf_ctrl[1] = 1
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, bf_loc(0))
    small = body(s, 1, bf_loc(0), 2)
    act(s, A.A_PLAY, hand_index(s, 0, "Fox-Fire"), 0)
    off = targets_offered(s, 0)
    assert rr not in off and small in off, off


@case(9309, "Flash away from Hidden Blade: no kill, so no draw 2")
def _():
    need("Hidden Blade", "Flash")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=9)
    give(s, 1, "Flash")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Hidden Blade", foe)
    cast(s, 1, "Flash", foe, -1)
    run(s)
    assert alive(s, foe) and int(s.n_hand[1]) == 0


@case(9307, "Whirlwind chooses nothing: no Deflect to pay")
def _():
    need("Whirlwind", "Vex - Apathetic")
    s = fresh(hand=[T.id_of("Whirlwind")], runes=9)
    vx = s.add_permanent(T.id_of("Vex - Apathetic"), 1, base_loc(1))
    body(s, 0, base_loc(0), 3)
    before = runes(s, 0)
    cast(s, 0, "Whirlwind")
    run(s, picking(vx))
    assert runes(s, 0) == before - int(T.power[T.id_of("Whirlwind")])


@case(9303, "an opponent Riding the Wind into your conquest is the defender")
def _():
    need("Ride The Wind")
    s = fresh(runes=9)
    give(s, 1, "Ride The Wind")
    s.runes_ready[1, :] = 9
    give(s, 0, "Smoke Screen")
    a = body(s, 0, base_loc(0), 3, ready=True)
    foe = body(s, 1, base_loc(1), 3)
    attack(s, 0, 0, a)
    cast(s, 1, "Ride The Wind", foe, bf_loc(0))
    run(s, stop=lambda s: bool(s.showdown_combat))
    assert int(s.attacker) == 0


@case(9301, "Eager Apprentice discounts a spell paying [Repeat]")
def _():
    need("Eager Apprentice", "Upstage Comedy")
    s = fresh(hand=[T.id_of("Upstage Comedy")])
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Eager Apprentice"), 0, bf_loc(0))
    u = body(s, 0, base_loc(0), 3)
    s.runes_ready[0, :] = 0
    s.runes_ready[0, 0] = 3
    cast(s, 0, "Upstage Comedy", u, u, repeat=True)
    run(s)
    assert int(s.runes_ready[0].sum()) == 0


@case(9297, "a countered card is not played: Viktor, Innovator makes nothing")
def _():
    need("Viktor, Innovator", "Discipline", "Defy")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    s.add_permanent(T.id_of("Viktor, Innovator"), 0, base_loc(0))
    give(s, 0, "Discipline")
    give(s, 1, "Defy", "Stupefy")
    u = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Stupefy", theirs)
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert not tokens(s, 0)


@case(9296, "Wages of Pain answered by Retreat: still a Gold")
def _():
    need("Wages of Pain", "Retreat")
    from rl.tests.judge.cases_30 import _wages_with_target_gone
    _wages_with_target_gone(9296)


@case(9295, "Deathgrip needs a friendly unit to play")
def _():
    need("Deathgrip")
    s = fresh(hand=[T.id_of("Deathgrip")])
    body(s, 1, base_loc(1), 3)
    assert "Deathgrip" not in hand_plays(s, 0)


@case(9291, "Lonely Poro dying beside another unit is not alone")
def _():
    need("Lonely Poro", "Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=9)
    s.bf_ctrl[1] = 1
    lp = s.add_permanent(T.id_of("Lonely Poro"), 1, bf_loc(0))
    other = body(s, 1, bf_loc(0), 2)
    cast(s, 0, "Piercing Light", lp, other)
    run(s)
    assert not alive(s, lp) and not alive(s, other) and int(s.n_hand[1]) == 0


@case(9281, "Cull the Weak chooses nothing: The Dreaming Tree stays quiet")
def _():
    need("Cull the Weak", "The Dreaming Tree")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=9)
    s.bf_card[0] = T.id_of("The Dreaming Tree")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    body(s, 1, base_loc(1), 3)
    cast(s, 0, "Cull the Weak")
    run(s, picking(mine))
    assert int(s.n_hand[0]) == 0 and int(s.n_hand[1]) == 0


@case(9277, "Ride The Wind must move the unit somewhere else")
def _():
    need("Ride The Wind")
    s = fresh(hand=[T.id_of("Ride The Wind")], runes=9)
    u = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Ride The Wind"), 0)
    choose(s, u)
    assert base_loc(0) not in targets_offered(s, 0)


@case(9272, "Not So Fast cannot counter a Not So Fast")
def _():
    need("Not So Fast", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    give(s, 0, "Not So Fast")
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 9
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Discipline", theirs)
    cast(s, 1, "Not So Fast", top_uid(s))
    pass_priority_to(s, 0)
    assert "Not So Fast" not in hand_plays(s, 0)


@case(9268, "Defy reads Hidden Blade's printed cost, Deflect paid or not")
def _():
    need("Defy", "Hidden Blade", "Vex - Apathetic")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=9)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    vx = s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(0))
    cast(s, 0, "Hidden Blade", vx)
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1)


@case(9258, "a second unit at a battlefield you already conquered doesn't conquer")
def _():
    need("Plundering Poro", "Retreat")
    s = fresh(runes=9)
    give(s, 0, "Retreat")
    rune_deck(s)
    first = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, first)
    run(s, picking())
    assert int(s.bf_ctrl[0]) == 0 and int(s.points[0]) == 1
    cast(s, 0, "Retreat", first)
    run(s)
    pp = s.add_permanent(T.id_of("Plundering Poro"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, pp)
    run(s, picking())
    assert int(s.points[0]) == 1 and not tokens(s, 0), "scored once this turn already"


@case(9253, "Long Sword's Quick-Draw attaches without paying the Equip cost")
def _():
    need("Long Sword")
    s = fresh(hand=[T.id_of("Long Sword")])
    u = body(s, 0, base_loc(0), 3)
    dom = int(T.domain_mask[T.id_of("Long Sword")]).bit_length() - 1
    s.runes_ready[0, :] = 0
    s.runes_ready[0, dom] = 2
    cast(s, 0, "Long Sword", base_loc(0))
    choose(s, u)
    run(s)
    ls = perm_of(s, "Long Sword")
    assert ls and int(s.perms[ls[0], P_ATTACHED_TO]) == u


@case(9243, "Arcane Shift needs an enemy unit at a battlefield")
def _():
    need("Arcane Shift")
    s = fresh(hand=[T.id_of("Arcane Shift")], runes=9)
    body(s, 0, base_loc(0), 3)
    body(s, 1, base_loc(1), 3)
    assert "Arcane Shift" not in hand_plays(s, 0)


@case(9241, "Flash on two units at The Dreaming Tree draws once")
def _():
    need("Flash", "The Dreaming Tree")
    s = fresh(hand=[T.id_of("Flash")], runes=9)
    s.bf_card[0] = T.id_of("The Dreaming Tree")
    s.bf_ctrl[0] = 0
    a = body(s, 0, bf_loc(0), 3)
    b = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Flash", a, b)
    run(s)
    assert int(s.n_hand[0]) == 1


@case(9235, "Smoke Screen on a 1 Might unit, then Discipline: 3")
def _():
    need("Smoke Screen", "Discipline", "Watchful Sentry")
    s = fresh(hand=[T.id_of("Smoke Screen")], runes=9)
    give(s, 0, "Discipline")
    ws = s.add_permanent(T.id_of("Watchful Sentry"), 1, base_loc(1))
    cast(s, 0, "Smoke Screen", ws)
    run(s)
    cast(s, 0, "Discipline", ws)
    run(s)
    assert combat.might(s, T, ws) == 3, "the -4 snapshotted at -0 (477.3.b)"


@case(9234, "healing before Imperial Decree's kill resolves doesn't save the unit")
def _():
    need("Imperial Decree", "Bellows Breath")
    s = fresh(hand=[T.id_of("Imperial Decree")], runes=9)
    u = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Imperial Decree")
    run(s)
    rsv.resolve(s, T, V1, SPECS["Bellows Breath"], 0, [u, -1, -1], -1, True)
    s.perms[u, P_DMG] = 0                     # the heal, in answer
    run(s)
    assert not alive(s, u)


@case(9233, "Grand Strategem misses units played after it")
def _():
    need("Grand Strategem", "Determined Sentry")
    s = fresh(hand=[T.id_of("Grand Strategem")], runes=12)
    give(s, 0, "Determined Sentry")
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Grand Strategem")
    run(s)
    cast(s, 0, "Determined Sentry", base_loc(0))
    run(s)
    ds = perm_of(s, "Determined Sentry")[0]
    assert combat.might(s, T, u) == 8 and combat.might(s, T, ds) == 1


@case(9232, "Get Excited! discards on resolution, not on play")
def _():
    need("Get Excited!", "Discipline")
    s = fresh(hand=[T.id_of("Get Excited!")], runes=9)
    give(s, 0, "Discipline")
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Get Excited!", foe)
    assert int(s.n_hand[0]) == 1, "still in hand while the spell waits"
    run(s, picking(0))
    assert int(s.n_hand[0]) == 0 and int(s.perms[foe, P_DMG]) == 2


@case(9228, "a hidden Sprite Call in answer to a Sprite's Temporary keeps a Sprite")
def _():
    need("Sprite Call")
    s = fresh()
    old = _sprite_at(s, 0, 0)
    hidden_at(s, 0, 0, "Sprite Call")
    _next_own_turn(s)
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(bf_loc(0)))
    assert not alive(s, old) and len(tokens(s, 0)) == 1


@case(9221, "Baron Nashor scores his Baron Pit on the way in")
def _():
    need("Baron Nashor")
    s = fresh(hand=[T.id_of("Baron Nashor")], runes=12)
    cast(s, 0, "Baron Nashor", base_loc(0))
    run(s, picking())
    assert int(s.points[0]) == 1


@case(9216, "Piercing Light: moving the first target home doesn't stop the second")
def _():
    need("Piercing Light", "Flash")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=9)
    give(s, 1, "Flash")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    u1 = body(s, 1, bf_loc(0), 5)
    u2 = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Piercing Light", u1, u2)
    cast(s, 1, "Flash", u1, -1)
    run(s)
    assert int(s.perms[u1, P_DMG]) == 0 and int(s.perms[u2, P_DMG]) == 2


@case(9211, "Punch First can't answer Challenge: both are [Action]")
def _():
    need("Challenge", "Punch First")
    s = fresh(hand=[T.id_of("Challenge")], runes=9)
    give(s, 1, "Punch First")
    s.runes_ready[1, :] = 9
    a = body(s, 0, base_loc(0), 3)
    b = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Challenge", a, b)
    pass_priority_to(s, 1)
    assert "Punch First" not in hand_plays(s, 1)
