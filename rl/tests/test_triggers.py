"""Triggered ability tests -- rules 382-383.

Run: python3 rl/tests/test_triggers.py

A triggered ability is not a new mechanism: 383.3 says it "behaves like an
Activated Ability and is placed on the Chain", so it reuses finalization,
targeting, priority and resolution wholesale. These tests check the places
where that reuse is *not* enough and the ability needs something a spell never
did:

  [1] It fires at all, from a game action rather than a player action -- and
      nothing fires in v0, which is what keeps the golden outcome pinned.
  [2] It is a real Chain Item, so the opponent gets a window to respond
      before it resolves (383.3.c).
  [3] "me" and "here" resolve to the source permanent (T_SELF / T_HERE),
      which is not a target and so cannot be a slot.
  [4] 355.8 -- an ability whose targets cannot all be validly chosen is never
      put on the chain. Cards are gated before they are offered, so this only
      ever bites abilities: a trigger fires whether or not the board can
      satisfy it.
  [5] "another unit" excludes the source (TargetSpec.not_self), which is a
      relation to the SOURCE and not to an earlier slot.
  [6] 383.2.c.2 -- an ability whose source has left the board resolves
      without it rather than dereferencing a dead row.
  [7] The coverage metric only credits cards whose text is fully transcribed.
"""
import sys
from dataclasses import replace

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

from rl.config import Config
from rl.engine import actions as A
from rl.engine import chain, combat
from rl.engine.cardtable import full_table
from rl.engine.effects import (ABILITIES, TR_DEATH as chain_TR_DEATH,
                               TR_MOVE as chain_TR_MOVE, TR_PLAY_ME,
                               abilities_for)
from rl.engine.state import (C_ABIL, C_CARD, C_SRC, MAIN, P_ALIVE, P_CARD,
                             P_LOC, P_READY, GameState, base_loc, bf_loc)

T = full_table()
V0 = Config().at_victory_score(3)                       # units only
V1 = replace(Config().at_victory_score(3), units_only=False)

YORDLE = T.id_of("Lecturing Yordle")          # [Tank] When you play me, draw 1
SPRITE_MOTHER = T.id_of("Sprite Mother")      # ...play a Sprite token here
FIRST_MATE = T.id_of("First Mate")            # ...ready another unit
RIPTIDE = T.id_of("Riptide Rex")              # ...deal 6 to an enemy at a bf
SPRITE = T.id_of("Sprite (274) // Buff")


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


def plain(might):
    """A body with no rules text and no damage-order keyword.

    Not `plays_as_printed`: only 10 unit slots in the whole corpus clear that
    bar, and none of them at 2 Might. What these tests need is a unit that does
    not fire anything of its own, which is exactly "no residual text".
    """
    for c in range(T.n):
        if (T.is_type(c, "Unit") and T.might[c] == might
                and not T.residual_text(c) and not T.is_token(c)
                and not any(T.has(c, k) for k in
                            ("Tank", "Backline", "Temporary"))):
            return c
    raise LookupError(might)


PLAIN2 = plain(2)


def fresh(hand=(), seat=0, runes=6):
    s = GameState()
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN2
    for j, c in enumerate(hand):
        s.hand[seat, j] = c
    s.n_hand[seat] = len(hand)
    s.runes_ready[:, :] = runes
    s.phase = MAIN
    s.active = seat
    s.priority = seat
    return s


def play(s, cfg, hand_idx, loc):
    """Play the unit at `hand_idx` to `loc`, through the real action layer."""
    A.apply(s, T, cfg, A.Action(A.A_PLAY, hand_idx))
    A.apply(s, T, cfg, A.Action(A.A_PLAY_AT, loc))


def drain(s, cfg, limit=40):
    """Both players pass until the chain is empty."""
    for _ in range(limit):
        if s.n_chain == 0 and s.pend_slot < 0 and s.pend_may < 0:
            return
        seat = A.acting_seat(s)
        if seat < 0:
            return
        legal = A.legal_actions(s, T, cfg, seat)
        if not legal:
            die("drain", f"seat {seat} to act with no legal actions "
                         f"(n_chain={s.n_chain} pend_slot={s.pend_slot})")
        pick = next((a for a in legal if a.kind == A.A_PASS), legal[0])
        A.apply(s, T, cfg, pick)
    die("drain", "chain did not drain")


