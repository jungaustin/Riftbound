"""RiftJudge batch 56 -- unused questions from 7867-7897."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7897, "the defender's trigger resolves before the attacker's")
def _():
    need("Volibear - Furious", "Ahri, Inquisitive")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    vb = s.add_permanent(T.id_of("Volibear - Furious"), 0, base_loc(0), ready=True)
    ah = s.add_permanent(T.id_of("Ahri, Inquisitive"), 1, bf_loc(0), ready=True)
    attack(s, 0, 0, vb)
    run(s, picking(ah, vb), limit=20,
        stop=lambda st: int(st.perms[ah, P_DMG]) >= 5)
    assert combat.might(s, T, vb) == 7, "her -2 landed first"
    assert int(s.perms[ah, P_DMG]) == 5


@case(7896, "both halves of Falling Star may name the same unit")
def _():
    need("Falling Star", "Noxus Hopeful")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    nh = s.add_permanent(T.id_of("Noxus Hopeful"), 1, base_loc(1), ready=True)
    cast(s, 0, "Falling Star", nh, nh)
    run(s)
    assert not alive(s, nh), "3 and 3 against 4 Might"


@case(7893, "a unit that changes controller never left the board")
def _():
    need("Possession", "Akshan - Mischievous", "B.F. Sword")
    s = fresh(runes=32)
    give(s, 1, "Akshan - Mischievous")
    s.runes_ready[1, :] = 32
    sword = s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    s.ply += 1
    s.active = s.priority = 1
    act(s, A.A_PLAY, hand_index(s, 1, "Akshan - Mischievous"), 1)
    act(s, A.A_PLAY_AT_FAST, base_loc(1), 1)
    run(s, picking(sword))
    ak = perm_of(s, "Akshan - Mischievous", 1)[0]
    assert int(s.perms[sword, P_CTRL]) == 1, "he took it"
    s.ply += 1
    s.active = s.priority = 0
    give(s, 0, "Possession")
    s.bf_ctrl[0] = 1
    s.set_location(ak, bf_loc(0))
    cast(s, 0, "Possession", ak)
    run(s)
    assert int(s.perms[ak, P_CTRL]) == 0, "you took him"
    assert int(s.perms[sword, P_CTRL]) == 1, "and he never left, so it stays"


@case(7886, "Flash in response empties the battlefield before the fight")
def _():
    need("Flash", "Dragon's Rage")
    s = fresh(hand=[T.id_of("Dragon's Rage")], runes=32)
    give(s, 1, "Flash")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = s.bf_ctrl[1] = 1
    mover = body(s, 1, bf_loc(0), 3)
    other = body(s, 1, bf_loc(1), 4)
    cast(s, 0, "Dragon's Rage", mover, bf_loc(1), other)
    cast(s, 1, "Flash", other, -1)
    run(s)
    assert alive(s, mover), "the unit it would have fought had gone home"
    assert int(s.perms[other, P_LOC]) == base_loc(1)


@case(7884, "Darius, Trifarian wants to BE the second card")
def _():
    need("Darius - Trifarian", "Discipline")
    s = fresh(hand=[T.id_of("Discipline"), T.id_of("Discipline"),
                    T.id_of("Darius - Trifarian")], runes=32)
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    run(s)
    cast(s, 0, "Discipline", u)
    run(s)
    act(s, A.A_PLAY, hand_index(s, 0, "Darius - Trifarian"), 0)
    choose(s, base_loc(0))
    run(s)
    dar = perm_of(s, "Darius - Trifarian", 0)[0]
    assert int(s.perms[dar, P_READY]) == 0, "he came down third"


@case(7883, "Sett's buff is base speed: not with a chain up")
def _():
    need("Sett, Brawler", "Discipline")
    s = fresh(runes=32)
    give(s, 0, "Discipline")
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    s.set_flag(sett, F_BUFFED)
    cast(s, 0, "Discipline", sett)
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE], "a chain is not an open state"


@case(7879, "a reaction drawn mid-chain can still answer that chain")
def _():
    need("Falling Star", "Hidden Blade", "Retreat")
    s = fresh(hand=[T.id_of("Falling Star")], runes=32)
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 3)
    b = body(s, 1, base_loc(1), 3)
    n = int(s.deck_ptr[1])
    s.deck[1, n:n + 2] = T.id_of("Retreat")
    slot = hidden_at(s, 1, 0, "Hidden Blade")
    cast(s, 0, "Falling Star", a, b)
    pass_priority_to(s, 1)
    act(s, A.A_PLAY_HIDDEN, slot, 1)
    choose(s, a)
    run(s, limit=20, stop=lambda st: not alive(st, a))
    assert not alive(s, a)
    pass_priority_to(s, 1)
    assert int(s.n_chain) >= 1, "Falling Star is still waiting"
    assert "Retreat" in hand_plays(s, 1), "drawn, and playable into that chain"


@case(7877, "a Recall is not a move, so Vilemaw's Lair does not stop it")
def _():
    need("Vilemaw's Lair", "Rune Prison")
    s = fresh(runes=32)
    give(s, 0, "Rune Prison")
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 1
    att = body(s, 0, base_loc(0), 3, ready=True)
    body(s, 1, bf_loc(0), 1)
    attack(s, 0, 0, att)
    cast(s, 0, "Rune Prison", att)
    fight(s)
    assert alive(s, att), "stunned, so it dealt nothing and took 1"
    assert int(s.perms[att, P_LOC]) == base_loc(0), "466.1.a.2 recalled it"


@case(7875, "[Deflect] is paid when the target is chosen, not at resolution")
def _():
    need("Void Seeker", "Draven - Audacious", "Discipline")
    s = fresh(hand=[T.id_of("Void Seeker")], runes=32)
    give(s, 1, "Discipline")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 1, bf_loc(0), ready=True)
    before = runes(s, 0)
    cast(s, 0, "Void Seeker", dr)
    assert before - runes(s, 0) == 2, "its own Power and the Deflect rune"
    cast(s, 1, "Discipline", dr)
    run(s)
    assert before - runes(s, 0) == 2, "answering changes nothing"


@case(7874, "Switcheroo resolves before the trigger it sets off")
def _():
    need("Switcheroo", "Darius - Trifarian")
    s = fresh(hand=[T.id_of("Switcheroo")], runes=32)
    s.bf_ctrl[0] = 0
    dar = s.add_permanent(T.id_of("Darius - Trifarian"), 0, bf_loc(0), ready=True)
    mate = body(s, 0, bf_loc(0), 2)
    cast(s, 0, "Switcheroo", dar, mate)
    run(s)
    assert combat.might(s, T, dar) == 2 and combat.might(s, T, mate) == 5


@case(7872, "0 Might alone does not kill")
def _():
    need("Frigid Touch")
    s = fresh(runes=32)
    give(s, 0, "Frigid Touch")
    u = body(s, 1, base_loc(1), 2)
    cast(s, 0, "Frigid Touch", u)
    run(s)
    assert alive(s, u) and combat.might(s, T, u) == 0


@case(7871, "Scrapheap discarded to a cost still draws")
def _():
    need("Scrapheap", "Traveling Merchant", "Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind", "Scrapheap")
    s.bf_ctrl[0] = 0
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, base_loc(0), ready=True)
    before = int(s.n_hand[0])
    cast(s, 0, "Ride The Wind", tm, bf_loc(0))
    run(s, picking(hand_index(s, 0, "Scrapheap") if "Scrapheap" in
                   {T.names[int(s.hand[0, j])] for j in range(int(s.n_hand[0]))}
                   else 0))
    assert int(s.n_hand[0]) >= before - 1, "discarded one, drew at least one"


@case(7870, "Ravenbloom Student's growth is a trigger, not a passive")
def _():
    need("Ravenbloom Student", "Stupefy", "Void Seeker")
    s = fresh(hand=[T.id_of("Void Seeker")], runes=32)
    give(s, 1, "Stupefy")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    rs = s.add_permanent(T.id_of("Ravenbloom Student"), 1, bf_loc(0), ready=True)
    cast(s, 0, "Void Seeker", rs)
    assert combat.might(s, T, rs) == 2, "nothing has resolved yet"
    run(s)
    assert not alive(s, rs), "4 damage against 2 Might"


@case(7869, "Darius, Executioner's +1 is on before anything can look")
def _():
    need("Darius - Executioner", "Fiora - Grand Duelist", "Determined Sentry")
    s = fresh(hand=[T.id_of("Determined Sentry")], runes=32)
    s.legend[0], s.legend_ready[0] = T.id_of("Fiora - Grand Duelist"), 1
    s.bf_ctrl[0] = 0
    de = s.add_permanent(T.id_of("Darius - Executioner"), 0, bf_loc(0), ready=True)
    act(s, A.A_PLAY, hand_index(s, 0, "Determined Sentry"), 0)
    choose(s, bf_loc(0))
    run(s, picking(accept=True), limit=20)
    ds = perm_of(s, "Determined Sentry", 0)[0]
    assert combat.might(s, T, ds) == 2, "1 printed plus his +1"
    assert de >= 0


@case(7868, "The Arena's Greatest pays a point at each player's first turn")
def _():
    need("The Arena's Greatest")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("The Arena's Greatest")
    _next_own_turn(s)
    run(s, limit=40)
    assert int(s.points[0]) == 1, "the start of your first Beginning Phase"


@case(7867, "an [Action] cannot get in front of a trigger already placed")
def _():
    need("Rebuke", "Yasuo - Remorseful")
    s = fresh(runes=32)
    give(s, 1, "Rebuke")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 12)
    attack(s, 0, 0, ya)
    choose(s, d)
    pass_priority_to(s, 1)
    assert "Rebuke" not in hand_plays(s, 1), "only a Reaction answers a trigger"
    drain(s)
    assert int(s.perms[d, P_DMG]) == 6


@case(7891, "Portal Rescue's replay lands the unit at its owner's base")
def _():
    need("Portal Rescue", "Thousand-Tailed Watcher")
    s = fresh(runes=32)
    give(s, 0, "Portal Rescue")
    s.bf_ctrl[0] = 0
    tw = s.add_permanent(T.id_of("Thousand-Tailed Watcher"), 0, bf_loc(0),
                         ready=True)
    foe = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Portal Rescue", tw)
    run(s, picking(accept=True), limit=40)
    back = perm_of(s, "Thousand-Tailed Watcher", 0)
    assert back and int(s.perms[back[0], P_LOC]) == base_loc(0)
    assert combat.might(s, T, foe) == 2, "and its play trigger ran again"
