"""Austin's own judge-call list, batch 1 -- not scraped from RiftJudge.

Ids are `AJ-NN` so they can never be mistaken for a RiftJudge question number.
Two of the three are `harness.KNOWN_BAD`: the ruling is right and the engine is
wrong, and the reason each fix is not small is recorded there.
"""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_06 import hidden_at
from rl.engine.state import C_CARD, F_STUNNED, P_DMG, P_FLAGS, P_LOC, P_READY
from rl.engine.chain import trig_card


# ---------------------------------------------------------------------------
@case("AJ-01", "Rengar in the conquer window is defender AND attacker: Mask fires twice")
def _():
    """466.6 puts the conquer triggers on the Chain BEFORE 466.7 ends the Combat
    and removes the designations, so a unit played into that window joins a
    Combat that is still live. 323.2.a then gives it "the same designation as
    its Controller", i.e. Defender -- Mask of Foresight's first +1. Once the
    Zaun Warrens trigger resolves and the Combat finally ends, the unit is
    standing on ground its opponent now controls, a NEW Combat opens with it as
    the attacker, and Mask fires a second time. 6 + 1 + 1 = 8.
    """
    need("Zaun Warrens", "Mask of Foresight", "Rengar, Trophy Hunter")
    s = fresh(runes=32, seat=0)
    s.bf_card[0] = T.id_of("Zaun Warrens")
    s.bf_ctrl[0] = 0                      # mine, and they are about to take it
    give(s, 0, "Rengar, Trophy Hunter", "Mask of Foresight")
    cast(s, 0, "Mask of Foresight", base_loc(0))
    drain(s)

    s.ply += 1                            # their turn
    s.active = s.priority = 1
    defender = body(s, 0, bf_loc(0), 1, ready=True)     # dies to their attacker
    body(s, 1, base_loc(1), 5, ready=True)
    attack(s, 1, 0, *[i for i in range(s.n_perms)
                      if alive(s, i) and int(s.perms[i, P_CTRL]) == 1
                      and int(s.perms[i, P_LOC]) == base_loc(1)])

    # Walk to the conquer window: they hold the ground, their Zaun Warrens
    # trigger is on the Chain, and I have priority to answer it.
    ren_id = T.id_of("Rengar, Trophy Hunter")
    for _ in range(70):
        who = A.acting_seat(s)
        if who < 0:
            break
        lg = A.legal_actions(s, T, V1, who)
        if not lg:
            break
        mine = [a for a in lg if a.kind == A.A_PLAY and who == 0
                and a.arg < int(s.n_hand[0]) and int(s.hand[0, a.arg]) == ren_id]
        if mine and int(s.bf_ctrl[0]) == 1 and not alive(s, defender):
            assert any(T.names[int(s.chain[i, C_CARD])] == "Zaun Warrens"
                       for i in range(int(s.n_chain))), \
                "the conquer trigger should be the thing I am responding to"
            assert int(s.showdown_bf) >= 0, (
                "466.7 -- the Combat must NOT have ended yet: 466.6 owes the "
                "conquer triggers a resolution first")
            A.apply(s, T, V1, mine[0])
            act(s, A.A_PLAY_AT, bf_loc(0), 0)
            break
        A.apply(s, T, V1, next((a for a in lg if a.kind == A.A_ORDER),
                               next((a for a in lg if a.kind == A.A_PASS), lg[0])))
    else:
        raise AssertionError("never reached the conquer window")

    fight(s)
    ren = perm_of(s, "Rengar, Trophy Hunter", 0)
    assert ren, "Rengar should still be on the board"
    got = combat.might(s, T, ren[0])
    assert got == 8, (f"6 base + 1 as the old Combat's defender + 1 as the new "
                      f"Combat's attacker = 8, got {got}")


