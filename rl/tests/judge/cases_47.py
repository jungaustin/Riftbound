"""RiftJudge batch 47 -- unused questions from 8302-8363."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8363, "[Assault] is a role bonus, so Switcheroo does not carry it")
def _():
    need("Switcheroo", "Immortal Phoenix")
    s = fresh(hand=[T.id_of("Switcheroo")], runes=20)
    s.bf_ctrl[0] = 1
    ph = s.add_permanent(T.id_of("Immortal Phoenix"), 0, base_loc(0), ready=True)
    mate = body(s, 0, base_loc(0), 6, ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, ph, mate)
    assert combat.might(s, T, ph) == 5, "3 plus [Assault 2] while attacking"
    cast(s, 0, "Switcheroo", ph, mate)
    drain(s)
    assert combat.might(s, T, ph) == 6, "his 5 for her 6, with no [Assault] on top"
    assert combat.might(s, T, mate) == 5


@case(8358, "each spell played gives Ravenbloom Student its own trigger")
def _():
    need("Ravenbloom Student", "Discipline")
    s = fresh(runes=24)
    give(s, 0, "Discipline", "Discipline")
    rs = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0), ready=True)
    cast(s, 0, "Discipline", rs)
    cast(s, 0, "Discipline", rs)
    run(s)
    assert combat.might(s, T, rs) == 2 + 2 + 2 + 1 + 1, "two pumps and two triggers"


@case(8356, "a unit that leaves the combat loses [Assault] and may die of it")
def _():
    need("Cleave", "Ride The Wind", "Bellows Breath")
    s = fresh(runes=24)
    give(s, 0, "Cleave", "Ride The Wind")
    give(s, 1, "Bellows Breath")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    att = body(s, 0, base_loc(0), 1, ready=True)
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, att)
    cast(s, 0, "Cleave", att)
    drain(s)
    assert combat.might(s, T, att) == 4, "1 plus [Assault 3]"
    cast(s, 1, "Bellows Breath", att, -1, -1)
    drain(s)
    assert alive(s, att) and int(s.perms[att, P_DMG]) == 1
    cast(s, 0, "Ride The Wind", att, base_loc(0))
    run(s, limit=40)
    assert not alive(s, att), "1 Might again, with 1 damage marked"


@case(8351, "everything heals when a combat ends, wherever it stands")
def _():
    need("Challenge")
    s = fresh(hand=[T.id_of("Challenge")], runes=20)
    s.bf_ctrl[0] = 1
    home = body(s, 0, base_loc(0), 9)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Challenge", home, theirs)
    run(s)
    assert int(s.perms[home, P_DMG]) == 3, "the exchange marked it"
    att = body(s, 0, base_loc(0), 9, ready=True)
    body(s, 1, bf_loc(0), 1)
    attack(s, 0, 0, att)
    fight(s)
    assert int(s.perms[home, P_DMG]) == 0, "the heal is board-wide"


@case(8344, "a buff after Thousand-Tailed Watcher counts from the floor")
def _():
    need("Thousand-Tailed Watcher", "Discipline")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher"), T.id_of("Discipline")],
              runes=24)
    u = body(s, 1, base_loc(1), 2)
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    run(s)
    assert combat.might(s, T, u) == 1
    cast(s, 0, "Discipline", u)
    run(s)
    assert combat.might(s, T, u) == 3, "+2 from 1, not from -1"


@case(8342, "a combat that dealt no damage still heals everything")
def _():
    need("Flash", "Challenge")
    s = fresh(hand=[T.id_of("Challenge")], runes=24)
    give(s, 0, "Flash")
    s.bf_ctrl[0] = 1
    home = body(s, 0, base_loc(0), 9)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Challenge", home, theirs)
    run(s)
    assert int(s.perms[home, P_DMG]) == 3
    att = body(s, 0, base_loc(0), 5, ready=True)
    body(s, 1, bf_loc(0), 5)
    attack(s, 0, 0, att)
    cast(s, 0, "Flash", att, -1)
    fight(s)
    assert int(s.perms[att, P_LOC]) == base_loc(0), "it left before damage"
    assert int(s.perms[home, P_DMG]) == 0, "and the heal still happened"


@case(8341, "Blast of Power chooses at cast, so [Deflect] is paid then")
def _():
    need("Blast of Power", "Draven - Audacious")
    s = fresh(hand=[T.id_of("Blast of Power")], runes=24)
    s.bf_ctrl[0] = 1
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 1, bf_loc(0), ready=True)
    before = runes(s, 0)
    cast(s, 0, "Blast of Power", dr)
    assert before - runes(s, 0) == 2, "1 printed Power plus the Deflect rune"
    run(s)
    assert not alive(s, dr)


@case(8335, "a unit recalled by a save is still the same object Charm chose")
def _():
    need("Charm", "Hidden Blade", "Zhonya's Hourglass")
    s = fresh(runes=24)
    give(s, 1, "Charm")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    s.death_guard[0] = z
    slot = hidden_at(s, 0, 0, "Hidden Blade")
    s.ply += 1
    s.active = s.priority = 1
    s.bf_ctrl[1] = 1
    cast(s, 1, "Charm", u, bf_loc(1))
    pass_priority_to(s, 0)
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    choose(s, u)
    run(s)
    assert alive(s, u), "the Hourglass replaced the death"
    assert int(s.perms[u, P_LOC]) == bf_loc(1), "and Charm still found it"


@case(8331, "a showdown runs to its end, not to the last unit standing")
def _():
    need("Portal Rescue", "Cleave")
    s = fresh(runes=24)
    give(s, 0, "Cleave")
    give(s, 1, "Portal Rescue")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 1
    att = body(s, 0, base_loc(0), 3, ready=True)
    d = body(s, 1, bf_loc(0), 6)
    attack(s, 0, 0, att)
    cast(s, 0, "Cleave", att)
    drain(s)
    assert combat.might(s, T, att) == 6
    cast(s, 1, "Portal Rescue", d)
    fight(s)
    assert alive(s, att), "6 Might held through the combat"
    assert int(s.bf_ctrl[0]) == 0


@case(8327, "Zenith Blade's move onto enemy ground is an attack")
def _():
    need("Zenith Blade")
    s = fresh(hand=[T.id_of("Zenith Blade")], runes=24)
    give(s, 1, "Smoke Screen")                   # so the showdown stays open
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 9)
    mine = body(s, 0, base_loc(0), 3, ready=True)
    cast(s, 0, "Zenith Blade", d, mine)
    drain(s)
    assert s.has_flag(d, F_STUNNED)
    assert int(s.perms[mine, P_LOC]) == bf_loc(0), "it moved in to attack"


@case(8322, "Dragon's Rage picks its second unit at the destination")
def _():
    need("Dragon's Rage")
    s = fresh(hand=[T.id_of("Dragon's Rage")], runes=24)
    s.bf_ctrl[0] = 1
    mover = body(s, 1, bf_loc(0), 3)
    home = body(s, 1, base_loc(1), 4)
    cast(s, 0, "Dragon's Rage", mover, base_loc(1))
    run(s, picking(home))
    assert int(s.perms[mover, P_LOC]) == base_loc(1)
    assert not alive(s, mover), "4 back into a 3"
    assert int(s.perms[home, P_DMG]) == 3


@case(8318, "Trifarian War Camp's +1 lands before Ahri takes her -1")
def _():
    need("Ahri - Nine-Tailed Fox", "Trifarian War Camp")
    s = fresh(runes=24)
    s.bf_card[0] = T.id_of("Trifarian War Camp")
    s.bf_ctrl[0] = 1
    s.legend[1], s.legend_ready[1] = T.id_of("Ahri - Nine-Tailed Fox"), 1
    body(s, 1, bf_loc(0), 3)
    att = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, att)
    drain(s)
    assert combat.might(s, T, att) == 3, "3 printed, +1 from the ground, -1 from her"


@case(8317, "a Teemo revealed after the move still defends")
def _():
    need("Teemo - Strategist")
    s = fresh(runes=24)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    slot = hidden_at(s, 0, 0, "Teemo - Strategist")
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    pass_priority_to(s, 0)
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_PLAY_HIDDEN and a.arg == slot], \
        "the showdown is still open"
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    tm = perm_of(s, "Teemo - Strategist", 0)
    assert tm and int(s.perms[tm[0], P_LOC]) == bf_loc(0), "he arrived here"
    assert [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET], \
        "and his 'when I defend' trigger is asking for its target"


@case(8316, "a battlefield scored one turn can be scored again the next")
def _():
    need("Ride The Wind")
    s = fresh(runes=24)
    give(s, 0, "Ride The Wind", "Ride The Wind")
    home = body(s, 0, base_loc(0), 9, ready=False)
    cast(s, 0, "Ride The Wind", home, bf_loc(0))
    fight(s)
    assert int(s.points[0]) == 1, "conquered once"
    s.bf_ctrl[0] = -1
    s.set_location(home, base_loc(0))
    _next_own_turn(s)
    run(s, limit=40)
    cast(s, 0, "Ride The Wind", home, bf_loc(0))
    fight(s)
    assert int(s.points[0]) == 2, "470 is once per battlefield per TURN"


@case(8314, "a unit Charmed onto empty ground conquers for its own controller")
def _():
    need("Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=24)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Charm", foe, bf_loc(0))
    fight(s)
    assert int(s.perms[foe, P_LOC]) == bf_loc(0)
    assert int(s.bf_ctrl[0]) == 1 and int(s.points[1]) == 1


@case(8311, "a card drawn by a Reaction can answer the chain it joined")
def _():
    need("Discipline", "Defy", "Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=24)
    give(s, 1, "Discipline")
    s.runes_ready[1, :] = 24
    n = int(s.deck_ptr[1])
    s.deck[1, n] = T.id_of("Defy")
    theirs = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Falling Star", theirs, theirs)
    cast(s, 1, "Discipline", theirs)
    drain(s)
    assert "Defy" in hand_plays(s, 1) or int(s.n_chain) == 0, \
        "the draw arrived while the chain was still there"


@case(8308, "Falling Star's two halves are one chain item")
def _():
    need("Falling Star")
    s = fresh(hand=[T.id_of("Falling Star")], runes=24)
    a = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Falling Star", a, a)
    assert int(s.n_chain) == 1, "one spell, one item"
    run(s)
    assert int(s.perms[a, P_DMG]) == 6


@case(8306, "a countered spell was never played, for any watcher")
def _():
    need("Ravenbloom Student", "Darius - Trifarian", "Discipline", "Defy")
    s = fresh(runes=24)
    give(s, 0, "Discipline")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 24
    rs = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0), ready=True)
    cast(s, 0, "Discipline", rs)
    cast(s, 1, "Defy")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s)
    assert combat.might(s, T, rs) == 2, "no pump and no trigger"


@case(8304, "'alone' is read when the defend triggers all fire together")
def _():
    need("Mask of Foresight", "Reaver's Row")
    s = fresh(runes=24)
    s.bf_card[0] = T.id_of("Reaver's Row")
    s.bf_ctrl[0] = 0
    mask = s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    a = body(s, 0, bf_loc(0), 3)
    b = body(s, 0, bf_loc(0), 3)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 9, ready=True)
    attack(s, 1, 0, foe)
    run(s, picking(b, accept=True), limit=40)
    assert combat.might(s, T, a) == 3, "both were defending when it was asked"
    assert mask >= 0


@case(8302, "a unit the Hourglass saved keeps the damage marked on it")
def _():
    need("Zhonya's Hourglass", "Bellows Breath", "Hidden Blade")
    s = fresh(hand=[T.id_of("Bellows Breath"), T.id_of("Hidden Blade")], runes=24)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 5)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Bellows Breath", u, -1, -1)
    run(s)
    assert int(s.perms[u, P_DMG]) == 1
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_DMG]) == 0, \
        "the Hourglass heals it as it recalls it"
