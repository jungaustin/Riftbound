"""Showdowns, Contested status, and who ends up the Attacker.

Run: python3 rl/tests/test_showdown.py

Combat had tests from the start; the *Showdown* did not, because for most of
the build there was only one kind of it. 344.2 opens a second kind at a
battlefield only one player has units at, and 348.2 closes it by establishing
Control -- which means walking onto empty ground is a decision window, not an
instant Conquer. Everything here follows from that and from the status the
window hangs on:

  [1] 344.2 -- a lone Move onto an uncontrolled battlefield opens a Non-Combat
      Showdown, and 348.2.a.1 scores it only when that Showdown closes.
  [2] 323.12 -- and not while a trigger is pending, because a Pending Chain
      Item closes the State.
  [3] 359.3.f.3 -- a Move captures BOTH of its ends, so "there" (the origin)
      and "that battlefield" (the destination) both outlive the unit, while
      "here" is a live read and is meant not to.
  [4] 323.11/323.11.a -- Contested is removed from a battlefield its applier
      has abandoned and handed to whoever is still standing there.
  [5] 464.2.c.1 -- the Attacker is whoever applied Contested, not whoever moved
      last, so an [Ambush] unit answering an invasion is a DEFENDER.
  [6] 822.1.d -- a printed permission on a card with [Ambush] widens the
      keyword, timing included.

The whole file is one worked line from the project owner: Irresistible Faefolk
moves in and targets a 6-Might Renekton; the Faefolk is Gusted away in response
to her own trigger; the trigger drags Renekton in anyway; and Renekton either
conquers on the opponent's turn or gets met by an Ambushed Rengar.
"""
import sys
from dataclasses import replace

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from rl.config import Config
from rl.engine import actions as A
from rl.engine.cardtable import full_table
from rl.engine.state import (GameState, MAIN, P_ALIVE, P_CARD, P_LOC,
                             base_loc, bf_loc)

T = full_table()
V1 = replace(Config().at_victory_score(8), units_only=False)

FAEFOLK = T.id_of("Irresistible Faefolk")    # move trigger, 1 Might
GUST = T.id_of("Gust")                       # [Reaction] bounce, 3 Might or less
RENEKTON = T.id_of("Renekton, Rage Fueled")  # 6 Might
RENGAR = T.id_of("Rengar, Trophy Hunter")    # 6 Might, [Ambush] to enemy ground
LILLIA = T.id_of("Lillia - Fae Fawn")        # "...play a Sprite THERE"
DRUMMER = T.id_of("Noxian Drummer")          # "...play a Recruit token HERE"


def plain(might):
    """A body with no rules text, small enough for a Gust to choose.

    The Showdown window only OPENS when somebody can actually act in it
    (`combat.window_is_live`), so a test that wants to observe one has to leave
    the opponent a legal play. A 3-Might vanilla unit and a Gust is the
    cheapest pair that does it.
    """
    for c in range(T.n):
        if (T.is_type(c, "Unit") and T.might[c] == might
                and not T.residual_text(c) and not T.is_token(c)
                and not any(T.has(c, k) for k in
                            ("Tank", "Backline", "Temporary", "Shield",
                             "Assault"))):
            return c
    raise LookupError(might)


PLAIN3 = plain(3)


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


def fresh(deck=FAEFOLK):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = deck
    s.runes_ready[:, :] = 6
    s.phase, s.active, s.priority = MAIN, 0, 0
    return s


def move(s, perm, dst):
    A.apply(s, T, V1, A.Action(A.A_DECLARE, dst))
    A.apply(s, T, V1, A.Action(A.A_ADD, perm))
    A.apply(s, T, V1, A.Action(A.A_COMMIT))


def drive(s, prefs=(), limit=40, stop=None):
    """Act by preference, else pass, until `stop` or nobody is left to act."""
    for _ in range(limit):
        if stop and stop(s):
            return
        seat = A.acting_seat(s)
        if seat < 0:
            return
        legal = A.legal_actions(s, T, V1, seat)
        pick = None
        for p in prefs:
            hit = [a for a in legal if p(s, seat, a)]
            if hit:
                pick = hit[0]
                break
        pick = pick or next((a for a in legal if a.kind == A.A_PASS), None)
        if pick is None:
            return
        A.apply(s, T, V1, pick)
    if stop and not stop(s):
        die("drive", "never reached the state under test")


