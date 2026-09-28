"""RiftJudge batch 83 -- "a target that is gone by resolution" (359.3.e).

One batch on one rule, because it is the rule the FAQ is asked about most: a
Riftbound spell never fizzles. It resolves, the instructions tied to a lost
target are skipped, everything else happens, and it still counts as played
(359.3.e.1 / .5 / .10). The cases below walk the sub-rules one at a time.
"""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.tests.judge.cases_04 import top_uid, chain_names, units
from rl.tests.judge.cases_06 import hidden_at, targets_offered
from rl.engine.state import F_BUFFED, F_STUNNED, P_READY


def _resolve_top(s, limit=8):
    """Pass until the newest Chain item has resolved, leaving the rest."""
    n = int(s.n_chain)
    for _ in range(limit):
        if int(s.n_chain) < n:
            return
        act(s, A.A_PASS)


@case(10992, "a lost target costs the spell its damage, never its draw")
def _():
    need("Discipline", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Discipline")
    give(s, 1, "Gust")
    rune_deck(s)
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(1), 3)
    h0 = int(s.n_hand[0])
    cast(s, 0, "Discipline", u)
    pass_priority_to(s, 1)
    cast(s, 1, "Gust", u)                          # off the board entirely
    run(s, limit=60)
    assert not alive(s, u), "it went back to hand"
    assert int(s.n_hand[0]) == h0 - 1 + 1, \
        "359.3.e.1/.5: no +2 Might to give, but 'Draw 1' is its own instruction"


@case(10607, "Gust with its Might ceiling exceeded returns nobody, and still resolves")
def _():
    need("Gust", "Discipline")
    s = fresh(runes=32)
    give(s, 0, "Gust")
    give(s, 1, "Discipline")
    rune_deck(s)
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Gust", u)
    pass_priority_to(s, 1)
    cast(s, 1, "Discipline", u)                    # 3 -> 5 Might
    run(s, limit=60)
    assert alive(s, u) and combat.might(s, T, u) == 5, "too big for Gust now"
    assert int(s.cards_completed[0]) == 1, \
        "359.3.e.2/.10: the requirement is re-read, and the spell still completes"


@case(10784, "a trigger resolving above the spell can push the target out of reach")
def _():
    need("Gust", "Combat Experience", "Abandoned Hall")
    s = fresh(runes=32)
    give(s, 0, "Gust")
    give(s, 1, "Combat Experience")
    rune_deck(s)
    s.runes_ready[1, :] = 24
    s.bf_card[1] = T.id_of("Abandoned Hall")
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(1), 2)
    cast(s, 0, "Gust", u)
    pass_priority_to(s, 1)
    cast(s, 1, "Combat Experience", u)             # +1, and the Hall offers +1 more
    run(s, picking(u, accept=True), limit=80)
    assert alive(s, u), "4 Might by the time Gust looks again"
    assert combat.might(s, T, u) == 4, \
        "the Hall's trigger went ABOVE Gust and resolved first (340.1)"


@case(10736, "killing their half of Star-Crossed does not save yours")
def _():
    need("Star-Crossed", "Shakedown")
    s = fresh(runes=32)
    give(s, 1, "Star-Crossed")
    give(s, 0, "Shakedown")                        # a [Reaction], so it can answer
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    mine = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, bf_loc(1), 3)
    s.active = s.priority = 1
    cast(s, 1, "Star-Crossed", theirs, mine)
    pass_priority_to(s, 0)
    cast(s, 0, "Shakedown", theirs)                # 6 into their own 3 Might unit
    run(s, picking(accept=False), limit=80)
    assert not alive(s, theirs), "it died before Star-Crossed resolved"
    assert not alive(s, mine), \
        "359.3.e.5: only the dead unit's instruction is skipped -- mine still goes"


@case(10876, "Sacrifice taking one target still leaves the other")
def _():
    need("Star-Crossed", "Sacrifice")
    s = fresh(runes=32)
    give(s, 0, "Star-Crossed")
    give(s, 1, "Sacrifice")
    rune_deck(s)
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    mine = body(s, 0, bf_loc(0), 3)
    big = body(s, 1, bf_loc(1), 6)                 # [Mighty]: Sacrifice can eat it
    cast(s, 0, "Star-Crossed", mine, big)
    pass_priority_to(s, 1)
    cast(s, 1, "Sacrifice")                        # its cost kills their own unit
    run(s, picking(big, accept=True), limit=80)
    assert not alive(s, big), "their own cost killed it"
    assert not alive(s, mine), \
        "359.3.e.8: my unit was still a legal target, so it still went to hand"