# ---------------------------------------------------------------------------
print("\n[1] a trigger fires from a game action, and never in v0")

s = fresh(hand=[YORDLE])
before = int(s.n_hand[0])
play(s, V1, 0, base_loc(0))
if s.n_chain != 1 or int(s.chain[0, C_ABIL]) < 0:
    die("fire", f"expected one ability on the chain, got n_chain={s.n_chain}")
ok("playing Lecturing Yordle puts its ETB ability on the Chain (383.3)")

drain(s, V1)
if int(s.n_hand[0]) != before - 1 + 1:
    die("fire", f"hand {int(s.n_hand[0])}, expected {before} "
                f"(-1 played, +1 drawn)")
ok("the ability resolves and draws 1")

s = fresh(hand=[YORDLE])
play(s, V0, 0, base_loc(0))
if s.n_chain != 0:
    die("v0", "a trigger fired with units_only=True; v0 must stay frozen")
ok("nothing fires in v0 -- 337.2's 'no response window' claim survives")


# ---------------------------------------------------------------------------
print("\n[2] the trigger is respondable (383.3.c)")

s = fresh(hand=[YORDLE])
play(s, V1, 0, base_loc(0))
# The controller keeps priority after finalizing (337.1.a), then it passes.
A.apply(s, T, V1, A.PASS)
if A.acting_seat(s) != 1:
    die("window", f"opponent never got priority (acting={A.acting_seat(s)})")
if not A.legal_actions(s, T, V1, 1):
    die("window", "the opponent's window offers nothing, not even a pass")
if s.n_chain != 1:
    die("window", "the ability resolved before the opponent could respond")
ok("the opponent holds priority with the ability still unresolved")


# ---------------------------------------------------------------------------
print("\n[3] 'here' is the source's location, not a chosen target")

s = fresh(hand=[SPRITE_MOTHER])
play(s, V1, 0, bf_loc(0))
s.bf_ctrl[0] = 0                      # she may only be played where we control
drain(s, V1)
tokens = [i for i in range(s.n_perms)
          if int(s.perms[i, P_CARD]) == SPRITE and s.perms[i, P_ALIVE] == 1]
if len(tokens) != 1:
    die("here", f"expected 1 Sprite token, got {len(tokens)}")
if int(s.perms[tokens[0], P_LOC]) != bf_loc(0):
    die("here", f"token at {int(s.perms[tokens[0], P_LOC])}, "
                f"expected {bf_loc(0)} -- 'here' is Sprite Mother's location")
if not s.perms[tokens[0], P_READY]:
    die("here", "the token entered exhausted; the card says 'a ready ... token'")
ok("Sprite Mother's token appears at HER location, ready")


# ---------------------------------------------------------------------------
print("\n[4] 355.8 -- an ability with no valid target never reaches the chain")

s = fresh(hand=[FIRST_MATE])
play(s, V1, 0, base_loc(0))
if s.n_chain != 0:
    die("355.8", "First Mate's 'ready another unit' went on the chain with no "
                 "other unit to ready -- the game deadlocks there")
ok("First Mate alone on the board: the trigger is not put on the chain")


# ---------------------------------------------------------------------------
print("\n[5] 'another unit' excludes the source")

s = fresh(hand=[FIRST_MATE])
other = s.add_permanent(PLAIN2, 0, base_loc(0), ready=False)
play(s, V1, 0, base_loc(0))
src = int(s.chain[0, C_SRC])
opts = A._slot_options(s, T, 0)
if src in opts:
    die("not_self", "First Mate was offered itself as 'another unit'")
if opts != [other]:
    die("not_self", f"expected [{other}], got {opts}")
ok("the only legal choice is the OTHER unit, never First Mate itself")

A.apply(s, T, V1, A.Action(A.A_TARGET, other))
drain(s, V1)
if not s.perms[other, P_READY]:
    die("not_self", "the chosen unit was not readied")
if s.perms[src, P_READY]:
    die("not_self", "First Mate readied itself -- it entered exhausted (359.2.c)")
ok("the other unit is readied; First Mate stays exhausted")


