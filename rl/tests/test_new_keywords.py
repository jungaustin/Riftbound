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
    # "Play this only to a battlefield" means ANY battlefield, confirmed by the
    # project owner. 806.3's control requirement is written for UNITS and
    # nothing extends it to gear -- and it is the permissive reading that makes
    # the keyword's other half worth printing, since "when an opponent holds
    # here, kill this" is the price of deploying onto ground you do not hold.
    _bf_card = next(c for c in range(len(NAMES)) if T.is_type(c, "Battlefield"))
    s = fresh()
    s.active = 0
    s.runes_ready[0, 0] = 6
    for _b in range(3):
        s.bf_card[_b] = _bf_card
    s.bf_ctrl[0] = 0                                   # we control bf 0
    s.bf_ctrl[1] = 1                                   # they control bf 1
    s.bf_ctrl[2] = -1                                  # nobody controls bf 2
    dsts = A.play_destinations(s, T, CFG, 0, dep)
    if base_loc(0) in dsts:
        die("deploy", "a [Deploy] card was offered its base -- 149.2's "
                      "base-only rule is REPLACED, not added to")
    for _b, _what in ((0, "one we control"), (1, "one the OPPONENT controls"),
                      (2, "an uncontrolled one")):
        if bf_loc(_b) not in dsts:
            die("deploy", f"a [Deploy] card was not offered {_what} -- the "
                          f"card says 'a battlefield', with no control clause")
    ok(f"{NAMES[dep]!r} may be played to ANY battlefield, never to base")

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

    # -- and 149.3's sweep must not undo it --------------------------------
    # "If an unattached non-Unit Gear is at a Battlefield for any reason during
    # a cleanup, it is recalled to its controller's Base." That is the
    # corrective half of 149.2's "unless an effect specifies otherwise", and a
    # [Deploy] card IS that effect. Without the exemption the keyword was
    # silently dead: the gear went home on the next Cleanup, so it was never
    # standing there when an opponent held and the death clause never fired.
    s = fresh()
    g = s.add_permanent(dep, 0, bf_loc(0), True)
    ordinary = next(i for i in range(len(NAMES))
                    if T.is_type(i, "Gear") and not T.is_type(i, "Unit")
                    and not T.has(i, "Deploy"))
    o = s.add_permanent(ordinary, 0, bf_loc(0), True)
    combat.recall_stray_gear(s, T)
    from rl.engine.state import P_LOC                              # noqa: E402
    if int(s.perms[g, P_LOC]) != bf_loc(0):
        die("deploy", "149.3's sweep recalled the [Deploy] gear to base -- it "
                      "belongs at a battlefield, so the keyword is undone")
    if int(s.perms[o, P_LOC]) != base_loc(0):
        die("deploy", f"the exemption leaked: ordinary gear {NAMES[ordinary]!r} "
                      f"was left standing at a battlefield")
    ok("149.3's stray-gear sweep spares it, and only it")


# ---------------------------------------------------------------------------
print("\n[Show Off] 'As you play this, you may reveal a unit from your hand "
      "or pick a friendly unit'")

if not have("Primordial Roar"):
    skip("no [Show Off] card in the visible sets")
else:
    from rl.engine.state import P_DMG, P_FLAGS                    # noqa: E402
    roar = NAMES.index("Primordial Roar")

    def board():
        s = fresh()
        s.active = 0
        s.priority = 0
        s.runes_ready[0, 0] = 8
        s.runes_ready[0, 1] = 8
        s.hand[0, 0] = roar
        s.hand[0, 1] = vanilla(5)
        s.n_hand[0] = 2
        mine = s.add_permanent(vanilla(3), 0, base_loc(0), True)
        foe = s.add_permanent(vanilla(4), 1, base_loc(1), True)
        return s, mine, foe

    def cast(choice):
        """Play Primordial Roar, answer [Show Off], then damage the enemy."""
        s, mine, foe = board()
        A.apply(s, T, CFG, A.Action(A.A_PLAY, 0))
        if int(s.pend_show_off) < 0:
            die("show-off", "the choice was not offered as the card was played")
        if A.acting_seat(s) != 0:
            die("show-off", "acting_seat disagrees with pend_show_off")
        legal = A.legal_actions(s, T, CFG, 0)
        if A.legal_actions(s, T, CFG, 1):
            die("show-off", "the non-choosing seat was offered actions")
        pick = {
            "hand": lambda: next(a for a in legal if a.kind == A.A_PICK),
            "board": lambda: next(a for a in legal
                                  if a.kind == A.A_TARGET and a.arg == mine),
            "decline": lambda: next(a for a in legal
                                    if a.kind == A.A_PICK_NONE),
        }[choice]()
        A.apply(s, T, CFG, pick)
        if int(s.pend_show_off) >= 0:
            die("show-off", "the choice stayed open after being answered")
        tgt = next(a for a in A.legal_actions(s, T, CFG, 0)
                   if a.kind == A.A_TARGET and a.arg == foe)
        A.apply(s, T, CFG, tgt)
        for _ in range(12):
            A._settle(s, T, CFG)
            if int(s.n_chain) == 0:
                break
            chain.resolve_top(s, T, CFG)
        return s, int(s.perms[foe, P_DMG])

    # Both sources are offered at once, and they are told apart by ACTION KIND
    # rather than by packing an arg -- A_PICK is a hand index, A_TARGET a row.
    s0, _, _ = board()
    A.apply(s0, T, CFG, A.Action(A.A_PLAY, 0))
    kinds = {a.kind for a in A.legal_actions(s0, T, CFG, 0)}
    if kinds != {A.A_PICK, A.A_TARGET, A.A_PICK_NONE}:
        die("show-off", f"expected hand picks, board picks and a decline, "
                        f"got kinds {sorted(kinds)}")
    ok("both sources are offered at once, plus a decline ('you may')")

    s, dmg = cast("hand")
    if dmg != 5:
        die("show-off", f"revealing a 5-Might unit from hand dealt {dmg}, not 5")
    if int(s.n_hand[0]) != 1:
        die("show-off", "revealing moved the card out of hand -- a reveal is "
                        "not a discard, the card stays put")
    ok("revealing a 5-Might unit from hand deals 5, and the card stays in hand")

    s, dmg = cast("board")
    if dmg != 3:
        die("show-off", f"picking a 3-Might friendly unit dealt {dmg}, not 3")
    ok("picking a 3-Might friendly unit deals 3")

    s, dmg = cast("decline")
    if dmg != 0:
        die("show-off", f"declining still dealt {dmg} -- COND_SHOWED_OFF is "
                        f"not gating the damage")
    ok("declining deals nothing, and the spell still resolves (355.8)")

    # The reveal is PUBLIC, so it has to reach the opponent's observation.
    from rl.obs import Encoder                                    # noqa: E402
    _e = Encoder(T, CFG)
    s, mine, foe = board()
    A.apply(s, T, CFG, A.Action(A.A_PLAY, 0))
    before = _e.encode(s, 1, A.legal_actions(s, T, CFG, 1)).globals.copy()
    A.apply(s, T, CFG, next(a for a in A.legal_actions(s, T, CFG, 0)
                            if a.kind == A.A_PICK))
    after = _e.encode(s, 1, A.legal_actions(s, T, CFG, 1)).globals
    if (before == after).all():
        die("show-off", "the OPPONENT's observation did not change when a card "
                        "was revealed from hand -- the reveal is public (it is "
                        "the price of showing off) and they must see it")
    ok("...and the opponent's observation moves: the reveal is public")


# ---------------------------------------------------------------------------
print("\n\033[32mall new-keyword tests passed\033[0m")
