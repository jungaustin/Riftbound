"""RiftJudge batch 41 -- unused questions from 8639-8685."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8685, "Vex, Apathetic stuns even Baron Nashor: she chooses nobody")
def _():
    need("Vex - Apathetic", "Baron Nashor")
    s = fresh(hand=[T.id_of("Baron Nashor")], runes=20)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(0), ready=True)
    act(s, A.A_PLAY, hand_index(s, 0, "Baron Nashor"), 0)
    choose(s, base_loc(0))
    run(s)
    bn = perm_of(s, "Baron Nashor", 0)[0]
    assert s.has_flag(bn, F_STUNNED), "a programmatic selection is not a choice"


@case(8684, "Elder Dragon's lethality is yours alone")
def _():
    need("Elder Dragon", "Flurry of Blades")
    s = fresh(runes=20)
    give(s, 1, "Flurry of Blades")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[0] = 0
    ed = s.add_permanent(T.id_of("Elder Dragon"), 0, bf_loc(0), ready=True)
    mine = body(s, 0, bf_loc(0), 3)
    s.ply += 1
    s.active = s.priority = 1
    cast(s, 1, "Flurry of Blades")
    run(s)
    assert alive(s, mine) and alive(s, ed), "1 damage is 1 damage against you"
    assert int(s.perms[mine, P_DMG]) == 1


@case(8682, "Bone Skewer may choose a Ruin Runner out of the hand")
def _():
    need("Bone Skewer", "Ruin Runner")
    s = fresh(hand=[T.id_of("Bone Skewer")], runes=12)
    give(s, 1, "Ruin Runner")
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Bone Skewer", bf_loc(0))
    run(s, picking(T.id_of("Ruin Runner")))
    rr = perm_of(s, "Ruin Runner", 1)
    assert rr, "they had to play it"
    assert s.has_flag(rr[0], F_STUNNED), "protection starts on the board"


@case(8680, "Thousand-Tailed Watcher floors a unit at 1 Might")
def _():
    need("Thousand-Tailed Watcher")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=16)
    u = body(s, 1, base_loc(1), 2)
    act(s, A.A_PLAY, hand_index(s, 0, "Thousand-Tailed Watcher"), 0)
    choose(s, base_loc(0))
    run(s)
    assert combat.might(s, T, u) == 1 and alive(s, u)


@case(8676, "Equipment stays on a unit Guardian Angel saved")
def _():
    need("Guardian Angel", "B.F. Sword", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=12)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    s.active = s.priority = 1
    for name in ("Guardian Angel", "B.F. Sword"):
        g = s.add_permanent(T.id_of(name), 1, bf_loc(0))
        act(s, A.A_ACTIVATE, g, 1)
        choose(s, u)
        run(s)
    s.active = s.priority = 0
    sword = perm_of(s, "B.F. Sword", 1)[0]
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u), "the death was replaced"
    assert int(s.perms[sword, P_ATTACHED_TO]) == u


@case(8669, "an attached Hexdrinker's own [Deflect] is what you pay for it")
def _():
    need("Hexdrinker", "Detonate")

    def spend(attached):
        s = fresh(hand=[T.id_of("Detonate")], runes=12)
        u = body(s, 1, base_loc(1), 3)
        g = s.add_permanent(T.id_of("Hexdrinker"), 1, base_loc(1))
        if attached:
            s.active = s.priority = 1
            act(s, A.A_ACTIVATE, g, 1)
            choose(s, u)
            run(s)
            s.active = s.priority = 0
        before = runes(s, 0)
        cast(s, 0, "Detonate", g)
        run(s)
        assert not alive(s, g)
        return before - runes(s, 0)

    assert spend(True) == spend(False), "718.2 sleeps its printed text either way"


@case(8663, "Frigid Touch alone never kills")
def _():
    need("Frigid Touch")
    s = fresh(runes=12)
    give(s, 0, "Frigid Touch")
    u = body(s, 1, base_loc(1), 2)
    cast(s, 0, "Frigid Touch", u, repeat=True)
    run(s, picking(u))
    assert alive(s, u), "142.2.a needs nonzero damage marked"
    assert combat.might(s, T, u) == 0


@case(8662, "Singularity cannot choose one unit twice")
def _():
    need("Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=16)
    u = body(s, 1, base_loc(1), 9)
    body(s, 1, base_loc(1), 9)
    act(s, A.A_PLAY, hand_index(s, 0, "Singularity"), 0)
    choose(s, u)
    assert u not in targets_offered(s, 0), "two units means two DIFFERENT units"


@case(8661, "Riptide Rex's trigger must choose when it can")
def _():
    need("Riptide Rex")
    s = fresh(hand=[T.id_of("Riptide Rex")], runes=20)
    s.bf_ctrl[1] = 1
    foe = body(s, 1, bf_loc(0), 9)
    act(s, A.A_PLAY, hand_index(s, 0, "Riptide Rex"), 0)
    choose(s, base_loc(0))
    offered = targets_offered(s, 0)
    assert offered == {foe}, "no declining while a legal choice exists"
    choose(s, foe)
    run(s)
    assert int(s.perms[foe, P_DMG]) == 6


@case(8659, "Rebuke can answer a unit moving onto open ground")
def _():
    need("Rebuke")
    s = fresh(runes=16)
    give(s, 1, "Rebuke")
    s.runes_ready[1, :] = 16
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    assert int(s.showdown_bf) == 0, "a non-combat showdown is still a showdown"
    pass_priority_to(s, 1)
    assert "Rebuke" in hand_plays(s, 1), "732.1.c.1 lets an [Action] in"
    cast(s, 1, "Rebuke", u)
    fight(s)
    assert not alive(s, u) and int(s.bf_ctrl[0]) < 0, "bounced before conquering"


@case(8658, "a hidden Guards! puts its token at the battlefield it was hidden")
def _():
    need("Guards!")
    s = fresh(runes=12)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    body(s, 0, bf_loc(0), 3)
    body(s, 0, bf_loc(1), 3)
    slot = hidden_at(s, 0, 0, "Guards!")
    act(s, A.A_PLAY_HIDDEN, slot, 0)
    run(s, picking(accept=False))
    tok = tokens(s, 0)
    assert tok and int(s.perms[tok[0], P_LOC]) == bf_loc(0), "737.1.d.3"


@case(8654, "Last Rites' conquer effect fires from the gear on the winner")
def _():
    need("Last Rites", "Determined Sentry")
    s = fresh(runes=16)
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    lr = s.add_permanent(T.id_of("Last Rites"), 0, base_loc(0))
    for j in range(2):
        s.trash[0, j] = T.id_of("Determined Sentry")
    s.n_trash[0] = 2
    act(s, A.A_ACTIVATE, lr, 0)
    choose(s, u)
    run(s)
    assert int(s.perms[lr, P_ATTACHED_TO]) == u
    s.trash[0, 0] = T.id_of("Determined Sentry")
    s.n_trash[0] = 1
    attack(s, 0, 0, u)
    run(s, picking(pack_trash(0, T.id_of("Determined Sentry")), bf_loc(0),
                   accept=True), limit=60)
    assert perm_of(s, "Determined Sentry", 0), "the gear's conquer effect ran"


@case(8652, "Spinning Axe equips any unit you control")
def _():
    need("Spinning Axe")
    s = fresh(runes=12)
    u = body(s, 0, base_loc(0), 3, ready=True)
    ax = s.add_permanent(T.id_of("Spinning Axe"), 0, base_loc(0))
    act(s, A.A_ACTIVATE, ax, 0)
    choose(s, u)
    run(s)
    assert int(s.perms[ax, P_ATTACHED_TO]) == u and combat.might(s, T, u) == 6


@case(8647, "'you' in a battlefield ability is the battlefield's controller")
def _():
    need("Ravenbloom Conservatory", "Ride The Wind")
    s = fresh(runes=16)
    give(s, 1, "Ride The Wind")
    s.runes_ready[1, :] = 16
    s.bf_card[0] = T.id_of("Ravenbloom Conservatory")
    s.bf_ctrl[0] = 1
    defender = body(s, 1, bf_loc(0), 3)
    s.ply += 1
    s.ply -= 1
    att = body(s, 0, base_loc(0), 3, ready=True)
    h0, h1 = int(s.n_hand[0]), int(s.n_hand[1])
    attack(s, 0, 0, att)
    drain(s)
    assert int(s.n_hand[0]) == h0, "the attacker reveals nothing"
    assert int(s.n_hand[1]) >= h1, "the defender is the 'you'"
    assert defender >= 0


@case(8646, "a Hard Bargained spell was never played, so no Ravenbloom +1")
def _():
    need("Stupefy", "Hard Bargain", "Ravenbloom Student")
    s = fresh(runes=16)
    give(s, 0, "Stupefy")
    give(s, 1, "Hard Bargain")
    s.runes_ready[1, :] = 16
    rs = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0), ready=True)
    foe = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Stupefy", foe)
    cast(s, 1, "Hard Bargain")
    choose(s, sorted(targets_offered(s, 1))[0])
    run(s, prefer=lambda st, who, legal: next(
        (a for a in legal if a.kind == A.A_DECLINE), None) if who == 0 else None)
    assert combat.might(s, T, foe) == 5, "the spell was countered"
    assert combat.might(s, T, rs) == 2, "so it was never played (412.1.b)"


@case(8645, "Fight or Flight fails at Vilemaw's Lair, but is still playable")
def _():
    need("Fight or Flight", "Vilemaw's Lair")
    s = fresh(hand=[T.id_of("Fight or Flight")], runes=12)
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    assert "Fight or Flight" in hand_plays(s, 0), "choosing it is legal"
    cast(s, 0, "Fight or Flight", u)
    run(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(0), "the move is what fails"


@case(8641, "Faithful Manufactor's Recruit arrives exhausted")
def _():
    need("Faithful Manufactor")
    s = fresh(hand=[T.id_of("Faithful Manufactor")], runes=12)
    act(s, A.A_PLAY, hand_index(s, 0, "Faithful Manufactor"), 0)
    choose(s, base_loc(0))
    run(s)
    tok = tokens(s, 0)
    assert tok and int(s.perms[tok[0], P_READY]) == 0


@case(8640, "Not So Fast needs the spell to choose one of YOUR units")
def _():
    need("Get Excited!", "Not So Fast")
    s = fresh(hand=[T.id_of("Get Excited!"), T.id_of("Smoke Screen")], runes=16)
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 16
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 9)
    cast(s, 0, "Get Excited!", mine)
    assert "Not So Fast" not in hand_plays(s, 1), "'friendly' is from its side"


@case(8639, "the two halves of Falling Star are one resolution")
def _():
    need("Falling Star", "Zhonya's Hourglass")
    s = fresh(hand=[T.id_of("Falling Star")], runes=16)
    a = body(s, 1, base_loc(1), 3)
    b = body(s, 1, base_loc(1), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Falling Star", a, b)
    run(s)
    assert not alive(s, z), "the Hourglass answered one of the two deaths"
    assert alive(s, a) != alive(s, b), "and only one of them"


@case(8678, "Darius, Trifarian counts himself as the card he is")
def _():
    need("Darius - Trifarian", "Discipline")
    s = fresh(hand=[T.id_of("Discipline"), T.id_of("Darius - Trifarian")], runes=16)
    body(s, 0, base_loc(0), 3)
    u = perm_of(s, "Shipyard Skulker", 0)[0]
    cast(s, 0, "Discipline", u)
    run(s)
    act(s, A.A_PLAY, hand_index(s, 0, "Darius - Trifarian"), 0)
    choose(s, base_loc(0))
    run(s)
    dar = perm_of(s, "Darius - Trifarian", 0)[0]
    assert int(s.perms[dar, P_READY]) == 1 and combat.might(s, T, dar) == 7


@case(8657, "Cull the Weak with no units of your own still kills theirs")
def _():
    need("Cull the Weak")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=12)
    a = body(s, 1, base_loc(1), 3)
    b = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Cull the Weak")
    run(s, picking(b))
    assert alive(s, a) and not alive(s, b), "they choose which of theirs dies"