# ---------------------------------------------------------------------------
print("\n[6] 383.2.c.2 -- a source that left the board")

s = fresh(hand=[SPRITE_MOTHER])
play(s, V1, 0, bf_loc(0))
src = int(s.chain[0, C_SRC])
s.perms[src, P_ALIVE] = 0             # killed in response, before it resolves
drain(s, V1)
tokens = [i for i in range(s.n_perms)
          if int(s.perms[i, P_CARD]) == SPRITE and s.perms[i, P_ALIVE] == 1]
if tokens:
    die("dead source", f"'here' resolved to a dead unit's last location "
                       f"and made {len(tokens)} token(s)")
ok("with the source gone, 'here' has no meaning and the op fizzles")


# ---------------------------------------------------------------------------
print("\n[7] a targeting trigger, end to end")

s = fresh(hand=[RIPTIDE], runes=9)
enemy = s.add_permanent(PLAIN2, 1, bf_loc(1))
safe = s.add_permanent(PLAIN2, 1, base_loc(1))     # at base: not a legal target
play(s, V1, 0, base_loc(0))
opts = A._slot_options(s, T, 0)
if opts != [enemy]:
    die("riptide", f"expected only the enemy AT A BATTLEFIELD ({enemy}), "
                   f"got {opts}")
ok("'an enemy unit at a battlefield' excludes the one at base")

A.apply(s, T, V1, A.Action(A.A_TARGET, enemy))
drain(s, V1)
if s.perms[enemy, P_ALIVE]:
    die("riptide", "6 damage did not kill a 2-Might unit")
if not s.perms[safe, P_ALIVE]:
    die("riptide", "the untargeted unit died")
ok("Riptide Rex deals 6 and kills its target")


# ---------------------------------------------------------------------------
print("\n[8] coverage credits only fully transcribed cards")

from rl.decks import plays_as_printed

# Membership in ABILITIES means "this card's ABILITY TEXT is transcribed". It
# does not by itself make the card played as printed -- an unread keyword or an
# unplayable token it creates still disqualifies it. So the invariant is that
# nothing in ABILITIES is blocked by its *text*, which is the part the spec
# claims to have covered.
blocked_by_text = [n for n in ABILITIES
                   if not plays_as_printed(T, T.id_of(n))
                   and not T.unread_keywords(T.id_of(n))]
if blocked_by_text:
    die("coverage", f"specs written but still not played as printed for a "
                    f"reason other than a keyword: {blocked_by_text}")
covered = sum(1 for n in ABILITIES if plays_as_printed(T, T.id_of(n)))
ok(f"{covered}/{len(ABILITIES)} ability specs fully covered; the rest wait "
   f"only on an unread keyword")

# Scuttle Crab has an ETB *and* a Deathknell; only one is expressible, so it
# must not be in ABILITIES at all -- a half-implemented card played as if whole
# is worse than one honestly substituted.
crab = T.id_of("Scuttle Crab")
if abilities_for(T, crab):
    die("coverage", "Scuttle Crab has an ability spec but its Deathknell is "
                    "not implemented; partial cards must stay out")
if plays_as_printed(T, crab):
    die("coverage", "Scuttle Crab counted as covered")
ok("a card with one unimplemented ability is not counted as covered")

# ---------------------------------------------------------------------------
print("\n[9] 383.3.a -- 'you may' is decided at FINALIZATION")

# No card in the pool is optional yet: every implementable "you may" ETB is
# gated behind a keyword the engine does not read ([Ambush] on Grim Apothecary,
# [Hidden] on Tideturner). So the accept/decline path is exercised with a
# SYNTHETIC ability rather than left as unreachable code that quietly rots.
# It is removed again below, so it never touches the coverage metric.
from rl.engine.effects import Ability, Op, OP_DRAW

_probe = T.names[PLAIN2]
ABILITIES[_probe] = (Ability(TR_PLAY_ME, ops=(Op(OP_DRAW, n=1),),
                             optional=True),)
