"""RiftJudge batch 28 -- unused questions from 9620-9733."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_NO_MOVE, P_ATTACHED_TO
from rl.engine.effects import ABILITIES, pack_trash


@case(9731, "Void Rush's {2 energy} off plus Legion plays Noxus Hopeful for 0")
def _():
    need("Void Rush", "Noxus Hopeful")
    s = fresh(hand=[T.id_of("Void Rush")], runes=9)
    s.deck[0, 0] = T.id_of("Noxus Hopeful")
    cast(s, 0, "Void Rush")
    run(s, stop=lambda s: s.n_chain == 0 or chain_mod.decision_open(s))
    s.runes_ready[0, :] = 0
    run(s, picking(0, base_loc(0)))
    assert perm_of(s, "Noxus Hopeful"), "4 - 2 (Legion) - 2 (Void Rush) = 0"


@case(9724, "Forbidding Waste re-reads 'alone' after the other defender dies")
def _():
    need("Forbidding Waste", "Hextech Ray", "Tideturner")
    s = fresh(runes=9)
    s.bf_card[0] = T.id_of("Forbidding Waste")
    s.bf_ctrl[0] = 1
    t1 = s.add_permanent(T.id_of("Tideturner"), 1, bf_loc(0))
    t2 = s.add_permanent(T.id_of("Tideturner"), 1, bf_loc(0))
    give(s, 0, "Hextech Ray")
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 6
    a = body(s, 0, base_loc(0), 9, ready=True)
    attack(s, 0, 0, a)
    assert combat.might(s, T, t2) == 2
    cast(s, 0, "Hextech Ray", t1)
    run(s, stop=lambda s: not alive(s, t1) and s.n_chain == 0)
    assert combat.might(s, T, t2) == 0, "now defending alone: 2 - 2"


@case(9718, "Gust cannot be played with no legal target")
def _():
    need("Gust")
    s = fresh(hand=[T.id_of("Gust")])
    body(s, 1, base_loc(1), 3)
    body(s, 1, bf_loc(0), 5)
    assert "Gust" not in hand_plays(s, 0)


@case(9717, "Defiant Dance works on two of your own units beside a Ruin Runner")
def _():
    need("Defiant Dance", "Ruin Runner")
    s = fresh(hand=[T.id_of("Defiant Dance")])
    s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1))
    body(s, 0, base_loc(0), 3)
    assert "Defiant Dance" not in hand_plays(s, 0)
    body(s, 0, base_loc(0), 3)
    assert "Defiant Dance" in hand_plays(s, 0)


@case(9716, "Punch First on a doubled Fiora - Peerless adds 5, not 10")
def _():
    need("Fiora - Peerless", "Punch First")
    s = fresh(hand=[T.id_of("Punch First")], runes=9)
    give(s, 1, "Smoke Screen")
    s.runes_ready[1, :] = 6
    s.bf_ctrl[0] = 1
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 0, base_loc(0), ready=True)
    body(s, 1, bf_loc(0), 1)
    attack(s, 0, 0, fi)
    run(s, stop=lambda s: s.n_chain == 0 and s.showdown_combat and A.acting_seat(s) == 0)
    assert combat.might(s, T, fi) == 6
    cast(s, 0, "Punch First", fi)
    run(s, stop=lambda s: s.n_chain == 0)
    assert combat.might(s, T, fi) == 11, combat.might(s, T, fi)


@case(9715, "Draven pushed back to base did not win the combat")
def _():
    need("Draven - Audacious", "Overzealous Fan")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 1
    s.add_permanent(T.id_of("Overzealous Fan"), 1, bf_loc(0))
    dr = s.add_permanent(T.id_of("Draven - Audacious"), 0, base_loc(0), ready=True)
    other = body(s, 0, base_loc(0), 5, ready=True)
    attack(s, 0, 0, dr, other)
    act(s, A.A_ACCEPT, None, 1)
    choose(s, dr)
    fight(s)
    assert int(s.perms[dr, P_LOC]) == base_loc(0)
    assert int(s.points[0]) == 1, "the conquest only; Draven was not there to win"


@case(9710, "Drag Under pays for [Deflect]")
def _():
    need("Drag Under", "Vex - Apathetic")
    s = fresh()
    vx = s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(0))
    assert rsv.deflect_cost(s, T, 0, [vx], SPECS["Drag Under"]) == 1


@case(9699, "Salvage may choose gear attached to Ruin Runner")
def _():
    need("Ruin Runner", "Salvage", "Long Sword")
    s = fresh(hand=[T.id_of("Salvage")], runes=9)
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1))
    ls = s.add_permanent(T.id_of("Long Sword"), 1, base_loc(1))
    s.attach(ls, rr)
    act(s, A.A_PLAY, hand_index(s, 0, "Salvage"), 0)
    assert ls in targets_offered(s, 0) and rr not in targets_offered(s, 0)


@case(9697, "Blue Sentinel doubles Grove of the God-Willow's hold draw")
def _():
    need("Blue Sentinel", "Grove of the God-Willow")
    s = fresh()
    s.bf_card[0] = T.id_of("Grove of the God-Willow")
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Blue Sentinel"), 0, bf_loc(0))
    _next_own_turn(s)
    run(s)
    assert int(s.n_hand[0]) == 3, "the turn's draw, and the Grove's draw twice"


@case(9695, "Blind Fury: you control the unit, the opponent still owns it")
def _():
    need("Blind Fury")
    s = fresh(hand=[T.id_of("Blind Fury")], runes=9)
    s.deck[1, 0] = T.id_of("Mindsplitter")
    cast(s, 0, "Blind Fury")
    run(s, picking(base_loc(0)))
    ms = perm_of(s, "Mindsplitter")
    assert ms and int(s.perms[ms[0], P_CTRL]) == 0
    from rl.engine.state import P_OWNER
    assert int(s.perms[ms[0], P_OWNER]) == 1


@case(9688, "Frigid Touch can push Might below 1")
def _():
    need("Frigid Touch")
    s = fresh(hand=[T.id_of("Frigid Touch")], runes=9)
    u = body(s, 1, base_loc(1), 1)
    cast(s, 0, "Frigid Touch", u)
    run(s)
    assert combat.might(s, T, u) == 0 and alive(s, u)
    combat.set_might_mod(s, T, u, 2)
    assert combat.might(s, T, u) == 1, "it was at -1, not floored at 0"


@case(9687, "Thrill of the Hunt drops a unit's Long Sword")
def _():
    need("Thrill of the Hunt", "Long Sword")
    s = fresh(hand=[T.id_of("Thrill of the Hunt")], runes=9)
    u = s.add_permanent(T.id_of("Mindsplitter"), 0, base_loc(0))
    ls = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
    s.attach(ls, u)
    cast(s, 0, "Thrill of the Hunt", u)
    run(s, picking(bf_loc(0)))
    ms = perm_of(s, "Mindsplitter", 0)
    assert ms and combat.might(s, T, ms[0]) == 7
    assert alive(s, ls) and int(s.perms[ls, P_ATTACHED_TO]) < 0


@case(9685, "Azir pushed to base by Overzealous Fan brings no tokens")
def _():
    need("Azir - Sovereign", "Overzealous Fan", "Sprite Call")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 1
    s.add_permanent(T.id_of("Overzealous Fan"), 1, bf_loc(0))
    az = s.add_permanent(T.id_of("Azir - Sovereign"), 0, base_loc(0), ready=True)
    s.bf_ctrl[1] = 0
    tok = _sprite_at(s, 0, 1)
    s.active = s.priority = 0
    attack(s, 0, 0, az)

    # the defender's trigger is placed above Azir's and resolves first
    def pref(s, who, legal):
        for want in (az, tok):
            for a in legal:
                if a.kind == A.A_TARGET and a.arg == want:
                    return a
        return next((a for a in legal if a.kind == A.A_ACCEPT), None)
    run(s, pref)
    assert int(s.perms[az, P_LOC]) == base_loc(0)
    assert int(s.perms[tok, P_LOC]) == bf_loc(1), "'this battlefield' is gone for Azir"


@case(9673, "Dazzling Aurora's end-of-turn trigger can be answered")
def _():
    need("Dazzling Aurora")
    s = fresh(runes=9)
    s.add_permanent(T.id_of("Dazzling Aurora"), 0, base_loc(0))
    give(s, 1, "Discipline")
    s.runes_ready[1, :] = 6
    body(s, 1, base_loc(1), 3)
    act(s, A.A_END_TURN, None, 0)
    A._settle(s, T, V1)
    assert "Dazzling Aurora" in chain_names(s)
    pass_priority_to(s, 1)
    assert "Discipline" in hand_plays(s, 1)


@case(9666, "Vanguard Armory may make Recruits the turn it is played")
def _():
    need("Vanguard Armory")
    s = fresh(hand=[T.id_of("Vanguard Armory")], runes=12)
    cast(s, 0, "Vanguard Armory", base_loc(0))
    run(s)
    va = perm_of(s, "Vanguard Armory")[0]
    assert int(s.perms[va, P_READY]) == 1, "gear enters ready (359.2.d)"
    assert any(a.kind == A.A_ACTIVATE and a.arg == va
               for a in A.legal_actions(s, T, V1, 0))


@case(9664, "Smite's banish replaces the death: no Deathknell")
def _():
    need("Smite", "Lonely Poro")
    s = fresh(hand=[T.id_of("Smite")], runes=9)
    s.bf_ctrl[1] = 1
    lp = s.add_permanent(T.id_of("Lonely Poro"), 1, bf_loc(0))
    cast(s, 0, "Smite", lp)
    run(s)
    assert not alive(s, lp) and int(s.n_hand[1]) == 0 and int(s.n_trash[1]) == 0


@case(9662, "Blighted Battleaxe asks whether THE EQUIPPED unit conquered")
def _():
    need("Blighted Battleaxe")
    s = fresh()
    u = body(s, 0, base_loc(0), 5)
    ax = s.add_permanent(T.id_of("Blighted Battleaxe"), 0, base_loc(0))
    s.attach(ax, u)
    other = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, other)
    run(s, picking())
    assert int(s.bf_ctrl[0]) == 0
    act(s, A.A_END_TURN, None, 0)
    run(s, picking())
    assert int(s.perms[ax, P_ATTACHED_TO]) < 0


@case(9660, "Hexdrinker's Deflect adds to Irelia, Fervent's own")
def _():
    need("Hexdrinker", "Irelia, Fervent")
    s = fresh()
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 1, base_loc(1))
    hx = s.add_permanent(T.id_of("Hexdrinker"), 1, base_loc(1))
    s.attach(hx, ir)
    assert rsv.deflect_cost(s, T, 0, [ir]) == 2


@case(9659, "a second enemy arriving does not re-fire an attack trigger")
def _():
    need("Ezreal - Dashing", "Ride The Wind")
    s = fresh(runes=9)
    give(s, 1, "Ride The Wind")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[0] = 1
    ez = s.add_permanent(T.id_of("Ezreal - Dashing"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 5)
    late = body(s, 1, base_loc(1), 9)
    attack(s, 0, 0, ez)
    run(s, picking(d), stop=lambda s: s.n_chain == 0)
    fired = 1
    cast(s, 1, "Ride The Wind", late, bf_loc(0))
    run(s, stop=lambda s: s.n_chain == 0 and s.n_trig == 0)
    assert "Ezreal - Dashing" not in chain_names(s)
    assert int(s.perms[late, P_DMG]) == 0, fired


@case(9655, "Repulse cannot answer a Bellows Breath repeated across two locations")
def _():
    need("Bellows Breath", "Repulse")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=9)
    give(s, 1, "Repulse")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[0] = s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    v = body(s, 1, bf_loc(1), 5)
    cast(s, 0, "Bellows Breath", u, -1, -1, v, -1, -1, repeat=True)
    pass_priority_to(s, 1)
    assert "Repulse" not in hand_plays(s, 1)


@case(9651, "Irelia, Fervent chosen by a countered Challenge keeps her +1")
def _():
    need("Challenge", "Irelia, Fervent", "Defy")
    s = fresh(hand=[T.id_of("Challenge")], runes=9)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0))
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Challenge", ir, foe)
    run(s, stop=lambda s: s.n_trig == 0 and "Irelia, Fervent" not in chain_names(s)
        and A.acting_seat(s) == 1)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert combat.might(s, T, ir) == 5 and int(s.perms[foe, P_DMG]) == 0


@case(9644, "Thousand-Tailed Watcher misses Mechs made after it resolved")
def _():
    need("Thousand-Tailed Watcher", "Ferrous Forerunner")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=12)
    ff = s.add_permanent(T.id_of("Ferrous Forerunner"), 1, base_loc(1))
    cast(s, 0, "Thousand-Tailed Watcher", base_loc(0))
    run(s)
    combat.destroy(s, T, ff)
    run(s)
    mechs = tokens(s, 1)
    assert len(mechs) == 2 and all(combat.might(s, T, m) == 3 for m in mechs)


@case(9638, "Ezreal - Dashing deals his Might at resolution")
def _():
    need("Ezreal - Dashing", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    s.bf_ctrl[0] = 1
    ez = s.add_permanent(T.id_of("Ezreal - Dashing"), 0, base_loc(0), ready=True)
    d = body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, ez)
    choose(s, d)                              # the trigger's target, as it is placed
    cast(s, 0, "Discipline", ez)
    run(s, stop=lambda s: int(s.perms[d, P_DMG]) > 0)
    assert int(s.perms[d, P_DMG]) == 5


@case(9635, "Sacrifice answering Hidden Blade: Hidden Blade's target is gone")
def _():
    need("Sacrifice", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=9)
    give(s, 1, "Sacrifice")
    s.runes_ready[1, :] = 9
    rune_deck(s)
    s.bf_ctrl[1] = 1
    foe = s.add_permanent(T.id_of("Mindsplitter"), 1, bf_loc(0))
    cast(s, 0, "Hidden Blade", foe)
    cast(s, 1, "Sacrifice", foe)
    run(s)
    assert int(s.n_hand[1]) == 2, "Sacrifice's 2; Hidden Blade's draw needs its kill"


@case(9625, "Vex - Apathetic stuns Ruin Runner: it chooses nothing")
def _():
    need("Vex - Apathetic", "Ruin Runner")
    s = fresh(hand=[T.id_of("Ruin Runner")], runes=9)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    cast(s, 0, "Ruin Runner", base_loc(0))
    run(s)
    rr = perm_of(s, "Ruin Runner")
    assert rr and s.has_flag(rr[0], F_STUNNED)


@case(9623, "a Hidden Blade whose target fled still counts as played")
def _():
    need("Hidden Blade", "Flash", "Ravenbloom Student")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=9)
    give(s, 1, "Flash")
    s.runes_ready[1, :] = 9
    st = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0))
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Hidden Blade", foe)
    cast(s, 1, "Flash", foe, -1)
    run(s)
    assert alive(s, foe) and combat.might(s, T, st) == 3


@case(9622, "Frozen Fortress's damage is nobody's: Elder Dragon doesn't apply")
def _():
    need("Elder Dragon", "Frozen Fortress")
    s = fresh(seat=1)
    s.add_permanent(T.id_of("Elder Dragon"), 0, base_loc(0))
    s.bf_card[0] = T.id_of("Frozen Fortress")
    s.bf_ctrl[0] = 1
    foe = body(s, 1, bf_loc(0), 5)
    s.ply += 2
    s.active = s.priority = 1
    phases.start_turn(s, T, V1)
    run(s, picking())
    assert alive(s, foe) and int(s.perms[foe, P_DMG]) == 1