# ---------------------------------------------------------------------------
@case("AJ-02", "Zhonya's beats Smite's banish, because 372 lets its controller choose")
def _():
    """Smite's "if it would die this turn, banish it instead" and Zhonya's
    Hourglass both replace the same death. 372: the controller of the object
    being acted on determines the order -- that is the FAEFOLK's controller, who
    applies Zhonya's, so the unit is recalled exhausted and never dies. 370.2
    then stops Smite applying to the event that replaced it, so the banish never
    happens (though it stays live for a later death this turn).
    """
    need("Smite", "Zhonya's Hourglass", "Irresistible Faefolk")
    s = fresh(runes=32, seat=1)
    give(s, 1, "Zhonya's Hourglass")
    give(s, 0, "Smite")
    s.bf_ctrl[0] = 1
    foe = s.add_permanent(T.id_of("Irresistible Faefolk"), 1, bf_loc(0), ready=True)
    # PLAYED, not staged: the guard is registered by its [Play] trigger, so an
    # `add_permanent` copy of Zhonya's does nothing at all.
    cast(s, 1, "Zhonya's Hourglass", base_loc(1))
    drain(s)
    zh = perm_of(s, "Zhonya's Hourglass", 1)[0]
    assert int(s.death_guard[1]) == zh, "the guard should be registered"

    s.ply += 1
    s.active = s.priority = 0
    cast(s, 0, "Smite", foe)
    drain(s)

    assert alive(s, foe), "372 -- its controller applies Zhonya's, so it lives"
    assert int(s.perms[foe, P_LOC]) == base_loc(1), "recalled to base"
    assert int(s.perms[foe, P_READY]) == 0, "recalled EXHAUSTED"
    assert not alive(s, zh), "Zhonya's is what dies instead"
    assert int(s.n_banished[1]) == 0, "370.2 -- Smite never gets to banish it"


# ---------------------------------------------------------------------------
def _yasuo_yuumi(place_first):
    """Attack with Yasuo - Remorseful and Yuumi, placing `place_first`'s trigger
    on the Chain first. Returns the damage Yasuo dealt."""
    s = fresh(runes=32, seat=0)
    s.bf_ctrl[0] = 1
    ya = s.add_permanent(T.id_of("Yasuo - Remorseful"), 0, base_loc(0), ready=True)
    yu = s.add_permanent(T.id_of("Yuumi - Magical Cat"), 0, base_loc(0), ready=True)
    foe = body(s, 1, bf_loc(0), 30, ready=True)
    attack(s, 0, 0, ya, yu)
    offered, ordered = 0, 0
    for _ in range(60):
        # **Read the damage before the Showdown closes.** 466.1.a.1 heals every
        # unit board-wide, so P_DMG afterwards is 0 whatever happened.
        if ordered and s.n_chain == 0 and s.n_trig == 0 \
                and not chain_mod.decision_open(s):
            break
        who = A.acting_seat(s)
        if who < 0:
            break
        lg = A.legal_actions(s, T, V1, who)
        if not lg:
            break
        orders = [a for a in lg if a.kind == A.A_ORDER]
        if orders:
            offered = len(orders)
            lbl = {a.arg: T.names[trig_card(s, int(s.trig[a.arg, 1]))]
                   for a in orders}
            pick = next((a for a in orders if lbl[a.arg] == place_first), orders[0])
            A.apply(s, T, V1, pick)
            ordered += 1
            continue
        tgt = [a for a in lg if a.kind == A.A_TARGET]
        if tgt:
            A.apply(s, T, V1, next((a for a in tgt if a.arg == foe), tgt[0]))
            continue
        A.apply(s, T, V1, next((a for a in lg if a.kind == A.A_PASS), lg[0]))
    return int(s.perms[foe, P_DMG]), offered