try:
    for decision, expect_draw in ((A.A_ACCEPT, 1), (A.A_DECLINE, 0)):
        s = fresh(hand=[PLAIN2])
        before = int(s.n_hand[0]) - 1              # the card leaves hand
        play(s, V1, 0, base_loc(0))
        if s.pend_may < 0:
            die("may", "an optional ability did not open a yes/no decision")
        kinds = {a.kind for a in A.legal_actions(s, T, V1, 0)}
        if kinds != {A.A_ACCEPT, A.A_DECLINE}:
            die("may", f"expected accept/decline only, got {kinds}")
        if A.acting_seat(s) != 0:
            die("may", "the wrong seat was asked")
        A.apply(s, T, V1, A.Action(decision))
        drain(s, V1)
        if int(s.n_hand[0]) != before + expect_draw:
            die("may", f"{A.KIND_NAMES[decision]}: hand "
                       f"{int(s.n_hand[0])}, expected {before + expect_draw}")
        if s.n_chain != 0 or s.pend_may >= 0:
            die("may", f"{A.KIND_NAMES[decision]} left the chain dirty")
    ok("accepting performs it; declining removes it from the chain (383.3.a.2)")
finally:
    del ABILITIES[_probe]

# ---------------------------------------------------------------------------
print("\n[10] [Accelerate] -- an Optional Additional Cost (805)")

from rl.engine.cost import accelerate_cost, plan_payment

RAMP = T.id_of("Legion Rearguard")          # text is [Accelerate] and nothing else
if accelerate_cost(T, RAMP) != (1, 1):
    die("accel", "Legion Rearguard should carry the {1 energy}{C} cost")
if accelerate_cost(T, PLAIN2) is not None:
    die("accel", "a card without [Accelerate] must have no additional cost")

s = fresh(hand=[RAMP], runes=6)
kinds = {a.kind for a in A.legal_actions(s, T, V1, 0)}
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
acts = A.legal_actions(s, T, V1, 0)
if not any(a.kind == A.A_PLAY_AT_FAST for a in acts):
    die("accel", "the accelerated variant was not offered with runes to spare")
ok("both variants are offered at the destination choice, not a later one")

# Normal: enters exhausted (359.2.c).
s1 = fresh(hand=[RAMP], runes=6)
play(s1, V1, 0, base_loc(0))
if s1.perms[0, P_READY]:
    die("accel", "a unit played normally must enter exhausted")

# Accelerated: enters READY, and costs one more energy and one power.
s2 = fresh(hand=[RAMP], runes=6)
A.apply(s2, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s2, T, V1, A.Action(A.A_PLAY_AT_FAST, base_loc(0)))
if not s2.perms[0, P_READY]:
    die("accel", "805.1.a -- paying the cost must make it enter ready")
if s2.total_ready_runes(0) >= s1.total_ready_runes(0):
    die("accel", "the additional Energy was never paid")
ok("805.6 -- it ENTERS ready rather than entering exhausted and then readying")

# Unaffordable: the variant simply is not offered.
s3 = fresh(hand=[RAMP], runes=0)
s3.runes_ready[0, :] = 0
s3.runes_ready[0, 0] = int(T.energy[RAMP])      # exactly the printed cost
A.apply(s3, T, V1, A.Action(A.A_PLAY, 0))
if any(a.kind == A.A_PLAY_AT_FAST for a in A.legal_actions(s3, T, V1, 0)):
    die("accel", "offered [Accelerate] with no rune to pay the extra Energy")
ok("with only the printed cost affordable, the fast variant is not offered")


# ---------------------------------------------------------------------------
print("\n[11] TR_MOVE captures the location LEFT (359.3.f.3)")

LILLIA = T.id_of("Lillia - Fae Fawn")
s = fresh(hand=[])
lil = s.add_permanent(LILLIA, 0, base_loc(0))
s.bf_ctrl[0] = -1
# Declare and commit an ordinary Move from base to battlefield 0.
A.apply(s, T, V1, A.Action(A.A_DECLARE, bf_loc(0)))
A.apply(s, T, V1, A.Action(A.A_ADD, lil))
A.apply(s, T, V1, A.Action(A.A_COMMIT))
drain(s, V1)
sprites = [i for i in range(s.n_perms)
           if int(s.perms[i, P_CARD]) == SPRITE and s.perms[i, P_ALIVE] == 1]
if len(sprites) != 1:
    die("move", f"expected 1 Sprite from Lillia's move, got {len(sprites)}")
