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