@case("AJ-03a", "383.3.d: my own two triggers, and LAST placed resolves FIRST")
def _():
    need("Yasuo - Remorseful", "Yuumi - Magical Cat")
    # Yasuo deals damage equal to his Might; Yuumi gives another unit here +3.
    # Placing Yasuo FIRST means Yuumi resolves first, so the buff lands before
    # he reads his own Might: 9 instead of 6. That is the whole decision.
    buffed, n = _yasuo_yuumi("Yasuo - Remorseful")
    assert n == 2, f"the controller must be offered the order, got {n} options"
    assert buffed == 9, f"Yuumi resolving first buffs him to 9, got {buffed}"
    plain, _ = _yasuo_yuumi("Yuumi - Magical Cat")
    assert plain == 6, f"Yasuo resolving first deals his base 6, got {plain}"


def _vex_tideturner(my_turn):
    """Vex - Apathetic (theirs) and Tideturner (mine) trigger together. Returns
    (tideturner moved?, tideturner stunned?, the ally moved?)."""
    s = fresh(runes=32, seat=0)
    s.bf_ctrl[0] = 1                      # theirs, with Vex standing on it
    s.add_permanent(T.id_of("Vex - Apathetic"), 1, bf_loc(0), ready=True)
    if my_turn:
        give(s, 0, "Tideturner")
        ally = body(s, 0, bf_loc(0), 3, ready=True)
        act(s, A.A_PLAY, hand_index(s, 0, "Tideturner"), 0)
        act(s, A.A_PLAY_AT, base_loc(0), 0)
        home = base_loc(0)
    else:
        # Their turn, so Tideturner comes in from the Facedown Zone during a
        # Showdown -- 811.6 gives a hidden card [Reaction].
        s.bf_ctrl[1] = 0                  # 107.3.c: I may only hide on my own
        ally = body(s, 0, base_loc(0), 3, ready=True)
        body(s, 0, bf_loc(1), 9, ready=True)          # a defender, so a Combat
        hidden_at(s, 0, 1, "Tideturner")
        s.ply += 1
        atk = body(s, 1, base_loc(1), 3, ready=True)
        attack(s, 1, 1, atk)
        pass_priority_to(s, 0)
        act(s, A.A_PLAY_HIDDEN, None, 0)
        home = bf_loc(1)
    for _ in range(40):
        who = A.acting_seat(s)
        if who < 0:
            break
        lg = A.legal_actions(s, T, V1, who)
        if not lg:
            break
        A.apply(s, T, V1, next(
            (a for a in lg if a.kind == A.A_ORDER),
            next((a for a in lg if a.kind == A.A_TARGET and a.arg == ally),
                 next((a for a in lg if a.kind == A.A_ACCEPT),
                      next((a for a in lg if a.kind == A.A_PASS), lg[0])))))
        if s.n_chain == 0 and s.n_trig == 0 and not chain_mod.decision_open(s):
            break
    tt = perm_of(s, "Tideturner", 0)[0]
    return (int(s.perms[tt, P_LOC]) != home,
            bool(int(s.perms[tt, P_FLAGS]) & F_STUNNED),
            int(s.perms[ally, P_LOC]) == home)


@case("AJ-03b", "Vex + Tideturner on MY turn: Vex resolves first, so the move is denied")
def _():
    need("Vex - Apathetic", "Tideturner")
    # Opposing triggers are placed in TURN ORDER with no choice: mine goes on
    # first, so Vex's goes on last and resolves first. Its "they can't move it"
    # is already up when Tideturner's own trigger resolves.
    moved, stunned, ally_moved = _vex_tideturner(my_turn=True)
    assert not moved, "Vex's stun is already up, so Tideturner cannot move"
    assert stunned, "...and it is stunned where it was played"
    assert ally_moved, "but the ally still moves -- do as much as you can"


@case("AJ-03c", "...and on THEIR turn it is the other way round: the move happens")
def _():
    need("Vex - Apathetic", "Tideturner")
    moved, stunned, ally_moved = _vex_tideturner(my_turn=False)
    assert moved, ("their trigger is placed first on their turn, so Tideturner's "
                   "resolves first and the swap goes through")
    assert stunned, "it still ends up stunned -- just at the intended location"
    assert ally_moved, "and the ally takes its original spot"