if int(s.perms[sprites[0], P_LOC]) != base_loc(0):
    die("move", f"the Sprite went to {int(s.perms[sprites[0], P_LOC])}; 'there' "
                f"is the location she LEFT ({base_loc(0)}), not the one she "
                f"arrived at")
if int(s.perms[lil, P_LOC]) != bf_loc(0):
    die("move", "Lillia did not actually move")
ok("Lillia's Sprite appears where she came from, not where she went")


# ---------------------------------------------------------------------------
print("\n[12] [Deathknell] fires from a death, through the queue (808)")

SENTRY = T.id_of("Watchful Sentry")
s = fresh(hand=[])
sen = s.add_permanent(SENTRY, 0, bf_loc(0))
before = int(s.n_hand[0])
combat.destroy(s, T, sen)
if s.n_trig != 1:
    die("death", "the Deathknell was not queued at the moment of death")
if s.n_chain != 0:
    die("death", "808 must not push straight onto the Chain -- `is_open` is "
                 "`n_chain == 0`, so that blocks the Cleanup that killed it")
ok("the trigger is QUEUED at death, not pushed onto the Chain")

chain.place(s, T, V1, 0)
drain(s, V1)
if int(s.n_hand[0]) != before + 1:
    die("death", f"Deathknell draw did not happen: hand {int(s.n_hand[0])}, "
                 f"expected {before + 1}")
ok("flushing puts it on the Chain and it resolves: draw 1")

# A card with no death ability must not queue anything -- the queue is bounded.
s = fresh(hand=[])
p0 = s.add_permanent(PLAIN2, 0, bf_loc(0))
combat.destroy(s, T, p0)
if s.n_trig:
    die("death", "a unit with no Deathknell queued a trigger anyway")
ok("a unit without one queues nothing, so the queue stays bounded")


# ---------------------------------------------------------------------------
print("\n[13] 383.3.d -- the controller orders simultaneous triggers")

# Two DIFFERENT triggers of the same controller, fired at once. Order matters
# because the Chain resolves newest-first (340.1): the one placed LAST resolves
# FIRST. Confirmed important by the project owner.
s = fresh(hand=[])
sen = s.add_permanent(SENTRY, 0, bf_loc(0))          # Deathknell: draw 1
lil = s.add_permanent(LILLIA, 0, bf_loc(0))          # move: make a Sprite
chain.queue(s, chain_TR_DEATH, sen, bf_loc(0))
chain.queue(s, chain_TR_MOVE, lil, bf_loc(0))
opts = chain.orderable(s, T, 0)
if len(opts) != 2:
    die("order", f"two distinguishable triggers should offer 2 choices, got {opts}")
if chain.next_placer(s) != 0:
    die("order", "383.3.d.1 -- the turn player places first")
ok("two different triggers from one controller offer a real ordering choice")

# Identical triggers are collapsed: swapping two copies of the same Deathknell
# cannot produce a different game.
s = fresh(hand=[])
a0 = s.add_permanent(SENTRY, 0, bf_loc(0))
a1 = s.add_permanent(SENTRY, 0, bf_loc(0))
chain.queue(s, chain_TR_DEATH, a0, bf_loc(0))
chain.queue(s, chain_TR_DEATH, a1, bf_loc(0))
if len(chain.orderable(s, T, 0)) != 1:
    die("order", "two identical Deathknells must collapse to one choice")
ok("interchangeable triggers collapse -- no branching for a distinction "
   "without a difference")

# 383.3.d.1 -- turn player empties their queue before the opponent is asked.
s = fresh(hand=[])
mine = s.add_permanent(SENTRY, 0, bf_loc(0))
theirs = s.add_permanent(SENTRY, 1, bf_loc(1))
chain.queue(s, chain_TR_DEATH, theirs, bf_loc(1))
chain.queue(s, chain_TR_DEATH, mine, bf_loc(0))
if chain.next_placer(s) != 0:
    die("order", "the turn player must place before the opponent, whatever "
                 "order the triggers were queued in")
chain.place(s, T, V1, chain.orderable(s, T, 0)[0])
if chain.next_placer(s) != 1:
    die("order", "the opponent places once the turn player is done")
ok("turn player first, then the opponent (383.3.d.1)")