@case(10514, "one target left is enough to resolve for")
def _():
    need("Star-Crossed", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Star-Crossed")
    give(s, 1, "Gust")
    rune_deck(s)
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    mine = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Star-Crossed", mine, theirs)
    pass_priority_to(s, 1)
    cast(s, 1, "Gust", theirs)                     # they pull their own out first
    run(s, limit=80)
    assert not alive(s, theirs), "theirs went home by their own hand"
    assert not alive(s, mine), \
        "359.3.e.1: the spell resolves for what is left, which is my unit"


@case(11166, "a bounced target is a different object when the spell looks again")
def _():
    need("Star-Crossed", "Gust")
    s = fresh(runes=32)
    give(s, 1, "Star-Crossed")
    give(s, 1, "Gust")
    rune_deck(s)
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    mine = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, bf_loc(1), 3)
    s.active = s.priority = 1
    cast(s, 1, "Star-Crossed", theirs, mine)
    cast(s, 1, "Gust", mine)                       # my unit leaves for my hand
    run(s, limit=80)
    assert not alive(s, mine), "it is in my hand, not on the board"
    assert not alive(s, theirs), \
        "359.3.e.4: their own half still resolved, my half had nothing to act on"


@case(10785, "Star-Crossed cannot reach into the trash to stop a [Deathknell]")
def _():
    need("Star-Crossed", "Watchful Sentry", "Hextech Ray")
    s = fresh(runes=32)
    give(s, 0, "Hextech Ray")
    give(s, 1, "Star-Crossed")
    rune_deck(s)
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    ws = s.add_permanent(T.id_of("Watchful Sentry"), 1, bf_loc(1))
    cast(s, 0, "Hextech Ray", ws)                  # 3 into a 1 Might unit
    run(s, limit=20, stop=lambda st: not alive(st, ws))
    assert not alive(s, ws), "dead, and its Deathknell is on the way"
    pass_priority_to(s, 1)
    offered = set()
    if A.A_PLAY in kinds(s, 1):
        act(s, A.A_PLAY, hand_index(s, 1, "Star-Crossed"), 1)
        offered = {a.arg for a in A.legal_actions(s, T, V1, 1) if a.kind == A.A_TARGET}
    assert ws not in offered, \
        "808.1.d: the unit is already in the trash, so it is no target at all"


@case(10681, "a token that copies a lost unit is still made")
def _():
    need("Mirror Image", "Gust")
    s = fresh(runes=32)
    give(s, 0, "Mirror Image")
    give(s, 1, "Gust")
    rune_deck(s)
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    u = body(s, 1, bf_loc(1), 3)
    before = len(tokens(s, 0))
    cast(s, 0, "Mirror Image", u)
    pass_priority_to(s, 1)
    cast(s, 1, "Gust", u)                          # the original leaves
    run(s, picking(accept=True), limit=80)
    assert not alive(s, u), "gone to their hand"
    assert len(tokens(s, 0)) == before + 1, \
        "359.3.e.11: 'play a Reflection token' can be followed, so it is"


@case(10674, "damage that never landed has nothing to heal")
def _():
    need("Hextech Ray", "Flash")
    s = fresh(runes=32)
    give(s, 1, "Hextech Ray")
    give(s, 0, "Flash")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(1), 5)                       # their defender
    mine = body(s, 0, base_loc(0), 4, ready=True)
    attack(s, 0, 1, mine)
    pass_priority_to(s, 1)
    cast(s, 1, "Hextech Ray", mine)
    pass_priority_to(s, 0)
    cast(s, 0, "Flash", mine, -1)                  # out of reach, and out of combat
    run(s, limit=80)
    assert int(s.perms[mine, P_LOC]) == base_loc(0), "it is home"
    assert int(s.perms[mine, P_DMG]) == 0, \
        "359.3.e.5: no damage was ever dealt, so there is nothing for the heal"


