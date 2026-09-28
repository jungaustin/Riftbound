"""RiftJudge batch 42 -- unused questions from 8591-8638."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_ATTACHED_TO
from rl.engine.effects import pack_trash


@case(8638, "Not So Fast cannot counter Riposte, which chooses YOUR unit")
def _():
    need("Riposte", "Not So Fast", "Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=16)
    give(s, 1, "Riposte")
    give(s, 0, "Not So Fast")
    s.runes_ready[1, :] = 16
    theirs = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Singularity", theirs, -1)
    cast(s, 1, "Riposte", theirs)
    choose(s, sorted(targets_offered(s, 1))[0])
    assert "Not So Fast" not in hand_plays(s, 0), "its unit is not friendly to you"


@case(8634, "Equipment stays on a unit Zhonya's Hourglass recalled")
def _():
    need("Zhonya's Hourglass", "B.F. Sword", "Hidden Blade")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=12)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    g = s.add_permanent(T.id_of("B.F. Sword"), 1, bf_loc(0))
    s.active = s.priority = 1
    act(s, A.A_ACTIVATE, g, 1)
    choose(s, u)
    run(s)
    s.active = s.priority = 0
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Hidden Blade", u)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_LOC]) == base_loc(1)
    assert int(s.perms[g, P_ATTACHED_TO]) == u, "it never left the board"


@case(8633, "Imperial Decree only kills what takes damage after it resolves")
def _():
    need("Imperial Decree", "Bellows Breath")
    s = fresh(hand=[T.id_of("Bellows Breath"), T.id_of("Imperial Decree")],
              runes=20)
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Bellows Breath", u, -1, -1)
    run(s)
    assert int(s.perms[u, P_DMG]) == 1 and alive(s, u)
    cast(s, 0, "Imperial Decree")
    run(s)
    assert alive(s, u), "damage already marked is not damage being taken"


@case(8627, "Brynhir does not stop an ability already on the board")
def _():
    need("Brynhir Thundersong", "Lux, Crownguard", "Singularity")
    s = fresh(runes=20)
    give(s, 0, "Smoke Screen")
    give(s, 1, "Brynhir Thundersong", "Singularity")
    s.runes_ready[1, :] = 20
    lux = s.add_permanent(T.id_of("Lux, Crownguard"), 0, base_loc(0), ready=True)
    body(s, 0, base_loc(0), 3)
    s.active = s.priority = 1
    s.ply += 1
    act(s, A.A_PLAY, hand_index(s, 1, "Brynhir Thundersong"), 1)
    choose(s, base_loc(1))
    run(s)
    act(s, A.A_PLAY, hand_index(s, 1, "Singularity"), 1)
    choose(s, -1)
    choose(s, -1)
    pass_priority_to(s, 0)
    assert hand_plays(s, 0) == set(), "they can't play cards this turn"
    assert [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_ACTIVATE and a.arg == lux], \
        "activating is not playing a card"


@case(8626, "Karthus doubles Machine Evangel's Deathknell: six tokens")
def _():
    need("Karthus - Eternal", "Machine Evangel", "Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=20)
    ka = s.add_permanent(T.id_of("Karthus - Eternal"), 1, base_loc(1), ready=True)
    me = s.add_permanent(T.id_of("Machine Evangel"), 1, base_loc(1), ready=True)
    cast(s, 0, "Singularity", ka, me)
    run(s)
    assert not alive(s, ka) and not alive(s, me)
    assert len(tokens(s, 1)) == 6, "he was on the board when it triggered"


@case(8625, "Sett must spend HIS buff, not just any buff")
def _():
    need("Sett, Brawler", "Call to Glory")
    s = fresh(runes=16)
    give(s, 0, "Call to Glory")
    sett = s.add_permanent(T.id_of("Sett, Brawler"), 0, base_loc(0), ready=True)
    s.set_flag(sett, F_BUFFED)
    other = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY_REPEAT, hand_index(s, 0, "Call to Glory"), 0)
    run(s, picking(other))
    assert not s.has_flag(sett, F_BUFFED), "the spell spent his buff"
    assert combat.might(s, T, sett) == 4, "and gave him nothing"
    assert not [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]


@case(8623, "Temporal Portal's Repeat on Meditation draws 3, not 4")
def _():
    need("Temporal Portal", "Meditation")
    s = fresh(hand=[T.id_of("Meditation")], runes=16)
    tp = s.add_permanent(T.id_of("Temporal Portal"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 3, ready=True)
    act(s, A.A_ACTIVATE, tp, 0)
    run(s)
    before = int(s.n_hand[0])
    act(s, A.A_PLAY_BOTH, hand_index(s, 0, "Meditation"), 0)
    run(s, picking(u))
    assert int(s.n_hand[0]) == before - 1 + 2 + 1, \
        "the optional cost is paid once, so 2 then 1"


@case(8622, "Trinity Force's point follows the conquer point at 6")
def _():
    need("Trinity Force", "Skyfall of Areion")
    s = fresh(runes=16)
    s.points[0] = 6
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 3, ready=True)
    for name in ("Trinity Force", "Skyfall of Areion"):
        g = s.add_permanent(T.id_of(name), 0, base_loc(0))
        act(s, A.A_ACTIVATE, g, 0)
        choose(s, u)
        run(s)
    attack(s, 0, 0, u)
    fight(s)
    assert int(s.points[0]) == 8, "the conquer, then the trigger"


@case(8620, "Confront readies token units too")
def _():
    need("Confront", "Sprite Call")
    s = fresh(hand=[T.id_of("Confront"), T.id_of("Guards!")], runes=16)
    s.bf_ctrl[0] = 0
    cast(s, 0, "Confront")
    run(s)
    cast(s, 0, "Guards!")
    run(s, picking(bf_loc(0), accept=False))
    tok = tokens(s, 0)
    assert tok and int(s.perms[tok[0], P_READY]) == 1, "179.1.d: a token is a unit"


@case(8619, "Irelia killed by Cull the Weak gains nothing")
def _():
    need("Cull the Weak", "Irelia, Fervent")
    s = fresh(runes=12)
    give(s, 1, "Cull the Weak")
    s.runes_ready[1, :] = 12
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0), ready=True)
    body(s, 1, base_loc(1), 3)
    s.ply += 1
    s.active = s.priority = 1
    cast(s, 1, "Cull the Weak")
    run(s, picking(ir))
    assert not alive(s, ir), "you had to kill one, and she was it"


@case(8617, "the unit the Hourglass could not save still rings its Deathknell")
def _():
    need("Falling Star", "Honest Broker", "Zhonya's Hourglass")
    s = fresh(hand=[T.id_of("Falling Star")], runes=16)
    s.bf_ctrl[1] = 1
    a = s.add_permanent(T.id_of("Honest Broker"), 1, bf_loc(0), ready=True)
    b = s.add_permanent(T.id_of("Honest Broker"), 1, base_loc(1), ready=True)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    cast(s, 0, "Falling Star", a, b)
    run(s)
    assert alive(s, a) != alive(s, b), "the Hourglass saved exactly one"
    assert len(tokens(s, 1)) == 1, "and the other one's Deathknell ran"


@case(8616, "King's Edict can name a Ruin Runner")
def _():
    need("King's Edict", "Ruin Runner")
    s = fresh(hand=[T.id_of("King's Edict")], runes=16)
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, base_loc(1), ready=True)
    cast(s, 0, "King's Edict")
    run(s, picking(rr))
    assert not alive(s, rr), "its own controller chose it"


@case(8614, "Card Sharp pays you back for each opponent who took the Gold")
def _():
    need("Card Sharp")
    s = fresh(hand=[T.id_of("Card Sharp")], runes=16)
    act(s, A.A_PLAY, hand_index(s, 0, "Card Sharp"), 0)
    choose(s, base_loc(0))
    run(s, picking(accept=True))
    assert len(tokens(s, 0)) == 2 and len(tokens(s, 1)) == 1


@case(8613, "Cull the Weak triggers no [Deflect]")
def _():
    need("Cull the Weak", "Draven - Audacious")

    def spend(deflect):
        s = fresh(hand=[T.id_of("Cull the Weak")], runes=16)
        if deflect:
            u = s.add_permanent(T.id_of("Draven - Audacious"), 1, base_loc(1),
                                ready=True)
        else:
            u = body(s, 1, base_loc(1), 6)
        body(s, 0, base_loc(0), 3)
        before = runes(s, 0)
        cast(s, 0, "Cull the Weak")
        run(s, picking(u))
        assert not alive(s, u)
        return before - runes(s, 0)

    assert spend(True) == spend(False), "735.1.c wants a choice, and there is none"


@case(8612, "Sabotage recycles, which is not discarding")
def _():
    need("Sabotage", "Scrapheap")
    s = fresh(hand=[T.id_of("Sabotage")], runes=12)
    give(s, 1, "Scrapheap")
    before = int(s.n_hand[1])
    cast(s, 0, "Sabotage")
    run(s, picking(T.id_of("Scrapheap")))
    assert int(s.n_hand[1]) == before - 1, "it left their hand"
    assert int(s.n_hand[1]) == 0, "and nothing was drawn back"


@case(8609, "the attacker does not control the ground, so nothing lands there")
def _():
    need("Arcane Shift")
    s = fresh(runes=16)
    give(s, 0, "Arcane Shift")
    s.bf_ctrl[0] = 1
    att = body(s, 0, base_loc(0), 3, ready=True)
    body(s, 1, bf_loc(0), 9)
    attack(s, 0, 0, att)
    assert int(s.bf_ctrl[0]) == 1, "190.4.b freezes control through the combat"


@case(8594, "Hidden Blade draws nobody cards when its target is Retreated")
def _():
    need("Hidden Blade", "Retreat")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=16)
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    before = int(s.n_hand[1])
    cast(s, 0, "Hidden Blade", u)
    cast(s, 1, "Retreat", u)
    run(s)
    assert not alive(s, u), "it went back to hand"
    assert int(s.n_hand[1]) == before + 1 - 1, "the unit back, the Retreat gone"


@case(8592, "Downwell leaves hidden cards where they are")
def _():
    need("Downwell")
    s = fresh(hand=[T.id_of("Downwell")], runes=20)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    slot = hidden_at(s, 0, 0, "Hidden Blade")
    cast(s, 0, "Downwell")
    run(s)
    assert T.id_of("Hidden Blade") not in [int(s.hand[0, j])
                                           for j in range(int(s.n_hand[0]))], \
        "a facedown card is neither a unit nor a gear"
    assert slot >= 0


@case(8591, "[Deflect] is a mandatory additional cost, not an option")
def _():
    need("Defiant Dance", "Draven - Audacious")
    s = fresh(runes=2)
    give(s, 0, "Defiant Dance")
    mine = body(s, 0, base_loc(0), 3)
    s.add_permanent(T.id_of("Draven - Audacious"), 1, base_loc(1), ready=True)
    s.runes_ready[0, :] = 0
    s.runes_ready[0, 0] = 2
    assert "Defiant Dance" not in hand_plays(s, 0), \
        "353.2.a.2: one rune covers the spell but not the tax"
    assert mine >= 0


@case(8602, "Singularity's two choices must be two units")
def _():
    need("Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=16)
    a = body(s, 1, base_loc(1), 9)
    b = body(s, 0, base_loc(0), 9)
    act(s, A.A_PLAY, hand_index(s, 0, "Singularity"), 0)
    choose(s, a)
    left = targets_offered(s, 0)
    assert a not in left and b in left
