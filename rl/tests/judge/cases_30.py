"""RiftJudge batch 30 -- unused questions from 9437-9530."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_NO_MOVE, P_ATTACHED_TO
from rl.engine.effects import ABILITIES, pack_trash


@case(9530, "a hidden Wages of Pain cannot choose a Ruin Runner")
def _():
    need("Wages of Pain", "Ruin Runner")
    s = fresh(seat=1, runes=9)
    s.bf_ctrl[0] = 0
    hidden_at(s, 0, 0, "Wages of Pain")
    body(s, 0, bf_loc(0), 3)
    give(s, 0, "Smoke Screen")
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1), ready=True)
    other = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, rr, other)
    pass_priority_to(s, 0)
    act(s, A.A_PLAY_HIDDEN, None, 0)
    off = targets_offered(s, 0)
    assert rr not in off and other in off, off


def _wages_with_target_gone(qid):
    s = fresh(hand=[T.id_of("Wages of Pain")], runes=9)
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 9
    rune_deck(s)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Wages of Pain", foe)
    cast(s, 1, "Retreat", foe)
    run(s)
    assert not alive(s, foe)
    assert tokens(s, 0), f"#{qid}: the Gold is not tied to the target"


@case(9528, "Wages of Pain still makes its Gold after the target is saved")
def _():
    need("Wages of Pain", "Retreat")
    _wages_with_target_gone(9528)


@case(9472, "Wages of Pain answered by a return to hand: still a Gold")
def _():
    need("Wages of Pain", "Retreat")
    _wages_with_target_gone(9472)


@case(9522, "Zenith Blade into the opponent's showdown: they stay the attacker")
def _():
    need("Zenith Blade")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    give(s, 0, "Zenith Blade")
    give(s, 1, "Smoke Screen")
    foe = body(s, 1, base_loc(1), 3, ready=True)
    mine = body(s, 0, base_loc(0), 5)
    attack(s, 1, 0, foe)
    assert int(s.attacker) == 1
    pass_priority_to(s, 0)
    cast(s, 0, "Zenith Blade", foe)
    run(s, picks(mine), stop=lambda s: bool(s.showdown_combat))
    assert int(s.perms[mine, P_LOC]) == bf_loc(0) and int(s.attacker) == 1


@case(9520, "Counter Strike prevents combat damage")
def _():
    need("Counter Strike")
    s = fresh(hand=[T.id_of("Counter Strike")], runes=9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 6
    s.bf_ctrl[0] = 1
    a = body(s, 0, base_loc(0), 2, ready=True)
    d = body(s, 1, bf_loc(0), 3)
    attack(s, 0, 0, a)
    cast(s, 0, "Counter Strike", a)
    fight(s)
    assert alive(s, a) and alive(s, d), "no damage to the attacker; 2 is not 3"


@case(9521, "both sides surviving a combat: the attacker is recalled")
def _():
    need("Counter Strike")
    s = fresh(hand=[T.id_of("Counter Strike")], runes=9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 6
    s.bf_ctrl[0] = 1
    a = body(s, 0, base_loc(0), 2, ready=True)
    d = body(s, 1, bf_loc(0), 3)
    attack(s, 0, 0, a)
    cast(s, 0, "Counter Strike", a)
    fight(s)
    assert int(s.perms[a, P_LOC]) == base_loc(0) and int(s.perms[d, P_LOC]) == bf_loc(0)
    assert int(s.bf_ctrl[0]) == 1


@case(9516, "Crescent Strike's 1 reaches a unit that can't be chosen")
def _():
    need("Crescent Strike", "Ruin Runner")
    s = fresh(hand=[T.id_of("Crescent Strike")], runes=9)
    s.bf_ctrl[1] = 1
    main = body(s, 1, bf_loc(0), 9)
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, bf_loc(0))
    cast(s, 0, "Crescent Strike", bf_loc(0), main)
    run(s)
    assert int(s.perms[rr, P_DMG]) == 1


@case(9515, "Sacrifice's kill is paid before anyone can answer")
def _():
    need("Sacrifice", "Stupefy")
    s = fresh(hand=[T.id_of("Sacrifice")], runes=9)
    give(s, 1, "Stupefy")
    s.runes_ready[1, :] = 9
    rune_deck(s)
    u = body(s, 0, base_loc(0), 5)
    cast(s, 0, "Sacrifice", u)
    assert not alive(s, u), "gone before the opponent has priority"


@case(9513, "Charm cannot take a unit from Vilemaw's Lair to base")
def _():
    need("Charm", "Vilemaw's Lair")
    s = fresh(hand=[T.id_of("Charm")], runes=9)
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Charm"), 0)
    choose(s, foe)
    off = targets_offered(s, 0)
    if base_loc(1) in off:
        choose(s, base_loc(1))
        run(s)
    assert int(s.perms[foe, P_LOC]) == bf_loc(0)


@case(9511, "Relentless Pursuit's move does not heal")
def _():
    need("Relentless Pursuit")
    s = fresh(hand=[T.id_of("Relentless Pursuit")], runes=9)
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 5)
    s.perms[u, P_DMG] = 2
    cast(s, 0, "Relentless Pursuit", u, bf_loc(1))
    run(s, picking(accept=False))
    assert int(s.perms[u, P_LOC]) == bf_loc(1) and int(s.perms[u, P_DMG]) == 2


@case(9508, "Not So Fast cannot answer Heedless Resurrection")
def _():
    need("Heedless Resurrection", "Not So Fast", "Determined Sentry")
    s = fresh(hand=[T.id_of("Heedless Resurrection")], runes=9)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 9
    body(s, 1, base_loc(1), 3)
    k = body(s, 0, base_loc(0), 3)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Determined Sentry"), 1
    cast(s, 0, "Heedless Resurrection", k, pack_trash(0, T.id_of("Determined Sentry")),
         base_loc(0))
    pass_priority_to(s, 1)
    assert "Not So Fast" not in hand_plays(s, 1)


@case(9506, "Stupefy still draws when its target has gone")
def _():
    need("Stupefy", "Retreat")
    s = fresh(hand=[T.id_of("Stupefy")], runes=9)
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 9
    rune_deck(s)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Stupefy", foe)
    cast(s, 1, "Retreat", foe)
    run(s)
    assert int(s.n_hand[0]) == 1


@case(9496, "Ride The Wind chooses Irelia, Fervent: +1")
def _():
    need("Ride The Wind", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("Ride The Wind")], runes=9)
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0))
    cast(s, 0, "Ride The Wind", ir, bf_loc(0))
    run(s, picking())
    assert combat.might(s, T, ir) == 5


@case(9494, "Hostile Takeover's end-of-turn recall ignores Vilemaw's Lair")
def _():
    need("Hostile Takeover", "Vilemaw's Lair")
    s = fresh(hand=[T.id_of("Hostile Takeover")], runes=9)
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Hostile Takeover", foe)
    run(s, picking())
    assert int(s.perms[foe, P_CTRL]) == 0
    act(s, A.A_END_TURN, None, 0)
    run(s, picking())
    f = [i for i in range(s.n_perms) if alive(s, i)
         and int(s.perms[i, P_CARD]) == VANILLA and int(s.perms[i, P_CTRL]) == 1]
    assert f and int(s.perms[f[0], P_LOC]) == base_loc(1), "a recall is not a move"


@case(9493, "Shield from Taric adds to Stalwart Poro's own")
def _():
    need("Stalwart Poro", "Taric - Protector")
    s = fresh(seat=1)
    s.bf_ctrl[0] = 0
    sp = s.add_permanent(T.id_of("Stalwart Poro"), 0, bf_loc(0))
    s.add_permanent(T.id_of("Taric - Protector"), 0, bf_loc(0))
    give(s, 0, "Smoke Screen")
    s.runes_ready[0, :] = 6
    a = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, a)
    run(s, stop=lambda s: bool(s.showdown_combat))
    assert combat.might(s, T, sp) == 4, "2 + Shield 1 + Shield 1"


@case(9491, "Eclipse alone does not kill an undamaged 4 Might unit")
def _():
    need("Eclipse")
    s = fresh(hand=[T.id_of("Eclipse")], runes=9)
    u = body(s, 1, base_loc(1), 4)
    cast(s, 0, "Eclipse", u)
    run(s, picking(accept=False))
    assert alive(s, u)


@case(9488, "Alpha Strike is fine with a single enemy unit")
def _():
    need("Alpha Strike")
    s = fresh(hand=[T.id_of("Alpha Strike")], runes=9)
    u = body(s, 0, base_loc(0), 4)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(1), 9)
    cast(s, 0, "Alpha Strike", u)
    run(s, picking(foe))
    assert int(s.perms[foe, P_DMG]) == 4


@case(9471, "Dunebreaker checks the hand as it enters")
def _():
    need("Dunebreaker")
    s = fresh(hand=[T.id_of("Dunebreaker")], runes=12)
    give(s, 0, "Discipline", "Discipline")
    cast(s, 0, "Dunebreaker", base_loc(0))
    run(s)
    db = perm_of(s, "Dunebreaker")
    assert db and int(s.perms[db[0], P_READY]) == 1, "two cards left in hand"


@case(9464, "Defy can counter a repeated Piercing Light")
def _():
    need("Defy", "Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=12)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Piercing Light", foe, -1, foe, -1, repeat=True)
    pass_priority_to(s, 1)
    assert "Defy" in hand_plays(s, 1)


@case(9463, "a Defied spell still counts for [Legion]")
def _():
    need("Defy", "Discipline", "Noxus Hopeful")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    give(s, 0, "Noxus Hopeful")
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    s.runes_ready[0, :] = 0
    s.runes_ready[0, 0] = 2
    assert "Noxus Hopeful" in hand_plays(s, 0), "4 - 2 with Legion on"


@case(9446, "Iron Ballista cannot choose Baron Nashor")
def _():
    need("Iron Ballista", "Baron Nashor")
    s = fresh()
    ib = s.add_permanent(T.id_of("Iron Ballista"), 0, base_loc(0))
    s.bf_ctrl[1] = 1
    bn = s.add_permanent(T.id_of("Baron Nashor"), 1, bf_loc(1))
    body(s, 1, bf_loc(1), 3)
    act(s, A.A_ACTIVATE, ib, 0)
    assert bn not in targets_offered(s, 0)


@case(9445, "Wallop with a spent buff costs no Energy")
def _():
    need("Wallop")
    s = fresh(hand=[T.id_of("Wallop")])
    s.runes_ready[0, :] = 0
    u = body(s, 0, base_loc(0), 3)
    s.set_flag(u, F_BUFFED)
    assert "Wallop" in hand_plays(s, 0)


@case(9443, "an Ambush to Star Spring may send your other unit home")
def _():
    need("Star Spring", "Vi - Peacekeeper")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    s.bf_card[0] = T.id_of("Star Spring")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    give(s, 0, "Vi - Peacekeeper")
    give(s, 1, "Smoke Screen")
    a = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, a)
    cast(s, 0, "Vi - Peacekeeper", bf_loc(0))
    run(s, picking(mine), stop=lambda s: int(s.perms[mine, P_LOC]) == base_loc(0))
    assert int(s.perms[mine, P_LOC]) == base_loc(0)


@case(9437, "Eager Apprentice's discount applies to the total with [Repeat]")
def _():
    need("Eager Apprentice", "Upstage Comedy")
    s = fresh(hand=[T.id_of("Upstage Comedy")])
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Eager Apprentice"), 0, bf_loc(0))
    u = body(s, 0, base_loc(0), 3)
    s.runes_ready[0, :] = 0
    s.runes_ready[0, 0] = 3
    kinds_now = {a.kind for a in A.legal_actions(s, T, V1, 0)}
    assert A.A_PLAY_REPEAT in kinds_now, "2 + 2 - 1 = 3"