ACCEPT = lambda s, q, a: a.kind == A.A_ACCEPT
def targets(row, seat):
    return lambda s, q, a: q == seat and a.kind == A.A_TARGET and a.arg == row
def plays(card):
    return lambda s, q, a: a.kind == A.A_PLAY and int(s.hand[q, a.arg]) == card
def plays_at(loc):
    return lambda s, q, a: (a.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)
                            and a.arg == loc)


def live(s):
    return {T.names[int(s.perms[i, P_CARD])]: int(s.perms[i, P_LOC])
            for i in range(s.n_perms) if s.perms[i, P_ALIVE] == 1}


# ---------------------------------------------------------------------------
print("\n[1] 344.2 -- walking onto empty ground opens a Showdown, and 348.2.a")
print("    is what scores it. A plain unit has no trigger, so it opens at once.")

s = fresh()
walker = s.add_permanent(PLAIN3, 0, base_loc(0), ready=True)
s.hand[1, 0], s.n_hand[1] = GUST, 1      # so the window is a real decision
move(s, walker, bf_loc(0))
if s.showdown_bf != 0 or s.showdown_combat:
    die("344.2", f"expected a Non-Combat Showdown at bf0, got "
                 f"showdown_bf={int(s.showdown_bf)} "
                 f"combat={int(s.showdown_combat)}")
if int(s.bf_contester[0]) != 0:
    die("344.2", f"190.3.a.1 -- the mover applies Contested, got "
                 f"{int(s.bf_contester[0])}")
if int(s.points[0]) or int(s.bf_ctrl[0]) >= 0:
    die("344.2", "Control was established before the Showdown closed")
ok("the Move opens a Non-Combat Showdown and banks nothing")

drive(s, stop=lambda s: s.showdown_bf < 0)
if int(s.points[0]) != 1 or int(s.bf_ctrl[0]) != 0:
    die("348.2", f"closing it should Conquer: points={list(s.points)} "
                 f"ctrl={list(s.bf_ctrl)}")
ok("348.2.a.1 -- it Conquers when the Showdown closes, not on arrival")


# ---------------------------------------------------------------------------
print("\n[2] 323.12 -- no Showdown opens while a trigger is pending")

s = fresh()
fae = s.add_permanent(FAEFOLK, 0, base_loc(0), ready=True)
s.add_permanent(RENEKTON, 1, base_loc(1), ready=True)
move(s, fae, bf_loc(0))
if s.showdown_bf >= 0:
    die("323.12", "a Pending Chain Item closes the State; 323.12 needs an "
                  "Open one, and 344.2 defers to the next Cleanup")
if not (int(s.n_chain) + int(s.n_trig)):
    die("323.12", "the move trigger should be on or bound for the Chain")
ok("her move trigger closes the State, so the Showdown waits")


# ---------------------------------------------------------------------------
print("\n[3] 359.3.f.3 -- a Move captures both of its ends")
print("    'there' is the origin, 'that battlefield' the destination, and")
print("    'here' is a live read of the source that is meant to fizzle.")

# "that battlefield": Irresistible Faefolk, with the Faefolk removed in
# response to her own trigger. 383.2.c.2 -- the ability resolves without her.
s = fresh()
fae = s.add_permanent(FAEFOLK, 0, base_loc(0), ready=True)
ren = s.add_permanent(RENEKTON, 1, base_loc(1), ready=True)
s.hand[1, 0], s.n_hand[1] = GUST, 1
move(s, fae, bf_loc(0))
drive(s, [ACCEPT, targets(ren, 0), plays(GUST), targets(fae, 1)],
      stop=lambda s: s.perms[fae, P_ALIVE] != 1 and s.n_chain == 0)
if s.perms[fae, P_ALIVE] == 1:
    die("that", "the Gust should have returned the Faefolk to hand")
if int(s.perms[ren, P_LOC]) != bf_loc(0):
    die("that", f"'that battlefield' was captured when the trigger fired, so "
                f"Renekton still moves; got loc={int(s.perms[ren, P_LOC])}")
ok("'that battlefield' survives its source being removed mid-Chain")

