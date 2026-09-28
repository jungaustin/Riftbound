"""RiftJudge batch 72 -- unused questions from 6990-7044."""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, P_MIGHT_MOD


@case(7039, "Salvage breaks the Hourglass before it can be spent")
def _():
    need("Salvage", "Zhonya's Hourglass")
    s = fresh(hand=[T.id_of("Salvage")], runes=32)
    s.bf_ctrl[0] = 1
    z = s.add_permanent(T.id_of("Zhonya's Hourglass"), 1, base_loc(1))
    s.death_guard[1] = z
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Salvage", z)
    run(s, limit=30)
    assert not alive(s, z), "the gear is gone"
    combat.destroy(s, T, u)
    run(s, limit=30)
    assert not alive(s, u), "so the promise it made cannot be kept"


@case(7036, "Leona, Determined's stun chooses, so [Deflect] is charged")
def _():
    need("Leona, Determined", "Pouty Poro")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 1
    poro = s.add_permanent(T.id_of("Pouty Poro"), 1, bf_loc(0))
    leona = s.add_permanent(T.id_of("Leona, Determined"), 0, base_loc(0), ready=True)
    before = runes(s, 0)
    attack(s, 0, 0, leona)
    run(s, picking(poro, accept=True), limit=40)
    assert s.has_flag(poro, F_STUNNED), "the stun landed"
    assert before - runes(s, 0) == 1, "809.1.c taxes an ability the same way"


@case(7033, "Riptide Rex deals nothing once his target leaves the battlefield")
def _():
    need("Riptide Rex", "Flash")
    s = fresh(hand=[T.id_of("Riptide Rex")], runes=32)
    give(s, 1, "Flash")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 9)
    cast(s, 0, "Riptide Rex", base_loc(0))
    choose(s, u)
    cast(s, 1, "Flash", u, -1)
    run(s, limit=40)
    assert int(s.perms[u, P_LOC]) == base_loc(1), "Flash pulled it home"
    assert int(s.perms[u, P_DMG]) == 0, "and the 6 had nowhere to land"


@case(7027, "Tideturner's swap exhausts nobody")
def _():
    need("Tideturner")
    s = fresh(hand=[T.id_of("Tideturner")], runes=32)
    s.bf_ctrl[0] = 0
    mate = body(s, 0, bf_loc(0), 3, ready=True)
    cast(s, 0, "Tideturner", base_loc(0))
    run(s, picking(mate, accept=True), limit=40)
    assert int(s.perms[mate, P_LOC]) == base_loc(0), "they traded places"
    assert int(s.perms[mate, P_READY]) == 1, "452: only a Standard Move exhausts"


@case(7025, "a unit at a battlefield it does not control opens a window")
def _():
    need("Sneaky Deckhand", "Gust")
    s = fresh(runes=32)
    give(s, 1, "Sneaky Deckhand")
    give(s, 0, "Gust")
    rune_deck(s)
    s.ply += 1
    s.active = s.priority = 1
    cast(s, 1, "Sneaky Deckhand", bf_loc(1))
    sd = perm_of(s, "Sneaky Deckhand", 1)[0]
    assert int(s.showdown_bf) == 1, "323.14: it staged a Showdown of its own"
    cast(s, 0, "Gust", sd)
    fight(s, limit=60)
    assert not alive(s, sd), "and that window was enough to answer it"


@case(7019, "Stand United reacts from one battlefield and buffs across the board")
def _():
    need("Stand United")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    here = body(s, 0, bf_loc(0), 3)
    there = body(s, 0, bf_loc(1), 3)
    s.set_flag(there, F_BUFFED)
    hidden_at(s, 0, 0, "Stand United")
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 1, foe)
    pass_priority_to(s, 0)
    act(s, A.A_PLAY_HIDDEN, None, 0)
    offered = targets_offered(s, 0)
    assert here in offered and there not in offered, \
        "811.1.d.2 keeps the buff at the battlefield it was hidden at"
    choose(s, here)
    drain(s)
    assert combat.might(s, T, there) == 5, "but the +1 to buffs is board-wide"