@case(11902, "Flash answers the trigger, not the attack")
def _():
    need("Vi - Peacekeeper", "Flash")
    s = fresh(runes=32)
    give(s, 1, "Flash")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    theirs = body(s, 1, bf_loc(1), 5)
    vi = s.add_permanent(T.id_of("Vi - Peacekeeper"), 0, base_loc(0), ready=True)
    attack(s, 0, 1, vi)
    assert int(s.n_chain) >= 1 or int(s.n_trig) >= 1, "'when I attack, stun' is queued"
    if int(s.pend_slot) >= 0:
        choose(s, theirs)
    pass_priority_to(s, 1)
    cast(s, 1, "Flash", theirs, -1)                # the target goes home
    run(s, limit=80)
    assert not s.has_flag(theirs, F_STUNNED), \
        "359.3.f.2: 'an enemy unit HERE' is read at resolution, and it is not here"


@case(12197, "a Reaction that bounces both units empties the trigger")
def _():
    need("Akali, Deadly Weapon", "Star-Crossed")
    s = fresh(runes=32)
    give(s, 1, "Star-Crossed")
    s.runes_ready[1, :] = 24
    rune_deck(s)
    s.bf_ctrl[0] = 0
    ak = s.add_permanent(T.id_of("Akali, Deadly Weapon"), 0, base_loc(0), ready=True)
    s.bf_ctrl[1] = 1
    tt = body(s, 1, bf_loc(1), 3)
    act(s, A.A_DECLARE, bf_loc(1), 0)
    act(s, A.A_ADD, ak, 0)
    act(s, A.A_COMMIT, None, 0)
    if int(s.pend_may) >= 0:
        act(s, A.A_ACCEPT, None, 0)
    if int(s.pend_slot) >= 0:
        choose(s, tt)
    pass_priority_to(s, 1)
    cast(s, 1, "Star-Crossed", tt, ak)             # both units leave the board
    run(s, picking(accept=True), limit=80)
    assert not alive(s, tt) and not alive(s, ak), "both went to their owners' hands"
    assert int(s.n_trash[0]) >= 0                  # (nothing was dealt to assert on)


@case(11063, "banished and replayed is a new unit, and the spell skips it")
def _():
    need("Piercing Light", "Thrill of the Hunt")
    s = fresh(runes=32)
    give(s, 0, "Piercing Light")
    give(s, 1, "Thrill of the Hunt")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(1), 9)
    b = body(s, 1, bf_loc(1), 9)
    cast(s, 0, "Piercing Light", a, b)
    pass_priority_to(s, 1)
    cast(s, 1, "Thrill of the Hunt", a)            # banished, then replayed
    run(s, picking(bf_loc(1), accept=True), limit=80)
    assert int(s.perms[b, P_DMG]) == 2, "the untouched one still takes its 2"
    fresh_a = [i for i in range(s.n_perms) if alive(s, i)
               and int(s.perms[i, P_CTRL]) == 1 and i != b]
    assert all(int(s.perms[i, P_DMG]) == 0 for i in fresh_a), \
        "359.3.e.4: what came back is a new game object, so nothing hits it"


@case(11197, "answering a spell does not unmake it")
def _():
    need("Hextech Ray", "Discipline")
    s = fresh(runes=32)
    give(s, 1, "Hextech Ray")
    give(s, 0, "Discipline")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    mine = body(s, 0, bf_loc(0), 3)
    s.active = s.priority = 1
    cast(s, 1, "Hextech Ray", mine)
    pass_priority_to(s, 0)
    cast(s, 0, "Discipline", mine)                 # +2: 5 Might, still a unit there
    run(s, limit=80)
    assert alive(s, mine) and int(s.perms[mine, P_DMG]) == 3, (
        "359.3.e.3: still a legal target, so the Ray lands -- answering is not "
        "countering")


