"""RiftJudge batch 14 -- unused questions from 10998-11251."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_EMPOWERED, P_ATTACHED_TO, P_MIGHT_MOD, P_EMPOWER
from rl.engine.effects import ABILITIES, pack_trash


def ready_runes(s, seat):
    return int(s.runes_ready[seat].sum())


@case(11247, "Soraka saves the unit killed for Atakhan's cost; the discount still applies")
def _():
    need("Atakhan", "Soraka - Wanderer")
    s = fresh(hand=[T.id_of("Atakhan")], runes=12)
    s.add_permanent(T.id_of("Soraka - Wanderer"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    before = ready_runes(s, 0)
    act(s, A.A_PLAY, 0, 0)
    for _ in range(4):
        legal = A.legal_actions(s, T, V1, 0)
        pick = next((a for a in legal if a.kind in _CHOICE_KINDS and a.arg == u), None)
        if pick is None:
            pick = next((a for a in legal if a.kind in (A.A_PLAY_AT,) and a.arg == base_loc(0)), None)
        if pick is None:
            break
        A.apply(s, T, V1, pick)
    run(s)
    assert alive(s, u) and int(s.perms[u, P_LOC]) == base_loc(0)
    assert perm_of(s, "Atakhan")
    assert before - ready_runes(s, 0) < int(T.energy[T.id_of("Atakhan")]), "discounted"


@case(11235, "Hidden Blade's target pulled home by Star Spring: no draw 2")
def _():
    need("Hidden Blade", "Star Spring")
    s = fresh(seat=1, hand=[T.id_of("Hidden Blade")])
    give(s, 0, "Shipyard Skulker")
    s.bf_card[0] = T.id_of("Star Spring")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 1, "Hidden Blade", u)
    # the defender plays a unit there; Star Spring sends the targeted one home
    rsv.resolve(s, T, V1, SPECS["Ride The Wind"], 0, [u, base_loc(0)], -1, True)
    run(s)
    assert alive(s, u) and int(s.n_hand[0]) == 1


@case(11206, "Soraka saves Baited Hook's unit: nothing was killed, so nothing is found")
def _():
    need("Baited Hook", "Soraka - Wanderer")
    s = fresh()
    s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
    s.add_permanent(T.id_of("Soraka - Wanderer"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3)
    s.deck[0, :5] = [T.id_of("Watchful Sentry")] * 5
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, u)
    run(s, picking(0))
    assert alive(s, u) and not perm_of(s, "Watchful Sentry")


@case(11201, "tokens have tags: The List naming Recruit can choose a Recruit token")
def _():
    need("The List", "Forge of the Future")
    from rl.engine.effects import tag_vocab
    s = fresh()
    g = s.add_permanent(T.id_of("The List"), 0, base_loc(0), ready=True)
    s.named[g] = tag_vocab(T).index("Recruit")
    f = s.add_permanent(T.id_of("Forge of the Future"), 1, base_loc(1))
    from rl.engine.chain import fire as _fire
    rsv.resolve(s, T, V1, ABILITIES["Forge of the Future"][0], 1, [], -1, False, source=f)
    tok = tokens(s, 1)[0]
    act(s, A.A_ACTIVATE, None, 0)
    assert tok in targets_offered(s, 0)


@case(11198, "Not So Fast counters Harnessed Dragon's kill aimed at your unit")
def _():
    need("Not So Fast", "Harnessed Dragon")
    s = fresh(hand=[T.id_of("Harnessed Dragon")], runes=12)
    give(s, 1, "Not So Fast")
    u = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Harnessed Dragon", base_loc(0))
    run(s, picks(u), stop=lambda s: s.n_chain and chain_names(s)[-1] == "Harnessed Dragon"
        and s.pend_slot < 0)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert alive(s, u)


@case(11193, "Moonfall to an open battlefield: you applied Contested, so you attack")
def _():
    need("Moonfall")
    s = fresh(hand=[T.id_of("Moonfall")])
    give(s, 1, "Smoke Screen")
    mine = body(s, 0, base_loc(0), 5, ready=True)
    foe = body(s, 1, base_loc(1), 3)
    attack(s, 0, 0, mine)
    assert s.showdown_bf == 0
    pass_priority_to(s, 0)
    cast(s, 0, "Moonfall", bf_loc(0), foe)
    run(s, stop=lambda s: int(s.perms[foe, P_LOC]) == bf_loc(0) and s.n_chain == 0)
    assert int(s.attacker) == 0


@case(11189, "Not So Fast counters Amateur Recital moving your unit")
def _():
    need("Not So Fast", "Amateur Recital")
    from rl.engine.effects import BF_ABILITIES
    from rl.engine.state import bf_src
    s = fresh()
    give(s, 1, "Not So Fast")
    s.bf_card[0] = T.id_of("Amateur Recital")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, bf_loc(1), 3)
    s.bf_ctrl[1] = 1
    chain_mod.queue(s, BF_ABILITIES["Amateur Recital"][0].trigger, bf_src(0), bf_loc(0), who=0)
    run(s, picks(theirs), stop=lambda s: s.n_chain and chain_names(s)[-1] == "Amateur Recital"
        and s.pend_slot < 0 and s.pend_may < 0)
    cast(s, 1, "Not So Fast", top_uid(s))
    run(s)
    assert int(s.perms[theirs, P_LOC]) == bf_loc(1)


@case(11184, "Vex - Cheerless in combat reduces the Deflect surcharge too")
def _():
    need("Vex - Cheerless", "Back Off", "Irelia, Fervent")
    s = fresh(hand=[T.id_of("Back Off")])
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    vx = s.add_permanent(T.id_of("Vex - Cheerless"), 0, base_loc(0), ready=True)
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 1, base_loc(1))
    attack(s, 0, 0, vx)
    assert s.showdown_bf == 0 and combat.in_combat(s, vx)
    pass_priority_to(s, 0)
    before = runes(s, 0)
    cast(s, 0, "Back Off", ir)
    assert runes(s, 0) == before, "the [A] off the total covers Irelia's Deflect"


@case(11159, "Defiant Dance taking a unit to 0 Might does not kill it")
def _():
    need("Defiant Dance")
    s = fresh()
    a = body(s, 0, base_loc(0), 3)
    b = body(s, 1, base_loc(1), 1)
    rsv.resolve(s, T, V1, SPECS["Defiant Dance"], 0, [a, b], -1, True)
    run(s)
    assert alive(s, b) and combat.might(s, T, b) == 0


@case(11149, "Star-Crossed on Azir - Sovereign in answer to his attack: tokens stay put")
def _():
    need("Azir - Sovereign", "Star-Crossed")
    s = fresh()
    give(s, 1, "Star-Crossed")
    s.bf_ctrl[0] = 1
    theirs = body(s, 1, bf_loc(0), 9)
    rsv.resolve(s, T, V1, SPECS["Sprite Call"], 0, [base_loc(0)], -1, True)
    tok = tokens(s, 0)[0]
    az = s.add_permanent(T.id_of("Azir - Sovereign"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, az)
    run(s, picks(tok, -1, -1, -1), stop=lambda s: s.n_chain and chain_names(s)[-1] == "Azir - Sovereign"
        and s.pend_slot < 0)
    mine = body(s, 1, base_loc(1), 3)
    cast(s, 1, "Star-Crossed", mine, az)
    run(s, stop=lambda s: "Azir - Sovereign" not in chain_names(s))
    assert int(s.perms[tok, P_LOC]) == base_loc(0)


@case(11144, "Abandoned Hall's +1 chooses the unit: Irelia, Fervent gets her +1 too")
def _():
    need("Abandoned Hall", "Irelia, Fervent", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")])
    s.bf_card[0] = T.id_of("Abandoned Hall")
    s.bf_ctrl[0] = 0
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, bf_loc(0))
    other = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", other)
    run(s, picking(ir))
    assert combat.might(s, T, ir) == 6, combat.might(s, T, ir)


@case(11136, "Mirror Image does not copy the gear on the chosen unit")
def _():
    need("Mirror Image", "B.F. Sword")
    s = fresh()
    u = body(s, 0, base_loc(0), 3)
    g = s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    s.attach(g, u)
    rsv.resolve(s, T, V1, SPECS["Mirror Image"], 0, [u], -1, True)
    A._settle(s, T, V1)
    tok = tokens(s, 0)[0]
    assert not s.attachments(tok) and combat.might(s, T, tok) == int(T.might[VANILLA])


@case(11111, "Unyielding Spirit does not stop Challenge: units deal that damage")
def _():
    need("Challenge", "Unyielding Spirit")
    s = fresh(hand=[T.id_of("Challenge")])
    mine = body(s, 0, base_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    rsv.resolve(s, T, V1, SPECS["Unyielding Spirit"], 1, [], -1, True)
    cast(s, 0, "Challenge", mine, foe)
    run(s)
    assert not alive(s, mine) and not alive(s, foe)


@case(11097, "Svellsongur on Ultrasoft Poro: two abilities, but one Exhaust between them")
def _():
    need("Svellsongur", "Ultrasoft Poro")
    s = fresh()
    s.bf_ctrl[0] = 0
    p = s.add_permanent(T.id_of("Ultrasoft Poro"), 0, bf_loc(0), ready=True)
    sv = s.add_permanent(T.id_of("Svellsongur"), 0, bf_loc(0))
    s.attach(sv, p)
    acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
    A.apply(s, T, V1, acts[0])
    run(s, picking(bf_loc(0)))
    assert len(tokens(s, 0)) == 2
    assert not [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE
                and a.arg in {x.arg for x in acts}], "the copy needs the same Exhaust"


@case(11074, "Bone Skewer plays their Thousand-Tailed Watcher: its -3 hits YOUR units")
def _():
    need("Bone Skewer", "Thousand-Tailed Watcher")
    s = fresh(hand=[T.id_of("Bone Skewer")])
    give(s, 1, "Thousand-Tailed Watcher")
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 6)
    cast(s, 0, "Bone Skewer", bf_loc(0))
    run(s, picking(0, accept=False))
    assert combat.might(s, T, mine) == 3


@case(11028, "Charm moving an enemy into your battlefield: they attack, you defend")
def _():
    need("Charm")
    s = fresh(hand=[T.id_of("Charm")])
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    foe = body(s, 1, base_loc(1), 3)
    cast(s, 0, "Charm", foe, bf_loc(0))
    run(s, stop=lambda s: s.showdown_bf >= 0 and s.n_chain == 0)
    assert int(s.attacker) == 1


@case(11013, "Forge of the Future's kill is a cost: it cannot recycle itself")
def _():
    need("Forge of the Future")
    s = fresh()
    s.trash[0, 0], s.n_trash[0] = VANILLA, 1
    s.add_permanent(T.id_of("Forge of the Future"), 0, base_loc(0), ready=True)
    act(s, A.A_ACTIVATE, None, 0)
    offered = targets_offered(s, 0)
    assert pack_trash(0, T.id_of("Forge of the Future")) not in offered, offered


@case(10999, "Beast Below can be played without another friendly unit")
def _():
    need("Beast Below")
    s = fresh(hand=[T.id_of("Beast Below")], runes=12)
    assert "Beast Below" in hand_plays(s, 0)
