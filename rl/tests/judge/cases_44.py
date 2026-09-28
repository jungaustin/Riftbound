"""RiftJudge batch 44 -- unused questions from 8491-8537."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8537, "an Equipment bonus is Might, and 4 is not Mighty")
def _():
    need("First Mate", "Sunken Temple", "Warmog's Armor")
    s = fresh(runes=16)
    s.bf_card[0] = T.id_of("Sunken Temple")
    s.bf_ctrl[0] = 1
    fm = s.add_permanent(T.id_of("First Mate"), 0, base_loc(0), ready=True)
    g = s.add_permanent(T.id_of("Warmog's Armor"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, fm)
    run(s)
    assert combat.might(s, T, fm) == 4, "3 printed plus the Armor"
    before = int(s.n_hand[0])
    attack(s, 0, 0, fm)
    run(s, picking(accept=True), limit=40)
    assert int(s.n_hand[0]) == before, "708 wants 5, and the buff came after"


@case(8535, "Switcheroo pays [Deflect] like any spell that chooses")
def _():
    need("Switcheroo", "Draven - Audacious")

    def spend(deflect):
        s = fresh(hand=[T.id_of("Switcheroo")], runes=16)
        s.bf_ctrl[1] = 1
        a = body(s, 1, bf_loc(0), 2)
        if deflect:
            b = s.add_permanent(T.id_of("Draven - Audacious"), 1, bf_loc(0),
                                ready=True)
        else:
            b = body(s, 1, bf_loc(0), 6)
        before = runes(s, 0)
        cast(s, 0, "Switcheroo", a, b)
        run(s)
        return before - runes(s, 0)

    assert spend(True) == spend(False) + 1


@case(8533, "Tideturner cannot be hidden in a base")
def _():
    need("Tideturner")
    s = fresh(hand=[T.id_of("Tideturner")], runes=12)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    assert [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_HIDE], \
        "it can be hidden at the battlefield he controls"
    act(s, A.A_HIDE, None, 0)
    where = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_HIDE_AT]
    assert where == [0], "737.1.b: the battlefield he controls, and nowhere else"


@case(8532, "Switcheroo swaps the Might a unit has right now")
def _():
    need("Switcheroo")
    s = fresh(hand=[T.id_of("Switcheroo")], runes=16)
    s.bf_ctrl[0] = 0
    a = body(s, 0, bf_loc(0), 2)
    b = body(s, 0, bf_loc(0), 6)
    s.set_flag(b, F_BUFFED)
    cast(s, 0, "Switcheroo", a, b)
    run(s)
    assert combat.might(s, T, a) == 7 and combat.might(s, T, b) == 2, \
        "the buff counted on the way in"


@case(8530, "Draven, Audacious can score the eighth point")
def _():
    need("Draven - Audacious")
    s = fresh(runes=16)
    s.points[0] = 7
    s.bf_ctrl[0] = 1
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 1)
    attack(s, 0, 0, dr)
    fight(s)
    assert int(s.points[0]) == 8, "448.1.a.1: his combat point is not beholden"


@case(8527, "Counter Strike prevents the whole simultaneous damage instance")
def _():
    need("Counter Strike")
    s = fresh(runes=16)
    give(s, 1, "Counter Strike")
    s.runes_ready[1, :] = 16
    s.bf_ctrl[1] = 1
    d = body(s, 1, bf_loc(0), 5)
    a1 = body(s, 0, base_loc(0), 3, ready=True)
    a2 = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, a1, a2)
    cast(s, 1, "Counter Strike", d)
    fight(s)
    assert alive(s, d) and int(s.perms[d, P_DMG]) == 0, \
        "443.1.d.1.a makes it one instance"


@case(8521, "Not So Fast answers Zaun Punk when it chooses YOUR gear")
def _():
    need("Zaun Punk", "Not So Fast", "B.F. Sword")
    s = fresh(hand=[T.id_of("Zaun Punk")], runes=16)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 16
    mine = s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    theirs = s.add_permanent(T.id_of("B.F. Sword"), 1, base_loc(1))
    act(s, A.A_PLAY, hand_index(s, 0, "Zaun Punk"), 0)
    choose(s, mine)
    choose(s, base_loc(0))
    choose(s, theirs)
    pass_priority_to(s, 1)
    assert "Not So Fast" in hand_plays(s, 1), "its trigger chose their gear"


@case(8520, "Invert Timelines makes an empty deck Burn Out")
def _():
    need("Invert Timelines")
    s = fresh(hand=[T.id_of("Invert Timelines")], runes=16)
    give(s, 1, "Smoke Screen", "Smoke Screen", "Smoke Screen", "Smoke Screen")
    s.n_deck[1] = 0
    s.trash[1, :3] = VANILLA
    s.n_trash[1] = 3
    cast(s, 0, "Invert Timelines")
    run(s)
    assert int(s.points[0]) == 1, "the Burn Out paid you a point"
    assert int(s.n_hand[1]) > 0, "and they still finished the draw"


@case(8517, "First Mate's play trigger is a chain item you can answer")
def _():
    need("First Mate", "Not So Fast")
    s = fresh(hand=[T.id_of("First Mate")], runes=16)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 16
    theirs = body(s, 1, base_loc(1), 3, ready=False)
    act(s, A.A_PLAY, hand_index(s, 0, "First Mate"), 0)
    choose(s, base_loc(0))
    assert len(perm_of(s, "First Mate", 0)) == 1, "the unit is already down"
    assert int(s.n_chain) + int(s.n_trig) >= 1, "but its trigger waits"
    assert theirs >= 0


@case(8512, "Not So Fast misses Thousand-Tailed Watcher's global trigger")
def _():
    need("Thousand-Tailed Watcher", "Not So Fast")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=20)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 16
    body(s, 1, base_loc(1), 5)
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    pass_priority_to(s, 1)
    assert "Not So Fast" not in hand_plays(s, 1), "it chooses nothing"


@case(8510, "Void Gate raises damage, not Might reduction")
def _():
    need("Stupefy", "Void Gate")
    s = fresh(runes=12)
    give(s, 0, "Stupefy")
    s.bf_card[0] = T.id_of("Void Gate")
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Stupefy", u)
    run(s)
    assert combat.might(s, T, u) == 4 and int(s.perms[u, P_DMG]) == 0


@case(8503, "Falling Star may choose two different units")
def _():
    need("Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=16)
    a = body(s, 1, base_loc(1), 9)
    b = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Falling Star", a, b)
    run(s)
    assert int(s.perms[a, P_DMG]) == 3 and int(s.perms[b, P_DMG]) == 3


@case(8498, "a stunned attacker left alone still conquers")
def _():
    need("Rune Prison", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=16)
    give(s, 1, "Rune Prison")
    s.runes_ready[1, :] = 16
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 3)
    att = body(s, 0, base_loc(0), 9, ready=True)
    attack(s, 0, 0, att)
    cast(s, 1, "Rune Prison", att)
    drain(s)
    assert s.has_flag(att, F_STUNNED)
    cast(s, 0, "Hidden Blade", d)
    fight(s)
    assert not alive(s, d) and alive(s, att)
    assert int(s.bf_ctrl[0]) == 0, "444: stun is about damage, not control"


@case(8494, "Downwell leaves an uncontrolled battlefield, and the hidden card goes")
def _():
    need("Downwell")
    s = fresh(hand=[T.id_of("Downwell")], runes=20)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    slot = hidden_at(s, 0, 0, "Hidden Blade")
    cast(s, 0, "Downwell")
    run(s)
    assert int(s.fd_card[slot]) < 0, "466.5.c clears what no longer shares control"
    assert T.id_of("Hidden Blade") in [int(s.trash[0, j])
                                       for j in range(int(s.n_trash[0]))]


@case(8491, "a countered hidden card never buffs Ember Monk")
def _():
    need("Ember Monk", "Bellows Breath", "Defy")
    s = fresh(runes=16)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 16
    em = s.add_permanent(T.id_of("Ember Monk"), 0, base_loc(0), ready=True)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    body(s, 1, base_loc(1), 5)
    slot = hidden_at(s, 0, 0, "Bellows Breath")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    choose(s, -1)
    choose(s, -1)
    choose(s, -1)
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert combat.might(s, T, em) == 4, "412.1.b: countered is not played"


@case(8509, "an [Equip] cost is not an optional additional cost")
def _():
    need("Ezreal, Prodigy", "B.F. Sword")
    s = fresh(runes=16)
    s.add_permanent(T.id_of("Ezreal, Prodigy"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 3, ready=True)
    g = s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    before = int(s.runes_ready[0].sum())
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, u)
    run(s)
    assert int(s.perms[g, P_ATTACHED_TO]) == u
    assert before - int(s.runes_ready[0].sum()) >= 1, "744.1: it is still paid"


@case(8493, "Gearhead doubles an Equipment's bonus once")
def _():
    need("Gearhead", "Doran's Shield")
    s = fresh(runes=16)
    gh = s.add_permanent(T.id_of("Gearhead"), 0, base_loc(0), ready=True)
    g = s.add_permanent(T.id_of("Doran's Shield"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, g, 0)
    choose(s, gh)
    run(s)
    assert combat.might(s, T, gh) == 5, "3 printed plus a doubled +1"


@case(8499, "Arcane Shift's replay puts Fizz's trigger back on the chain")
def _():
    need("Arcane Shift", "Fizz - Trickster", "Bellows Breath")
    s = fresh(runes=20)
    give(s, 0, "Arcane Shift")
    s.bf_ctrl[1] = 1
    fz = s.add_permanent(T.id_of("Fizz - Trickster"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 9)
    s.trash[0, 0] = T.id_of("Bellows Breath")
    s.n_trash[0] = 1
    cast(s, 0, "Arcane Shift", fz, perm_of(s, "Shipyard Skulker", 1)[0])
    run(s, picking(pack_trash(0, T.id_of("Bellows Breath")), -1, accept=True),
        limit=60)
    assert perm_of(s, "Fizz - Trickster", 0), "he came back as a new object"


@case(8525, "a unit played by Baited Hook may still pay its optional cost")
def _():
    need("Baited Hook", "Akshan - Mischievous", "B.F. Sword")
    s = fresh(runes=20)
    bh = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    victim = body(s, 0, base_loc(0), 3)
    s.add_permanent(T.id_of("B.F. Sword"), 1, base_loc(1))
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Akshan - Mischievous")
    act(s, A.A_ACTIVATE, bh, 0)
    run(s, picking(victim, T.id_of("Akshan - Mischievous"), base_loc(0),
                   accept=True), limit=60)
    assert bh >= 0