@case(7017, "a hidden gear is played to base, and Zhonya's is global from there")
def _():
    need("Zhonya's Hourglass")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    hidden_at(s, 0, 0, "Zhonya's Hourglass")
    body(s, 0, bf_loc(0), 3)                      # 190.4.c: hold the ground it
    far = body(s, 0, bf_loc(1), 3)                # was hidden at, or it is wiped
    s.ply += 1
    foe = body(s, 1, base_loc(1), 5, ready=True)
    attack(s, 1, 1, foe)
    pass_priority_to(s, 0)
    act(s, A.A_PLAY_HIDDEN, None, 0)
    drain(s)
    z = perm_of(s, "Zhonya's Hourglass", 0)[0]
    assert int(s.perms[z, P_LOC]) == base_loc(0), "a gear cannot stand at a battlefield"
    fight(s, limit=60)
    assert alive(s, far) and not alive(s, z), "it reached the other battlefield"
    assert int(s.perms[far, P_LOC]) == base_loc(0), "recalled, healed and exhausted"


@case(7016, "Hidden Blade moved off the battlefield kills nothing and draws nothing")
def _():
    need("Hidden Blade", "Flash")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    give(s, 1, "Flash")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Hidden Blade", u)
    before = int(s.n_hand[1])
    cast(s, 1, "Flash", u, -1)
    run(s, limit=40)
    assert alive(s, u), "there was no unit at a battlefield to kill"
    assert int(s.n_hand[1]) == before - 1, "and its controller drew nothing"


@case(6993, "Hidden Blade whose target went to hand draws nobody two cards")
def _():
    need("Hidden Blade", "Retreat")
    s = fresh(hand=[T.id_of("Hidden Blade")], runes=32)
    rune_deck(s)
    give(s, 1, "Retreat")
    s.bf_ctrl[0] = 1
    u = body(s, 1, bf_loc(0), 3)
    cast(s, 0, "Hidden Blade", u)
    before = int(s.n_hand[1])
    cast(s, 1, "Retreat", u)
    run(s, limit=40)
    assert not alive(s, u), "Retreat took it off the board"
    assert int(s.n_hand[1]) == before, "-1 for Retreat, +1 for the unit, and no draw"


@case(7008, "Challenge is not combat, so nothing heals afterwards")
def _():
    need("Challenge")
    s = fresh(hand=[T.id_of("Challenge")], runes=32)
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 5)
    s.bf_ctrl[1] = 1
    theirs = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Challenge", mine, theirs)
    run(s, limit=40)
    assert not alive(s, theirs), "5 into a 3 Might unit"
    assert alive(s, mine) and int(s.perms[mine, P_DMG]) == 3, \
        "and the 3 it took is still marked on it"


@case(7003, "Ravenbloom Student grows in time to survive Hextech Ray")
def _():
    need("Ravenbloom Student", "Hextech Ray", "Downstage Dramatics")
    s = fresh(runes=32)
    give(s, 1, "Hextech Ray")
    give(s, 0, "Downstage Dramatics")
    s.bf_ctrl[0] = 0
    rb = s.add_permanent(T.id_of("Ravenbloom Student"), 0, bf_loc(0))
    s.perms[rb, P_MIGHT_MOD] = 1                  # an earlier spell: 3 Might
    s.ply += 1
    s.active = s.priority = 1
    cast(s, 1, "Hextech Ray", rb)
    cast(s, 0, "Downstage Dramatics")
    run(s, limit=40)
    assert alive(s, rb), "4 Might by the time the 3 arrived"
    assert int(s.perms[rb, P_DMG]) == 3


