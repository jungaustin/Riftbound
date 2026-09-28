"""RiftJudge batch 20 -- unused questions from 10166-10292."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_EMPOWERED, P_ATTACHED_TO, P_MIGHT_MOD
from rl.engine.effects import ABILITIES, pack_trash


@case(10292, "Meditation may exhaust the only attacker, and combat goes on")
def _():
    need("Meditation", "Ride The Wind")
    s = fresh(hand=[T.id_of("Meditation")], runes=9)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    a = body(s, 0, base_loc(0), 3, ready=True)
    cast(s, 0, "Ride The Wind", a, bf_loc(0))
    drain(s)
    assert int(s.showdown_bf) == 0 and int(s.perms[a, P_READY]) == 1
    cast(s, 0, "Meditation", repeat=True)
    run(s, picks(a), stop=lambda s: int(s.n_hand[0]) >= 2)
    assert int(s.n_hand[0]) == 2, "the optional cost was paid: draw 2"
    assert int(s.perms[a, P_READY]) == 0 and int(s.perms[a, P_LOC]) == bf_loc(0)
    assert int(s.showdown_bf) == 0, "exhausting an attacker does not end combat"


@case(10291, "playing Baron Nashor conquers the Baron Pit it creates")
def _():
    need("Baron Nashor")
    s = fresh(hand=[T.id_of("Baron Nashor")], runes=12)
    cast(s, 0, "Baron Nashor", base_loc(0))
    run(s, picking())
    pit = [i for i in range(len(s.bf_card)) if int(s.bf_card[i]) == T.id_of("Baron Pit")]
    assert pit, "the Baron Pit token was added"
    bn = perm_of(s, "Baron Nashor")
    assert bn and int(s.perms[bn[0], P_LOC]) == bf_loc(pit[0])
    assert int(s.points[0]) >= 1, int(s.points[0])


@case(10287, "Mindsplitter can discard Baron Nashor out of a hand")
def _():
    need("Mindsplitter", "Baron Nashor")
    s = fresh(hand=[T.id_of("Mindsplitter")], runes=12)
    give(s, 1, "Baron Nashor")
    cast(s, 0, "Mindsplitter", base_loc(0))
    run(s, picks(0))
    assert int(s.n_hand[1]) == 0 and int(s.n_trash[1]) == 1
    assert int(s.trash[1, 0]) == T.id_of("Baron Nashor")


@case(10283, "Upstage Comedy may be played on a unit that is already ready")
def _():
    need("Upstage Comedy")
    s = fresh(hand=[T.id_of("Upstage Comedy")])
    u = body(s, 0, base_loc(0), 3, ready=True)
    act(s, A.A_PLAY, hand_index(s, 0, "Upstage Comedy"), 0)
    assert u in targets_offered(s, 0)


@case(10281, "Sacrifice's kill on a unit under Tactical Retreat: full value")
def _():
    need("Sacrifice", "Tactical Retreat")
    s = fresh(hand=[T.id_of("Tactical Retreat")], runes=9)
    give(s, 0, "Sacrifice")
    rune_deck(s)
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 5)
    cast(s, 0, "Tactical Retreat", u)
    run(s)
    cast(s, 0, "Sacrifice", u)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_LOC]) == base_loc(0)
    assert int(s.n_hand[0]) == 2, "Sacrifice still drew 2"


@case(10278, "Tactical Retreat saves a [Temporary] unit from its own trigger")
def _():
    need("Sprite Call", "Tactical Retreat")
    s = fresh()
    sprite = _sprite_at(s, 0, 0)
    give(s, 0, "Tactical Retreat")
    s.runes_ready[0, :] = 6
    _next_own_turn(s)
    assert any("Sprite" in n for n in chain_names(s)) or s.n_chain, chain_names(s)
    cast(s, 0, "Tactical Retreat", sprite)
    run(s)
    assert alive(s, sprite)


@case(10277, "Kha'Zix's condition is read when it triggers: two enemies, no bonus")
def _():
    need("Kha'Zix - Mutating Horror", "Gust")
    s = fresh()
    s.bf_ctrl[0] = 1
    kz = s.add_permanent(T.id_of("Kha'Zix - Mutating Horror"), 1, bf_loc(0))
    a1 = body(s, 0, base_loc(0), 3, ready=True)
    a2 = body(s, 0, base_loc(0), 3, ready=True)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 6
    attack(s, 0, 0, a1, a2)
    assert "Kha'Zix - Mutating Horror" not in chain_names(s)
    cast(s, 1, "Gust", a1)
    fight(s)
    assert int(s.xp[1]) == 0, "the trigger never entered the chain"


@case(10176, "an Ambush after Kha'Zix's trigger does not take the bonus away")
def _():
    need("Kha'Zix - Mutating Horror", "Vi - Peacekeeper")
    s = fresh(runes=9)
    s.bf_ctrl[0] = 1
    s.add_permanent(T.id_of("Kha'Zix - Mutating Horror"), 1, bf_loc(0))
    a1 = body(s, 0, base_loc(0), 3, ready=True)
    give(s, 0, "Vi - Peacekeeper")
    attack(s, 0, 0, a1)
    assert "Kha'Zix - Mutating Horror" in chain_names(s)
    cast(s, 0, "Vi - Peacekeeper", bf_loc(0))
    fight(s)
    assert int(s.xp[1]) == 2, "the condition was true when it triggered"


@case(10273, "Facebreaker's friendly target dies: the enemy is still stunned")
def _():
    need("Facebreaker")
    s = fresh(hand=[T.id_of("Facebreaker")])
    u = body(s, 0, bf_loc(0), 3)
    e = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Facebreaker", u, e)
    combat.destroy(s, T, u)
    run(s)
    assert not alive(s, u) and s.has_flag(e, F_STUNNED)


@case(10269, "Jayce's gear may be played later in the same turn, for free")
def _():
    need("Jayce, Man of Progress", "Vanguard Armory", "Warmog's Armor")
    s = fresh(hand=[T.id_of("Jayce, Man of Progress")], runes=6)
    give(s, 0, "Vanguard Armory")
    g = s.add_permanent(T.id_of("Warmog's Armor"), 0, base_loc(0))
    cast(s, 0, "Jayce, Man of Progress", base_loc(0))
    run(s, picks(g))
    assert not alive(s, g)
    # its 7 Energy is ignored; its 1 Power is not, so one rune of its own
    # domain is all that is still owed
    dom = int(T.domain_mask[T.id_of("Vanguard Armory")]).bit_length() - 1
    s.runes_ready[0, :] = 0
    s.runes_ready[0, dom] = 1
    assert "Vanguard Armory" in hand_plays(s, 0), hand_plays(s, 0)


@case(10266, "Bone Skewer ignores Clockwork Keeper's optional cost too")
def _():
    need("Bone Skewer", "Clockwork Keeper")
    s = fresh(hand=[T.id_of("Bone Skewer")])
    give(s, 1, "Clockwork Keeper")
    s.runes_ready[1, :] = 0
    cast(s, 0, "Bone Skewer", bf_loc(0))
    run(s, picks(0))
    ck = perm_of(s, "Clockwork Keeper")
    assert ck and s.has_flag(ck[0], F_STUNNED)
    assert int(s.n_hand[1]) == 1, "the free draw off an ignored additional cost"
    assert int(s.runes_ready[1].sum()) == 0


@case(10264, "Star Spring's move may be declined")
def _():
    need("Star Spring", "Determined Sentry")
    s = fresh(hand=[T.id_of("Determined Sentry")])
    s.bf_card[0] = T.id_of("Star Spring")
    s.bf_ctrl[0] = 0
    keep = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Determined Sentry", bf_loc(0))
    run(s, picking(accept=False))
    assert int(s.perms[keep, P_LOC]) == bf_loc(0)


@case(10257, "Flash may choose a unit that is already in base")
def _():
    need("Flash")
    s = fresh(hand=[T.id_of("Flash")])
    u = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Flash"), 0)
    assert u in targets_offered(s, 0)


@case(10256, "Call to Battle can't move a unit to the battlefield it is on")
def _():
    need("Call to Battle")
    s = fresh(hand=[T.id_of("Call to Battle")], runes=6)
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    u = body(s, 0, bf_loc(0), 3)
    body(s, 1, base_loc(1), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Call to Battle"), 0)
    choose(s, u)
    offered = targets_offered(s, 0)
    assert bf_loc(0) not in offered and bf_loc(1) in offered, offered


@case(10255, "Friendship counts the tags among your units, once each")
def _():
    need("Friendship", "Crimson Pigeons", "Mutated Mouser", "Lonely Poro")
    s = fresh(hand=[T.id_of("Friendship")])
    for n in ("Crimson Pigeons", "Mutated Mouser", "Lonely Poro"):
        s.add_permanent(T.id_of(n), 0, base_loc(0))
    s.add_permanent(T.id_of("Crimson Pigeons"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Friendship", u)
    run(s)
    assert combat.might(s, T, u) == 6, combat.might(s, T, u)


@case(10252, "Sacrifice's additional cost is a kill Immortal Phoenix sees")
def _():
    need("Sacrifice", "Immortal Phoenix")
    s = fresh(hand=[T.id_of("Sacrifice")], runes=9)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Immortal Phoenix"), 1
    rune_deck(s)
    u = body(s, 0, base_loc(0), 5)
    cast(s, 0, "Sacrifice", u)
    run(s, picking(base_loc(0)))
    assert perm_of(s, "Immortal Phoenix"), "played from the trash"


@case(10251, "Discipline on Alpha Wildclaw makes the kill spell mistarget")
def _():
    need("Alpha Wildclaw", "Discipline", "Death from Below")
    s = fresh(seat=1, runes=9)
    s.bf_ctrl[0] = 0
    aw = s.add_permanent(T.id_of("Alpha Wildclaw"), 0, bf_loc(0))
    u = body(s, 0, bf_loc(0), 8)
    give(s, 0, "Discipline")
    give(s, 1, "Death from Below")
    s.runes_ready[1, :] = 9
    cast(s, 1, "Death from Below", u)
    cast(s, 0, "Discipline", aw)
    run(s)
    assert combat.might(s, T, aw) == 9 and alive(s, u), "8 < 9: no longer choosable"


@case(10250, "Mageseeker Warden does not stop Baron Nashor's replacement")
def _():
    need("Baron Nashor", "Mageseeker Warden")
    s = fresh(hand=[T.id_of("Baron Nashor")], runes=12)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Mageseeker Warden"), 1, bf_loc(1))
    assert "Baron Nashor" in hand_plays(s, 0)
    cast(s, 0, "Baron Nashor", base_loc(0))
    run(s, picking())
    pit = [i for i in range(len(s.bf_card)) if int(s.bf_card[i]) == T.id_of("Baron Pit")]
    bn = perm_of(s, "Baron Nashor")
    assert pit and bn and int(s.perms[bn[0], P_LOC]) == bf_loc(pit[0])


@case(10245, "Glasc Mixologist's Deathknell may revive at its own battlefield")
def _():
    need("Glasc Mixologist", "Determined Sentry")
    s = fresh()
    s.bf_ctrl[0] = 0
    g = s.add_permanent(T.id_of("Glasc Mixologist"), 0, bf_loc(0))
    s.trash[0, 0], s.n_trash[0] = T.id_of("Determined Sentry"), 1
    combat.destroy(s, T, g)
    run(s, picks(pack_trash(0, T.id_of("Determined Sentry")), bf_loc(0)))
    ds = perm_of(s, "Determined Sentry")
    assert ds and int(s.perms[ds[0], P_LOC]) == bf_loc(0)
    assert int(s.bf_ctrl[0]) == 0, "control was never lost mid-chain"


@case(10243, "Ahri - Alluring takes you from 6 to 8 on one battlefield")
def _():
    need("Ahri - Alluring")
    s = fresh()
    s.points[0] = 6
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Ahri - Alluring"), 0, bf_loc(0))
    _next_own_turn(s)
    run(s, picking())
    assert int(s.points[0]) == 8, int(s.points[0])
    assert s.check_winner(8) == 0


@case(10242, "Vex - Apathetic stuns a Reflection token as it is played")
def _():
    need("Vex - Apathetic", "Mirror Image")
    s = fresh(hand=[T.id_of("Mirror Image")], runes=6)
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Mirror Image", u)
    run(s)
    tok = tokens(s, 0)
    assert tok and s.has_flag(tok[-1], F_STUNNED)


@case(10241, "Not So Fast is not offered against Bone Skewer")
def _():
    need("Bone Skewer", "Not So Fast")
    s = fresh(hand=[T.id_of("Bone Skewer")])
    give(s, 1, "Not So Fast")
    s.runes_ready[1, :] = 6
    body(s, 1, base_loc(1), 3)
    cast(s, 0, "Bone Skewer", bf_loc(0))
    pass_priority_to(s, 1)
    assert "Not So Fast" not in hand_plays(s, 1), hand_plays(s, 1)


@case(10240, "Piercing Light's second half lands after the first target leaves")
def _():
    need("Piercing Light")
    s = fresh(hand=[T.id_of("Piercing Light")], runes=9)
    s.bf_ctrl[1] = 1
    u1 = body(s, 1, bf_loc(0), 5)
    u2 = body(s, 1, bf_loc(0), 5)
    cast(s, 0, "Piercing Light", u1, u2)
    combat.return_to_hand(s, T, u1)
    run(s)
    assert int(s.perms[u2, P_DMG]) == 2, int(s.perms[u2, P_DMG])


@case(10239, "a Mirror Image copy gets neither the buff nor the gear")
def _():
    need("Mirror Image", "Warmog's Armor")
    s = fresh(hand=[T.id_of("Mirror Image")], runes=6)
    u = body(s, 0, base_loc(0), 3)
    g = s.add_permanent(T.id_of("Warmog's Armor"), 0, base_loc(0))
    s.attach(g, u)
    s.set_flag(u, F_BUFFED)
    before = combat.might(s, T, u)
    cast(s, 0, "Mirror Image", u)
    run(s)
    tok = tokens(s, 0)[-1]
    assert before > 3 and combat.might(s, T, tok) == 3, (before, combat.might(s, T, tok))
    assert int(s.perms[tok, P_ATTACHED_TO]) < 0 and not s.has_flag(tok, F_BUFFED)


@case(10200, "a Reflection token is not 0 Might: it copies the printed Might")
def _():
    need("Mirror Image", "Mindsplitter")
    s = fresh(hand=[T.id_of("Mirror Image")], runes=6)
    u = s.add_permanent(T.id_of("Mindsplitter"), 0, base_loc(0))
    cast(s, 0, "Mirror Image", u)
    run(s)
    tok = tokens(s, 0)[-1]
    assert combat.might(s, T, tok) == 7, combat.might(s, T, tok)
