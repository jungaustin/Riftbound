"""RiftJudge batch 73 -- unused questions from 6920-6983."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_MIGHT_MOD
from rl.engine.effects import pack_trash


@case(6983, "Mask of Foresight's +1 stays once the unit is no longer alone")
def _():
    need("Mask of Foresight", "Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    s.bf_ctrl[0] = 0
    lone = body(s, 0, bf_loc(0), 3)
    friend = body(s, 0, base_loc(0), 3)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    drain(s)
    assert combat.might(s, T, lone) == 4, "it defended alone"
    cast(s, 0, "Ride The Wind", friend, bf_loc(0))
    drain(s)
    assert int(s.perms[friend, P_LOC]) == bf_loc(0), "company arrived"
    assert combat.might(s, T, lone) == 4, "'when' fired once; it is not a static"


@case(6981, "Dragon's Rage moves an enemy anywhere, and does not exhaust it")
def _():
    need("Dragon's Rage")
    s = fresh(hand=[T.id_of("Dragon's Rage")], runes=32)
    s.bf_ctrl[0] = 1
    s.bf_ctrl[1] = 1
    mover = s.add_permanent(VANILLA, 1, bf_loc(0), ready=True)
    s.base_might_ply[mover], s.base_might_val[mover] = int(s.ply), 4
    target = body(s, 1, bf_loc(1), 4)
    act(s, A.A_PLAY, hand_index(s, 0, "Dragon's Rage"), 0)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert mover in offered
    choose(s, mover)
    dests = {a.arg for a in A.legal_actions(s, T, V1, 0)
             if a.kind in _CHOICE_KINDS}
    assert bf_loc(1) in dests and base_loc(1) in dests, \
        "449.1: any location but the one it stands on"
    choose(s, bf_loc(1))
    run(s, picking(target, accept=True), limit=40)
    assert not alive(s, mover) and not alive(s, target), "4 into 4, both ways"
    assert int(s.perms[mover, P_READY]) == 1, "452: an effect move never exhausts"


@case(6955, "Salvage is playable with no gear in the game at all")
def _():
    need("Salvage")
    s = fresh(hand=[T.id_of("Salvage")], runes=32)
    before = int(s.n_hand[0])
    cast(s, 0, "Salvage", -1)
    run(s, limit=30)
    assert int(s.n_hand[0]) == before, "-1 for Salvage, +1 for its draw"


@case(6978, "a Retreat whose unit is already gone channels nothing")
def _():
    need("Retreat", "Gust")
    s = fresh(hand=[T.id_of("Retreat")], runes=32)
    rune_deck(s)
    give(s, 1, "Gust")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Retreat", u)
    left = int(s.rune_left[0])
    cast(s, 1, "Gust", u)
    run(s, limit=40)
    assert not alive(s, u), "Gust resolved first and took it to hand"
    assert int(s.rune_left[0]) == left, "359.3.e: no unit, so no owner to channel"


@case(6930, "two Retreats on one unit channel one rune")
def _():
    need("Retreat")
    s = fresh(runes=32)
    rune_deck(s)
    give(s, 0, "Retreat", "Retreat")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    left = int(s.rune_left[0])
    cast(s, 0, "Retreat", u)
    cast(s, 0, "Retreat", u)
    run(s, limit=40)
    assert not alive(s, u)
    assert left - int(s.rune_left[0]) == 1, "the second one had nothing to return"


@case(6974, "three Rockets are three discards, and Jinx counts each")
def _():
    need("Jinx - Rebel", "Super Mega Death Rocket!")
    s = fresh(runes=32)
    give(s, 0, "Cleave", "Cleave", "Cleave")
    rocket = T.id_of("Super Mega Death Rocket!")
    s.trash[0, 0] = s.trash[0, 1] = s.trash[0, 2] = rocket
    s.n_trash[0] = 3
    jinx = s.add_permanent(T.id_of("Jinx - Rebel"), 0, base_loc(0))
    s.bf_ctrl[0] = -1
    taker = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, taker)
    run(s, picking(accept=True), limit=80)
    assert int(s.bf_ctrl[0]) == 0, "conquered"
    assert list(s.hand[0, :int(s.n_hand[0])]).count(rocket) == 3, \
        "383.3.d: three triggers, each resolving on its own"
    assert combat.might(s, T, jinx) == 8, "+1 Might per discard event"


@case(6973, "a free play ignores the cost, not [Accelerate]")
def _():
    need("Baited Hook", "Legion Rearguard")
    s = fresh(runes=32)
    s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0))
    bait = body(s, 0, base_loc(0), 1)
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Legion Rearguard")     # 2 Might: 1 more than the bait
    before = runes(s, 0)
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, bait)
    run(s, limit=20, stop=lambda st: int(st.pend_look) >= 0)
    choose(s, 0)
    opts = A.legal_actions(s, T, V1, 0)
    assert any(a.kind == A.A_PLAY_AT_FAST for a in opts), \
        "820.1: an OPTIONAL additional cost is still there to pay"
    act(s, A.A_PLAY_AT_FAST, base_loc(0), 0)
    run(s, limit=40)
    rg = perm_of(s, "Legion Rearguard", 0)[0]
    assert int(s.perms[rg, P_READY]) == 1, "paying it is what buys the readiness"
    assert before - runes(s, 0) == 2, "the Hook's rune, and [Accelerate]'s"


@case(6968, "a play with no trigger opens no window to react in")
def _():
    need("Gust", "First Mate")

    def window(card):
        s = fresh(runes=32)
        give(s, 0, "Gust")
        rune_deck(s)
        give(s, 1, card)
        body(s, 1, base_loc(1), 3)                # something for a trigger
        s.bf_ctrl[0] = 1
        body(s, 1, bf_loc(0), 3)                  # and something for the Gust
        s.ply += 1
        s.active = s.priority = 1
        act(s, A.A_PLAY, hand_index(s, 1, card), 1)
        choose(s, base_loc(1))
        seen = [False]

        def pref(st, who, legal):
            if who == 0:
                seen[0] = True
            return None
        run(s, pref, limit=20)
        return seen[0]

    assert not window(T.names[VANILLA]), "349: playing a unit is not a Chain item"
    assert window("First Mate"), "but the trigger it fires is"


@case(6966, "Imperial Decree kills a unit that arrived after it")
def _():
    need("Imperial Decree", "Bellows Breath")
    s = fresh(runes=32)
    give(s, 0, "Imperial Decree", "Bellows Breath")
    s.bf_ctrl[0] = 1
    cast(s, 0, "Imperial Decree")
    run(s, limit=30)
    late = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Bellows Breath", late, -1, -1)
    run(s, limit=40)
    assert not alive(s, late), "1 damage is enough while the Decree stands"


@case(6963, "En Garde cannot save a unit from a spell played after it")
def _():
    need("En Garde", "Cannon Barrage")
    s = fresh(runes=32)
    give(s, 0, "En Garde")
    give(s, 1, "Cannon Barrage")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    small = body(s, 0, base_loc(0), 2, ready=True)
    big = body(s, 0, base_loc(0), 9, ready=True)
    attack(s, 0, 0, small, big)
    cast(s, 0, "En Garde", small)
    cast(s, 1, "Cannon Barrage")
    run(s, limit=40)
    assert not alive(s, small), "the 2 resolved first, at 2 Might"


@case(6959, "Hextech Ray deals nothing to a unit Flashed home")
def _():
    need("Hextech Ray", "Flash")
    s = fresh(runes=32)
    give(s, 1, "Hextech Ray")
    give(s, 0, "Flash")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 9)
    s.ply += 1
    s.active = s.priority = 1
    cast(s, 1, "Hextech Ray", u)
    cast(s, 0, "Flash", u, -1)
    run(s, limit=40)
    assert int(s.perms[u, P_LOC]) == base_loc(0)
    assert int(s.perms[u, P_DMG]) == 0, "'a unit at a battlefield' was not there"


@case(6958, "Stupefy on a 1 Might unit still draws")
def _():
    need("Stupefy")
    s = fresh(hand=[T.id_of("Stupefy")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 1)
    cast(s, 0, "Stupefy", u)
    before = int(s.n_hand[0])
    run(s, limit=30)
    assert combat.might(s, T, u) == 1, "the minimum is the floor, not a legality"
    assert int(s.n_hand[0]) == before + 1


@case(6950, "Riptide Rex's 6 lands after Rex himself is dead")
def _():
    need("Riptide Rex")
    s = fresh(hand=[T.id_of("Riptide Rex")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Riptide Rex", base_loc(0))
    choose(s, u)
    rex = perm_of(s, "Riptide Rex", 0)[0]
    combat.destroy(s, T, rex)
    run(s, limit=40)
    assert not alive(s, rex), "he is in the trash"
    assert int(s.perms[u, P_DMG]) == 6, "and his ability needed nothing from him"


@case(6946, "two Masks of Foresight are +2")
def _():
    need("Mask of Foresight")
    s = fresh(runes=32)
    s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    s.bf_ctrl[0] = 0
    lone = body(s, 0, bf_loc(0), 3)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    drain(s)
    assert combat.might(s, T, lone) == 5, "each copy is its own ability"


@case(6945, "Bullet Time countered costs its caster no Power at all")
def _():
    need("Bullet Time", "Wind Wall")
    s = fresh(hand=[T.id_of("Bullet Time")], runes=32)
    give(s, 1, "Wind Wall")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    before = runes(s, 0)
    cast(s, 0, "Bullet Time", bf_loc(0))
    cast(s, 1, "Wind Wall", top_uid(s))
    run(s, limit=40)
    assert alive(s, u) and int(s.perms[u, P_DMG]) == 0, "countered"
    assert before - runes(s, 0) == 0, "the amount is chosen at resolution it never had"


@case(6940, "contesting an open Showdown denies the conquer")
def _():
    need("Zenith Blade")
    s = fresh(runes=32)
    give(s, 0, "Zenith Blade")
    s.bf_ctrl[1] = -1
    mine = body(s, 0, base_loc(0), 3)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 1, foe)
    assert int(s.showdown_bf) == 1, "a Non-Combat Showdown over open ground"
    cast(s, 0, "Zenith Blade", foe)
    run(s, picking(mine, bf_loc(1), accept=True), limit=30)
    assert int(s.perms[mine, P_LOC]) == bf_loc(1), "it is contested now"
    fight(s, limit=80)
    assert int(s.bf_ctrl[1]) != 1, "190.4: control cannot be established here"


@case(6936, "Showstopper moves a buffed unit without buffing it twice")
def _():
    need("Showstopper")
    s = fresh(hand=[T.id_of("Showstopper")], runes=32)
    s.bf_ctrl[0] = 0
    u = body(s, 0, base_loc(0), 3)
    s.set_flag(u, F_BUFFED)
    cast(s, 0, "Showstopper", u)
    run(s, picking(bf_loc(0), accept=True), limit=40)
    assert int(s.perms[u, P_LOC]) == bf_loc(0), "as much as it could"
    assert combat.might(s, T, u) == 4, "703: one buff, and it already had it"


@case(6928, "Ravenbloom Conservatory's defend trigger is a Chain item")
def _():
    need("Ravenbloom Conservatory", "Cleave", "Discipline")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Ravenbloom Conservatory")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Cleave")
    give(s, 0, "Discipline")
    give(s, 1, "Discipline")
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    assert int(s.n_chain) + int(s.n_trig) >= 1, "it is on the Chain, not a static"
    assert "Discipline" in hand_plays(s, 0), "the defender may answer its own trigger"
    act(s, A.A_PASS, None, 0)
    assert "Discipline" in hand_plays(s, 1), "and then so may the attacker"
    fight(s, limit=60)
    assert T.id_of("Cleave") in list(s.hand[0, :int(s.n_hand[0])]), \
        "a spell on top went to hand"


@case(6922, "Singularity's second target cannot be re-chosen")
def _():
    need("Singularity", "Gust")
    s = fresh(hand=[T.id_of("Singularity")], runes=32)
    rune_deck(s)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 3)
    b = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Singularity", a, b)
    cast(s, 1, "Gust", a)
    run(s, limit=40)
    assert not alive(s, a), "it went to hand"
    assert int(s.perms[b, P_DMG]) == 6, "the other half still happened"
