"""RiftJudge batch 34 -- unused questions from 9034-9163."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(9163, "Irelia keeps the +1 from a spell that is later countered")
def _():
    need("Irelia, Fervent", "Ride The Wind", "Defy")
    s = fresh(hand=[T.id_of("Ride The Wind")], runes=9)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0), ready=False)
    cast(s, 0, "Ride The Wind", ir, bf_loc(0))
    cast(s, 1, "Defy", 0)
    run(s)
    assert int(s.perms[ir, P_READY]) == 0, "the counter stopped the ready"
    assert combat.might(s, T, ir) == 5, "but choosing her already triggered"


@case(9160, "Singularity can choose a unit sitting in a base")
def _():
    need("Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=12)
    u = body(s, 1, base_loc(1), 5)
    act(s, A.A_PLAY, hand_index(s, 0, "Singularity"), 0)
    assert u in targets_offered(s, 0), "no location restriction is printed"


@case(9159, "Ride the Wind moves a unit from one battlefield to another")
def _():
    need("Ride The Wind")
    s = fresh(hand=[T.id_of("Ride The Wind")], runes=9)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Ride The Wind", u, bf_loc(1))
    run(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(1), "only a Standard Move is base-bound"


@case(9158, "Retreat cannot bounce an enemy unit")
def _():
    need("Retreat")
    s = fresh(hand=[T.id_of("Retreat")], runes=6)
    mine = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Retreat"), 0)
    offered = targets_offered(s, 0)
    assert mine in offered and theirs not in offered


@case(9154, "Not So Fast counters a Thwonk! aimed at your attacker")
def _():
    need("Not So Fast", "Thwonk!")
    s = fresh(runes=9)
    give(s, 0, "Not So Fast")
    give(s, 1, "Thwonk!")
    s.runes_ready[1, :] = 9
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 5, ready=True)
    body(s, 1, bf_loc(0), 5)
    attack(s, 0, 0, u)
    cast(s, 1, "Thwonk!", u)
    cast(s, 0, "Not So Fast", top_uid(s))
    drain(s)
    assert not s.has_flag(u, F_STUNNED), "the stun was countered"


@case(9147, "Brynhir Thundersong shuts off the opponent's reactions")
def _():
    need("Brynhir Thundersong", "Defy")
    s = fresh(hand=[T.id_of("Brynhir Thundersong")], runes=9)
    give(s, 1, "Defy")
    s.runes_ready[1, :] = 9
    act(s, A.A_PLAY, hand_index(s, 0, "Brynhir Thundersong"), 0)
    run(s)
    assert hand_plays(s, 1) == set(), "opponents can't play cards this turn"


@case(9145, "Rocket Barrage is base speed, so it is no reaction")
def _():
    need("Rocket Barrage", "Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=12)
    give(s, 1, "Rocket Barrage")
    s.runes_ready[1, :] = 12
    u = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Singularity", u, -1)
    assert "Rocket Barrage" not in hand_plays(s, 1)


@case(9142, "Meditation's exhaust is a cost, so The Dreaming Tree stays quiet")
def _():
    need("Meditation", "The Dreaming Tree")
    s = fresh(hand=[T.id_of("Meditation")], runes=9)
    s.bf_card[0] = T.id_of("The Dreaming Tree")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3, ready=True)
    before = int(s.n_hand[0])
    cast(s, 0, "Meditation", repeat=True)
    run(s, picking(u))
    assert int(s.perms[u, P_READY]) == 0, "the additional cost exhausted it"
    assert int(s.n_hand[0]) == before - 1 + 2, "2 drawn, none from the Tree"


@case(9135, "Darius, Trifarian counts himself as the second card played")
def _():
    need("Darius - Trifarian", "Meditation")
    s = fresh(hand=[T.id_of("Meditation"), T.id_of("Darius - Trifarian")], runes=12)
    cast(s, 0, "Meditation")
    run(s)
    act(s, A.A_PLAY, hand_index(s, 0, "Darius - Trifarian"), 0)
    choose(s, base_loc(0))
    run(s)
    dar = perm_of(s, "Darius - Trifarian", 0)[0]
    assert combat.might(s, T, dar) == 7 and int(s.perms[dar, P_READY]) == 1


@case(9127, "Sett's buff is standard speed: not on the opponent's turn")
def _():
    need("Sett, Brawler")
    s = fresh(runes=9)
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    s.set_flag(sett, F_BUFFED)
    s.active = s.priority = 1
    s.ply += 1
    assert not [a for a in A.legal_actions(s, T, V1, 0)
                if a.kind == A.A_ACTIVATE and a.arg == sett]


@case(9118, "Wages of Pain kills a 3 Might unit outright")
def _():
    need("Wages of Pain")
    s = fresh(hand=[T.id_of("Wages of Pain")], runes=9)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Wages of Pain", u)
    run(s)
    assert not alive(s, u), "3 damage meets 3 Might (142.2.a)"


@case(9110, "Ruin Runner can't be chosen by an enemy spell")
def _():
    need("Ruin Runner", "Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=12)
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1), ready=True)
    mine = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Singularity"), 0)
    offered = targets_offered(s, 0)
    assert rr not in offered and mine in offered


@case(9102, "Thousand-Tailed Watcher shrinks Ruin Runner: it chooses nothing")
def _():
    need("Ruin Runner", "Thousand-Tailed Watcher")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=12)
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1), ready=True)
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    run(s)
    assert combat.might(s, T, rr) == 2, "a global effect is not a choice"


@case(9097, "a unit saved by Guardian Angel keeps its other Equipment")
def _():
    need("Guardian Angel", "Brutalizer", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=9)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 1, bf_loc(0))
    br = s.add_permanent(T.id_of("Brutalizer"), 1, bf_loc(0))
    s.active = s.priority = 1
    for g in (ga, br):
        act(s, A.A_ACTIVATE, g, 1)
        choose(s, u)
        run(s)
    s.active = s.priority = 0
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u) and not alive(s, ga), "the Angel died instead"
    assert int(s.perms[br, P_ATTACHED_TO]) == u, "the other gear rode along"


@case(9089, "Cull the Weak chooses nothing, so Irelia gains no Might")
def _():
    need("Cull the Weak", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=9)
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0), ready=True)
    mine = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Cull the Weak")
    run(s, picks(mine, theirs))
    assert not alive(s, mine) and not alive(s, theirs)
    assert combat.might(s, T, ir) == 4, "a forced kill never chooses (8619)"


@case(9078, "a repeated Bellows Breath can hit the same unit twice")
def _():
    need("Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=12)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Bellows Breath", u, -1, repeat=True)
    run(s, picks(u, -1))
    assert int(s.perms[u, P_DMG]) == 2, "each instance targets separately"


@case(9075, "Singularity's 'up to two' allows a single choice")
def _():
    need("Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=12)
    a = body(s, 1, base_loc(1), 5)
    b = body(s, 0, base_loc(0), 5)
    cast(s, 0, "Singularity", a, -1)
    run(s)
    assert not alive(s, a) and alive(s, b)


@case(9074, "Ride the Wind gives Irelia +2: one for chosen, one for readied")
def _():
    need("Irelia, Fervent", "Ride The Wind")
    s = fresh(hand=[T.id_of("Ride The Wind")], runes=9)
    s.bf_ctrl[0] = 0
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0), ready=False)
    cast(s, 0, "Ride The Wind", ir, bf_loc(0))
    run(s)
    assert int(s.perms[ir, P_READY]) == 1
    assert combat.might(s, T, ir) == 6, "chosen and readied are two triggers"


@case(9073, "Piercing Light's second target still takes 2 when the first dies")
def _():
    need("Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=9)
    s.bf_ctrl[1] = 1
    front = body(s, 1, bf_loc(0), 2)
    home = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Piercing Light", front, home)
    run(s)
    assert not alive(s, front), "2 damage meets 2 Might"
    assert int(s.perms[home, P_DMG]) == 2, "'then' is timing, not a condition"


@case(9070, "Cull the Weak: each player picks their own unit on resolution")
def _():
    need("Cull the Weak")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=9)
    a1 = body(s, 0, base_loc(0), 3)
    a2 = body(s, 0, base_loc(0), 5)
    b1 = body(s, 1, base_loc(1), 3)
    b2 = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Cull the Weak")
    run(s, picks(a2, b2))
    assert alive(s, a1) and alive(s, b1)
    assert not alive(s, a2) and not alive(s, b2)


@case(9057, "Whirlwind lets each player bounce a unit, starting with the next")
def _():
    need("Whirlwind")
    s = fresh(hand=[T.id_of("Whirlwind")], runes=9)
    mine = body(s, 0, base_loc(0), 3)
    theirs = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Whirlwind")
    run(s, picks(theirs, mine))
    assert not alive(s, mine) and not alive(s, theirs)
    assert int(s.n_hand[0]) >= 1 and int(s.n_hand[1]) >= 1


@case(9056, "two Forecasters are two separate instances of [Vision]")
def _():
    need("Forecaster", "Carrion Dredger")

    def vision_windows(n_forecasters):
        s = fresh(hand=[T.id_of("Carrion Dredger")], runes=9)
        for _ in range(n_forecasters):
            s.add_permanent(T.id_of("Forecaster"), 0, base_loc(0), ready=True)
        act(s, A.A_PLAY, hand_index(s, 0, "Carrion Dredger"), 0)
        choose(s, base_loc(0))
        seen = [0]

        def pref(st, who, legal):
            if any(a.kind == A.A_PICK_NONE for a in legal):
                seen[0] += 1
            return None
        run(s, pref)
        return seen[0]

    assert vision_windows(1) == 1, vision_windows(1)
    assert vision_windows(2) == 2, "743.2: each instance triggers"


@case(9054, "a hidden spell must choose at the battlefield it was hidden at")
def _():
    need("Hidden Blade")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    here = body(s, 1, bf_loc(0), 3)
    away = body(s, 1, bf_loc(1), 3)
    hidden_at(s, 0, 0, "Hidden Blade")
    act(s, A.A_PLAY_HIDDEN, 0, 0)
    offered = targets_offered(s, 0)
    assert here in offered and away not in offered, "737.1.d.2"


@case(9034, "Brutalizer re-attached in one turn is +3, never +4")
def _():
    need("Brutalizer")
    s = fresh(runes=9)
    u = body(s, 0, base_loc(0), 3, ready=True)
    br = s.add_permanent(T.id_of("Brutalizer"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, br, 0)
    choose(s, u)
    run(s)
    assert combat.might(s, T, u) == 6, "+1 printed and +2 for this turn"


@case(9091, "Undertitan pumps your other units, not itself")
def _():
    need("Undertitan")
    s = fresh(hand=[T.id_of("Undertitan")], runes=12)
    mate = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Undertitan"), 0)
    choose(s, base_loc(0))
    run(s)
    ut = perm_of(s, "Undertitan", 0)[0]
    assert combat.might(s, T, mate) == 5 and combat.might(s, T, ut) == 5
