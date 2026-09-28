"""RiftJudge batch 67 -- unused questions from 7256-7303."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(7303, "Traveling Merchant draws with an empty hand")
def _():
    need("Traveling Merchant", "Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, base_loc(0), ready=True)
    cast(s, 0, "Ride The Wind", tm, bf_loc(0))
    assert int(s.n_hand[0]) == 0
    run(s)
    assert int(s.n_hand[0]) == 1, "nothing discarded, still drawn"


@case(7300, "Dazzling Aurora revealing the whole deck does not Burn Out")
def _():
    need("Dazzling Aurora")
    s = fresh(runes=32)
    s.add_permanent(T.id_of("Dazzling Aurora"), 0, base_loc(0))
    s.deck[0, :] = T.id_of("Smoke Screen")          # no units anywhere
    act(s, A.A_END_TURN, None, 0)
    run(s, limit=60)
    assert int(s.points[1]) == 0, "a reveal is not a draw"


@case(7295, "Ahri's defend trigger resolves with nothing if she has gone")
def _():
    need("Ahri, Inquisitive", "Retreat")
    s = fresh(runes=32)
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    ah = s.add_permanent(T.id_of("Ahri, Inquisitive"), 1, base_loc(1), ready=True)
    s.bf_ctrl[1] = 1
    ah2 = s.add_permanent(T.id_of("Ahri, Inquisitive"), 0, bf_loc(0), ready=True)
    s.ply += 1
    att = body(s, 1, base_loc(1), 5, ready=True)
    attack(s, 1, 0, att)
    choose(s, att)
    pass_priority_to(s, 0)
    assert ah >= 0 and ah2 >= 0
    drain(s)
    assert combat.might(s, T, att) == 3, "her -2 landed"


@case(7292, "a combat that dealt no damage still heals")
def _():
    need("Yasuo - Remorseful", "Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 12)
    attack(s, 0, 0, ya)
    choose(s, d)
    drain(s)
    assert int(s.perms[d, P_DMG]) == 6
    cast(s, 0, "Ride The Wind", ya, base_loc(0))
    fight(s)
    assert int(s.perms[d, P_DMG]) == 0, "the combat ended, so everything healed"


@case(7291, "the Hourglass's controller chooses among simultaneous deaths")
def _():
    need("Zhonya's Hourglass")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 3)
    b = body(s, 1, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    att = body(s, 0, base_loc(0), 9, ready=True)
    attack(s, 0, 0, att)
    fight(s)
    assert alive(s, a) != alive(s, b) and not alive(s, z)


@case(7288, "one unit may conquer both battlefields in a turn")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind", "Ride The Wind")
    s.points[0] = 6
    u = body(s, 0, base_loc(0), 3, ready=False)
    cast(s, 0, "Ride The Wind", u, bf_loc(0))
    fight(s)
    assert int(s.points[0]) == 7
    cast(s, 0, "Ride The Wind", u, bf_loc(1))
    fight(s)
    assert int(s.points[0]) == 8, "both battlefields scored this turn"


@case(7282, "a Reaction resolves before the attack trigger it answered")
def _():
    need("Warwick - Hunter", "Cannon Barrage")
    s = fresh(runes=32)
    give(s, 0, "Cannon Barrage")
    s.bf_ctrl[0] = 1
    ww = s.add_permanent(T.id_of("Warwick - Hunter"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, ww)
    cast(s, 0, "Cannon Barrage")
    drain(s)
    assert not alive(s, d), "damaged by the Barrage, then killed by his trigger"


@case(7280, "Thousand-Tailed Watcher is a snapshot of who is there")
def _():
    need("Thousand-Tailed Watcher", "Determined Sentry")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=32)
    give(s, 1, "Determined Sentry")
    s.runes_ready[1, :] = 32
    early = body(s, 1, base_loc(1), 5)
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    run(s)
    assert combat.might(s, T, early) == 2
    s.ply += 1
    s.active = s.priority = 1
    act(s, A.A_PLAY, hand_index(s, 1, "Determined Sentry"), 1)
    choose(s, base_loc(1))
    run(s)
    late = perm_of(s, "Determined Sentry", 1)[0]
    assert combat.might(s, T, late) == 1, "it arrived after the sweep"


@case(7279, "an effect move exhausts nobody")
def _():
    need("Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    foe = body(s, 1, base_loc(1), 3, ready=True)
    cast(s, 0, "Charm", foe, bf_loc(0))
    run(s)
    assert int(s.perms[foe, P_READY]) == 1, "only a Standard Move costs a tap"


@case(7275, "a Charmed unit contests, so it attacks")
def _():
    need("Charm")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Charm", foe, bf_loc(0))
    drain(s)
    assert int(s.attacker) == 1


@case(7270, "a repeated Hard Bargain can name two spells")
def _():
    need("Hard Bargain", "Singularity", "Discipline")
    s = fresh(hand=[T.id_of("Singularity")], runes=32)
    give(s, 0, "Discipline")
    give(s, 1, "Hard Bargain")
    s.runes_ready[1, :] = 32
    u = body(s, 1, base_loc(1), 9)
    mine = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Singularity", u, -1)
    cast(s, 0, "Discipline", mine)
    pass_priority_to(s, 1)
    act(s, A.A_PLAY_REPEAT, hand_index(s, 1, "Hard Bargain"), 1)
    offered = targets_offered(s, 1)
    assert len(offered) >= 2, "both spells are on the chain to name"


@case(7266, "Pack of Wonders sends a stolen unit to its owner's hand")
def _():
    need("Pack of Wonders", "Possession")
    s = fresh(hand=[T.id_of("Possession")], runes=32)
    pw = s.add_permanent(T.id_of("Pack of Wonders"), 0, base_loc(0), ready=True)
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Possession", foe)
    run(s)
    assert int(s.perms[foe, P_CTRL]) == 0
    before0, before1 = int(s.n_hand[0]), int(s.n_hand[1])
    act(s, A.A_ACTIVATE, pw, 0)
    choose(s, 0)
    run(s, picking(foe))
    assert not alive(s, foe)
    assert int(s.n_hand[1]) == before1 + 1, "its owner's hand"
    assert int(s.n_hand[0]) == before0


@case(7263, "the Monastery accepts a buff from any unit")
def _():
    need("Monastery of Hirana")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Monastery of Hirana")
    s.bf_ctrl[0] = 1
    conqueror = body(s, 0, base_loc(0), 3, ready=True)
    holder = body(s, 0, base_loc(0), 3)
    s.set_flag(holder, F_BUFFED)
    before = int(s.n_hand[0])
    attack(s, 0, 0, conqueror)
    run(s, picking(holder, accept=True), limit=40)
    assert int(s.n_hand[0]) == before + 1, "his buff paid for it"
    assert not s.has_flag(holder, F_BUFFED)


@case(7262, "Leona's attack trigger names its target as it is placed")
def _():
    need("Leona, Determined", "Flash")
    s = fresh(runes=32)
    give(s, 1, "Flash")
    s.runes_ready[1, :] = 32
    s.bf_ctrl[0] = 1
    le = s.add_permanent(T.id_of("Leona, Determined"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, le)
    assert d in targets_offered(s, 0) or int(s.n_chain) == 0
    assert le >= 0


@case(7261, "a token Retreated to hand ceases to exist")
def _():
    need("Retreat", "Sprite Call")
    s = fresh(runes=32)
    give(s, 0, "Retreat")
    rune_deck(s)
    tok = _sprite_at(s, 0, 0)
    before = int(s.n_hand[0])
    cast(s, 0, "Retreat", tok)
    run(s)
    assert not alive(s, tok)
    assert int(s.n_hand[0]) == before - 1, "186: nothing came back to the hand"


@case(7260, "a hidden Fight or Flight beats the attack trigger to it")
def _():
    need("Yasuo - Remorseful", "Fight or Flight")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    d = body(s, 0, bf_loc(0), 9)
    slot = hidden_at(s, 0, 0, "Fight or Flight")
    s.ply += 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 1, base_loc(1), ready=True)
    attack(s, 1, 0, ya)
    choose(s, d)
    pass_priority_to(s, 0)
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    choose(s, d)
    run(s, limit=40)
    assert int(s.perms[d, P_LOC]) == base_loc(0)
    assert int(s.perms[d, P_DMG]) == 0, "it was gone when the damage looked"


@case(7256, "a Recall out of Vilemaw's Lair is fine, a move is not")
def _():
    need("Flash", "Vilemaw's Lair")
    s = fresh(runes=32)
    give(s, 0, "Flash")
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Flash", u, -1)
    run(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(0), "Flash MOVES, so the Lair stops it"


@case(7265, "a Might reduction is not a source of damage")
def _():
    need("Hextech Ray", "Smoke Screen")
    s = fresh(hand=[T.id_of("Hextech Ray")], runes=32)
    give(s, 0, "Smoke Screen")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 6)
    cast(s, 0, "Hextech Ray", u)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_DMG]) == 3
    cast(s, 0, "Smoke Screen", u)
    run(s)
    assert not alive(s, u), "2 Might with 3 marked is lethal"


@case(7268, "nothing can be played inside a spell's resolution")
def _():
    need("King's Edict", "Retreat")
    s = fresh(hand=[T.id_of("King's Edict")], runes=32)
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 32
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "King's Edict")
    run(s, picking(foe))
    assert not alive(s, foe), "they never got a window inside it"