# The decision reaches the action layer, and the chain ends up two deep.
s = fresh(hand=[])
sen = s.add_permanent(SENTRY, 0, bf_loc(0))
lil = s.add_permanent(LILLIA, 0, bf_loc(0))
chain.queue(s, chain_TR_DEATH, sen, bf_loc(0))
chain.queue(s, chain_TR_MOVE, lil, bf_loc(0))
A.apply(s, T, V1, A.PASS)                 # any action runs the settle step
if s.pend_order != 0:
    die("order", "the ordering decision was never offered to the player")
acts = A.legal_actions(s, T, V1, 0)
if {a.kind for a in acts} != {A.A_ORDER}:
    die("order", f"expected only A_ORDER, got {[a for a in acts]}")
A.apply(s, T, V1, acts[1])                # place the SECOND one first
A.apply(s, T, V1, A.legal_actions(s, T, V1, 0)[0])
if s.n_chain != 2:
    die("order", f"both triggers should be on the chain, got {s.n_chain}")
ok("the choice is a real action, and both triggers reach the Chain")


# ---------------------------------------------------------------------------
print("\n[14] Gear -- a permanent that is not a Unit")

from rl.engine import phases

FOUNTAIN = T.id_of("Sprite Fountain")     # [Temporary], ETB + Deathknell Sprite

s = fresh(hand=[FOUNTAIN])
acts = A.legal_actions(s, T, V1, 0)
if not any(a.kind == A.A_PLAY for a in acts):
    die("gear", "Gear was never offered in the Main Phase")
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
dsts = [a.arg for a in A.legal_actions(s, T, V1, 0)]
if dsts != [base_loc(0)]:
    die("gear", f"149.2 -- Gear is base-only, but got destinations {dsts}")
ok("Gear is offered, and only to its controller's base (149.2)")

A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
gear_row = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == FOUNTAIN)
if not s.perms[gear_row, P_READY]:
    die("gear", "359.2.d -- non-unit Gear enters READY, unlike a unit")
ok("it enters ready (359.2.d), where a unit would enter exhausted")

# It must not count as a garrison. `seats_at` decides Control and whether a
# Combat happens, so a gear counted there would defend a battlefield.
if s.units_at(base_loc(0), 0).size != 0:
    die("gear", "units_at counted a gear -- seats_at would garrison with it")
if s.permanents_at(base_loc(0), 0).size != 1:
    die("gear", "permanents_at should still see the gear")
ok("units_at excludes it; permanents_at still sees it")

drain(s, V1)
def _sprites(st):
    return [i for i in range(st.n_perms)
            if int(st.perms[i, P_CARD]) == SPRITE and st.perms[i, P_ALIVE] == 1]
if len(_sprites(s)) != 1:
    die("gear", f"the ETB should have made one Sprite, got {len(_sprites(s))}")
ok("its 'when you play this' trigger fires like a unit's")

# [Temporary] kills it at the start of the Beginning Phase; its Deathknell
# then repeats the play effect. That loop is the whole Sprite archetype.
phases.expire_temporary(s, T)
A._settle(s, T, V1)
drain(s, V1)
if s.perms[gear_row, P_ALIVE]:
    die("gear", "[Temporary] did not kill the gear")
if len(_sprites(s)) != 1:
    die("gear", f"the Deathknell should have replaced the expired Sprite, "
                f"got {len(_sprites(s))}")
ok("[Temporary] expiry fires its [Deathknell], which makes another Sprite")

# 185.3 -- the token ceased to exist; only the gear CARD reached the trash.
if int(s.n_trash[0]) != 1:
    die("gear", f"trash holds {int(s.n_trash[0])}; a token that dies must "
                f"cease to exist rather than being trashed (185.3)")
ok("185.3 -- the dead token left no card behind, only the gear did")


# ---------------------------------------------------------------------------
print("\n[15] activated abilities (151) -- cost, then ':', then effect")

HDI = T.id_of("Heart of Dark Ice")     # Exhaust: give a unit +3 Might
SEAL = T.id_of("Seal of Insight")      # Exhaust: [Reaction] - [Add] {Mind}

