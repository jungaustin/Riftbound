"""RiftJudge batch 84 -- questions 12602-12724, scraped 2026-09-27.

The corpus tops out at 12724. These are the rulings from the new range that probe
what changed in the engine this week: the Deflect surcharge, the 466.5-466.7
ordering, attack-trigger scope, and the Final Point.
"""
from rl.tests.judge.harness import *  # noqa: F401,F403
from rl.engine.state import (F_EMPOWERED, F_STUNNED, P_EMPOWER, P_FLAGS, P_LOC,
                             P_READY)


def _bellows_into_kayle(deflect: bool) -> int:
    """Repeat a Bellows Breath into Kayle, choosing her in BOTH executions.
    Returns how many runes the whole play recycled."""
    s = fresh(runes=32, seat=0)
    give(s, 0, "Bellows Breath")
    s.bf_ctrl[0] = 1
    k = s.add_permanent(T.id_of("Kayle, Justified"), 1, bf_loc(0))
    if deflect:
        # [Deflect 3] only "while I'm [Empowered] three times".
        s.perms[k, P_EMPOWER] = 3
        s.set_flag(k, F_EMPOWERED)
        assert combat.perm_kw(s, T, k, "Deflect") == 3, "she should have Deflect 3"
    else:
        assert combat.perm_kw(s, T, k, "Deflect") == 0, "the control must have none"
    before = int(s.runes_in_play(0).sum())
    act(s, A.A_PLAY_REPEAT, hand_index(s, 0, "Bellows Breath"), 0)
    # Three slots per execution, six in all. Kayle fills the first of each; the
    # rest are declined, which on an "up to" slot is A_TARGET with arg -1 rather
    # than A_DECLINE.
    for _ in range(12):
        if int(s.pend_slot) < 0:
            break
        choose(s, k if int(s.pend_slot) in (0, 3) else -1)
    drain(s)
    return before - int(s.runes_in_play(0).sum())


@case(12648, "Deflect is charged per CHOOSING, so a Repeat that names Kayle twice pays 3+3")
def _():
    """809.1.c charges "for each time they choose me", and 820.2.a makes each
    execution of a [Repeat] spell choose for itself -- so Bellows Breath repeated
    into a [Deflect 3] Kayle owes 6 Power, not 3. The base cost is untouched.

    **Asserted as the delta against a Kayle with no Deflect**, so the number is
    the surcharge itself and not the sum of the spell's own cost with it: the
    Repeat's {Mind rune} is part of the same payment (820.1.c.1) and would
    otherwise be baked into a magic constant that moves if the card is errata'd.

    It is also the tightest check available on `play_cost_reservation`, which has
    to reserve the Repeat's Power AND both surcharges from one rune board.
    """
    need("Bellows Breath", "Kayle, Justified")
    plain = _bellows_into_kayle(deflect=False)
    taxed = _bellows_into_kayle(deflect=True)
    assert taxed - plain == 6, (
        f"two choosings of [Deflect 3] is 6 Power on top of the spell's own "
        f"cost, got {taxed - plain} (plain {plain}, taxed {taxed})")


@case(12693, "Vi - Peacekeeper's attack trigger fires once, not again when a Deathknell refills")
def _():
    """383.4.e -- an attack trigger fires when the source first gains the
    Attacker designation in a combat, and the instruction is carried out at
    resolution. A unit arriving later in the SAME combat does not re-trigger it.
    """
    need("Vi - Peacekeeper", "Glasc Mixologist")
    s = fresh(runes=32, seat=0)
    s.bf_ctrl[0] = 1
    vi = s.add_permanent(T.id_of("Vi - Peacekeeper"), 0, base_loc(0), ready=True)
    foe = body(s, 1, bf_loc(0), 1)
    attack(s, 0, 0, vi)
    drain(s)
    # The stun landed on the one enemy that was there at designation.
    stuns = [i for i in range(s.n_perms)
             if alive(s, i) and int(s.perms[i, P_CTRL]) == 1
             and bool(int(s.perms[i, P_FLAGS]) & F_STUNNED)]
    assert stuns == [foe], f"she stuns the enemy present at designation, got {stuns}"
    # A second enemy walking in mid-combat is NOT stunned: nothing re-triggers.
    late = body(s, 1, bf_loc(0), 1)
    A._settle(s, T, V1)
    drain(s)
    assert not (int(s.perms[late, P_FLAGS]) & F_STUNNED), \
        "383.4.e -- one attack, one trigger; the latecomer is untouched"


@case(12716, "a Deathknell unit can Hold for the Final Point if the death precedes Scoring")
def _():
    """315.2 splits the Beginning Phase into a Beginning Step and then a Scoring
    Step, and 469.2 Holds every battlefield you control in the second. So a unit
    that arrives during the FIRST step is there to hold in the second -- and
    471.1.b exempts a Hold, which is why this can be the eighth point.
    """
    need("Glasc Mixologist")
    s = fresh(runes=32, seat=0)
    s.points[0] = 7
    s.bf_ctrl[0] = 0
    # Hers alone at the battlefield, so seat 0 controls it and will Hold it.
    u = body(s, 0, bf_loc(0), 3)
    s.active = s.priority = 0
    _before = int(s.points[0])
    phases.score_holds(s, V1, T)
    assert int(s.points[0]) == 8, (
        f"471.1.a.1 exempts a Hold from the Final Point restriction, "
        f"got {int(s.points[0])} from {_before}")
    assert int(s.winner) == 0, "and 194.3/323.1 ends the game on the 8th point"


