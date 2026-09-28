"""RiftJudge batch 71 -- unused questions from 7051-7101."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_MIGHT_MOD, P_OWNER
from rl.engine.effects import pack_trash


@case(7101, "Ride The Wind joins the combat already happening there")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    keep = body(s, 0, bf_loc(0), 1)               # 1 Might: no answer alone
    help_ = body(s, 0, base_loc(0), 9)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 5, ready=True)
    attack(s, 1, 0, foe)
    cast(s, 0, "Ride The Wind", help_, bf_loc(0))
    run(s, limit=20, stop=lambda st: st.n_chain == 0 and st.n_trig == 0)
    assert int(s.showdown_bf) == 0, "the same Showdown, not a second one"
    assert int(s.perms[help_, P_LOC]) == bf_loc(0)
    fight(s)
    assert not alive(s, foe), "the 9 that walked in dealt its damage in this combat"
    assert not alive(s, keep), "the attacker's 5 still landed somewhere"


@case(7094, "an exhausted rune pays Defy's Power")
def _():
    need("Defy", "Feral Strength")
    s = fresh(hand=[T.id_of("Defy")], runes=0)
    rune_deck(s)
    give(s, 1, "Feral Strength")
    s.runes_ready[0, 1] = 1                       # one ready rune, for Energy
    s.runes_spent[0, 1] = 3                       # and three already spent
    s.runes_ready[1, :] = 6
    s.ply += 1
    s.active = s.priority = 1
    mine = body(s, 0, base_loc(0), 3)
    cast(s, 1, "Feral Strength", mine)
    cast(s, 0, "Defy", _top_uid(s))
    run(s, limit=30)
    assert combat.might(s, T, mine) == 3, "Feral Strength was countered"
    assert s.total_ready_runes(0) == 0, "the ready rune paid the Energy"
    assert runes(s, 0) == 3, "and an exhausted one was recycled for the Power"


@case(7092, "a hidden card needs something on the Chain in the Ending Phase")
def _():
    need("Fight or Flight", "Sona, Harmonious")

    def offered(with_trigger):
        s = fresh(runes=32)
        s.bf_ctrl[0] = 0
        body(s, 0, bf_loc(0), 3)
        hidden_at(s, 0, 0, "Fight or Flight")
        if with_trigger:
            s.bf_ctrl[1] = 1
            s.add_permanent(T.id_of("Sona, Harmonious"), 1, bf_loc(1))
        s.ply += 1
        s.active = s.priority = 1
        seen = [False]

        def pref(st, who, legal):
            if who == 0 and any(a.kind == A.A_PLAY_HIDDEN for a in legal):
                seen[0] = True
            return None
        act(s, A.A_END_TURN, None, 1)
        run(s, pref, limit=40)
        return seen[0]

    assert not offered(False), "no Chain, no window at all in the Ending Phase"
    assert offered(True), "811.1.b gave it [Reaction]: Sona's trigger opens one"


@case(7080, "Hallowed Tomb gives the Chosen Champion back on a Hold")
def _():
    need("Hallowed Tomb", "Garen - Commander")
    s = fresh()
    s.bf_card[0] = T.id_of("Hallowed Tomb")
    s.bf_ctrl[0] = 0
    s.champion[0] = T.id_of("Garen - Commander")
    s.trash[0, 0], s.n_trash[0] = T.id_of("Garen - Commander"), 1
    s.add_permanent(VANILLA, 0, bf_loc(0))
    phases.score_holds(s, V1, T)
    A._settle(s, T, V1)
    run(s, picking(pack_trash(0, T.id_of("Garen - Commander")), accept=True))
    assert int(s.n_trash[0]) == 0, "it left the trash"
    assert T.id_of("Garen - Commander") in list(s.hand[0, :int(s.n_hand[0])]), \
        "a copy of the Chosen Champion's name is playable again"


@case(7076, "Stupefy draws even when Retreat took its target away")
def _():
    need("Stupefy", "Retreat")
    s = fresh(hand=[T.id_of("Stupefy")], runes=32)
    rune_deck(s)
    give(s, 1, "Retreat")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Stupefy", u)
    cast(s, 1, "Retreat", u)
    before = int(s.n_hand[0])
    run(s, limit=30)
    assert not alive(s, u), "Retreat resolved first"
    assert int(s.n_hand[0]) == before + 1, "the draw is not conditional"


@case(7074, "Irelia - Graceful discounts a repeated spell only once")
def _():
    need("Irelia - Graceful", "Feral Strength")
    s = fresh(hand=[T.id_of("Feral Strength")], runes=0)
    s.runes_ready[0, 0] = 4                       # 2 + 2 Repeat, less Irelia's 1
    ir = s.add_permanent(T.id_of("Irelia - Graceful"), 0, base_loc(0))
    act(s, A.A_PLAY_REPEAT, hand_index(s, 0, "Feral Strength"), 0)
    run(s, picks(ir, ir), limit=30)
    assert combat.might(s, T, ir) == 8, "+2 twice on a 4 Might Irelia"
    assert s.total_ready_runes(0) == 1, "3 Energy, not 2 and not 4"


@case(7070, "Viktor, Innovator's Recruit waits for the spell to resolve")
def _():
    need("Viktor, Innovator", "Discipline")
    s = fresh(runes=32)
    give(s, 0, "Discipline")
    s.add_permanent(T.id_of("Viktor, Innovator"), 0, base_loc(0))
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    cast(s, 0, "Discipline", mine)
    fight(s, limit=60)
    assert len(tokens(s, 0, base_loc(0))) == 1, "one Recruit, at my base"


@case(7069, "Hostile Takeover hands the unit back at end of turn")
def _():
    need("Hostile Takeover")
    s = fresh(hand=[T.id_of("Hostile Takeover")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Hostile Takeover", u)
    run(s, limit=40)
    assert int(s.perms[u, P_CTRL]) == 0 and int(s.bf_ctrl[0]) == 0, "taken, and conquered"
    act(s, A.A_END_TURN, None, 0)
    run(s, limit=40)
    assert int(s.perms[u, P_CTRL]) == 1, "control reverted"
    assert int(s.perms[u, P_LOC]) == base_loc(1), "and it was recalled, not moved"


@case(7068, "a hidden Fox-Fire can only choose at its own battlefield")
def _():
    need("Fox-Fire")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    here = body(s, 1, bf_loc(0), 2)
    there = body(s, 1, bf_loc(1), 2)
    hidden_at(s, 0, 0, "Fox-Fire")
    act(s, A.A_PLAY_HIDDEN, None, 0)
    offered = targets_offered(s, 0)
    assert here in offered, "the units where it was hidden are fair game"
    assert there not in offered, "811.1.d.2 keeps the choice at that battlefield"


@case(7067, "Icathian Rain pays Deflect once per choice of the same unit")
def _():
    need("Icathian Rain", "Pouty Poro")
    s = fresh(hand=[T.id_of("Icathian Rain")], runes=32)
    s.bf_ctrl[0] = 1
    poro = s.add_permanent(T.id_of("Pouty Poro"), 1, bf_loc(0))
    plain = body(s, 1, bf_loc(0), 9)
    before = runes(s, 0)
    cast(s, 0, "Icathian Rain", poro, poro, plain, plain, plain, plain)
    run(s, limit=40)
    assert not alive(s, poro), "4 damage on a 2 Might Poro"
    assert before - runes(s, 0) == 3 + 2, "3 Power, and Deflect twice"


@case(7066, "Gust returns the Ravenbloom Student before its own trigger")
def _():
    need("Gust", "Ravenbloom Student")
    s = fresh(hand=[T.id_of("Gust")], runes=32)
    s.bf_ctrl[0] = 0
    rb = s.add_permanent(T.id_of("Ravenbloom Student"), 0, bf_loc(0))
    s.perms[rb, P_MIGHT_MOD] = 1                  # an earlier spell already hit
    assert combat.might(s, T, rb) == 3
    cast(s, 0, "Gust", rb)
    run(s, limit=30)
    assert not alive(s, rb), "3 Might was within Gust's reach"
    assert T.id_of("Ravenbloom Student") in list(s.hand[0, :int(s.n_hand[0])]), \
        "and it was in hand before its own trigger could grow it"


@case(7065, "Gemcraft Seer gives a token [Vision] too")
def _():
    need("Gemcraft Seer", "Desert's Call")

    def vision_windows(with_seer):
        s = fresh(hand=[T.id_of("Desert's Call")], runes=32)
        if with_seer:
            s.add_permanent(T.id_of("Gemcraft Seer"), 0, base_loc(0))
        seen = [0]

        def pref(st, who, legal):
            if any(a.kind == A.A_PICK_NONE for a in legal):
                seen[0] += 1
            return None
        cast(s, 0, "Desert's Call")
        run(s, pref, limit=40)
        assert len(tokens(s, 0)) >= 1, "the Sand Soldier arrived"
        return seen[0]

    assert vision_windows(False) == 0, "a bare token looks at nothing"
    assert vision_windows(True) == 1, "tokens are units, and units get the grant"


@case(7063, "two Cleaves are Assault 6")
def _():
    need("Cleave")
    s = fresh(runes=32)
    give(s, 0, "Cleave", "Cleave")
    s.bf_ctrl[0] = 1
    wall = body(s, 1, bf_loc(0), 8)               # 6 is not enough, 9 is
    u = body(s, 0, base_loc(0), 3, ready=True)
    cast(s, 0, "Cleave", u)
    run(s, limit=20)
    cast(s, 0, "Cleave", u)
    run(s, limit=20)
    assert combat.might(s, T, u) == 3, "Assault is nothing until it attacks"
    attack(s, 0, 0, u)
    fight(s)
    assert not alive(s, wall), "3 + 3 + 3: both instances counted"


@case(7061, "Dazzling Aurora stops at the first unit it reveals")
def _():
    need("Dazzling Aurora", "Pouty Poro", "Navori Scout")
    s = fresh(hand=[T.id_of("Dazzling Aurora")], runes=32)
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Cleave")
    s.deck[0, n + 1] = T.id_of("Pouty Poro")
    s.deck[0, n + 2] = T.id_of("Navori Scout")
    cast(s, 0, "Dazzling Aurora", base_loc(0))
    run(s, limit=30)
    act(s, A.A_END_TURN, None, 0)
    run(s, picking(base_loc(0), accept=True), limit=60)
    assert perm_of(s, "Pouty Poro", 0), "the first unit revealed came out"
    assert not perm_of(s, "Navori Scout", 0), "and the reveal stopped there"


@case(7060, "Guerilla Warfare has no speed, so no showdown")
def _():
    need("Guerilla Warfare", "Discipline")
    s = fresh(runes=32)
    give(s, 0, "Guerilla Warfare", "Discipline")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    pass_priority_to(s, 0)
    plays = hand_plays(s, 0)
    assert "Discipline" in plays, "a Reaction is playable here"
    assert "Guerilla Warfare" not in plays, "a speedless spell is not"


@case(7059, "one Hourglass saves one of two simultaneous deaths")
def _():
    need("Zhonya's Hourglass")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    a = body(s, 0, bf_loc(0), 3)
    b = body(s, 0, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 0, base_loc(0))
    s.death_guard[0] = z
    s.ply += 1
    foe = body(s, 1, base_loc(1), 6, ready=True)
    attack(s, 1, 0, foe)
    fight(s)
    assert alive(s, a) != alive(s, b), "exactly one was replaced"
    assert not alive(s, z), "one Hourglass per death prevented"
    # Deliberately agnostic about WHICH one, because it was the engine's pick
    # when this was written. 373 gives that choice to the guard's controller and
    # `cases_72.py` #7059/.1/.2 assert it -- this case stays as the "exactly one"
    # half, which is 373.2 and holds however the choice goes.


@case(7056, "Baited Hook ignores the cost printed, not the cost demanded")
def _():
    need("Baited Hook", "Cruel Patron")
    s = fresh(runes=32)
    hook = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0))
    bait = body(s, 0, base_loc(0), 5)
    spare = body(s, 0, base_loc(0), 1)
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Cruel Patron")
    before = runes(s, 0)
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, bait)                               # the Hook's own kill
    run(s, limit=20, stop=lambda st: int(st.pend_look) >= 0)
    choose(s, 0)                                  # the Patron, top of the five
    choose(s, spare)                              # 820.1: his kill is still owed
    choose(s, base_loc(0))
    run(s, limit=60)
    assert not alive(s, bait), "the Hook's own cost"
    assert perm_of(s, "Cruel Patron", 0), "and the Patron came out for no Energy"
    assert not alive(s, spare), "but his additional cost was still paid"
    assert before - runes(s, 0) == 1, "only the Hook's {Order rune}"


@case(7054, "Deflect gained after the choice is not charged")
def _():
    need("Stupefy", "Discipline", "Fiora - Victorious")
    s = fresh(hand=[T.id_of("Stupefy")], runes=32)
    give(s, 1, "Discipline")
    s.bf_ctrl[0] = 1
    fi = s.add_permanent(T.id_of("Fiora - Victorious"), 1, bf_loc(0))
    assert not combat.perm_kw(s, T, fi, "Deflect"), "4 Might is not [Mighty]"
    cast(s, 0, "Stupefy", fi)
    paid = runes(s, 0)
    cast(s, 1, "Discipline", fi)
    run(s, limit=40)
    assert combat.perm_kw(s, T, fi, "Deflect"), "6 Might made her Mighty mid-chain"
    assert combat.might(s, T, fi) == 5, "+2 from Discipline, -1 from Stupefy"
    assert runes(s, 0) == paid, "the choice was made before she had [Deflect]"


@case(7052, "Unchecked Power chooses nothing, so it pays no Deflect")
def _():
    need("Unchecked Power", "Pouty Poro")
    s = fresh(hand=[T.id_of("Unchecked Power")], runes=32)
    s.bf_ctrl[0] = 1
    poro = s.add_permanent(T.id_of("Pouty Poro"), 1, bf_loc(0))
    before = runes(s, 0)
    cast(s, 0, "Unchecked Power")
    run(s, limit=40)
    assert not alive(s, poro), "12 to ALL units at battlefields"
    assert before - runes(s, 0) == 2, "its own Power and nothing else"


@case(7051, "Cull the Weak asks a player with no units for nothing")
def _():
    need("Cull the Weak")
    s = fresh(hand=[T.id_of("Cull the Weak")], runes=32)
    mine = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Cull the Weak")
    run(s, picking(mine, accept=True), limit=40)
    assert not alive(s, mine), "I still had to kill one"
    assert int(s.n_chain) == 0, "and the spell finished with the other half empty"
