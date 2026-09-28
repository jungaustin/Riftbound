"""RiftJudge batch 15 -- unused questions from 10854-10997."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_EMPOWERED, F_BUFFED, P_ATTACHED_TO, P_MIGHT_MOD
from rl.engine.effects import ABILITIES, pack_trash


def ready_runes(s, seat):
    return int(s.runes_ready[seat].sum())


@case(10995, "a spell whose only target became illegal still counts for Ravenbloom Student")
def _():
    need("Ravenbloom Student", "Gust")
    s = fresh(hand=[T.id_of("Gust")])
    st = s.add_permanent(T.id_of("Ravenbloom Student"), 0, base_loc(0))
    foe = body(s, 1, bf_loc(0), 3)
    s.bf_ctrl[0] = 1
    cast(s, 0, "Gust", foe)
    rsv.resolve(s, T, V1, SPECS["Discipline"], 1, [foe], -1, True)   # now 5 Might
    run(s)
    assert alive(s, foe) and combat.might(s, T, st) == 3


@case(10994, "Grim Apothecary played to a battlefield may return itself")
def _():
    need("Grim Apothecary")
    s = fresh(hand=[T.id_of("Grim Apothecary")])
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Grim Apothecary", bf_loc(0))
    ga = perm_of(s, "Grim Apothecary")[0]
    assert ga in targets_offered(s, 0)


@case(10984, "Moonfall pulling a second defender in turns Master Yi's +2 off")
def _():
    need("Moonfall", "Master Yi - Wuju Bladesman")
    s = fresh(hand=[T.id_of("Moonfall")])
    s.legend[1], s.legend_ready[1] = T.id_of("Master Yi - Wuju Bladesman"), 1
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    yi = body(s, 1, bf_loc(0), 3)
    other = body(s, 1, base_loc(1), 3)
    a = body(s, 0, base_loc(0), 5, ready=True)
    attack(s, 0, 0, a)
    assert s.showdown_bf == 0 and combat.might(s, T, yi) == 5
    pass_priority_to(s, 0)
    cast(s, 0, "Moonfall", bf_loc(0), other)
    run(s, stop=lambda s: s.n_chain == 0)
    assert combat.might(s, T, yi) == 1, combat.might(s, T, yi)


@case(10980, "Jae Medarda chosen by an opponent's spell: its controller draws nothing")
def _():
    need("Jae Medarda", "Discipline")
    s = fresh(seat=1, hand=[T.id_of("Discipline")])
    jae = s.add_permanent(T.id_of("Jae Medarda"), 0, base_loc(0))
    cast(s, 1, "Discipline", jae)
    run(s)
    assert int(s.n_hand[0]) == 0
    s2 = fresh(hand=[T.id_of("Discipline")])
    jae2 = s2.add_permanent(T.id_of("Jae Medarda"), 0, base_loc(0))
    cast(s2, 0, "Discipline", jae2)
    run(s2)
    assert int(s2.n_hand[0]) == 2, "its own spell: Jae's draw and Discipline's"


@case(10977, "Star-Crossed on Leona, Determined in answer to her attack: no stun")
def _():
    need("Leona, Determined", "Star-Crossed")
    s = fresh()
    give(s, 1, "Star-Crossed")
    s.bf_ctrl[0] = 1
    d = body(s, 1, bf_loc(0), 3)
    le = s.add_permanent(T.id_of("Leona, Determined"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, le)
    run(s, picks(d), stop=lambda s: s.n_chain and chain_names(s)[-1] == "Leona, Determined"
        and s.pend_slot < 0)
    cast(s, 1, "Star-Crossed", d, le)
    run(s, stop=lambda s: "Leona, Determined" not in chain_names(s))
    assert not s.has_flag(d, F_STUNNED)


@case(10973, "Relentless Pursuit moves an exhausted unit")
def _():
    need("Relentless Pursuit")
    s = fresh(hand=[T.id_of("Relentless Pursuit")])
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Relentless Pursuit", u, bf_loc(0), -1)
    run(s, picking(accept=False))                      # stay after conquering
    assert int(s.perms[u, P_LOC]) == bf_loc(0) and int(s.perms[u, P_READY]) == 0


@case(10971, "Fiora - Peerless doubles Might that includes her Equipment")
def _():
    need("Fiora - Peerless", "B.F. Sword")
    s = fresh()
    give(s, 1, "Smoke Screen")
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 1)
    fi = s.add_permanent(T.id_of("Fiora - Peerless"), 0, base_loc(0), ready=True)
    g = s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    s.attach(g, fi)
    m = combat.might(s, T, fi)
    attack(s, 0, 0, fi)
    run(s, stop=lambda s: "Fiora - Peerless" not in chain_names(s) and s.n_trig == 0
        and s.pend_slot < 0)
    assert combat.might(s, T, fi) == 2 * m, (m, combat.might(s, T, fi))


@case(10962, "Imperial Decree + a Repeated Bellows Breath: Guardian Angel saves only once")
def _():
    need("Imperial Decree", "Bellows Breath", "Guardian Angel")
    s = fresh(hand=[T.id_of("Bellows Breath")], runes=12)
    s.bf_ctrl[0] = 1
    ir = body(s, 1, bf_loc(0), 9)
    ga = s.add_permanent(T.id_of("Guardian Angel"), 1, bf_loc(0))
    s.attach(ga, ir)
    rsv.resolve(s, T, V1, SPECS["Imperial Decree"], 0, [], -1, True)
    act(s, A.A_PLAY_REPEAT, 0, 0)
    for c in (ir, -1, -1, ir, -1, -1):
        choose(s, c)
    run(s)
    assert not alive(s, ir) and not alive(s, ga)


@case(10952, "Deathgrip whose killed unit was removed still draws 1")
def _():
    need("Deathgrip")
    s = fresh(hand=[T.id_of("Deathgrip")])
    a = body(s, 0, base_loc(0), 3)
    b = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Deathgrip", a, b)
    combat.return_to_hand(s, T, a)
    run(s)
    assert int(s.n_hand[0]) == 2 and combat.might(s, T, b) == 3


@case(10942, "Piercing Light's first target killed in answer: the second still takes 2")
def _():
    need("Piercing Light", "Hidden Blade")
    s = fresh(hand=[T.id_of("Piercing Light")])
    s.bf_ctrl[0] = 1
    first = body(s, 1, bf_loc(0), 5)
    second = body(s, 1, base_loc(1), 5)
    cast(s, 0, "Piercing Light", first, second)
    rsv.resolve(s, T, V1, SPECS["Hidden Blade"], 1, [first], -1, True)
    run(s)
    assert int(s.perms[second, P_DMG]) == 2


@case(10940, "Void Seeker's 4 on Darius, then The List's -2: he dies")
def _():
    need("Void Seeker", "The List", "Darius - Trifarian")
    from rl.engine.effects import tag_vocab
    s = fresh()
    d = s.add_permanent(T.id_of("Darius - Trifarian"), 1, bf_loc(0))
    s.bf_ctrl[0] = 1
    rsv.resolve(s, T, V1, SPECS["Void Seeker"], 0, [d], -1, True)
    assert alive(s, d)
    g = s.add_permanent(T.id_of("The List"), 0, base_loc(0), ready=True)
    s.named[g] = tag_vocab(T).index("Noxus")
    act(s, A.A_ACTIVATE, None, 0)
    run(s, picking(d))
    assert not alive(s, d)


@case(10939, "Retreat whose unit was Sacrificed first: no rune is channeled")
def _():
    need("Retreat", "Sacrifice")
    s = fresh(hand=[T.id_of("Retreat")])
    rune_deck(s)
    u = body(s, 0, base_loc(0), 5)
    before = runes(s, 0)
    cast(s, 0, "Retreat", u)
    after_cost = runes(s, 0)
    combat.destroy(s, T, u)
    run(s)
    assert runes(s, 0) == after_cost, (before, after_cost, runes(s, 0))


@case(10935, "Desert's Call's Sand Soldier: base or a battlefield you control, not an open one")
def _():
    need("Desert's Call")
    s = fresh(hand=[T.id_of("Desert's Call")])
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    act(s, A.A_PLAY, 0, 0)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert offered == {base_loc(0), bf_loc(0)}, offered


@case(10933, "Ride the Wind cannot move a unit to where it already is")
def _():
    need("Ride The Wind")
    s = fresh(hand=[T.id_of("Ride The Wind")])
    u = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, 0, 0)
    choose(s, u)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert base_loc(0) not in offered and bf_loc(0) in offered, offered


@case(10929, "Solari Shieldbearer can be played with no unit to stun")
def _():
    need("Solari Shieldbearer")
    s = fresh(hand=[T.id_of("Solari Shieldbearer")])
    assert "Solari Shieldbearer" in hand_plays(s, 0)


@case(10928, "Tactical Retreat in answer to the Temporary kill saves the unit")
def _():
    need("Tactical Retreat", "Sprite Call")
    s = fresh(seat=1)
    give(s, 0, "Tactical Retreat")
    s.bf_ctrl[0] = 0
    rsv.resolve(s, T, V1, SPECS["Sprite Call"], 0, [bf_loc(0)], -1, True)
    act(s, A.A_END_TURN, None, 1)
    saved = []

    def pref(s, who, legal):
        if who == 0 and not saved and any(a.kind == A.A_PLAY for a in legal) and s.n_chain:
            saved.append(1)
            act(s, A.A_PLAY, hand_index(s, 0, "Tactical Retreat"), 0)
            spr = tokens(s, 0)
            return next(a for a in A.legal_actions(s, T, V1, 0)
                        if a.kind == A.A_TARGET and a.arg == spr[0])
        return None
    run(s, pref, stop=lambda s: int(s.active) == 0 and s.phase == MAIN
        and s.n_chain == 0 and s.n_trig == 0)
    assert saved and tokens(s, 0), "healed, exhausted and recalled instead"


@case(10895, "Grim Apothecary may return a friendly unit at another battlefield")
def _():
    need("Grim Apothecary")
    s = fresh(hand=[T.id_of("Grim Apothecary")])
    s.bf_ctrl[0] = s.bf_ctrl[1] = 0
    body(s, 0, bf_loc(0), 3)
    far = body(s, 0, bf_loc(1), 3)
    cast(s, 0, "Grim Apothecary", bf_loc(0))
    assert far in targets_offered(s, 0)


@case(10893, "Showstopper on an already buffed unit still moves it")
def _():
    need("Showstopper")
    s = fresh(hand=[T.id_of("Showstopper")])
    u = body(s, 0, base_loc(0), 3)
    s.set_flag(u, F_BUFFED)
    cast(s, 0, "Showstopper", u, bf_loc(0))
    run(s)
    assert int(s.perms[u, P_LOC]) == bf_loc(0) and combat.might(s, T, u) == 4


@case(10889, "Lonely Poro beside a Determined Sentry did not die alone: no draw")
def _():
    need("Lonely Poro", "Determined Sentry", "Bellows Breath")
    s = fresh(seat=1, hand=[T.id_of("Bellows Breath")], runes=12)
    lp = s.add_permanent(T.id_of("Lonely Poro"), 0, base_loc(0))
    ds = s.add_permanent(T.id_of("Determined Sentry"), 0, base_loc(0))
    act(s, A.A_PLAY_REPEAT, 0, 1)
    for c in (lp, ds, -1, lp, -1, -1):
        choose(s, c)
    run(s)
    assert not alive(s, lp) and not alive(s, ds) and int(s.n_hand[0]) == 0


@case(10884, "Switcheroo cannot be played with only one unit at a battlefield")
def _():
    need("Switcheroo")
    s = fresh(hand=[T.id_of("Switcheroo")])
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    assert "Switcheroo" not in hand_plays(s, 0)


@case(10868, "Daisy! costs 1 less per distinct animal tag, not per unit")
def _():
    need("Daisy!")
    s = fresh(hand=[T.id_of("Daisy!")], runes=12)
    for n in ("Loyal Poro", "Loyal Poro", "Loyal Poro", "Fretful Feline"):
        s.add_permanent(T.id_of(n), 0, base_loc(0))
    from rl.engine.cost import effective_energy
    assert effective_energy(s, T, 0, T.id_of("Daisy!")) == int(T.energy[T.id_of("Daisy!")]) - 2


@case(10863, "Tideturner moving Drag Under's target to another battlefield: it still dies")
def _():
    need("Drag Under", "Tideturner")
    s = fresh(hand=[T.id_of("Drag Under")], runes=9)
    s.bf_ctrl[0] = s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(0), 3)
    tt = s.add_permanent(T.id_of("Tideturner"), 1, bf_loc(1))
    cast(s, 0, "Drag Under", u)
    rsv.resolve(s, T, V1, ABILITIES["Tideturner"][0], 1, [u], -1, False, source=tt)
    run(s)
    assert not alive(s, u)


@case(10861, "Singularity can be played with only one unit on the board")
def _():
    need("Singularity")
    s = fresh(hand=[T.id_of("Singularity")], runes=9)
    body(s, 0, base_loc(0), 3)
    assert "Singularity" in hand_plays(s, 0)


@case(10856, "Moonfall's -2 does not reach a unit that arrives afterwards")
def _():
    need("Moonfall")
    s = fresh()
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    rsv.resolve(s, T, V1, SPECS["Moonfall"], 0, [bf_loc(0), -1], -1, True)
    late = body(s, 1, bf_loc(0), 5)
    assert combat.might(s, T, late) == 5


@case(10855, "Arise!'s Sand Soldiers may be played to a battlefield you control")
def _():
    need("Arise!")
    s = fresh(hand=[T.id_of("Arise!")], runes=12)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    s.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0))
    cast(s, 0, "Arise!", bf_loc(0))
    run(s)
    assert len(tokens(s, 0, bf_loc(0))) == 2
