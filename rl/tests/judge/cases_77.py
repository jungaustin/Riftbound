"""RiftJudge batch 77 -- unused questions from 6600-6689."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_STUNNED, P_MIGHT_MOD, P_ATTACHED_TO


@case(6688, "Bonus Damage adds nothing to a spell that deals none")
def _():
    need("Rabadon's Deathcrown", "Smoke Screen", "Hextech Ray")
    s = fresh(runes=32)
    give(s, 0, "Smoke Screen", "Hextech Ray")
    crown = s.add_permanent(T.id_of("Rabadon's Deathcrown"), 0, base_loc(0))
    mine = body(s, 0, base_loc(0), 3)
    s.attach(crown, mine)
    s.bf_ctrl[0] = 1
    a = body(s, 1, bf_loc(0), 9)
    b = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Smoke Screen", a)
    run(s, limit=30)
    assert int(s.perms[a, P_DMG]) == 0, "a Might reduction is not damage"
    cast(s, 0, "Hextech Ray", b)
    run(s, limit=30)
    assert int(s.perms[b, P_DMG]) == 6, "but the spell that deals 3 now deals 6"


@case(6683, "Karma played by Dazzling Aurora misses the recycles that carried her")
def _():
    need("Dazzling Aurora", "Karma - Channeler")
    s = fresh(hand=[T.id_of("Dazzling Aurora")], runes=32)
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Cleave")               # a non-unit, so it is recycled
    s.deck[0, n + 1] = T.id_of("Karma - Channeler")
    mine = body(s, 0, base_loc(0), 3)
    cast(s, 0, "Dazzling Aurora", base_loc(0))
    run(s, limit=30)
    act(s, A.A_END_TURN, None, 0)

    def answer(s, who, legal):
        # Her own [Vision] recycle WOULD buff (she is on the board for that
        # one), so decline it and leave only Aurora's recycle to answer for.
        for a in legal:
            if a.kind == A.A_PICK_NONE:
                return a
            if a.kind == A.A_PLAY_AT and a.arg == base_loc(0):
                return a
        return None

    run(s, answer, limit=80)
    assert perm_of(s, "Karma - Channeler", 0), "she came out of the reveal"
    assert not s.has_flag(mine, F_BUFFED), \
        "354.3: her play waited until Aurora had finished recycling"


@case(6678, "Mystic Reversal makes the spell the thief's own play")
def _():
    need("Mystic Reversal", "Hextech Ray", "Darius - Trifarian")

    def stage(steal):
        s = fresh(runes=32)
        give(s, 0, "Hextech Ray", "Hextech Ray")
        give(s, 1, "Mystic Reversal")
        s.runes_ready[1, :] = 24
        s.bf_ctrl[0] = 1
        u = body(s, 1, bf_loc(0), 9)               # big enough to eat both Rays
        d = s.add_permanent(T.id_of("Darius - Trifarian"), 0, base_loc(0),
                            ready=False)
        cast(s, 0, "Hextech Ray", u)
        run(s, limit=40)
        assert int(s.cards_completed[0]) == 1 and not int(s.perms[d, P_READY])
        cast(s, 0, "Hextech Ray", u)               # their second card...
        if steal:
            cast(s, 1, "Mystic Reversal", top_uid(s))
        run(s, picking(u, accept=True), limit=60)
        return s, d

    s, d = stage(False)
    assert int(s.cards_completed[0]) == 2 and int(s.perms[d, P_READY]), \
        "unstolen, the second card readies him"
    assert combat.might(s, T, d) == int(T.might[T.id_of("Darius - Trifarian")]) + 2

    s, d = stage(True)
    assert int(s.cards_completed[1]) == 2 and int(s.cards_completed[0]) == 1, \
        "419.4.a: the Ray was completed by the thief, so it is theirs"
    assert not int(s.perms[d, P_READY]), "so Darius is not readied"
    assert combat.might(s, T, d) == int(T.might[T.id_of("Darius - Trifarian")]), \
        "and gets no +2"


@case(6674, "a hidden unit whose only destination is forbidden cannot be played")
def _():
    need("Rockfall Path", "Tideturner")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("Rockfall Path")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 0, "Tideturner")
    assert A.A_PLAY_HIDDEN not in kinds(s, 0), \
        "811.1.d.1 sends it there, and 355.8 will not let it go"


@case(6672, "Wind Wall counters spells, and a trigger is not one")
def _():
    need("Wind Wall", "Riptide Rex")
    s = fresh(runes=32)
    give(s, 0, "Riptide Rex")
    give(s, 1, "Wind Wall")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    act(s, A.A_PLAY, hand_index(s, 0, "Riptide Rex"), 0)
    choose(s, base_loc(0))
    choose(s, u)
    assert int(s.n_chain) == 1, "his trigger is the only thing on the Chain"
    pass_priority_to(s, 1)
    assert "Wind Wall" not in hand_plays(s, 1), "425: it wants a SPELL"
    run(s, limit=40)
    assert int(s.perms[u, P_DMG]) == 6


@case(6669, "Ride The Wind names its unit at once and its destination later")
def _():
    need("Ride The Wind")
    s = fresh(hand=[T.id_of("Ride The Wind")], runes=32)
    s.bf_ctrl[0] = 0
    u = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, 0, 0)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert offered == {u}, "the unit is chosen to put it on the Chain"
    choose(s, u)
    assert int(s.n_chain) == 1 and not chain_mod.decision_open(s), \
        "and then it waits, destination and all"
    run(s, picking(bf_loc(0)), limit=30)
    assert int(s.perms[u, P_LOC]) == bf_loc(0)


@case(6666, "equipping chooses the unit, and Irelia, Fervent notices")
def _():
    need("Irelia, Fervent", "Warmog's Armor")
    s = fresh(runes=32)
    ir = s.add_permanent(T.id_of("Irelia, Fervent"), 0, base_loc(0))
    wa = s.add_permanent(T.id_of("Warmog's Armor"), 0, base_loc(0))
    assert combat.might(s, T, ir) == 4, "printed"
    act(s, A.A_ACTIVATE, None, 0)
    run(s, picking(ir, accept=True), limit=40)
    assert int(s.perms[wa, P_ATTACHED_TO]) == ir, "the Armor is on her"
    assert combat.might(s, T, ir) == 6, "+1 from the Armor, +1 for being chosen"


@case(6663, "Sigil of the Storm wants a rune recycled, not Power paid")
def _():
    need("Sigil of the Storm", "Seal of Rage")
    s = fresh(runes=0)
    rune_deck(s, 4)
    s.runes_ready[0, 3] = 2
    s.bf_card[0] = T.id_of("Sigil of the Storm")
    s.bf_ctrl[0] = -1
    seal = s.add_permanent(T.id_of("Seal of Rage"), 0, base_loc(0))
    taker = body(s, 0, base_loc(0), 3, ready=True)
    act(s, A.A_ACTIVATE, None, 0)                 # float the Fury first
    run(s, limit=20)
    assert int(s.perms[seal, P_READY]) == 0 and int(s.pool_power[0].sum()) >= 1
    before = runes(s, 0)
    attack(s, 0, 0, taker)
    run(s, picking(accept=True), limit=60)
    assert int(s.bf_ctrl[0]) == 0, "conquered"
    assert before - runes(s, 0) == 1, "a rune left the board all the same"


@case(6652, "[Temporary] kills before the Hold is scored")
def _():
    need("Sprite Call")
    s = fresh()
    rune_deck(s)
    spr = _sprite_at(s, 0, 0)
    before = int(s.points[0])
    _next_own_turn(s)
    run(s, limit=40)
    assert not alive(s, spr), "315.2.a came first"
    assert int(s.points[0]) == before, "so there was nothing left to Hold with"


@case(6646, "Charming the last unit away takes the battlefield and the hidden card")
def _():
    need("Charm", "Hidden Blade")
    s = fresh(hand=[T.id_of("Charm")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    fd = hidden_at(s, 1, 0, "Hidden Blade")
    cast(s, 0, "Charm", u, base_loc(1))
    run(s, limit=40)
    assert int(s.perms[u, P_LOC]) == base_loc(1)
    assert int(s.bf_ctrl[0]) != 1, "190.4.c: an empty battlefield is a lost one"
    assert int(s.fd_card[fd]) < 0, "466.5.c: and the hidden card goes with it"


@case(6636, "Cruel Patron's kill is a cost, so there is no window to answer it")
def _():
    need("Cruel Patron")
    s = fresh(hand=[T.id_of("Cruel Patron")], runes=32)
    give(s, 1, "Discipline")
    s.runes_ready[1, :] = 24
    food = body(s, 0, base_loc(0), 3)
    act(s, A.A_PLAY, hand_index(s, 0, "Cruel Patron"), 0)
    choose(s, food)
    assert not alive(s, food), "820: paid as part of playing him"
    assert int(s.n_chain) == 0, "337.2: and a unit never reached the Chain"


@case(6632, "a hidden card answers the [Temporary] trigger that is about to kill it")
def _():
    need("Sprite Call", "Consult the Past")
    s = fresh()
    rune_deck(s)
    spr = _sprite_at(s, 0, 0)
    hidden_at(s, 0, 0, "Consult the Past")
    before = int(s.n_hand[0])
    _next_own_turn(s)
    assert int(s.n_chain) >= 1, "Temporary is on the Chain"
    assert A.A_PLAY_HIDDEN in kinds(s, 0), "and a Chain item is a window"
    act(s, A.A_PLAY_HIDDEN, None, 0)
    # Let the hidden card resolve but stop before the Temporary trigger under
    # it does -- the draws land while the Sprite is still standing. Reading
    # this after `run` would instead measure the new turn's own draw.
    for _ in range(8):
        if int(s.n_chain) <= 1:
            break
        act(s, A.A_PASS)
    assert int(s.n_hand[0]) == before + 2 and alive(s, spr), \
        "drawn before the sprite went"
    run(s, limit=40)
    assert not alive(s, spr), "816.1.c still expires it"


@case(6630, "Mask of Foresight pays out once per combat, so twice in two")
def _():
    need("Mask of Foresight", "Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.add_permanent(T.id_of("Mask of Foresight"), 0, base_loc(0))
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    s.ply += 1
    lone = body(s, 0, bf_loc(0), 6)
    first = body(s, 1, base_loc(1), 1, ready=True)
    second = body(s, 1, base_loc(1), 1, ready=True)
    attack(s, 1, 0, first)
    drain(s)
    assert combat.might(s, T, lone) == 7, "one combat, one +1"
    fight(s, limit=60)
    attack(s, 1, 0, second)
    drain(s)
    assert combat.might(s, T, lone) == 8, "a second combat is a second instance"


@case(6627, "'defending alone' switches on the moment the company leaves")
def _():
    need("Wielder of Water", "Fight or Flight")
    s = fresh(runes=32)
    give(s, 0, "Fight or Flight")
    s.bf_ctrl[0] = 0
    w = s.add_permanent(T.id_of("Wielder of Water"), 0, bf_loc(0))
    crowd = body(s, 0, bf_loc(0), 3)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    drain(s)
    assert combat.might(s, T, w) == 2, "not alone"
    pass_priority_to(s, 0)
    cast(s, 0, "Fight or Flight", crowd)
    drain(s)
    assert int(s.perms[crowd, P_LOC]) == base_loc(0)
    assert combat.might(s, T, w) == 4, "a static is checked continuously"


@case(6615, "banishing a unit is not killing it")
def _():
    need("Portal Rescue", "Tasty Faefolk")
    s = fresh(hand=[T.id_of("Portal Rescue")], runes=32)
    rune_deck(s)
    tf = s.add_permanent(T.id_of("Tasty Faefolk"), 0, base_loc(0))
    before = int(s.n_hand[0])
    left = int(s.rune_left[0])
    cast(s, 0, "Portal Rescue", tf)
    run(s, limit=60)
    assert perm_of(s, "Tasty Faefolk", 0), "it came straight back"
    # Portal Rescue's own {1 power} recycles a rune, so the deck GAINS one. A
    # [Deathknell] channel would have taken two out of it, and drawn.
    assert int(s.rune_left[0]) == left + 1 and int(s.n_hand[0]) == before - 1, \
        "427.2.a: no [Deathknell], so no channel and no draw"


@case(6637, "[Assault] is nothing at an open battlefield")
def _():
    need("Vayne - Hunter", "Discipline")
    s = fresh(runes=32)
    # A [Reaction] in the other hand, so the Showdown is still open to be read:
    # with no legal answer on either side it would close inside the COMMIT.
    give(s, 1, "Discipline")
    s.bf_ctrl[0] = -1
    v = s.add_permanent(T.id_of("Vayne - Hunter"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, v)
    assert int(s.showdown_bf) == 0 and not int(s.showdown_combat), \
        "323.14: a Showdown, but nobody is defending, so it is Non-Combat"
    assert combat.might(s, T, v) == int(T.might[T.id_of("Vayne - Hunter")]), \
        "807.1.d: no Attacker designation, so [Assault] adds nothing"


@case(6655, "Guerilla Warfare makes hiding free")
def _():
    need("Guerilla Warfare", "Hidden Blade")
    s = fresh(runes=32)
    rune_deck(s)
    give(s, 0, "Guerilla Warfare", "Hidden Blade")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Guerilla Warfare", -1, -1)
    run(s, limit=40)
    before = runes(s, 0)
    hides = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_HIDE]
    assert hides, "there is a card to hide"
    A.apply(s, T, V1, hides[0])
    act(s, A.A_HIDE_AT, None, 0)
    run(s, limit=20)
    assert runes(s, 0) == before, "811.1.b's {any rune} was ignored"


@case(6621, "an Action does not hand priority back to its own player")
def _():
    need("Challenge", "Grand Strategem")
    s = fresh(runes=32)
    give(s, 0, "Challenge", "Grand Strategem")
    s.bf_ctrl[1] = 1
    mine = body(s, 0, base_loc(0), 5, ready=True)
    theirs = body(s, 1, bf_loc(1), 3)
    attack(s, 0, 1, mine)
    # 346.1: the Combat Chain opened from triggered abilities, so Focus did NOT
    # pass when it emptied -- the attacker still has it.
    assert int(s.n_chain) == 0 and int(s.focus) == 0 and int(s.priority) == 0
    cast(s, 0, "Challenge", mine, theirs)
    drain(s)
    assert int(s.focus) == 1 and int(s.priority) == 1, \
        "346: Focus passes once that Chain has emptied"
    assert not hand_plays(s, 0), "so no second Action back-to-back"
