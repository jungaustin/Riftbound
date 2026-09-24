"""RiftJudge batch 22 -- unused questions from 10166-10292 (third pass)."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_NO_MOVE, P_ATTACHED_TO
from rl.engine.effects import ABILITIES, pack_trash


@case(10271, "Meditation repeated by The Academy draws 2, then 1")
def _():
    need("Meditation", "The Academy")
    s = fresh(hand=[T.id_of("Meditation")], runes=9)
    # the state The Academy's hold trigger leaves behind
    s.next_spell_repeat_ply[0] = int(s.ply)
    u = body(s, 0, base_loc(0), 3, ready=True)
    kinds_now = {a.kind for a in A.legal_actions(s, T, V1, 0)}
    assert A.A_PLAY_BOTH in kinds_now, "pay the exhaust AND the Repeat"
    act(s, A.A_PLAY_BOTH, hand_index(s, 0, "Meditation"), 0)
    run(s, picks(u))
    assert int(s.n_hand[0]) == 3, int(s.n_hand[0])
    assert int(s.perms[u, P_READY]) == 0, "the cost was paid exactly once"


@case(10272, "Call to Glory's spent buff does not buy off the Repeat's cost")
def _():
    need("Call to Glory", "The Academy")
    s = fresh(hand=[T.id_of("Call to Glory")])
    s.next_spell_repeat_ply[0] = int(s.ply)
    u = body(s, 0, base_loc(0), 3)
    s.set_flag(u, F_BUFFED)
    dom = int(T.domain_mask[T.id_of("Call to Glory")]).bit_length() - 1
    s.runes_ready[0, :] = 0
    s.runes_ready[0, dom] = 2
    assert A.A_PLAY_BOTH not in {a.kind for a in A.legal_actions(s, T, V1, 0)}, \
        "two runes cannot pay a {3 energy} Repeat"
    s.runes_ready[0, dom] = 3
    act(s, A.A_PLAY_BOTH, hand_index(s, 0, "Call to Glory"), 0)
    run(s, picks(u, u))
    assert combat.might(s, T, u) == 9, combat.might(s, T, u)
    assert int(s.runes_ready[0].sum()) == 0, "the three went to the Repeat"
    assert not s.has_flag(u, F_BUFFED), "and the buff went to the spell's cost"


@case(10290, "Lillia's Sprite is played, so Vex - Apathetic stuns it")
def _():
    need("Lillia - Fae Fawn", "Vex - Apathetic")
    s = fresh()
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    li = s.add_permanent(T.id_of("Lillia - Fae Fawn"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, li)
    drain(s)
    sprite = [i for i in tokens(s, 0) if int(s.perms[i, P_LOC]) == base_loc(0)]
    assert sprite, "the Sprite is left where she moved FROM"
    assert s.has_flag(sprite[0], F_STUNNED), "Vex saw a unit being played"


@case(10289, "Elder Dragon's 1 damage kills a unit healed a moment earlier")
def _():
    need("Elder Dragon")
    s = fresh(hand=[T.id_of("Elder Dragon")], runes=12)
    foe = body(s, 1, base_loc(1), 6)
    s.perms[foe, P_DMG] = 3
    cast(s, 0, "Elder Dragon", base_loc(0))
    # the heal a Janna played in answer to the trigger would have done
    s.perms[foe, P_DMG] = 0
    run(s, picking(foe))
    assert not alive(s, foe), "any amount of your damage is enough, healed or not"


@case(10286, "at 7 points, holding one battlefield then conquering the other wins")
def _():
    need("Ride The Wind")
    s = fresh(runes=9)
    give(s, 0, "Ride The Wind")
    s.points[0] = 6
    s.bf_ctrl[0] = 0
    hold = s.add_permanent(VANILLA, 0, bf_loc(0))
    u = body(s, 0, base_loc(0), 3, ready=True)
    _next_own_turn(s)
    run(s, picking())
    assert int(s.points[0]) == 7 and int(s.bf_scored[0, 0]) == 1
    cast(s, 0, "Ride The Wind", u, bf_loc(1))
    run(s, picking())
    assert int(s.points[0]) == 8 and s.check_winner(8) == 0


@case(10282, "Ezreal, Prodigy does not discount Death from Below's Power")
def _():
    need("Ezreal, Prodigy", "Death from Below")
    s = fresh(hand=[T.id_of("Death from Below")], runes=9)
    s.add_permanent(T.id_of("Ezreal, Prodigy"), 0, base_loc(0))
    s.bf_ctrl[1] = 1
    small = body(s, 1, bf_loc(0), 3)
    other = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Death from Below", small)
    run(s)
    before = runes(s, 0)
    act(s, A.A_PLAY_FLOW, 0, 0)
    choose(s, other)
    run(s)
    assert not alive(s, other)
    assert runes(s, 0) == before - 1, "the {any rune} was still owed"


@case(10280, "Blade of the Ruined King kills at activation, and can mistarget")
def _():
    need("Blade of the Ruined King", "Star-Crossed")
    s = fresh(runes=9)
    brk = s.add_permanent(T.id_of("Blade of the Ruined King"), 0, base_loc(0))
    keeper = body(s, 0, base_loc(0), 3)
    fodder = body(s, 0, base_loc(0), 3)
    give(s, 1, "Star-Crossed")
    s.runes_ready[1, :] = 9
    body(s, 1, base_loc(1), 3)
    act(s, A.A_ACTIVATE, brk, 0)
    picked = [fodder, keeper]
    for want in picked:
        choose(s, want)
    assert not alive(s, fodder), "the kill is a cost, paid at activation"
    cast(s, 1, "Star-Crossed", perm_of(s, "Shipyard Skulker", 1)[0], keeper)
    run(s)
    assert not alive(s, keeper)
    assert int(s.perms[brk, P_ATTACHED_TO]) < 0, "the Equip had nothing to attach to"


@case(10274, "Lotus Trap halves what must be ASSIGNED to kill (see rejected.json)")
def _():
    need("Lotus Trap")
    s = fresh(runes=9)
    s.bf_ctrl[1] = 1
    d1 = body(s, 1, bf_loc(0), 4)
    assert combat.lethal_cost(s, T, d1) == 4
    rsv.resolve(s, T, V1, SPECS["Lotus Trap"], 1, [d1], -1, True)
    # 465.2.c.4.a, whose worked example IS this card: "the assigning player can
    # only choose to assign 1 or 2 damage to this unit ... the minimum applied
    # value such that the unit would take lethal damage in this way is 4".
    assert combat.lethal_cost(s, T, d1) == 2, combat.lethal_cost(s, T, d1)


@case(10263, "Azir - Sovereign may move a Reflection token that copied a unit")
def _():
    need("Azir - Sovereign", "Mirror Image")
    s = fresh(hand=[T.id_of("Mirror Image")], runes=12)
    az = s.add_permanent(T.id_of("Azir - Sovereign"), 0, base_loc(0), ready=True)
    u = body(s, 0, base_loc(0), 3)
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Mirror Image", u)
    run(s)
    tok = tokens(s, 0)[-1]
    attack(s, 0, 0, az)
    run(s, picks(tok), stop=lambda s: int(s.perms[tok, P_LOC]) == bf_loc(0))
    assert int(s.perms[tok, P_LOC]) == bf_loc(0), int(s.perms[tok, P_LOC])


@case(10262, "killing a Reflection copy of Atakhan pays all of Atakhan's cost")
def _():
    need("Atakhan", "Mirror Image")
    s = fresh(hand=[T.id_of("Mirror Image")], runes=12)
    at = s.add_permanent(T.id_of("Atakhan"), 0, base_loc(0))
    cast(s, 0, "Mirror Image", at)
    run(s)
    assert tokens(s, 0), "a Reflection copy of Atakhan"
    give(s, 0, "Atakhan")
    s.runes_ready[0, :] = 0
    assert "Atakhan" in hand_plays(s, 0), "10 Energy and 3 Power, all discounted"


@case(10260, "Abandon on your own spell makes Lilting Lullaby mistarget")
def _():
    need("Abandon", "Lilting Lullaby", "Discipline")
    s = fresh(hand=[T.id_of("Discipline")], runes=9)
    give(s, 0, "Abandon")
    give(s, 1, "Lilting Lullaby")
    s.runes_ready[1, :] = 9
    u = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Discipline", u)
    mine = top_uid(s)
    cast(s, 1, "Lilting Lullaby", mine)
    cast(s, 0, "Abandon", mine)
    run(s, picking(accept=False))
    assert int(s.no_spells[0]) == 0, "the counter instruction was ignored"
    assert T.id_of("Discipline") in list(s.hand[0, :int(s.n_hand[0])]), \
        "Abandon returns it to hand"


@case(10254, "a showdown trigger goes on the Chain before an attack trigger")
def _():
    need("Diana - Lunari", "Kha'Zix, Evolving Hunter")
    s = fresh(seat=1, runes=12)
    s.bf_ctrl[0] = 0
    s.add_permanent(T.id_of("Diana - Lunari"), 0, bf_loc(0))
    kz = s.add_permanent(T.id_of("Kha'Zix, Evolving Hunter"), 1,
                         base_loc(1), ready=True)
    attack(s, 1, 0, kz)
    names = chain_names(s)
    assert names[:2] == ["Diana - Lunari", "Kha'Zix, Evolving Hunter"], names
    assert names[-1] == "Kha'Zix, Evolving Hunter", "so the attack trigger is first out"


@case(10247, "Void Assault emptying a battlefield still lets Yone conquer it")
def _():
    need("Void Assault", "Yone - Blademaster")
    s = fresh(hand=[T.id_of("Void Assault")], runes=9)
    yo = s.add_permanent(T.id_of("Yone - Blademaster"), 0, base_loc(0), ready=True)
    s.bf_ctrl[0] = 1
    holder = body(s, 1, bf_loc(0), 3)
    home = body(s, 1, base_loc(1), 9)
    cast(s, 0, "Void Assault", yo, bf_loc(0), holder, base_loc(1))
    run(s, picking(home))
    assert int(s.perms[yo, P_LOC]) == bf_loc(0) and int(s.bf_ctrl[0]) == 0
    assert int(s.perms[home, P_DMG]) == 5, "his conquer trigger found a base"


@case(10234, "Vex - Apathetic stuns a unit played to your own battlefield")
def _():
    need("Vex - Apathetic", "Determined Sentry")
    s = fresh(hand=[T.id_of("Determined Sentry")], runes=9)
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(1))
    assert "Determined Sentry" in hand_plays(s, 0)
    cast(s, 0, "Determined Sentry", bf_loc(0))
    run(s)
    ds = perm_of(s, "Determined Sentry")
    assert ds and s.has_flag(ds[0], F_STUNNED) and s.has_flag(ds[0], F_NO_MOVE)


@case(10216, "two Allay, Eager Admirers give your other units Deflect 2")
def _():
    need("Allay, Eager Admirer")
    s = fresh()
    s.bf_ctrl[0] = 0
    a1 = s.add_permanent(T.id_of("Allay, Eager Admirer"), 0, bf_loc(0))
    a2 = s.add_permanent(T.id_of("Allay, Eager Admirer"), 0, bf_loc(0))
    other = body(s, 0, bf_loc(0), 3)
    assert rsv.deflect_cost(s, T, 1, [other]) == 2, rsv.deflect_cost(s, T, 1, [other])
    assert rsv.deflect_cost(s, T, 1, [a1]) == 2, "its own printed one, plus the other's"
    assert rsv.deflect_cost(s, T, 1, [a2]) == 2


@case(10213, "answering an opponent's move with Rengar makes you the defender")
def _():
    need("Rengar, Trophy Hunter")
    s = fresh(seat=1, runes=9)
    s.runes_ready[0, :] = 9
    give(s, 0, "Rengar, Trophy Hunter")
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    assert int(s.attacker) == 1, "they contested it first (442.1.a.1)"
    cast(s, 0, "Rengar, Trophy Hunter", bf_loc(0))
    drain(s)
    assert int(s.attacker) == 1, "playing a defender does not take the role over"


@case(10174, "Fizz may replay the Heedless Resurrection that revived him")
def _():
    need("Fizz - Trickster", "Heedless Resurrection", "Mindsplitter")
    s = fresh(hand=[T.id_of("Heedless Resurrection")], runes=9)
    s.trash[0, 0], s.n_trash[0] = T.id_of("Fizz - Trickster"), 1
    big = s.add_permanent(T.id_of("Mindsplitter"), 0, base_loc(0))
    # a second unit to pay the replay's kill cost, and a cheap unit for it
    body(s, 0, base_loc(0), 3)
    s.trash[0, 1], s.n_trash[0] = T.id_of("Determined Sentry"), 2
    cast(s, 0, "Heedless Resurrection", big)
    hr = pack_trash(0, T.id_of("Heedless Resurrection"))
    seen = []

    def pref(s, who, legal):
        args = {a.arg for a in legal if a.kind in (A.A_TARGET, A.A_PICK)}
        if hr in args:
            seen.append(True)
        return picks(pack_trash(0, T.id_of("Fizz - Trickster")), base_loc(0))(
            s, who, legal) if not seen else None
    run(s, pref, stop=lambda s: bool(seen))
    assert perm_of(s, "Fizz - Trickster") and seen, \
        "it finished resolving, so it was in the trash for Fizz"
