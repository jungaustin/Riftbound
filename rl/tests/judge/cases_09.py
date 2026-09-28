"""RiftJudge batch 9 -- unused questions from 12047-12234."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_EMPOWERED, P_EMPOWER, P_MIGHT_MOD
from rl.engine.effects import ABILITIES, pack_trash
from rl.engine.state import P_ATTACHED_TO


def ready_runes(s, seat):
    return int(s.runes_ready[seat].sum())


@case(12047, "Frigid Jewel triggers once, on the second card, however many are drawn")
def _():
    need("Frigid Jewel")
    s = fresh()
    s.add_permanent(T.id_of("Frigid Jewel"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    phases.draw_for(s, 0, 6)
    A._settle(s, T, V1)
    run(s, picking(u))
    assert combat.might(s, T, u) == 5, combat.might(s, T, u)


@case(12051, "Lightning Rush looking at Undertitan adds no Energy: looking is not revealing")
def _():
    need("Lightning Rush", "Undertitan")
    s = fresh(hand=[T.id_of("Lightning Rush")])
    s.deck[0, :3] = [T.id_of("Undertitan")] * 3
    cast(s, 0, "Lightning Rush")
    run(s, picking())
    assert int(s.pool_energy[0]) == 0


@case(12056, "Shuriken Flip's move does not exhaust the unit")
def _():
    need("Shuriken Flip")
    s = fresh(hand=[T.id_of("Shuriken Flip")])
    u = body(s, 0, base_loc(0), 3, ready=True)
    act(s, A.A_PLAY, 0, 0)
    choose(s, -1)
    choose(s, bf_loc(1))
    choose(s, u)
    run(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(1) and int(s.perms[u, P_READY]) == 1


@case(12070, "an empowered Gangplank chosen by Star-Crossed stays and gets +3")
def _():
    need("Gangplank, Naval", "Star-Crossed")
    s = fresh(seat=1, hand=[T.id_of("Star-Crossed")])
    gp = s.add_permanent(T.id_of("Gangplank, Naval"), 0, base_loc(0))
    s.set_flag(gp, F_EMPOWERED)
    mine = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Star-Crossed", mine, gp)
    run(s)
    assert alive(s, gp) and combat.might(s, T, gp) == 9 and not alive(s, mine)


@case(12072, "Decree of Unity can only choose a Chaos gear")
def _():
    need("Decree of Unity", "Seal of Discord", "Frigid Jewel")
    s = fresh(hand=[T.id_of("Decree of Unity")])
    chaos = s.add_permanent(T.id_of("Seal of Discord"), 1, base_loc(1))
    other = s.add_permanent(T.id_of("Frigid Jewel"), 1, base_loc(1))
    assert T.domain_mask[T.id_of("Seal of Discord")] & 4 and not \
        T.domain_mask[T.id_of("Frigid Jewel")] & 4
    act(s, A.A_PLAY, 0, 0)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert chaos in offered and other not in offered, offered


@case(12075, "Spinning Axe's Equip cannot be used on the opponent's turn")
def _():
    need("Spinning Axe", "Discipline")
    s = fresh(seat=1, hand=[T.id_of("Discipline")])
    s.add_permanent(T.id_of("Spinning Axe"), 0, base_loc(0), ready=True)
    body(s, 0, base_loc(0), 3)
    u = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Discipline", u)
    pass_priority_to(s, 0)
    assert A.A_ACTIVATE not in kinds(s, 0)


@case(12080, "a Flow spell with no speed keyword cannot be played on the opponent's turn")
def _():
    need("Perfect Execution", "Discipline")
    s = fresh(seat=1, hand=[T.id_of("Discipline")])
    s.trash[0, 0], s.n_trash[0] = T.id_of("Perfect Execution"), 1
    body(s, 0, base_loc(0), 3)
    u = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Discipline", u)
    pass_priority_to(s, 0)
    assert A.A_PLAY_FLOW not in kinds(s, 0)


@case(12097, "Temporal Breach on your unit at your own battlefield starts no showdown")
def _():
    need("Temporal Breach")
    s = fresh()
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Temporal Breach"], 0, [u], -1, True)
    run(s)
    assert int(s.showdown_bf) < 0 and int(s.bf_ctrl[0]) == 0 and units(s, 0, bf_loc(0))


@case(12101, "burning Flame Chompers is not discarding it")
def _():
    need("Flame Chompers", "Death Mark")
    s = fresh()
    s.deck[0, :3] = [T.id_of("Flame Chompers")] * 3
    rsv.resolve(s, T, V1, SPECS["Death Mark"], 0, [base_loc(0)], -1, True)
    A._settle(s, T, V1)
    assert s.pend_may < 0 and "Flame Chompers" not in chain_names(s) and s.n_trig == 0


@case(12103, "Stupefy on your empowered Gangplank with an empowered Mel: just +3")
def _():
    need("Stupefy", "Gangplank, Naval", "Mel, Newly Awakened")
    s = fresh()
    mel = s.add_permanent(T.id_of("Mel, Newly Awakened"), 0, base_loc(0))
    s.set_flag(mel, F_EMPOWERED)
    gp = s.add_permanent(T.id_of("Gangplank, Naval"), 0, base_loc(0))
    s.set_flag(gp, F_EMPOWERED)
    rsv.resolve(s, T, V1, SPECS["Stupefy"], 0, [gp], -1, True)
    assert combat.might(s, T, gp) == 9, combat.might(s, T, gp)


@case(12107, "Kayle, Justified may be Empowered a second and third time")
def _():
    need("Kayle, Justified")
    s = fresh()
    k = s.add_permanent(T.id_of("Kayle, Justified"), 0, base_loc(0))
    for n in (1, 2, 3):
        act(s, A.A_ACTIVATE, None, 0)
        run(s)
        assert s.empower_count(k) == n, (n, s.empower_count(k))
    assert combat.might(s, T, k) == 9
    assert A.A_ACTIVATE not in kinds(s, 0), "three is the limit"


@case(12108, "a Temporal Breached defender comes back as the defender")
def _():
    need("Temporal Breach")
    s = fresh()
    give(s, 1, "Smoke Screen")                        # keeps the showdown open
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 3)
    a = body(s, 0, base_loc(0), 5, ready=True)
    attack(s, 0, 0, a)
    assert s.showdown_bf == 0 and int(s.attacker) == 0
    rsv.resolve(s, T, V1, SPECS["Temporal Breach"], 1, [d], -1, True)
    A._settle(s, T, V1)
    assert int(s.attacker) == 0 and int(s.bf_ctrl[0]) == 1


@case(12110, "Ivern - Friend to All counts tags on units anywhere, base included")
def _():
    need("Ivern - Friend to All")
    s = fresh()
    iv = s.add_permanent(T.id_of("Ivern - Friend to All"), 0, base_loc(0), ready=True)
    from rl.engine.effects import GRANTABLE_TAGS
    s.tag_grant[iv] = GRANTABLE_TAGS.index("Bird")
    cat, dog, poro = (T.id_of(n) for n in ("Fretful Feline", "Hungry Wolf", "Loyal Poro"))
    for c in (cat, dog, poro):
        s.add_permanent(c, 0, base_loc(0))
    attack(s, 0, 0, iv)
    run(s, picking())
    assert int(s.points[0]) == 2, int(s.points[0])


@case(12122, "Astral Heron as your first card at a battlefield discounts the next")
def _():
    need("Astral Heron")
    s = fresh(hand=[T.id_of("Astral Heron")], runes=9)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Astral Heron", bf_loc(0))
    run(s)
    assert list(s.next_discount[0]) == [2, 2]


@case(12124, "Renekton, Brute's +1 cannot be activated on the opponent's turn")
def _():
    need("Renekton, Brute", "Discipline")
    s = fresh(seat=1, hand=[T.id_of("Discipline")])
    s.add_permanent(T.id_of("Renekton, Brute"), 0, base_loc(0))
    u = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Discipline", u)
    pass_priority_to(s, 0)
    assert A.A_ACTIVATE not in kinds(s, 0)


@case(12130, "Defy on a spell played with Flow: it is banished")
def _():
    need("Defy", "Public Execution")
    s = fresh(runes=12)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Public Execution"), 1
    give(s, 1, "Defy")
    mine = body(s, 0, base_loc(0), 5)
    foe = body(s, 1, base_loc(1), 3)
    act(s, A.A_PLAY_FLOW, None, 0)
    choose(s, mine)
    choose(s, foe)
    cast(s, 1, "Defy", top_uid(s))
    run(s)
    assert alive(s, foe) and int(s.n_banished[0]) == 1 and int(s.n_trash[0]) == 0


@case(12132, "an empowered Applied Researchers also discounts a Repeat")
def _():
    need("Applied Researchers", "Frigid Touch")
    s = fresh(hand=[T.id_of("Frigid Touch")], runes=12)
    ar = s.add_permanent(T.id_of("Applied Researchers"), 0, base_loc(0))
    s.set_flag(ar, F_EMPOWERED)
    u = body(s, 1, base_loc(1), 9)
    before = ready_runes(s, 0)
    cast(s, 0, "Frigid Touch", u, u, repeat=True)
    run(s)
    assert before - ready_runes(s, 0) == 3, before - ready_runes(s, 0)


@case(12134, "two Mech tokens from Ferrous Forerunner: two Pridestalker triggers")
def _():
    need("Rengar - Pridestalker", "Ferrous Forerunner")
    s = fresh()
    s.legend[0] = T.id_of("Rengar - Pridestalker")
    ff = s.add_permanent(T.id_of("Ferrous Forerunner"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    combat.destroy(s, T, ff)
    run(s, picking(u))
    assert len(tokens(s, 0)) == 2 and combat.might(s, T, u) == 5, combat.might(s, T, u)


@case(12138, "an enemy's Amateur Recital cannot choose Baron Nashor")
def _():
    need("Amateur Recital", "Baron Nashor")
    s = fresh()
    s.bf_card[0] = T.id_of("Amateur Recital")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    bn = s.add_permanent(T.id_of("Baron Nashor"), 1, bf_loc(1))
    s.bf_ctrl[1] = 1
    from rl.engine.effects import BF_ABILITIES
    ab = BF_ABILITIES["Amateur Recital"][0]
    from rl.engine.state import bf_src
    assert bn not in rsv.legal_targets(s, T, ab, 0, 0, [], -1, source=bf_src(0))


@case(12142, "Shuriken Flip whose enemy was Retreated still moves your unit")
def _():
    need("Shuriken Flip")
    s = fresh(hand=[T.id_of("Shuriken Flip")])
    foe = body(s, 1, bf_loc(0), 3)
    s.bf_ctrl[0] = 1
    u = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, 0, 0)
    choose(s, foe)
    choose(s, bf_loc(1))
    choose(s, u)
    combat.return_to_hand(s, T, foe)
    run(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(1)


@case(12145, "Threshold of the Gray adds nothing on a conquer with no combat")
def _():
    need("Threshold of the Gray")
    s = fresh()
    s.bf_card[0] = T.id_of("Threshold of the Gray")
    u = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, u)
    run(s, picking())
    assert int(s.pool_energy[0]) == 0 and int(s.pool_energy[1]) == 0


@case(12146, "declining Sunken Temple's pay-to-draw leaves nothing on the Chain")
def _():
    need("Sunken Temple")
    s = fresh()
    s.bf_card[0] = T.id_of("Sunken Temple")
    u = body(s, 0, base_loc(0), 5, ready=True)
    attack(s, 0, 0, u)
    for _ in range(10):
        if s.pend_may >= 0 or any(a.kind == A.A_DECLINE for a in A.legal_actions(s, T, V1, 0)):
            break
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who)
        if not legal:
            break
        A.apply(s, T, V1, next((a for a in legal if a.kind in (A.A_ORDER, A.A_PASS)), legal[0]))
    act(s, A.A_DECLINE, None, 0)
    A._settle(s, T, V1)
    assert "Sunken Temple" not in chain_names(s) and int(s.n_hand[0]) == 0


@case(12147, "Atakhan's attack makes the defender kill a unit -- Ruin Runner included")
def _():
    need("Atakhan", "Ruin Runner")
    s = fresh()
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    rr = s.add_permanent(T.id_of("Ruin Runner"), 1, bf_loc(0))
    at = s.add_permanent(T.id_of("Atakhan"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, at)
    run(s, picking(rr), stop=lambda s: not alive(s, rr) or (s.n_chain == 0 and s.n_trig == 0
                                                            and s.showdown_bf < 0))
    assert not alive(s, rr)


@case(12174, "Dragon Roost cannot let Perched Grimwyrm be played where it wasn't conquered")
def _():
    need("Perched Grimwyrm", "Dragon Roost")
    s = fresh(hand=[T.id_of("Perched Grimwyrm")], runes=12)
    s.bf_card[0] = T.id_of("Dragon Roost")
    assert "Perched Grimwyrm" not in hand_plays(s, 0)


@case(12183, "Tideturner in answer to Vex's trigger: the unit is still stunned")
def _():
    need("Tideturner", "Vex - Apathetic")
    s = fresh(hand=[VANILLA])
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    cast(s, 0, "Shipyard Skulker", bf_loc(0))
    new = [i for i in units(s, 0) if int(s.perms[i, P_LOC]) == bf_loc(0)][-1]
    assert "Vex - Apathetic" in chain_names(s) or s.n_trig
    A._settle(s, T, V1)
    tt = s.add_permanent(T.id_of("Tideturner"), 0, base_loc(0))
    rsv.resolve(s, T, V1, ABILITIES["Tideturner"][0], 0, [new], -1, False, source=tt)
    run(s)
    assert s.has_flag(new, F_STUNNED) and int(s.perms[new, P_LOC]) == base_loc(0)


@case(12187, "Hard Bargain paid: Rampage with its extra cost still gives +2")
def _():
    need("Hard Bargain", "Rampage")
    s = fresh(hand=[T.id_of("Rampage")], runes=12)
    give(s, 1, "Hard Bargain")
    mine = body(s, 0, base_loc(0), 3)
    foe = body(s, 1, base_loc(1), 9)
    act(s, A.A_PLAY_REPEAT, 0, 0)
    choose(s, mine)
    choose(s, foe)
    cast(s, 1, "Hard Bargain", top_uid(s))
    run(s, picking())
    assert combat.might(s, T, mine) == 5 and int(s.perms[foe, P_DMG]) == 5


@case(12188, "Gust the unit a Spinning Axe is attaching to: the Axe enters unattached")
def _():
    need("Spinning Axe", "Gust")
    s = fresh(hand=[T.id_of("Spinning Axe")])
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Spinning Axe", base_loc(0))
    choose(s, u)                                       # Quick-Draw's attach trigger
    assert chain_names(s) == ["Spinning Axe"]
    combat.return_to_hand(s, T, u)
    run(s, picking())
    ax = perm_of(s, "Spinning Axe")
    assert ax and int(s.perms[ax[0], P_ATTACHED_TO]) < 0


@case(12189, "Back Off on your own Irelia, then Defy it: she keeps the +1")
def _():
    need("Back Off", "Defy", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("Back Off"), T.id_of("Defy")], runes=12)
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0))
    cast(s, 0, "Back Off", ir)
    run(s, stop=lambda s: s.n_chain and chain_names(s)[-1] == "Back Off" and s.n_trig == 0)
    uid = top_uid(s)
    cast(s, 0, "Defy", uid)
    run(s)
    assert combat.might(s, T, ir) == 5 and not s.has_flag(ir, F_STUNNED)


@case(12199, "Public Execution needs an enemy with less Might than the friendly unit")
def _():
    need("Public Execution")
    s = fresh(hand=[T.id_of("Public Execution")])
    mine = body(s, 0, base_loc(0), 4)
    small = body(s, 1, base_loc(1), 3)
    same = body(s, 1, base_loc(1), 4)
    act(s, A.A_PLAY, 0, 0)
    choose(s, mine)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert small in offered and same not in offered, offered


@case(12202, "Flurry of Blades with an enemy Elder Dragon kills Baron Nashor")
def _():
    need("Flurry of Blades", "Elder Dragon", "Baron Nashor")
    s = fresh(seat=1)
    s.add_permanent(T.id_of("Elder Dragon"), 1, base_loc(1))
    bn = s.add_permanent(T.id_of("Baron Nashor"), 0, bf_loc(0))
    rsv.resolve(s, T, V1, SPECS["Flurry of Blades"], 1, [], -1, True)
    A._settle(s, T, V1)
    assert not alive(s, bn)


@case(12204, "Cull the Weak can be played with an empty board")
def _():
    need("Cull the Weak")
    s = fresh(hand=[T.id_of("Cull the Weak")])
    assert "Cull the Weak" in hand_plays(s, 0)


@case(12212, "Resonating Strike moving Astral Heron to a battlefield as your first card")
def _():
    need("Astral Heron", "Resonating Strike")
    s = fresh(hand=[T.id_of("Resonating Strike")])
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    her = s.add_permanent(T.id_of("Astral Heron"), 0, base_loc(0))
    cast(s, 0, "Resonating Strike", bf_loc(0), her)
    run(s)
    assert int(s.perms[her, P_LOC]) == bf_loc(0) and list(s.next_discount[0]) == [2, 2]


@case(12216, "an attached Spinning Axe has no Equip to use")
def _():
    need("Spinning Axe")
    s = fresh()
    u = body(s, 0, base_loc(0), 3)
    body(s, 0, base_loc(0), 3)
    ax = s.add_permanent(T.id_of("Spinning Axe"), 0, base_loc(0), ready=True)
    s.attach(ax, u)
    assert A.A_ACTIVATE not in kinds(s, 0)


@case(12219, "Star-Crossed whose friendly unit left still returns the enemy")
def _():
    need("Star-Crossed")
    s = fresh(hand=[T.id_of("Star-Crossed")])
    mine = body(s, 0, base_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Star-Crossed", mine, foe)
    combat.destroy(s, T, mine)
    run(s)
    assert not alive(s, foe) and int(s.n_hand[1]) == 1


@case(12224, "Bellows Breath's 1 damage, then Thousand-Tailed Watcher: the Herder dies")
def _():
    need("Bellows Breath", "Thousand-Tailed Watcher", "Stellacorn Herder")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=12)
    h = s.add_permanent(T.id_of("Stellacorn Herder"), 1, base_loc(1))
    rsv.resolve(s, T, V1, SPECS["Bellows Breath"], 0, [h, -1, -1], -1, True)
    assert alive(s, h) and int(s.perms[h, P_DMG]) == 1
    cast(s, 0, "Thousand-Tailed Watcher", base_loc(0))
    run(s, picking(accept=False))
    assert not alive(s, h)


@case(12228, "Tideturner swapping Elder Dragon's chosen unit away: it takes nothing")
def _():
    need("Elder Dragon", "Tideturner")
    s = fresh(hand=[T.id_of("Elder Dragon")], runes=12)
    s.bf_ctrl[0] = 1
    target = body(s, 1, bf_loc(0), 3)
    s.perms[target, P_DMG] = 0
    act(s, A.A_PLAY, 0, 0)
    choose(s, base_loc(0))
    run(s, picking(target), stop=lambda s: s.n_chain and chain_names(s)[-1] == "Elder Dragon"
        and s.pend_slot < 0)
    tt = s.add_permanent(T.id_of("Tideturner"), 1, base_loc(1))
    rsv.resolve(s, T, V1, ABILITIES["Tideturner"][0], 1, [target], -1, False, source=tt)
    run(s)
    assert alive(s, target) and int(s.perms[target, P_DMG]) == 0


@case(12230, "Punch First cannot answer a Rampage on the Chain")
def _():
    need("Punch First", "Rampage")
    s = fresh(hand=[T.id_of("Rampage")])
    give(s, 1, "Punch First")
    mine = body(s, 0, base_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Rampage", mine, foe)
    pass_priority_to(s, 1)
    assert "Punch First" not in hand_plays(s, 1)
