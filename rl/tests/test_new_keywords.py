"""Keywords introduced by a set that is not out yet.

Run from the repo root. These need the cards, so run them with the gate open:

    RIFTBOUND_UPCOMING=1 python -m rl.tests.test_new_keywords

Without the flag the suite reports what it skipped and exits 0, so it is safe
in the default sequence -- an unreleased set must not be able to fail the build
for a released game.

Each keyword here is SYNTHESISED from the keyword rather than transcribed onto
each card that prints it, the same way [Hunt], [Vision] and [Temporary] are:
the effect is fixed by the keyword, so writing it per card would be one more
chance to write it differently.
"""
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from rl.config import Config                                      # noqa: E402
from rl.engine import actions as A, chain, combat, phases         # noqa: E402
from rl.engine.cardtable import full_table                        # noqa: E402
from rl.engine.state import (GameState, P_ALIVE, base_loc,        # noqa: E402
                             bf_loc)
from riftbound import upcoming                                    # noqa: E402

T = full_table()
NAMES = list(T.names)
CFG = replace(Config().at_victory_score(3).with_solved_damage(), units_only=False)


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def skip(name):
    print(f"  \033[33mSKIP\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


def have(name: str) -> bool:
    return name in NAMES


def fresh() -> GameState:
    s = GameState()
    s.n_deck[:] = 10
    return s


def settle_out(s):
    """Resolve everything the engine has queued, answering any target choice.

    The Chain is drained explicitly rather than by passing priority, because
    these fixtures are bare boards with no turn structure for a pass loop to
    run in.
    """
    for _ in range(24):
        A._settle(s, T, CFG)
        seat = A.acting_seat(s)
        if seat >= 0:
            legal = A.legal_actions(s, T, CFG, seat)
            tgt = next((a for a in legal if a.kind == A.A_TARGET), None)
            if tgt is not None:
                A.apply(s, T, CFG, tgt)
                continue
        if int(s.n_chain):
            chain.resolve_top(s, T, CFG)
            continue
        if int(s.n_trig) == 0:
            return
    die("settle", "the engine did not settle in 24 steps")


def vanilla(might: int) -> int:
    """A unit with nothing that interferes with the step under test."""
    return next(i for i in range(len(NAMES))
                if T.is_type(i, "Unit") and int(T.might[i]) == might
                and not any(T.has(i, k) for k in
                            ("Tank", "Backline", "Shield", "Assault",
                             "Temporary", "Deflect", "Ambush")))


if not upcoming.visible_sets():
    print("\nNo upcoming set is visible. Re-run with "
          f"{upcoming.ENV_FLAG}=1 to exercise these keywords.")
    print(f"\n\033[33mnew-keyword tests skipped\033[0m")
    sys.exit(0)


# ---------------------------------------------------------------------------
print("\n[Disarm] 'When I attack, give an enemy unit here -1 Might this turn'")

if not have("Kai'Sa, Rebel"):
    skip("no [Disarm] card in the visible sets")
else:
    kaisa = NAMES.index("Kai'Sa, Rebel")
    if not T.has(kaisa, "Disarm"):
        die("disarm", "Kai'Sa, Rebel does not carry the parsed keyword")
    s = fresh()
    s.active = 0
    k = s.add_permanent(kaisa, 0, base_loc(0), True)
    d = s.add_permanent(vanilla(4), 1, bf_loc(0), True)
    s.bf_ctrl[0] = 1
    before = combat.might(s, T, d)
    combat.declare_move(s, bf_loc(0))
    combat.add_to_declaration(s, k)
    combat.commit_declaration(s, T, CFG)
    settle_out(s)
    after = combat.might(s, T, d)
    if after != before - 1:
        die("disarm", f"defender Might went {before} -> {after}, expected "
                      f"{before - 1}")
    ok(f"attacking took the defender from {before} to {after} Might")

    # ...and it is ROLE_ATTACK, not "attack or defend". Ahri, Inquisitive is
    # the two-sided version and leaves `subject_role` off; copying her shape
    # would have made every [Disarm] unit shrink attackers on defence too.
    s = fresh()
    s.active = 1
    k = s.add_permanent(kaisa, 0, bf_loc(0), True)     # Kai'Sa DEFENDS here
    atk = s.add_permanent(vanilla(4), 1, base_loc(1), True)
    s.bf_ctrl[0] = 0
    before = combat.might(s, T, atk)
    combat.declare_move(s, bf_loc(0))
    combat.add_to_declaration(s, atk)
    combat.commit_declaration(s, T, CFG)
    settle_out(s)
    after = combat.might(s, T, atk)
    if after != before:
        die("disarm", f"[Disarm] fired on DEFENCE: attacker went {before} -> "
                      f"{after}. The reminder says 'when I attack'.")
    ok("...and it does not fire on defence (ROLE_ATTACK, unlike Ahri's)")


# ---------------------------------------------------------------------------
print("\n[Deploy] 'Play this only to a battlefield. "
      "When an opponent holds here, kill this.'")

_dep = [i for i in range(len(NAMES)) if T.has(i, "Deploy")]
if not _dep:
    skip("no [Deploy] card in the visible sets")
else:
    dep = NAMES.index("Pillaged Armory") if have("Pillaged Armory") else _dep[0]

    # -- half one: the play restriction ------------------------------------
    s = fresh()
    s.active = 0
    s.runes_ready[0, 0] = 6
    s.bf_ctrl[0] = 0                                   # we control bf 0
    s.bf_ctrl[1] = 1                                   # they control bf 1
    dsts = A.play_destinations(s, T, CFG, 0, dep)
    if base_loc(0) in dsts:
        die("deploy", "a [Deploy] card was offered its base -- 149.2's "
                      "base-only rule is REPLACED, not added to")
    if bf_loc(0) not in dsts:
        die("deploy", "a [Deploy] card was not offered a battlefield we control")
    if bf_loc(1) in dsts:
        die("deploy", "a [Deploy] card was offered a battlefield the opponent "
                      "controls (see the approximation note in "
                      "actions.play_destinations)")
    ok(f"{NAMES[dep]!r} may be played only to a battlefield we control")

    # -- half two: the death trigger ---------------------------------------
    def hold_with(owner: int) -> int:
        s = fresh()
        g = s.add_permanent(dep, owner, bf_loc(0), True)
        s.add_permanent(vanilla(3), 0, bf_loc(0), True)
        s.bf_ctrl[0] = 0                               # seat 0 holds
        s.active = 0
        phases.score_holds(s, CFG, T)
        settle_out(s)
        return int(s.perms[g, P_ALIVE])

    if hold_with(1) != 0:
        die("deploy", "an opponent held the battlefield and the [Deploy] card "
                      "survived")
    ok("an opponent holding here kills it")
    if hold_with(0) != 1:
        die("deploy", "holding your OWN battlefield killed your own [Deploy] "
                      "card -- the trigger is 'an opponent holds', not 'anyone'")
    ok("...and holding it yourself does not -- only an OPPONENT's hold")


# ---------------------------------------------------------------------------
print("\n\033[32mall new-keyword tests passed\033[0m")
