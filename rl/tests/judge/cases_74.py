"""RiftJudge batch 74 -- unused questions from 6845-6919."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_MIGHT_MOD, P_OWNER
from rl.engine.effects import pack_trash


def _showdown_with_chain(s):
    """Seat 1 attacks, then puts a Retreat on the Chain."""
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    mine = body(s, 1, bf_loc(0), 3)
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    cast(s, 1, "Retreat", mine)
    return mine


@case(6919, "Challenge is an Action, and a Chain is open")
def _():
    need("Challenge", "Retreat", "Discipline")
    s = fresh(runes=32)
    rune_deck(s)
    give(s, 0, "Challenge", "Discipline")
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 12
    _showdown_with_chain(s)
    pass_priority_to(s, 0)
    plays = hand_plays(s, 0)
    assert "Discipline" in plays, "a Reaction answers a Chain item"
    assert "Challenge" not in plays, "an Action does not"


@case(6873, "the same Showdown offers an Action again once the Chain empties")
def _():
    need("Challenge", "Retreat")
    s = fresh(runes=32)
    rune_deck(s)
    give(s, 0, "Challenge")
    give(s, 1, "Retreat")
    s.runes_ready[1, :] = 12
    _showdown_with_chain(s)
    drain(s)
    assert int(s.showdown_bf) == 0, "the Showdown is still open"
    pass_priority_to(s, 0)
    assert "Challenge" in hand_plays(s, 0), "and an Action is playable in it again"


@case(6918, "Pirate's Haven watches readying, not entering ready")
def _():
    need("Pirate's Haven", "Confront", "Upstage Comedy")

    def readied():
        s = fresh(runes=32)
        s.add_permanent(T.id_of("Pirate's Haven"), 0, base_loc(0))
        u = body(s, 0, base_loc(0), 3)            # enters exhausted
        give(s, 0, "Upstage Comedy")
        cast(s, 0, "Upstage Comedy", u)
        run(s, limit=30)
        return combat.might(s, T, u)

    def entered_ready():
        s = fresh(runes=32)
        s.add_permanent(T.id_of("Pirate's Haven"), 0, base_loc(0))
        give(s, 0, "Confront", T.names[VANILLA])
        cast(s, 0, "Confront")
        run(s, limit=30)
        act(s, A.A_PLAY, hand_index(s, 0, T.names[VANILLA]), 0)
        choose(s, base_loc(0))
        run(s, limit=30)
        u = [i for i in range(s.n_perms) if alive(s, i)
             and int(s.perms[i, P_CARD]) == VANILLA][-1]
        assert int(s.perms[u, P_READY]) == 1, "Confront did its job"
        return combat.might(s, T, u)

    assert readied() == 4, "an exhausted unit made ready is 'readied'"
    assert entered_ready() == int(T.might[VANILLA]), \
        "421: entering ready is not the game action of readying"


@case(6917, "Get Excited! locks its target at the Chain and discards at resolution")
def _():
    need("Get Excited!", "Riptide Rex")
    s = fresh(runes=32)
    give(s, 0, "Get Excited!", "Riptide Rex")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    act(s, A.A_PLAY, hand_index(s, 0, "Get Excited!"), 0)
    offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert offered == {u}, "the target is chosen as it goes on the Chain"
    choose(s, u)
    assert int(s.pend_discard) < 0, "and nothing is discarded yet"
    run(s, picking(hand_index(s, 0, "Riptide Rex"), accept=True), limit=40)
    assert int(s.perms[u, P_DMG]) == 6, "Rex's 6 Energy, decided at resolution"


@case(6914, "Convergent Mutation chooses two units")
def _():
    need("Convergent Mutation")
    s = fresh(hand=[T.id_of("Convergent Mutation")], runes=32)
    small = body(s, 0, base_loc(0), 2)
    big = body(s, 0, base_loc(0), 7)
    act(s, A.A_PLAY, 0, 0)
    choose(s, small)
    second = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
    assert big in second, "the unit it takes the Might from is chosen too"
    choose(s, big)
    run(s, limit=30)
    assert combat.might(s, T, small) == 7, "increased TO the other's Might"


@case(6912, "Yordle Explorer reads the printed Power, not what was paid")
def _():
    need("Yordle Explorer", "Switcheroo")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    body(s, 0, bf_loc(0), 5)
    s.add_permanent(T.id_of("Yordle Explorer"), 0, base_loc(0))
    hidden_at(s, 0, 0, "Switcheroo")
    before = int(s.n_hand[0])
    act(s, A.A_PLAY_HIDDEN, None, 0)
    run(s, picking(accept=True), limit=40)
    assert int(s.n_hand[0]) == before + 1, "{any rune}{any rune} printed is enough"


@case(6911, "Ride The Wind needs no [Ganking]")
def _():
    need("Ride The Wind")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    u = body(s, 0, bf_loc(0), 3)
    body(s, 0, bf_loc(1), 3)
    assert not T.has(VANILLA, "Ganking")
    cast(s, 0, "Ride The Wind", u, bf_loc(1))
    run(s, limit=30)
    assert int(s.perms[u, P_LOC]) == bf_loc(1), "450: the spell's own permission"


@case(6905, "Wielder of Water's +2 is already there when it attacks")
def _():
    need("Wielder of Water", "Gust", "Discipline")
    s = fresh(runes=32)
    give(s, 1, "Gust", "Discipline")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    w = s.add_permanent(T.id_of("Wielder of Water"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, w)
    assert combat.might(s, T, w) == 4, "a static, not a trigger"
    pass_priority_to(s, 1)
    plays = hand_plays(s, 1)
    assert "Discipline" in plays, "there is a window here"
    assert "Gust" not in plays, "but it is 4 Might, and Gust wants 3 or less"


@case(6903, "Gusting the Merchant does not stop his trigger")
def _():
    need("Traveling Merchant", "Gust")
    s = fresh(runes=32)
    rune_deck(s)
    give(s, 1, "Gust")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[0] = 0
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 0, base_loc(0), ready=True)
    give(s, 0, "Cleave")
    before_trash = int(s.n_trash[0])
    act(s, A.A_DECLARE, bf_loc(0), 0)
    act(s, A.A_ADD, tm, 0)
    act(s, A.A_COMMIT, None, 0)
    cast(s, 1, "Gust", tm)
    run(s, limit=40)
    assert not alive(s, tm), "Gust resolved first"
    assert int(s.n_trash[0]) > before_trash, "and the move trigger still resolved"


@case(6899, "The Harrowing is in the trash before Annie - Stubborn asks")
def _():
    need("The Harrowing", "Annie - Stubborn")
    s = fresh(hand=[T.id_of("The Harrowing")], runes=32)
    s.trash[0, 0] = T.id_of("Annie - Stubborn")
    s.n_trash[0] = 1
    cast(s, 0, "The Harrowing")
    run(s, picking(pack_trash(0, T.id_of("Annie - Stubborn")), base_loc(0),
                   pack_trash(0, T.id_of("The Harrowing")), accept=True), limit=60)
    assert perm_of(s, "Annie - Stubborn", 0), "she came back"
    assert T.id_of("The Harrowing") in list(s.hand[0, :int(s.n_hand[0])]), \
        "and the spell that did it was already in the trash to be taken"


@case(6894, "Hidden Blade draws for a unit a replacement saved")
def _():
    need("Hidden Blade", "Zhonya's Hourglass")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    before = int(s.n_hand[1])
    cast(s, 0, "Hidden Blade", u)
    run(s, limit=40)
    assert alive(s, u) and not alive(s, z), "the Hourglass took the death"
    assert int(s.n_hand[1]) == before + 2, "the kill still happened to it"


@case(6884, "Bullet Time's Power is paid as it resolves")
def _():
    need("Bullet Time")
    s = fresh(hand=[T.id_of("Bullet Time")], runes=32)
    rune_deck(s, 6)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Bullet Time", bf_loc(0))
    assert int(s.perms[u, P_DMG]) == 0, "nothing has been paid or dealt yet"
    before = runes(s, 0)
    run(s, picks(3, accept=True), limit=40)
    assert int(s.perms[u, P_DMG]) == 3, "the amount was chosen during resolution"
    assert before - runes(s, 0) == 3, "and paid then"


@case(6881, "a Might reduction reduces the damage that unit deals")
def _():
    need("Thousand-Tailed Watcher")
    s = fresh(hand=[T.id_of("Thousand-Tailed Watcher")], runes=32)
    s.bf_ctrl[0] = 1
    big = body(s, 1, bf_loc(0), 7)
    cast(s, 0, "Thousand-Tailed Watcher", base_loc(0))
    run(s, limit=40)
    assert combat.might(s, T, big) == 4, "7 less 3"
    w = perm_of(s, "Thousand-Tailed Watcher", 0)[0]
    s.perms[w, P_READY] = 1
    attack(s, 0, 0, w)
    fight(s)
    assert alive(s, w), "4 damage on a 7 Might unit"
    assert not alive(s, big), "and 7 on a unit down to 4"


@case(6877, "Challenge with its own unit dead does nothing")
def _():
    need("Challenge", "Hidden Blade")
    s = fresh(runes=32)
    give(s, 0, "Challenge")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[0] = 1
    theirs = body(s, 1, bf_loc(0), 9)
    mine = body(s, 0, bf_loc(0), 5)
    hidden_at(s, 1, 0, "Hidden Blade")     # 811.1.b gave it [Reaction]
    cast(s, 0, "Challenge", mine, theirs)
    pass_priority_to(s, 1)
    act(s, A.A_PLAY_HIDDEN, None, 1)
    choose(s, mine)
    run(s, limit=40)
    assert not alive(s, mine), "killed while Challenge waited"
    assert int(s.perms[theirs, P_DMG]) == 0, "so nothing was exchanged"


@case(6875, "The Arena's Greatest pays out once, on the first round")
def _():
    need("The Arena's Greatest")
    s = fresh()
    s.bf_card[0] = T.id_of("The Arena's Greatest")
    s.bf_ctrl[0] = -1
    s.turn = 1

    def begin(seat):
        s.active = s.priority = seat
        phases.start_turn(s, T, V1)
        A._settle(s, T, V1)
        run(s, limit=40)
        s.ply += 1

    begin(0)
    begin(1)
    assert list(s.points[:2]) == [1, 1], "each player, on their own first one"
    s.turn = 2
    begin(0)
    assert list(s.points[:2]) == [1, 1], "and never again"


@case(6866, "Seal of Rage's Fury pays a Power cost")
def _():
    need("Seal of Rage", "Cleave")
    s = fresh(hand=[T.id_of("Cleave")], runes=0)
    s.runes_ready[0, 3] = 1                   # 1 Energy for Cleave, no Power
    seal = s.add_permanent(T.id_of("Seal of Rage"), 0, base_loc(0))
    u = body(s, 0, base_loc(0), 3, ready=True)
    assert "Cleave" in hand_plays(s, 0), "its Energy is payable from the rune"
    act(s, A.A_ACTIVATE, None, 0)
    run(s, limit=20)
    assert int(s.perms[seal, P_READY]) == 0, "exhausted for the Fury"
    cast(s, 0, "Cleave", u)
    run(s, limit=30)
    assert combat.perm_kw(s, T, u, "Assault") == 3, "and the spell was paid for"


@case(6863, "Sigil of the Storm still scores with no runes to recycle")
def _():
    need("Sigil of the Storm")
    s = fresh(runes=0)
    rune_deck(s, 4)
    s.bf_card[0] = T.id_of("Sigil of the Storm")
    s.bf_ctrl[0] = -1
    taker = body(s, 0, base_loc(0), 3, ready=True)
    attack(s, 0, 0, taker)
    run(s, picking(accept=True), limit=60)
    assert int(s.bf_ctrl[0]) == 0 and int(s.points[0]) >= 1, "conquered and scored"


@case(6857, "Carnivorous Snapvine killed in response deals nothing")
def _():
    need("Carnivorous Snapvine")
    s = fresh(hand=[T.id_of("Carnivorous Snapvine")], runes=32)
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Carnivorous Snapvine", base_loc(0))
    choose(s, u)
    vine = perm_of(s, "Carnivorous Snapvine", 0)[0]
    combat.destroy(s, T, vine)
    run(s, limit=40)
    assert int(s.perms[u, P_DMG]) == 0, "143.2.b: a dead unit's Might is nothing"


@case(6856, "Vilemaw's Lair stops Flash as much as a Standard Move")
def _():
    need("Vilemaw's Lair", "Flash")
    s = fresh(hand=[T.id_of("Flash")], runes=32)
    s.bf_card[0] = T.id_of("Vilemaw's Lair")
    s.bf_ctrl[0] = 0
    u = body(s, 0, bf_loc(0), 3)
    cast(s, 0, "Flash", u, -1)
    run(s, limit=30)
    assert int(s.perms[u, P_LOC]) == bf_loc(0), "the move simply does not happen"