s = fresh(hand=[HDI])
target = s.add_permanent(PLAIN2, 0, bf_loc(0))
play(s, V1, 0, base_loc(0))
gear = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == HDI)
acts = A.legal_actions(s, T, V1, 0)
if not any(a.kind == A.A_ACTIVATE and a.arg == gear for a in acts):
    die("activate", "the gear's activated ability was never offered")
ok("an activated ability is offered as its own action")

A.apply(s, T, V1, A.Action(A.A_ACTIVATE, gear))
A.apply(s, T, V1, A.Action(A.A_TARGET, target))
if s.perms[gear, P_READY]:
    die("activate", "the Exhaust cost was not paid at finalization")
if any(a.kind == A.A_ACTIVATE for a in A.legal_actions(s, T, V1, 0)):
    die("activate", "an exhausted source was offered again")
ok("'Exhaust:' is a real cost -- paid at finalization, and not repeatable")

base = combat.might(s, T, target)
drain(s, V1)
if combat.might(s, T, target) != base + 3:
    die("activate", f"effect did not apply: {combat.might(s, T, target)}")
ok("the effect resolves through the Chain like a spell (151.2.a.1)")

# 337.2 -- a resource-adding ability resolves IMMEDIATELY, no Chain, no window.
s = fresh(hand=[SEAL])
play(s, V1, 0, base_loc(0))
seal = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == SEAL)
before = s.pool_power[0].sum()
A.apply(s, T, V1, A.Action(A.A_ACTIVATE, seal))
if s.n_chain != 0:
    die("add", "337.2 -- an [Add] ability must not touch the Chain; the card "
               "says outright that it cannot be reacted to")
if s.pool_power[0].sum() != before + 1:
    die("add", "no Power was added to the Rune Pool")
ok("[Add] resolves immediately: Power appears with nothing on the Chain")

# ---------------------------------------------------------------------------
# Vex - Apathetic: "When an opponent plays a unit while I'm at a battlefield,
# [Stun] it. They can't move it this turn."
#
# The mirror image of Lillia's "when you play a unit": same trigger, opposite
# side, which is one flag rather than a second trigger. Three restrictions, and
# each is separately checkable because dropping any one widens the card.

from rl.engine import chain as chain_mod
from rl.engine import combat as _combat
from rl.engine.state import (C_FINAL, F_NO_MOVE as _F_NO_MOVE,
                             F_STUNNED as _F_STUNNED)

VEX = T.id_of("Vex - Apathetic")
VEX_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit")
                and not T.is_token(c))


def vex_play(vex_loc, player=1):
    """Seat `player` plays a unit while seat 0 has a Vex at `vex_loc`."""
    s = GameState()
    s.phase, s.active, s.priority = MAIN, player, player
    s.add_permanent(VEX, 0, vex_loc)
    played = s.add_permanent(VEX_BODY, player, bf_loc(0))
    chain_mod.fire_play_unit(s, T, player, VEX_BODY, played)
    while s.n_trig:
        chain_mod.place(s, T, V1, 0)
    for i in range(int(s.n_chain)):
        s.chain[i, C_FINAL] = 1
    while s.n_chain:
        chain_mod.resolve_top(s, T, V1)
    return s, played


s, p = vex_play(bf_loc(0))
if not s.has_flag(p, _F_STUNNED) or not s.has_flag(p, _F_NO_MOVE):
    die("vex", "an opponent's unit is stunned and pinned")
s.active = 1
s.perms[p, P_READY] = 1
if _combat.can_move(s, T, V1, p, base_loc(1)):
    die("vex", "'they can't move it this turn' must block the retreat home too")
ok("Vex stuns what an opponent plays, and pins it for the turn")

s, p = vex_play(base_loc(0))
if s.has_flag(p, _F_STUNNED):
    die("vex", "'while I'm at a BATTLEFIELD' -- a Vex in a base watches nothing")
ok("...only while she is at a battlefield")

s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
s.add_permanent(VEX, 0, bf_loc(0))
own = s.add_permanent(VEX_BODY, 0, bf_loc(0))
chain_mod.fire_play_unit(s, T, 0, VEX_BODY, own)
if int(s.n_trig):
    die("vex", "'when an OPPONENT plays' -- my own units must not trigger it")
ok("...and never on her own controller's units")

print("\n\033[32mall trigger tests passed\033[0m")