# "there": Lillia's origin, same removal.
s = fresh(LILLIA)
lil = s.add_permanent(LILLIA, 0, bf_loc(0), ready=True)
s.bf_ctrl[0] = 0
s.hand[1, 0], s.n_hand[1] = GUST, 1
move(s, lil, bf_loc(1))
drive(s, [plays(GUST), targets(lil, 1)],
      stop=lambda s: s.perms[lil, P_ALIVE] != 1 and s.n_chain == 0)
sprites = [i for i in range(s.n_perms)
           if s.perms[i, P_ALIVE] == 1 and T.is_token(int(s.perms[i, P_CARD]))]
if len(sprites) != 1 or int(s.perms[sprites[0], P_LOC]) != bf_loc(0):
    die("there", f"'there' is the location she LEFT: got {live(s)}")
ok("'there' survives too, and means the origin rather than the destination")

# "here": Noxian Drummer, same removal -- and this one must NOT happen.
s = fresh(DRUMMER)
drum = s.add_permanent(DRUMMER, 0, base_loc(0), ready=True)
s.hand[1, 0], s.n_hand[1] = GUST, 1
if T.might[DRUMMER] > 3:
    die("here", "the fixture needs a Drummer a Gust can legally choose")
move(s, drum, bf_loc(0))
drive(s, [plays(GUST), targets(drum, 1)],
      stop=lambda s: s.perms[drum, P_ALIVE] != 1 and s.n_chain == 0)
if any(s.perms[i, P_ALIVE] == 1 and T.is_token(int(s.perms[i, P_CARD]))
       for i in range(s.n_perms)):
    die("here", "'play a Recruit token HERE' has no referent once she is gone "
                "(383.2.c.2); it must not place the token anywhere")
ok("'here' is a live read and correctly does nothing with its source gone")


# ---------------------------------------------------------------------------
print("\n[4] 323.11/323.11.a -- Contested is handed off, and the new holder")
print("    Conquers on the other player's turn")

s = fresh()
fae = s.add_permanent(FAEFOLK, 0, base_loc(0), ready=True)
ren = s.add_permanent(RENEKTON, 1, base_loc(1), ready=True)
s.hand[1, 0], s.n_hand[1] = GUST, 1
move(s, fae, bf_loc(0))
# Neither seat can respond once the Gust is spent, so the Showdown that opens
# for Renekton closes in the same call -- `window_is_live` skips a window
# nobody can act in. Block [5] holds it open with an [Ambush] unit and checks
# the Contested hand-off and Focus from inside it; here only the outcome is
# observable, which is the half the project owner asked about.
drive(s, [ACCEPT, targets(ren, 0), plays(GUST), targets(fae, 1)],
      stop=lambda s: s.showdown_bf < 0 and int(s.bf_ctrl[0]) >= 0)
if int(s.active) != 0:
    die("off-turn", "seat 0 should still be the turn player")
if int(s.points[1]) != 1 or int(s.bf_ctrl[0]) != 1:
    die("off-turn", f"seat 1 should Conquer on seat 0's turn: "
                    f"points={list(s.points)} ctrl={list(s.bf_ctrl)}")
if int(s.points[0]):
    die("off-turn", "seat 0 must not keep a point for ground it was Gusted off")
ok("seat 1 Conquers on seat 0's turn, and seat 0 scores nothing")


# ---------------------------------------------------------------------------
print("\n[5] 464.2.c.1 + 822.1.d -- an Ambushed answer is a DEFENDER")

s = fresh()
fae = s.add_permanent(FAEFOLK, 0, base_loc(0), ready=True)
ren = s.add_permanent(RENEKTON, 1, base_loc(1), ready=True)
s.hand[1, 0], s.n_hand[1] = GUST, 1
s.hand[0, 0], s.n_hand[0] = RENGAR, 1
move(s, fae, bf_loc(0))
drive(s, [ACCEPT, targets(ren, 0), plays(GUST), targets(fae, 1)],
      stop=lambda s: s.showdown_bf >= 0
                     and int(s.perms[ren, P_LOC]) == bf_loc(0))
if s.showdown_combat:
    die("344.2", "only seat 1 has units there, so this is the Non-Combat kind")
if int(s.bf_contester[0]) != 1:
    die("323.11.a", f"Contested should pass to seat 1, whose unit is the one "
                    f"left standing; got {int(s.bf_contester[0])}")