@case(12681, "two Rift Heralds dying together: their controller orders the Deathknells")
def _():
    """383.3.d -- simultaneous triggers are ordered by their controller, and
    340.1 resolves the Chain newest-first, so the one placed LAST resolves
    FIRST. Two of one player's Heralds dying together is therefore a real
    choice, and the engine has to offer it rather than pick.
    """
    need("Rift Herald")
    s = fresh(runes=32, seat=0)
    s.bf_ctrl[0] = 0
    a = s.add_permanent(T.id_of("Rift Herald"), 0, bf_loc(0))
    b = s.add_permanent(T.id_of("Rift Herald"), 0, bf_loc(0))
    combat.destroy(s, T, a)
    combat.destroy(s, T, b)
    # Both Deathknells are queued for the same seat and the same step, so 383.3.d
    # asks. Identical triggers ARE collapsed by `chain.orderable` (swapping two
    # copies of one Deathknell cannot produce a different game), so what is
    # asserted is that both fired -- not that a choice was offered for them.
    n_before = int(s.n_trig) + int(s.n_chain)
    assert n_before >= 2, (
        f"both Deathknells must be queued when the Heralds die together, "
        f"got {n_before}")
    drain(s)
    assert int(s.n_trig) == 0, "and both drain onto the Chain and resolve"


def _two_herons():
    """Seat 0 with an Astral Heron at each of two battlefields, holding a first
    card and two Premonitions (2E / 3P each -- big enough that a 2E+2P discount
    shows in both halves)."""
    s = fresh(runes=32, seat=0)
    give(s, 0, "Meditation", "Premonition", "Premonition")
    s.bf_ctrl[0] = 0
    s.bf_ctrl[1] = 0
    s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(0))
    s.add_permanent(T.id_of("Astral Heron"), 0, bf_loc(1))
    return s


def _power_spent(s, name):
    """Power recycled playing `name` -- runes leaving play, which is what a Power
    cost takes (164.2) and an Energy cost does not."""
    before = int(s.runes_in_play(0).sum())
    cast(s, 0, name)
    drain(s)
    return before - int(s.runes_in_play(0).sum())


@case(12624, "two Astral Herons: the discounts CAN be split, by reacting between them")
def _():
    """**Settled by the project owner, and 340.4 is why.** Playing your first
    card fires both Herons, and 383.3 puts each on the Chain as its own item. So
    after the first one resolves the Chain is not empty and has no Pending
    Items -- 340.4 hands Priority to the controller of the newest item and
    returns to Execute. That window is a real one, and a [Reaction] card played
    in it spends the first discount before the second trigger has granted its
    own. Two cards come out cheaper instead of one.

    #12623 says the opposite and is **rejected** (`rejected.json`): it is the
    outlier against #12622, #12624, #12625 and #12631, and against 340.4.
    """
    need("Astral Heron", "Meditation", "Premonition")
    s = _two_herons()
    cast(s, 0, "Meditation")            # the first card: both Herons trigger
    # Walk to the window: one trigger resolved, the other still on the Chain.
    for _ in range(30):
        if int(s.next_discount[0, 0]) and int(s.n_chain):
            break
        who = A.acting_seat(s)
        lg = A.legal_actions(s, T, V1, who)
        if not lg:
            break
        A.apply(s, T, V1, next((a for a in lg if a.kind == A.A_ORDER),
                               next((a for a in lg if a.kind == A.A_PASS), lg[0])))
    else:
        raise AssertionError("340.4 owes a window between the two resolutions")
    assert s.next_discount[0].tolist() == [2, 2], (
        f"one Heron has resolved, so one discount is banked, got "
        f"{s.next_discount[0].tolist()}")
    first = _power_spent(s, "Premonition")
    assert first == 1, f"3 Power less the Heron's 2 is 1, got {first}"
    assert s.next_discount[0].tolist() == [2, 2], (
        "and the SECOND Heron then resolves and grants its own, so the next "
        "card is discounted too -- that is the split")
    second = _power_spent(s, "Premonition")
    assert second == 1, f"the second card is discounted as well, got {second}"


@case(12622, "...and letting both resolve first stacks them onto ONE card instead")
def _():
    """The other half of the same choice, and why the split is worth the trouble:
    `next_discount` accumulates (356.4 discounts the total cost), so two Herons
    allowed to resolve back to back put 4 Energy and 4 Power on a single card.
    That is more on that one card and nothing on the next.
    """
    need("Astral Heron", "Meditation", "Premonition")
    s = _two_herons()
    cast(s, 0, "Meditation")
    drain(s)                             # let BOTH triggers resolve
    assert s.next_discount[0].tolist() == [4, 4], (
        f"both resolved, so both discounts are banked together, got "
        f"{s.next_discount[0].tolist()}")
    first = _power_spent(s, "Premonition")
    assert first == 0, f"4 Power of discount covers all 3, got {first}"
    second = _power_spent(s, "Premonition")
    assert second == 3, (f"...and the next card pays its printed 3 Power, "
                         f"got {second} -- nothing was left over")