@case(7002, "your own conquer triggers are yours to order")
def _():
    need("Kai'Sa, Survivor", "The Candlelit Sanctum")
    s = fresh(runes=32)
    s.bf_card[0] = T.id_of("The Candlelit Sanctum")
    s.bf_ctrl[0] = 1
    kai = s.add_permanent(T.id_of("Kai'Sa, Survivor"), 0, base_loc(0), ready=True)
    seen = [False]

    def pref(st, who, legal):
        if any(a.kind == A.A_ORDER for a in legal):
            seen[0] = True
        return None
    attack(s, 0, 0, kai)
    run(s, pref, limit=60)
    assert int(s.bf_ctrl[0]) == 0, "she took it"
    assert seen[0], "383.3.d: two of my triggers at once, and I place them"


@case(7001, "Garen's static is on the moment he arrives")
def _():
    need("Garen - Commander", "Bellows Breath")
    s = fresh(runes=32)
    give(s, 1, "Bellows Breath")
    s.runes_ready[1, :] = 12
    s.bf_ctrl[0] = 1
    body(s, 1, bf_loc(0), 9)
    small = body(s, 0, base_loc(0), 1, ready=True)
    gar = s.add_permanent(T.id_of("Garen - Commander"), 0, base_loc(0), ready=True)
    attack(s, 0, 0, small, gar)
    assert combat.might(s, T, small) == 2, "+1 from Garen, standing beside him"
    cast(s, 1, "Bellows Breath", small, -1, -1)
    drain(s)
    assert alive(s, small), "1 damage on a 2 Might unit"


@case(6998, "Hidden Blade kills the Merchant without denying his trigger")
def _():
    need("Hidden Blade", "Traveling Merchant")
    s = fresh(runes=32)
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    hidden_at(s, 0, 0, "Hidden Blade")
    tm = s.add_permanent(T.id_of("Traveling Merchant"), 1, base_loc(1), ready=True)
    s.ply += 1
    s.n_hand[1] = 0
    give(s, 1, "Cleave")
    before_trash = int(s.n_trash[1])
    attack(s, 1, 0, tm)
    pass_priority_to(s, 0)
    act(s, A.A_PLAY_HIDDEN, None, 0)
    choose(s, tm)
    fight(s, limit=60)
    assert not alive(s, tm), "killed while his move trigger sat on the Chain"
    assert int(s.n_trash[1]) > before_trash, "and the discard still happened"


@case(6996, "Gusting the Hook's target leaves it nothing to trade in")
def _():
    need("Baited Hook", "Gust")
    s = fresh(runes=32)
    give(s, 1, "Gust")
    rune_deck(s)
    s.runes_ready[1, :] = 12
    s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0))
    s.bf_ctrl[0] = 0
    bait = body(s, 0, bf_loc(0), 3)
    n = int(s.deck_ptr[0])
    s.deck[0, n] = T.id_of("Cruel Patron")
    act(s, A.A_ACTIVATE, None, 0)
    choose(s, bait)
    cast(s, 1, "Gust", bait)
    run(s, limit=60)
    assert not alive(s, bait), "it went to hand, not to the trash"
    assert not perm_of(s, "Cruel Patron", 0), "nothing was killed, so nothing was hooked"


@case(6991, "a unit brought into a combat takes its controller's side")
def _():
    need("Ride The Wind", "Sharkling")
    s = fresh(runes=32)
    give(s, 0, "Ride The Wind")
    s.bf_ctrl[0] = 0
    body(s, 0, bf_loc(0), 3)
    shark = s.add_permanent(T.id_of("Sharkling"), 0, base_loc(0))
    s.ply += 1
    foe = body(s, 1, base_loc(1), 3, ready=True)
    attack(s, 1, 0, foe)
    cast(s, 0, "Ride The Wind", shark, bf_loc(0))
    run(s, limit=20, stop=lambda st: st.n_chain == 0 and st.n_trig == 0)
    assert int(s.showdown_bf) == 0 and int(s.attacker) == 1
    assert combat.might(s, T, shark) == 1, "[Assault 4] is an attacker's keyword"