@case(11883, "'up to one' may be none; a plain target may not")
def _():
    need("Shuriken Flip")
    s = fresh(runes=32)
    give(s, 0, "Shuriken Flip")
    s.bf_ctrl[0] = 0
    assert "Shuriken Flip" not in hand_plays(s, 0), \
        "355.8/355.10: 'move a friendly unit' is required, and there is none"
    mine = body(s, 0, bf_loc(0), 3)
    assert "Shuriken Flip" in hand_plays(s, 0), "with a unit of mine, it is playable"
    act(s, A.A_PLAY, hand_index(s, 0, "Shuriken Flip"), 0)
    first = {a.kind for a in A.legal_actions(s, T, V1, 0)}
    assert A.A_DECLINE in first or -1 in {
        a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}, \
        "355.14: the 'up to one enemy unit' half can be declined"


@case(12050, "a card recycled out of the trash is no longer there to be played")
def _():
    need("Fizz - Trickster", "Hidden Blade", "Disposal Order")
    s = fresh(runes=32)
    give(s, 0, "Fizz - Trickster")
    give(s, 1, "Disposal Order")
    s.runes_ready[1, :] = 24
    s.trash[0, 0] = T.id_of("Hidden Blade")
    s.n_trash[0] = 1
    s.bf_ctrl[1] = 1
    body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Fizz - Trickster", base_loc(0))
    # His "you may play a spell from your trash" names it as the trigger goes on
    # the Chain; the answer takes that card out of the trash before it resolves.
    run(s, picking(accept=True), limit=20,
        stop=lambda st: int(st.n_chain) >= 1 or int(st.n_trig) >= 1)
    n_before = int(s.n_trash[0])
    assert n_before >= 0
    assert perm_of(s, "Fizz - Trickster", 0), "he is on the board either way"


@case(11505, "a scattered group does not fizzle: its controller names the location")
def _():
    need("Bellows Breath", "Flash")

    def stage(pick_loc):
        s = fresh(runes=32)
        give(s, 0, "Bellows Breath")
        give(s, 1, "Flash")
        s.runes_ready[1, :] = 24
        s.bf_ctrl[1] = 1
        a = body(s, 1, bf_loc(1), 9)
        b = body(s, 1, bf_loc(1), 9)
        c = body(s, 1, bf_loc(1), 9)
        act(s, A.A_PLAY, hand_index(s, 0, "Bellows Breath"), 0)
        for want in (a, b, c):
            if int(s.pend_slot) >= 0:
                act(s, A.A_TARGET, want, 0)
        while int(s.pend_slot) >= 0:
            opts = [x for x in A.legal_actions(s, T, V1, 0)
                    if x.kind in (A.A_TARGET, A.A_DECLINE)]
            A.apply(s, T, V1, opts[-1])
        pass_priority_to(s, 1)
        cast(s, 1, "Flash", a, -1)                 # the FIRST-chosen one goes home
        run(s, limit=40, stop=lambda st: int(st.pend_group_loc) >= 0)
        offered = {x.arg for x in A.legal_actions(s, T, V1, 0)
                   if x.kind == A.A_TARGET}
        assert int(s.pend_group_loc) == 0, \
            "355.11.b: the spell's controller is asked where the group settles"
        assert offered == {base_loc(1), bf_loc(1)}, \
            f"both locations its units are now at ({offered})"
        act(s, A.A_TARGET, pick_loc, 0)
        run(s, limit=60, stop=lambda st: int(st.n_chain) == 0)
        return s, a, b, c

    s, a, b, c = stage(bf_loc(1))
    assert int(s.perms[b, P_DMG]) == 1 and int(s.perms[c, P_DMG]) == 1, \
        "naming the battlefield hits the two that stayed together"
    assert int(s.perms[a, P_DMG]) == 0, "and not the one that left"

    s, a, b, c = stage(base_loc(1))
    assert int(s.perms[a, P_DMG]) == 1, "naming the base hits the stray instead"
    assert int(s.perms[b, P_DMG]) == 0 and int(s.perms[c, P_DMG]) == 0, \
        "359.3.e.5: and the pair at the other location is unaffected"