if A.acting_seat(s) != 1:
    die("345", f"Focus goes to whoever applied Contested, got "
               f"seat {A.acting_seat(s)}")
ok("seat 0 abandons the ground, seat 1's arrival inherits Contested and Focus")

dsts = A.play_destinations(s, T, V1, 0, RENGAR, ambush_only=True)
if dsts != [bf_loc(0)]:
    die("822.1.d", f"Rengar's printed permission is an Ambush verb and widens "
                   f"the keyword's Reaction timing with it; got {dsts}")
ok("822.1.d -- Rengar may be Ambushed onto enemy-held ground in the window")

drive(s, [plays(RENGAR), plays_at(bf_loc(0))],
      stop=lambda s: bool(s.showdown_combat))
if not s.showdown_combat or s.showdown_bf != 0:
    die("344.1", "the Non-Combat Showdown should become a Combat Showdown in "
                 "place rather than opening a second one")
if int(s.attacker) != 1:
    die("464.2.c.1", f"Renekton applied Contested, so seat 1 attacks and the "
                     f"Ambushed Rengar defends; got attacker "
                     f"seat {int(s.attacker)}")
ok("344.1 escalates in place and Renekton keeps the Attacker designation")


print("\n\033[32mall showdown tests passed\033[0m")


# ---------------------------------------------------------------------------
print("\n[enter_main] a Cleanup that OPENS a Showdown keeps its priority")

# `enter_main` runs a Cleanup because a Combat staged during the opponent's
# turn has nowhere else to be initiated (461, and 321 forbids a Cleanup while
# the Chain resolves). That Cleanup can therefore OPEN a Showdown -- and
# `enter_main` then reset priority and Focus for the Main Phase anyway,
# clobbering the values 345/464.2.d had just written.
#
# The failure is silent and total: Focus sits at -1, `after_resolution` passes
# it with `1 - focus` so it flips to 2 and back to -1 forever, `acting_seat`
# returns a seat that does not exist, and the driver loop exits. The game is
# scored undecided with `truncated` False -- a stall wearing a draw's clothes.
# Found by a random deck game, not by a test, which is why an invariant now
# asserts it too.
from rl.engine import phases as _ph
from rl.engine.state import N_SEATS as _N_SEATS

_s = fresh()
_s.active, _s.priority = 0, 0
# Seat 1 has a unit standing where seat 0 controls the battlefield: contested
# ground with no Combat yet initiated, which is what `cleanup` is for. Seat 1
# also holds an affordable [Reaction], because a Showdown whose window nobody
# can act in runs straight through to Combat and never yields -- and it is the
# yield that leaves the corrupted Focus visible.
_s.bf_ctrl[0] = 0
_s.hand[1, 0] = GUST
_s.n_hand[1] = 1
_mine = _s.add_permanent(PLAIN3, 0, bf_loc(0), is_unit=True)
_theirs = _s.add_permanent(PLAIN3, 1, bf_loc(0), is_unit=True)
_ph.enter_main(_s, T, V1)

if int(_s.showdown_bf) < 0:
    die("enter_main", "the Cleanup should have initiated the staged Combat")
if not 0 <= int(_s.focus) < _N_SEATS:
    die("enter_main", f"a live Showdown must have a real Focus, got "
                      f"{int(_s.focus)} -- 345/464.2.d give it to a SEAT")
if not 0 <= int(_s.priority) < _N_SEATS:
    die("enter_main", f"...and a real priority, got {int(_s.priority)}")
if A.acting_seat(_s) < 0:
    die("enter_main", "nobody can act: the driver loop exits here and the "
                      "game is scored undecided with truncated=False")
ok("a Showdown opened by enter_main's Cleanup keeps priority and Focus")

# The control: with nothing to contest, the Main Phase defaults still apply.
_s = fresh()
_s.active, _s.priority = 0, 0
_s.add_permanent(PLAIN3, 0, bf_loc(0), is_unit=True)
_ph.enter_main(_s, T, V1)
if int(_s.showdown_bf) >= 0:
    die("enter_main", "uncontested ground must not open a Showdown")
if int(_s.priority) != 0 or int(_s.focus) != -1:
    die("enter_main", "with no Showdown, Main resets priority to the turn "
                      "player and clears Focus")
ok("...and with nothing staged the Main Phase defaults are still written")

print("\n\033[32mall showdown tests passed\033[0m")