def _two_doomed_with_a_guard():
    """Seat 1 holding a played Zhonya's Hourglass, with a 2 Might and a 6 Might
    unit both about to take exactly lethal damage at the same battlefield."""
    s = fresh(runes=32, seat=1)
    give(s, 1, "Zhonya's Hourglass")
    s.bf_ctrl[0] = 1
    # PLAYED, so its [Play] trigger registers the guard -- staging the gear with
    # `add_permanent` leaves `death_guard` at -1 and measures nothing.
    cast(s, 1, "Zhonya's Hourglass", base_loc(1))
    drain(s)
    zh = perm_of(s, "Zhonya's Hourglass", 1)[0]
    small = body(s, 1, bf_loc(0), 2)
    big = body(s, 1, bf_loc(0), 6)
    s.perms[small, P_DMG] = 2
    s.perms[big, P_DMG] = 6
    return s, zh, small, big


def _answer_guard(s, perm):
    who = A.acting_seat(s)
    lg = A.legal_actions(s, T, V1, who)
    opts = sorted(a.arg for a in lg if a.kind == A.A_PICK)
    A.apply(s, T, V1, next(a for a in lg if a.kind == A.A_PICK and a.arg == perm))
    drain(s)
    return who, opts


@case(7059, "one Zhonya's, two simultaneous deaths: its controller picks which")
def _():
    """373 spells this out and its worked example is this card: "Two units
    controlled by the same player die in the same cleanup. That player also
    controls Zhonya's Hourglass. They must decide which event to apply Zhonya's
    Hourglass to first." 374 makes the chooser the REPLACEMENT's controller.

    It used to be decided by row order -- the invisible tie-break this engine
    keeps having to remove. `_destroy` now suspends on `pend_guard` when more
    than one death qualifies, exactly as it does for the 372 order and for Altar
    of Blood, by returning without killing.
    """
    need("Zhonya's Hourglass")
    s, zh, small, big = _two_doomed_with_a_guard()
    assert sorted(combat.guard_candidates(s, T, 1, (small, big), small)) \
        == sorted((small, big)), "both units of the batch qualify"
    combat.enforce_lethal(s, T)
    assert int(s.pend_guard) == 1, (
        f"373 owes the guard's controller a choice, got pend_guard="
        f"{int(s.pend_guard)}")
    who, opts = _answer_guard(s, big)
    assert who == 1 and opts == sorted((small, big)), \
        f"374 -- asked of the guard's controller, both deaths offered: {who} {opts}"
    assert alive(s, big) and int(s.perms[big, P_LOC]) == base_loc(1) \
        and int(s.perms[big, P_READY]) == 0, "the chosen one is healed and recalled"
    assert not alive(s, small), "373.2 -- one replacement, one sequence"
    assert not alive(s, zh), "and the Hourglass is what died instead"


@case(7059.1, "...and the other pick is reachable, which is the whole point")
def _():
    need("Zhonya's Hourglass")
    s, zh, small, big = _two_doomed_with_a_guard()
    combat.enforce_lethal(s, T)
    _answer_guard(s, small)
    assert alive(s, small) and not alive(s, big), \
        "saving the 2 Might one instead has to be a legal answer"
    assert not alive(s, zh)


@case(7059.2, "a single qualifying death asks nothing and behaves as before")
def _():
    """The guard against a needless decision point: with one death there is
    nothing for 373 to order, so no window opens at all."""
    need("Zhonya's Hourglass")
    s, zh, small, big = _two_doomed_with_a_guard()
    s.perms[big, P_DMG] = 0                      # only the small one is doomed
    assert combat.guard_candidates(s, T, 1, (small,), small) == [small]
    combat.enforce_lethal(s, T)
    assert int(s.pend_guard) < 0, "one candidate is not a choice"
    assert alive(s, small) and int(s.perms[small, P_LOC]) == base_loc(1), \
        "and it is saved without asking"
    assert not alive(s, zh) and alive(s, big)