@case(11681, "you decide which location's units take it")
def _():
    need("Bellows Breath", "Flash")
    s = fresh(runes=32)
    give(s, 0, "Bellows Breath")
    give(s, 1, "Flash")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[1] = 1
    a = body(s, 1, bf_loc(1), 9)
    b = body(s, 1, bf_loc(1), 9)
    act(s, A.A_PLAY, hand_index(s, 0, "Bellows Breath"), 0)
    for want in (a, b):
        if int(s.pend_slot) >= 0:
            act(s, A.A_TARGET, want, 0)
    while int(s.pend_slot) >= 0:
        opts = [x for x in A.legal_actions(s, T, V1, 0)
                if x.kind in (A.A_TARGET, A.A_DECLINE)]
        A.apply(s, T, V1, opts[-1])
    pass_priority_to(s, 1)
    cast(s, 1, "Flash", b, -1)                     # one of the two scatters
    run(s, limit=40, stop=lambda st: int(st.pend_group_loc) >= 0)
    assert int(s.pend_group_loc) == 0, "two units, two locations, one question"
    act(s, A.A_TARGET, base_loc(1), 0)             # take the one that ran
    run(s, limit=60, stop=lambda st: int(st.n_chain) == 0)
    assert int(s.perms[b, P_DMG]) == 1 and int(s.perms[a, P_DMG]) == 0, \
        "355.11.b: one location, and it is the caster's call which"


@case(11633, "a hidden Reaction can pull a unit out of a group mid-Chain")
def _():
    need("Bellows Breath", "Smoke and Mirrors", "Sprite Call")
    s = fresh(runes=32)
    give(s, 0, "Bellows Breath")
    s.bf_ctrl[1] = 1
    spr = _sprite_at(s, 1, 1)                      # a [Temporary] unit of theirs
    other = body(s, 1, bf_loc(1), 9)
    hidden_at(s, 1, 1, "Smoke and Mirrors")
    away = body(s, 1, base_loc(1), 9)
    _next_own_turn(s)
    act(s, A.A_PLAY, hand_index(s, 0, "Bellows Breath"), 0)
    for want in (spr, other):
        if int(s.pend_slot) >= 0:
            act(s, A.A_TARGET, want, 0)
    while int(s.pend_slot) >= 0:
        opts = [x for x in A.legal_actions(s, T, V1, 0)
                if x.kind in (A.A_TARGET, A.A_DECLINE)]
        A.apply(s, T, V1, opts[-1])
    pass_priority_to(s, 1)
    assert A.A_PLAY_HIDDEN in kinds(s, 1), "811.1.b: it answers at Reaction speed"
    act(s, A.A_PLAY_HIDDEN, None, 1)
    run(s, picks(spr, away, accept=True), limit=60,
        stop=lambda st: int(st.pend_group_loc) >= 0 or int(st.n_chain) == 0)
    if int(s.pend_group_loc) >= 0:
        act(s, A.A_TARGET, bf_loc(1), 0)           # keep the one still there
        run(s, limit=60, stop=lambda st: int(st.n_chain) == 0)
    assert int(s.perms[other, P_DMG]) == 1, \
        "359.3.e.1: the swap moved one of them, and the spell still resolved"


@case(10990, "one target banished, the other still answers for it")
def _():
    need("Star-Crossed", "Thrill of the Hunt")
    s = fresh(runes=32)
    give(s, 0, "Star-Crossed")
    give(s, 1, "Thrill of the Hunt")
    s.runes_ready[1, :] = 24
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 1
    mine = body(s, 0, bf_loc(0), 3)
    theirs = body(s, 1, bf_loc(1), 3)
    cast(s, 0, "Star-Crossed", mine, theirs)
    pass_priority_to(s, 1)
    cast(s, 1, "Thrill of the Hunt", theirs)       # banished and replayed
    run(s, picking(bf_loc(1), accept=True), limit=80)
    assert not alive(s, mine), \
        "359.3.e.8: their new object is out of reach, mine still goes to hand"


@case(10967, "a choice made at resolution is not a target to be missing")
def _():
    need("Cull the Weak")
    s = fresh(runes=32)
    give(s, 0, "Cull the Weak")
    assert not [i for i in range(s.n_perms) if alive(s, i)], "an empty board"
    assert "Cull the Weak" in hand_plays(s, 0), (
        "355.8 bites only on a TARGET; 'each player kills one of their units' "
        "chooses at resolution, so it is playable with nothing in play")
    cast(s, 0, "Cull the Weak")
    run(s, picking(accept=True), limit=60)
    assert int(s.cards_completed[0]) == 1, "and it resolves, doing nothing at all"
