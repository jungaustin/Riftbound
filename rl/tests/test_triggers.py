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
from rl.obs import Encoder
from rl.engine.state import (C_ABIL, C_CARD, C_SRC, MAIN, P_ALIVE, P_CARD, P_DMG,
                             P_LOC, P_READY, RK_SPELL, GameState, base_loc,
                             bf_loc, fd_slots)

T = full_table()
V0 = Config().at_victory_score(3).with_solved_damage()                       # units only
V1 = replace(Config().at_victory_score(3).with_solved_damage(), units_only=False)

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
# Tokens are exempt: a token is never a deck card (185.3), so coverage never
# credits one -- Shadow Clone's ABILITIES entry is what the cards that MAKE it
# rely on.
blocked_by_text = [n for n in ABILITIES
                   if not T.is_token(T.id_of(n))
                   and not plays_as_printed(T, T.id_of(n))
                   and not T.unread_keywords(T.id_of(n))]
if blocked_by_text:
    die("coverage", f"specs written but still not played as printed for a "
                    f"reason other than a keyword: {blocked_by_text}")
covered = sum(1 for n in ABILITIES if plays_as_printed(T, T.id_of(n)))
ok(f"{covered}/{len(ABILITIES)} ability specs fully covered; the rest wait "
   f"only on an unread keyword")

# Scuttle Crab has an ETB *and* a Deathknell, and for a long time only the ETB
# was expressible -- so the card was deliberately kept out of ABILITIES, since
# a half-implemented card played as if whole is worse than an honest
# substitution. This guard used to assert that exclusion, and it fired the
# moment the Deathknell landed, which is exactly what it was for. Now it
# asserts the other direction: BOTH halves are present, or the card goes back
# out. Its Deathknell is the engine's only source of standing visibility, so a
# silently missing one would leave the observation work with nothing to grant.
crab = T.id_of("Scuttle Crab")
triggers = {a.trigger for a in abilities_for(T, crab)}
if triggers != {TR_PLAY_ME, chain_TR_DEATH}:
    die("coverage", f"Scuttle Crab needs BOTH its ETB and its Deathknell; "
                    f"has {sorted(triggers)}")
if not plays_as_printed(T, crab):
    die("coverage", "...and with both transcribed it must count as covered")
ok("Scuttle Crab carries both halves, so it is covered honestly")

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
from rl.engine import resolve as rsv_mod
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

# ---------------------------------------------------------------------------
# Hwei - Brooding Painter: the discard is a CHOICE, and it picks the mode
#
# "When I move, draw 1, then discard 1. Then, do the following based on the
# discarded card's type: Spell - Draw 1. Gear - Ready up to 2 runes. Unit -
# Give me +3 Might this turn."
#
# `phases.discard` takes the oldest card and always has -- its docstring says
# "the day a card says 'discard a card of your choice' this becomes a decision
# point rather than a rule here". This is that card: which card you pitch IS
# the mode selector, so taking the oldest would choose the mode for the player.

HWEI = T.id_of("Hwei - Brooding Painter")
HWEI_AB = ABILITIES["Hwei - Brooding Painter"][0]
H_SPELL = next(c for c in range(T.n) if T.is_type(c, "Spell"))
H_GEAR = next(c for c in range(T.n) if T.is_type(c, "Gear") and not T.is_token(c))
H_UNIT = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c))


def hwei_pitch(idx):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    h = s.add_permanent(HWEI, 0, bf_loc(0))
    s.n_hand[0] = 3
    s.hand[0, 0], s.hand[0, 1], s.hand[0, 2] = H_SPELL, H_GEAR, H_UNIT
    s.n_deck[0] = 10
    s.runes_spent[0, 0] = 3
    rsv_mod.resolve(s, T, V1, HWEI_AB, 0, [], -1, True, source=h)
    if s.pend_discard < 0:
        die("hwei", "the discard must pend as a choice, not take the oldest")
    before = _combat.might(s, T, h)
    A.apply(s, T, V1, A.Action(A.A_PICK, idx))
    return (int(s.n_hand[0]), int(s.runes_ready[0].sum()),
            _combat.might(s, T, h) - before)


# Every card in hand is offered -- the player picks the mode by picking the
# card, so nothing may be filtered out.
s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
h = s.add_permanent(HWEI, 0, bf_loc(0))
s.n_hand[0] = 3
s.hand[0, 0], s.hand[0, 1], s.hand[0, 2] = H_SPELL, H_GEAR, H_UNIT
s.n_deck[0] = 10
rsv_mod.resolve(s, T, V1, HWEI_AB, 0, [], -1, True, source=h)
if len(A.legal_actions(s, T, V1, 0)) != int(s.n_hand[0]):
    die("hwei", "every card in hand is a legal pitch")
ok("Hwei's discard is a decision point over the whole hand")

hand, ready, dmight = hwei_pitch(0)          # a Spell
if ready or dmight:
    die("hwei", "pitching a spell takes only the Spell branch")
hand, ready, dmight = hwei_pitch(1)          # a Gear
if ready != 2 or dmight:
    die("hwei", f"the Gear branch readies up to 2 runes, got {ready}")
hand, ready, dmight = hwei_pitch(2)          # a Unit
if dmight != 3 or ready:
    die("hwei", f"the Unit branch gives +3 Might, got {dmight}")
ok("...and the discarded card's TYPE selects which branch runs")

# ---------------------------------------------------------------------------
# Ekko - Recurrent: "[Deathknell] Recycle me to ready your runes."
#
# "Recycle me" is a cost within the instructions (383.3.b) but NOT an optional
# one -- the card never says "you may" -- so it is simply the first op.
#
# The subtlety is whose row answers "me". 383.2.c.2 blanks a source that has
# left the board, and a Deathknell's source is dead by definition, so `source`
# is -1 by the time this resolves. `dead_source` is kept for exactly the
# questions a corpse can still answer, and "recycle ME" names a card rather
# than a board position, so it is one of them.

EKKO = T.id_of("Ekko - Recurrent")

s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
e = s.add_permanent(EKKO, 0, bf_loc(0))
s.runes_spent[0, 0] = 4
s.n_deck[0] = 5
for i in range(5):
    s.deck[0, i] = EKKO
_combat.destroy(s, T, e)
while s.n_trig:
    chain_mod.place(s, T, V1, 0)
for i in range(int(s.n_chain)):
    s.chain[i, C_FINAL] = 1
while s.n_chain:
    chain_mod.resolve_top(s, T, V1)

if int(s.n_trash[0]) != 0 or int(s.n_deck[0]) != 6:
    die("ekko", f"the card leaves the trash for the deck, got trash="
                f"{int(s.n_trash[0])} deck={int(s.n_deck[0])}")
if int(s.deck[0, int(s.n_deck[0]) - 1]) != EKKO:
    die("ekko", "416.1.a -- a Recycle goes to the BOTTOM")
ok("383.2.c.2 -- 'recycle me' reads dead_source, the row kept for a corpse")

if int(s.runes_spent[0].sum()) != 0 or int(s.runes_ready[0].sum()) != 4:
    die("ekko", "'ready your runes' is unbounded -- every spent rune readies")
ok("...and 'ready your runes' readies all of them, not a capped number")

# ---------------------------------------------------------------------------
# Heimerdinger - Inventor: "I have all Exhaust abilities of all friendly
# legends, units, and gear."
#
# He HAS them, so a borrowed ability is his: the Exhaust cost taps HIM and the
# donor is untouched. That is the whole card -- one exhaust reused across the
# board, and the donors keep theirs.
#
# An A_ACTIVATE used to be identified by its permanent alone. Heimerdinger
# holds many abilities, so the arg carries a packed (permanent, donor) -- and
# since Legion Marauder and Tools of Empire print two activated abilities each,
# it carries an ability INDEX too. All three round-trip through one encoding.

HEIMER = T.id_of("Heimerdinger - Inventor")
DARK_ICE = T.id_of("Heart of Dark Ice")      # Exhaust: give a unit +3 Might
# No rules text: the fixture stands at an uncontrolled battlefield, so a body
# with a conquer trigger (Adaptatron, once scripted) fires it at Cleanup.
HEIM_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit")
                 and not T.is_token(c) and int(T.might[c]) >= 3
                 and not T.residual_text(c))

for _perm, _donor in ((0, 0), (5, 5), (3, 7), (47, 0), (0, 47)):
    if A.unpack_activate(A.pack_activate(_perm, _donor)) != (_perm, _donor, 0):
        die("heimer", f"the packed activate arg must round-trip "
                      f"({_perm}, {_donor})")
ok("a packed (permanent, donor) activate arg round-trips")

# ...and so does an own-permanent ability index, in a band that leaves every
# older value meaning what it did.
for _perm in (0, 5, 47):
    for _k in (0, 1, 2, 5):
        got = A.unpack_activate(A.pack_activate(_perm, _perm, _k))
        if got != (_perm, _perm, _k):
            die("heimer", f"(perm={_perm}, k={_k}) round-tripped to {got}")
_all = {A.pack_activate(p, p, k) for p in range(48) for k in range(4)}
_all |= {A.pack_activate(p, d) for p in range(48) for d in range(48) if p != d}
_all |= {A.pack_legend_activate(k) for k in range(A.MAX_LEGEND_ACT)}
if len(_all) != 48 * 4 + 48 * 47 + A.MAX_LEGEND_ACT:
    die("heimer", "two different activations collided on one arg -- the bands "
                  "overlap, and a policy would be choosing blind")
ok("...and the three bands never collide: every activation has its own arg")

s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
h = s.add_permanent(HEIMER, 0, bf_loc(0))
d = s.add_permanent(DARK_ICE, 0, base_loc(0))
u = s.add_permanent(HEIM_BODY, 0, bf_loc(0))
before = _combat.might(s, T, u)

borrowed = [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_ACTIVATE
            and A.unpack_activate(a.arg) == (h, d, 0)]
if not borrowed:
    die("heimer", "Heimerdinger should be offered the gear's Exhaust ability")
A.apply(s, T, V1, borrowed[0])
while s.pend_slot >= 0:
    A.apply(s, T, V1, [x for x in A.legal_actions(s, T, V1, A.acting_seat(s))
                       if x.arg == u][0])
for _ in range(8):
    if s.n_chain == 0:
        break
    A.apply(s, T, V1, A.Action(A.A_PASS))

if _combat.might(s, T, u) != before + 3:
    die("heimer", "the borrowed effect should resolve as the donor's does")
if int(s.perms[h, P_READY]) != 0:
    die("heimer", "the Exhaust cost taps HEIMERDINGER -- the ability is his")
if int(s.perms[d, P_READY]) != 1:
    die("heimer", "...and leaves the donor untouched, which is the whole card")
ok("...and a borrowed Exhaust ability taps him, never the donor")

# ---------------------------------------------------------------------------
# Three small conditions, each the mirror or the origin of something already
# here -- and each wrong in a way that would be invisible without a test.

LOYAL_PORO = T.id_of("Loyal Poro")
HARPOON = T.id_of("Harpoon Squad")
COND_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit")
                 and not T.is_token(c))


def loyal_poro_drew(with_friend):
    """Loyal Poro: "If I DIDN'T die alone, draw 1" -- Lonely Poro inverted."""
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    p = s.add_permanent(LOYAL_PORO, 0, bf_loc(0))
    s.n_deck[0] = 10
    if with_friend:
        s.add_permanent(COND_BODY, 0, bf_loc(0))
    _combat.destroy(s, T, p)
    while s.n_trig:
        chain_mod.place(s, T, V1, 0)
    for i in range(int(s.n_chain)):
        s.chain[i, C_FINAL] = 1
    while s.n_chain:
        chain_mod.resolve_top(s, T, V1)
    return int(s.n_hand[0])


if loyal_poro_drew(with_friend=False) != 0:
    die("loyal", "dying alone is exactly when this card does NOTHING")
if loyal_poro_drew(with_friend=True) != 1:
    die("loyal", "with a friend at the same location it draws")
ok("Loyal Poro reads F_DIED_ALONE inverted -- the mirror of Lonely Poro")

# Harpoon Squad: "when I move FROM a battlefield". TR_MOVE captures the
# location LEFT BEHIND (359.3.f.3), so this asks where it came from -- a unit
# walking home qualifies, one leaving its base does not.
HARPOON_AB = ABILITIES["Harpoon Squad"][0]
for ctx, want in ((bf_loc(0), 2), (base_loc(0), 0)):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    h = s.add_permanent(HARPOON, 0, base_loc(0))
    before = _combat.might(s, T, h)
    rsv_mod.resolve(s, T, V1, HARPOON_AB, 0, [], -1, True, source=h, ctx=ctx)
    if _combat.might(s, T, h) - before != want:
        die("harpoon", f"moving from {ctx} should give +{want} Might")
ok("...and 'move FROM a battlefield' asks about ctx, not where it is now")

# ---------------------------------------------------------------------------
# Watcher triggers: something happens to ONE permanent, and a DIFFERENT one
# fires. `chain.fire_watchers` is `fire_play_unit` generalised, so all of these
# share one place that knows how to ask "who was watching for this".

CENTAUR = T.id_of("Spectral Centaur")     # when ANOTHER friendly unit dies
PRIZE = T.id_of("Prize of Progress")      # when you use a GEAR's ability
W_GEAR = T.id_of("Heart of Dark Ice")
W_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
              and not T.residual_text(c))   # textless: see HEIM_BODY


def _drain(s):
    while s.n_trig:
        chain_mod.place(s, T, V1, 0)
    for i in range(int(s.n_chain)):
        s.chain[i, C_FINAL] = 1
    while s.n_chain:
        chain_mod.resolve_top(s, T, V1)


s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
cen = s.add_permanent(CENTAUR, 0, bf_loc(0))
other = s.add_permanent(W_BODY, 0, bf_loc(0))
before = _combat.might(s, T, cen)
_combat.destroy(s, T, other)
_drain(s)
if _combat.might(s, T, cen) - before != 2:
    die("centaur", "another friendly unit dying gives +2")

# TR_DEATH fires for the thing that died; this is the other question, and the
# dying unit must never be its own watcher.
s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
cen = s.add_permanent(CENTAUR, 0, bf_loc(0))
_combat.destroy(s, T, cen)
if int(s.n_trig):
    die("centaur", "'ANOTHER friendly unit' -- its own death must not trigger it")
ok("a watcher for another's death, and never for its own")

s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
pp = s.add_permanent(PRIZE, 0, bf_loc(0))
g = s.add_permanent(W_GEAR, 0, base_loc(0))
tgt = s.add_permanent(W_BODY, 0, bf_loc(0))
before = _combat.might(s, T, pp)
act = next(a for a in A.legal_actions(s, T, V1, 0)
           if a.kind == A.A_ACTIVATE and A.unpack_activate(a.arg)[1] == g)
A.apply(s, T, V1, act)
while s.pend_slot >= 0:
    A.apply(s, T, V1, [x for x in A.legal_actions(s, T, V1, A.acting_seat(s))
                       if x.arg == tgt][0])
for _ in range(8):
    if s.n_chain == 0 and s.n_trig == 0:
        break
    A.apply(s, T, V1, A.Action(A.A_PASS))
if _combat.might(s, T, pp) - before != 1:
    die("prize", "using a gear's activated ability gives +1")
ok("...and a watcher for a GEAR's activated ability being used")

# Jinx - Rebel: "When you discard ONE OR MORE cards, ready me and give me +1
# Might this turn." One trigger per discard EVENT, not per card -- a card that
# pitches two fires this once -- and nothing at all if the hand was empty.

JINX = T.id_of("Jinx - Rebel")
J_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c))


def jinx_after(n_discard, hand_size):
    from rl.engine.effects import OP_DISCARD as _OP_DISCARD
    from rl.engine.effects import CardSpec as _CS, Op as _Op, SPEED_MAIN as _SM
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    j = s.add_permanent(JINX, 0, bf_loc(0))
    s.perms[j, P_READY] = 0
    s.n_hand[0] = hand_size
    for i in range(hand_size):
        s.hand[0, i] = J_BODY
    before = _combat.might(s, T, j)
    rsv_mod.resolve(s, T, V1, _CS(speed=_SM, ops=(_Op(_OP_DISCARD, n=n_discard),)),
                    0, [], -1, True)
    while s.n_trig:
        chain_mod.place(s, T, V1, 0)
    for i in range(int(s.n_chain)):
        s.chain[i, C_FINAL] = 1
    while s.n_chain:
        chain_mod.resolve_top(s, T, V1)
    return int(s.perms[j, P_READY]), _combat.might(s, T, j) - before


if jinx_after(1, 3) != (1, 1):
    die("jinx", "discarding readies it and gives +1")
if jinx_after(2, 3) != (1, 1):
    die("jinx", "'one or more' is ONE trigger for the event, not one per card")
if jinx_after(1, 0) != (0, 0):
    die("jinx", "an empty hand discards nothing, so nothing triggers")
ok("'discard one or more cards' fires once per event, and not on nothing")

# Wraith of Echoes: "The FIRST TIME a friendly unit dies each turn, draw 1."
# A watcher for another's death with a once-per-turn gate, reusing the same
# `state.once_used` turn stamp Zilean's "once each turn" uses -- a stamp rather
# than a flag, so nothing has to remember to reset it.

WRAITH = T.id_of("Wraith of Echoes")
WR_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c))

s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
s.turn = 1
s.add_permanent(WRAITH, 0, bf_loc(0))
s.n_deck[0] = 20
first = s.add_permanent(WR_BODY, 0, bf_loc(0))
second = s.add_permanent(WR_BODY, 0, bf_loc(0))

_combat.destroy(s, T, first)
_drain(s)
if int(s.n_hand[0]) != 1:
    die("wraith", "the first friendly death each turn draws")
_combat.destroy(s, T, second)
_drain(s)
if int(s.n_hand[0]) != 1:
    die("wraith", "'the FIRST time each turn' -- a second death draws nothing")

s.ply += 1          # the next player-TURN; `turn` is a round (see state.ply)
third = s.add_permanent(WR_BODY, 0, bf_loc(0))
_combat.destroy(s, T, third)
_drain(s)
if int(s.n_hand[0]) != 2:
    die("wraith", "the turn stamp must re-arm on a new turn")
ok("'the first time each turn' fires once, then re-arms next turn")

# ---------------------------------------------------------------------------
# Diana - Lunari: two deferred decisions in sequence, behind an optional COST
#
# "When a showdown begins here, you may pay {1 energy}. If you do, [Predict],
# then reveal the top card of your Main Deck. If it's a spell, draw it."
#
# Every suspending op used to have to be its card's LAST, because resolution
# returns there. `Op.then_key` lifts that: a follow-up op list runs once the
# decision comes back, and it may suspend again. Diana is the card that needs
# it -- Predict, THEN reveal.
#
# 383.3.b is the other half: "you may PAY" is an optional COST, not a free
# yes/no, so accepting is only offered when it can be paid.

DIANA = T.id_of("Diana - Lunari")
D_UNIT = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c))
D_SPELL = next(c for c in range(T.n) if T.is_type(c, "Spell"))


def diana_board(energy, top_card):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.add_permanent(DIANA, 0, bf_loc(0))
    s.add_permanent(D_UNIT, 1, bf_loc(0))
    s.runes_ready[0, 0] = energy
    s.n_deck[0] = 4
    for i in range(4):
        s.deck[0, i] = top_card
    _combat.open_showdown(s, T, 0, attacker=0)
    while s.n_trig:
        chain_mod.place(s, T, V1, 0)
    for _ in range(6):
        if s.pend_may >= 0:
            break
        A.apply(s, T, V1, A.legal_actions(s, T, V1, A.acting_seat(s))[0])
    return s


s = diana_board(0, D_UNIT)
kinds = {A.KIND_NAMES[a.kind] for a in A.legal_actions(s, T, V1, A.acting_seat(s))}
if kinds != {"decline"}:
    die("diana", f"383.3.b -- an unaffordable optional cost offers only a "
                 f"decline, got {kinds}")
ok("383.3.b -- 'you may PAY' is offered only when the cost can be paid")

s = diana_board(3, D_UNIT)
before = int(s.runes_ready[0].sum())
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
if int(s.runes_ready[0].sum()) != before - 1 or int(s.runes_spent[0].sum()) != 1:
    die("diana", "accepting must actually pay the {1 energy}")

# Accepting FINALIZES the ability; it resolves once priority passes, and only
# then does the Predict suspend. That ordering is 383.3 doing its job, so the
# test drives the passes rather than asserting through them.
for _ in range(6):
    if s.pend_look >= 0:
        break
    A.apply(s, T, V1, A.legal_actions(s, T, V1, A.acting_seat(s))[0])
if s.pend_look < 0:
    die("diana", "the Predict should suspend for a choice once it resolves")
A.apply(s, T, V1, A.Action(A.A_PICK_NONE))
if s.pend_look < 0:
    die("diana", "the FOLLOW-UP reveal must suspend too -- that is the chain")
ok("...and a follow-up decision chains off the first (Predict, then reveal)")

# Two counting conditions, both wrong in a way a threshold reading would hide.
#
# Shen: "if there is EXACTLY ONE other unit you control here" -- a second
# friendly unit turns it OFF again. Kinkou Initiate: "if your OTHER units have
# total Might 5 or more" -- effective Might, and excluding itself.

SHEN = T.id_of("Shen, Scourge of Shadows")
KINKOU = T.id_of("Kinkou Initiate")


def _unit_of(m):
    return next(c for c in range(T.n) if T.is_type(c, "Unit")
                and not T.is_token(c) and int(T.might[c]) == m)


def shen_drew(n_others):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    h = s.add_permanent(SHEN, 0, bf_loc(0))
    s.n_deck[0] = 10
    for _ in range(n_others):
        s.add_permanent(_unit_of(2), 0, bf_loc(0))
    # 383.2.a.1 -- "When I hold, IF exactly one other unit..." is asked as the
    # ability triggers (`chain.ability_cond_holds`), not on resolution.
    from rl.engine.chain import ability_cond_holds as _ach
    ab = ABILITIES["Shen, Scourge of Shadows"][0]
    if _ach(s, T, ab, 0, h):
        rsv_mod.resolve(s, T, V1, ab, 0, [], -1, True, source=h)
    return int(s.n_hand[0])


if shen_drew(0) or shen_drew(2):
    die("shen", "'EXACTLY one other' is off at zero AND at two")
if shen_drew(1) != 1:
    die("shen", "...and on at exactly one")
ok("'exactly one other unit here' is an exact count, not a threshold")


def kinkou_drew(mights):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    k = s.add_permanent(KINKOU, 0, base_loc(0))
    s.n_deck[0] = 10
    for m in mights:
        s.add_permanent(_unit_of(m), 0, base_loc(0))
    rsv_mod.resolve(s, T, V1, ABILITIES["Kinkou Initiate"][0], 0, [], -1, True,
                    source=k)
    return int(s.n_hand[0])


if kinkou_drew([2, 2]) != 0 or kinkou_drew([2, 3]) != 1:
    die("kinkou", "'total Might 5 or more' is exact at the boundary")
ok("...and a Might TOTAL over the other units is exact at its boundary too")

# Viktor - Leader: "When another NON-RECRUIT unit you control dies, play a
# 1 Might Recruit unit token into your base."
#
# The tag exclusion is load-bearing rather than flavour: Viktor MAKES Recruits,
# so without it every token's death would make another one and the engine would
# never stop. The token does carry the Recruit tag (187.1), so the check has
# something real to test against.

VIKTOR = T.id_of("Viktor - Leader")
RECRUIT_TOK = T.id_of("Recruit (271) // Buff")
NON_RECRUIT = next(c for c in range(T.n) if T.is_type(c, "Unit")
                   and not T.is_token(c) and "Recruit" not in T.tags[c])


def viktor_tokens(dying_card):
    s = GameState()
    s.phase, s.active, s.priority = MAIN, 0, 0
    s.add_permanent(VIKTOR, 0, bf_loc(0))
    d = s.add_permanent(dying_card, 0, bf_loc(0), is_unit=True)
    before = sum(1 for i in range(s.n_perms) if s.perms[i, P_ALIVE] == 1)
    _combat.destroy(s, T, d)
    _drain(s)
    after = sum(1 for i in range(s.n_perms) if s.perms[i, P_ALIVE] == 1)
    return after - (before - 1)


if viktor_tokens(NON_RECRUIT) != 1:
    die("viktor", "a non-Recruit death should make one Recruit")
if viktor_tokens(RECRUIT_TOK) != 0:
    die("viktor", "'NON-Recruit' -- a Recruit dying must make nothing, or the "
                  "card is a perpetual motion machine")
ok("a subject tag exclusion, which is what stops Viktor feeding on himself")

# ---------------------------------------------------------------------------
print("\n[16] a play watcher sees only the card TYPE it names")

# Every permanent play -- unit, token and gear alike -- comes through the one
# `fire_play_unit` site, so "when you play a UNIT" fired on a gear until the
# watcher was made to state its type. Reluctant Leader grew +2 Might off a
# Cull, and Vex would have stunned one. The bug is invisible in a units-only
# game, which is why nothing caught it: v0 has no gear at all.

LEADER = T.id_of("Reluctant Leader")     # when you play ANOTHER unit, +2 Might
PIT = T.id_of("Pit Crew")                # when you play a GEAR, ready me
GEAR = T.id_of("Cull")                   # a gear whose only text is its Equip


def played(watcher, card, ready=True):
    """Put `watcher` on the board, play `card`, and return its row + state."""
    s = fresh(hand=[card])
    w = s.add_permanent(watcher, 0, base_loc(0), ready=ready, is_unit=True)
    play(s, V1, 0, base_loc(0))
    drain(s, V1)
    return s, w


s, w = played(LEADER, GEAR)
if combat.might(s, T, w) != int(T.might[LEADER]):
    die("type filter", f"a GEAR play grew a 'when you play another UNIT' "
                       f"watcher to {combat.might(s, T, w)}")
ok("playing a gear does not fire 'when you play another unit'")

s, w = played(LEADER, PLAIN2)
if combat.might(s, T, w) != int(T.might[LEADER]) + 2:
    die("type filter", "...but a UNIT play must still fire it")
ok("...while a unit play still does, so the filter did not silence the card")

s, w = played(PIT, GEAR, ready=False)
if int(s.perms[w, P_READY]) != 1:
    die("pit crew", "Pit Crew must ready itself when a gear is played")
ok("Pit Crew reads the other half of the same filter: gear, not units")

s, w = played(PIT, PLAIN2, ready=False)
if int(s.perms[w, P_READY]) != 0:
    die("pit crew", "...and a unit play must leave it exhausted")
ok("...and a unit play leaves it exhausted, which is the whole restriction")

# ---------------------------------------------------------------------------
print("\n[17] 383.3.b -- an optional cost paid in a BODY, not in runes")

# Overzealous Fan: "When I defend, you may kill me to move an attacking unit to
# its base." Until now every optional trigger cost was runes, which are checked
# for affordability before the offer. A kill-self cost is always affordable and
# is paid at FINALIZATION, so the source is a corpse before targets are chosen.

FAN = T.id_of("Overzealous Fan")


def fan_fight(accept):
    """Seat 1 attacks bf0; seat 0 defends with the Fan. Returns (state, rows)."""
    s = fresh(seat=1)
    s.active = s.priority = 1
    fan = s.add_permanent(FAN, 0, bf_loc(0), is_unit=True)
    atk = s.add_permanent(PLAIN2, 1, bf_loc(0), is_unit=True)
    combat.open_showdown(s, T, 0, attacker=1)
    for _ in range(40):
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        if not legal:
            die("fan", f"seat {who} to act with no legal action -- a cost was "
                       f"paid and the ability could not be completed")
        kinds = {a.kind for a in legal}
        if accept and A.A_ACCEPT in kinds:
            pick = next(a for a in legal if a.kind == A.A_ACCEPT)
        elif A.A_DECLINE in kinds:
            pick = next(a for a in legal if a.kind == A.A_DECLINE)
        elif A.A_TARGET in kinds:
            pick = next(a for a in legal if a.kind == A.A_TARGET)
        else:
            pick = next((a for a in legal if a.kind == A.A_PASS), legal[0])
        A.apply(s, T, V1, pick)
        if (s.n_chain == 0 and s.n_trig == 0
                and s.pend_may < 0 and s.pend_slot < 0):
            break
    return s, fan, atk


s, fan, atk = fan_fight(accept=True)
if s.perms[fan, P_ALIVE] == 1:
    die("fan", "accepting pays the cost -- the Fan must be dead")
if int(s.perms[atk, P_LOC]) != base_loc(1):
    die("fan", "the attacking unit goes home to ITS OWN base")
ok("'you may kill me to ...' -- the cost is paid and the effect happens")

s, fan, atk = fan_fight(accept=False)
if s.perms[fan, P_ALIVE] != 1:
    die("fan", "declining costs nothing -- 383.3.a.2, it never triggered")
if int(s.perms[atk, P_LOC]) != bf_loc(0):
    die("fan", "...and the attacker stays where it is")
ok("...while declining leaves both the Fan and the attacker untouched")

# The role gate is the other half of the card: an Overzealous Fan that ATTACKS
# has no ability at all, and a trigger that fired anyway would let it throw
# itself at a defender it was never meant to reach.
s = fresh()
s.add_permanent(FAN, 0, bf_loc(0), is_unit=True)
s.add_permanent(PLAIN2, 1, bf_loc(0), is_unit=True)
combat.open_showdown(s, T, 0, attacker=0)
if int(s.n_trig) != 0:
    die("fan", "'when I DEFEND' must not fire for an attacking Fan")
ok("...and it does not trigger at all when the Fan is the attacker")

# ---------------------------------------------------------------------------
print("\n[18] a watcher on the OPPONENT's points, from every site that awards one")

# Sumpworks Map: "When an opponent scores, draw 1." The engine has no single
# "award a point" primitive -- Hold pays in `phases.score_holds`, Conquer in
# `combat._establish_control`, and OP_SCORE grants one outright -- so the
# trigger has three firing sites and a fourth would need wiring too. Both of
# the reachable ones are checked here, in each direction.

from rl.engine import phases as _ph

MAP = T.id_of("Sumpworks Map")
V8 = replace(V1, victory_score=8)


def held_by(map_owner):
    """Seat 1 holds bf0 and scores; `map_owner` owns the Map."""
    s = fresh(seat=1)
    s.active = s.priority = 1
    s.add_permanent(MAP, map_owner, base_loc(map_owner), is_unit=False)
    s.add_permanent(PLAIN2, 1, bf_loc(0), is_unit=True)
    s.bf_ctrl[0] = 1
    gained = _ph.score_holds(s, V8, T)
    return gained, int(s.n_trig)


gained, trig = held_by(0)
if gained != 1 or trig != 1:
    die("sumpworks", f"the opponent of the scorer must trigger "
                     f"(scored {gained}, {trig} queued)")
ok("a Hold by one player fires the OTHER player's 'when an opponent scores'")

gained, trig = held_by(1)
if trig != 0:
    die("sumpworks", "'an OPPONENT scores' -- your own Hold must not fire it, "
                     "or the card reads every point on the board")
ok("...and never fires for the player who actually scored")

# Conquer is the second site, and the one a Hold-only wiring would miss.
s = fresh(seat=1)
s.active = s.priority = 1
s.add_permanent(MAP, 0, base_loc(0), is_unit=False)
s.add_permanent(PLAIN2, 1, bf_loc(0), is_unit=True)
s.bf_ctrl[:] = -1
before = int(s.n_hand[0])
combat.cleanup(s, T, V8, mover=1, dst=bf_loc(0))
if int(s.n_trig) != 1:
    die("sumpworks", "a Conquer awards a point too, and must fire it")
# `drain` stops at an empty Chain, but the trigger is still in the QUEUE at
# this point -- it reaches the Chain only once a player acts.
for _ in range(30):
    who = A.acting_seat(s)
    if who < 0:
        break
    legal = A.legal_actions(s, T, V8, who)
    if not legal:
        die("sumpworks", f"seat {who} to act with no legal action")
    A.apply(s, T, V8, next((a for a in legal if a.kind == A.A_PASS), legal[0]))
    if s.n_chain == 0 and s.n_trig == 0:
        break
if int(s.n_hand[0]) != before + 1:
    die("sumpworks", "the draw has to actually happen, not just queue")
ok("...and a Conquer fires it as well, drawing the card the text promises")

# ---------------------------------------------------------------------------
print("\n[19] readying and choosing are events cards can watch")

# Austin's ruling: **the Awaken Phase counts as readying.** That decides the
# whole family -- Pirate's Haven pays out once per exhausted unit every turn,
# which is what makes it a reward for attacking with everything rather than a
# marginal trick. What it must NOT do is pay for a unit that was already ready,
# since that unit never became ready; Awaken writes the whole board in one
# vectorised store, so the transition has to be captured before the write.

def drain_all(s, cfg=None):
    """`drain` stops at an empty Chain, but a fired trigger sits in the QUEUE
    until someone acts -- it reaches the Chain only on the next decision."""
    cfg = cfg or V1
    for _ in range(60):
        if s.n_chain == 0 and s.n_trig == 0 and s.pend_slot < 0 \
                and s.pend_may < 0:
            return
        who = A.acting_seat(s)
        if who < 0:
            return
        legal = A.legal_actions(s, T, cfg, who)
        if not legal:
            die("drain_all", f"seat {who} to act with no legal action")
        A.apply(s, T, cfg,
                next((a for a in legal if a.kind == A.A_PASS), legal[0]))


IRELIA = T.id_of("Irelia, Fervent")     # when you choose OR ready ME, +1 Might
HAVEN = T.id_of("Pirate's Haven")       # when you ready a friendly unit, +1 it
STUPEFY = T.id_of("Stupefy")            # give a unit -1 Might this turn


def after_awaken(card, ready, watcher=None, seat=0, active=0):
    """Put `card` on the board (maybe already ready) and run Awaken."""
    s = fresh()
    s.active = s.priority = active
    if watcher is not None:
        s.add_permanent(watcher, 0, base_loc(0), is_unit=False)
    row = s.add_permanent(card, seat, base_loc(seat), ready=ready,
                          is_unit=True)
    before = combat.might(s, T, row)
    phases.awaken(s, T)
    drain_all(s)
    return before, combat.might(s, T, row)


before, after = after_awaken(IRELIA, ready=False)
if after != before + 1:
    die("readied", "Awaken counts as readying -- an exhausted Irelia grows")
ok("the Awaken Phase readies, and 'when you ready me' fires for it")

before, after = after_awaken(IRELIA, ready=True)
if after != before:
    die("readied", "a unit that was ALREADY ready has not become ready")
ok("...but not for a unit that never was exhausted, which is the whole gate")

# The discriminating case for `subject_is_self`: Awaken fires once PER unit,
# so with a friend beside her Irelia sees two readying events and must react to
# exactly one. Without the flag she reads "when you ready a friendly unit" and
# scales with the width of your board.
s = fresh()
ire = s.add_permanent(IRELIA, 0, base_loc(0), ready=False, is_unit=True)
s.add_permanent(PLAIN2, 0, base_loc(0), ready=False, is_unit=True)
before = combat.might(s, T, ire)
phases.awaken(s, T)
drain_all(s)
if combat.might(s, T, ire) != before + 1:
    die("readied", f"'ready ME' -- Irelia must grow by exactly 1 with a friend "
                   f"beside her, not once per unit readied "
                   f"(got {combat.might(s, T, ire) - before})")
ok("...and 'ME' means her alone: a friend waking beside her adds nothing")

before, after = after_awaken(PLAIN2, ready=False, watcher=HAVEN)
if after != before + 1:
    die("readied", "Pirate's Haven pumps the unit that woke")
ok("Pirate's Haven reads the same event with the SUBJECT as its target")

before, after = after_awaken(PLAIN2, ready=False, watcher=HAVEN,
                             seat=1, active=1)
if after != before:
    die("readied", "'a FRIENDLY unit' -- an enemy's Awaken feeds you nothing")
ok("...and only for its controller's units, not the opponent's")


def stupefied_by(caster):
    """`caster` plays Stupefy on a unit of seat 0. Returns the Might delta."""
    def delta(card):
        s = fresh(seat=caster)
        s.active = s.priority = caster
        row = s.add_permanent(card, 0, base_loc(0), is_unit=True)
        s.hand[caster, 0] = STUPEFY
        s.n_hand[caster] = 1
        before = combat.might(s, T, row)
        A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
        legal = A.legal_actions(s, T, V1, A.acting_seat(s))
        A.apply(s, T, V1, next(a for a in legal
                               if a.kind == A.A_TARGET and a.arg == row))
        drain_all(s)
        return combat.might(s, T, row) - before
    return delta


# Measured against a CONTROL rather than against an expected number: Stupefy is
# a debuff, so "Irelia ended on the same Might" could mean the trigger fired or
# that nothing happened at all. The difference between the two deltas is the
# only part that is Irelia's.
own = stupefied_by(0)
if own(PLAIN2) != -1:
    die("chosen", "Stupefy alone is -1, which is the control")
if own(IRELIA) != 0:
    die("chosen", "choosing your own Irelia fires her: -1 debuff, +1 trigger")
ok("'when you choose me' fires on your own targeting (+1 against a -1 control)")

foe = stupefied_by(1)
if foe(IRELIA) != -1:
    die("chosen", "'YOU choose' -- an opponent's spell must not grow her, or "
                  "[Deflect] would be rewarding the thing it taxes")
ok("...and never when the OPPONENT chooses her, which is a different event")

print("\n\033[32mall trigger tests passed\033[0m")


# ---------------------------------------------------------------------------
print("\n[20] a BATTLEFIELD is an ability source (BF_ABILITIES)")
# Everything above sources an ability from a permanent row. A battlefield has
# no row -- no controller, no location of its own, nothing that can die -- so
# "when you conquer here, draw 1 for each other battlefield you control" needed
# a source encoding that is not a row, and a controlling seat carried alongside
# it. Both are what these check.
from rl.engine import phases
from rl.engine.effects import (BF_ABILITIES, TR_CONQUER, TR_HOLD,
                               bf_abilities_for)
from rl.engine.state import bf_src, is_bf_src, bf_src_index

SEAT_OF_POWER = T.id_of("Seat of Power")
GROVE = T.id_of("Grove of the God-Willow")
WARRENS = T.id_of("Zaun Warrens")

if not is_bf_src(bf_src(0)) or bf_src_index(bf_src(1)) != 1:
    die("bf-src", "the battlefield source encoding must round-trip")
if is_bf_src(0) or is_bf_src(-1):
    die("bf-src", "a permanent row (or the -1 'no source') must never read as "
                  "a battlefield, or `fire` would look up the wrong table")
ok("the battlefield source sentinel round-trips and cannot collide with a row")


def held_by(bf_cards, ctrl, seat=0):
    """A board where `seat` holds every battlefield in `ctrl`, then Awaken."""
    s = fresh(seat=seat)
    s.active = s.priority = seat
    for i, c in enumerate(bf_cards):
        s.bf_card[i] = c
    for i in ctrl:
        s.bf_ctrl[i] = seat
        s.add_permanent(PLAIN2, seat, bf_loc(i), is_unit=True)
    return s


# -- Hold: fires once for the holder, not once per unit standing there.
s = held_by([GROVE, -1], [0])
s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)     # a SECOND unit there
before = int(s.n_hand[0])
phases.score_holds(s, V1, T)
if s.n_trig != 1:
    die("bf-hold", f"expected exactly one queued trigger, got {s.n_trig} -- "
                   f"a battlefield's ability fires for the PLAYER, so two "
                   f"units standing on it must not fire it twice")
drain_all(s)
if int(s.n_hand[0]) != before + 1:
    die("bf-hold", f"Grove of the God-Willow drew {int(s.n_hand[0]) - before}")
ok("'when you hold here' fires once for the holder, with two units present")

# -- and it is the HOLDER who draws, not the turn player.
s = held_by([GROVE, -1], [0], seat=1)
before = [int(s.n_hand[0]), int(s.n_hand[1])]
phases.score_holds(s, V1, T)
drain_all(s)
if int(s.n_hand[1]) != before[1] + 1 or int(s.n_hand[0]) != before[0]:
    die("bf-hold", "the battlefield has no controller of its own -- the seat "
                   "the trigger fired FOR must be the one that resolves it")
ok("...and for the holding seat, which is carried on the queue entry")

# -- Conquer: "each OTHER battlefield" excludes the one being conquered.
def conquer_draw(also_controls):
    s = fresh()
    s.bf_card[0] = SEAT_OF_POWER
    s.bf_card[1] = GROVE
    s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
    if also_controls:
        s.bf_ctrl[1] = 0
    before = int(s.n_hand[0])
    combat._establish_control(s, T, V1, 0)
    drain_all(s)
    return int(s.n_hand[0]) - before


if conquer_draw(False) != 0:
    die("bf-conquer", "controlling nothing else must draw nothing -- if the "
                      "battlefield counted ITSELF this would be 1")
if conquer_draw(True) != 1:
    die("bf-conquer", "one other battlefield controlled is one card")
ok("Seat of Power counts other battlefields, and never the one it is printed on")

# -- The ability must not leak into the permanent-side lookup. A battlefield
#    that landed in ABILITIES would be walked by `fire_watchers` and friends,
#    which read `perms[w, P_CARD]` and would source it from a unit's row.
for _nm in BF_ABILITIES:
    if _nm in ABILITIES:
        die("bf-tables", f"{_nm} is in BOTH ability tables; the permanent-side "
                         f"loops would fire it with a unit as its source")
    if not bf_abilities_for(T, T.id_of(_nm)):
        die("bf-tables", f"{_nm} is not reachable through bf_abilities_for")
if abilities_for(T, SEAT_OF_POWER):
    die("bf-tables", "a battlefield must have no PERMANENT-side abilities")
ok("the two ability tables stay disjoint, and battlefields are only in one")

# -- "Discard 1, THEN draw 1": order is the whole content of the word "then".
WARRENS_BF = T.id_of("Zaun Warrens")


def warrens(hand_n):
    """Conquer Zaun Warrens with `hand_n` cards in hand. Returns the deltas.

    Runes are stripped so nothing in hand is castable: otherwise the drain loop
    plays units out of the hand it is supposed to be measuring.
    """
    s = fresh(hand=[PLAIN2] * hand_n, runes=0)
    s.bf_card[0] = WARRENS_BF
    s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
    # The deck is consumed by `deck_ptr`, not by `n_deck` -- `n_deck` is how
    # many cards were dealt and never moves.
    before = (int(s.n_hand[0]), int(s.deck_ptr[0]), int(s.n_trash[0]))
    combat._establish_control(s, T, V1, 0)
    for _ in range(30):
        if s.n_chain == 0 and s.n_trig == 0 and s.pend_discard < 0 \
                and s.pend_slot < 0 and s.pend_may < 0:
            break
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        if not legal:
            die("bf-warrens", "seat to act with no legal action")
        A.apply(s, T, V1,
                next((a for a in legal if a.kind == A.A_PASS), legal[0]))
    return tuple(x - y for x, y in
                 zip((int(s.n_hand[0]), int(s.deck_ptr[0]), int(s.n_trash[0])),
                     before))


if warrens(3) != (0, 1, 1):
    die("bf-warrens", f"discard 1 then draw 1 gave {warrens(3)}, expected "
                      f"(hand 0, one card off the deck, trash +1)")
ok("Zaun Warrens: one card leaves the hand and one replaces it")

# The order is not cosmetic. If the draw ran first, a 0-card hand would end
# with 1 drawn and then 1 discarded -- net zero, with a card in the trash.
if warrens(0) != (1, 1, 0):
    die("bf-warrens", f"an empty hand gave {warrens(0)}: 'then' is sequencing, "
                      f"not a condition, so the draw still happens -- and with "
                      f"nothing to discard the trash must stay empty")
ok("...and an empty hand still draws, with nothing reaching the trash")


# ---------------------------------------------------------------------------
print("\n[21] 486.5 -- each deck presents ONE of its OWN three battlefields")
from rl.decks import DeckLoad, load_all, matchup, present

_DECKS = {d.name: d for d in load_all(T, warn=False)}
_WITH_BF = [d for d in _DECKS.values() if len(d.battlefields) >= 3]
if len(_WITH_BF) < 2:
    die("matchup", "this test needs two decks printing three battlefields")
_A, _B = _WITH_BF[0], _WITH_BF[1]

# The bug this pins: `matchup` read deck A's FIRST and deck B's SECOND from a
# shared pool, so the pair it produced depended on ARGUMENT ORDER. Every
# evaluator averages over a seat swap to cancel the first-player advantage --
# and each half of that average was being played on a different pair of
# battlefields, which is a confound and not an average.
_, _, _fwd, _, _ = matchup(_A, _B)
_, _, _rev, _, _ = matchup(_B, _A)
if sorted(_fwd) != sorted(_rev):
    die("matchup", f"swapping the seats changed which battlefields are in "
                   f"play: {[T.names[c] for c in _fwd]} vs "
                   f"{[T.names[c] for c in _rev]}")
if _fwd != _rev[::-1]:
    die("matchup", "the swap must exchange the two slots and nothing else")
ok("a seat swap exchanges the seats, and leaves the battlefield pair alone")

if _fwd[0] not in _A.battlefields or _fwd[1] not in _B.battlefields:
    die("matchup", "each seat must present a battlefield from its OWN deck")
ok("...and each battlefield in play came from the deck that presented it")

# `picks` is the decision the Bo3 format is built around, so it has to reach
# all nine pairings rather than a diagonal.
_grid = {tuple(matchup(_A, _B, picks=(i, j))[2])
         for i in range(3) for j in range(3)}
if len(_grid) != 9:
    die("matchup", f"the 3x3 presentation grid produced {len(_grid)} distinct "
                   f"pairs, not 9 -- a caller cannot evaluate a choice it "
                   f"cannot express")
ok("the 3x3 grid of presentations reaches all nine pairs")

# A decklist with no battlefields must not supply BOTH of them.
_EMPTY = DeckLoad(name="none", main=list(_A.main), runes=list(_A.runes),
                  battlefields=[], coverage=1.0)
_, _, _borrowed, _, _ = matchup(_EMPTY, _B)
if _borrowed[0] not in _B.battlefields or _borrowed[1] not in _B.battlefields:
    die("matchup", "a deck printing no battlefields borrows, which is fine")
if present(_EMPTY, 0, None) != -1:
    die("matchup", "with nothing to borrow either, there is no battlefield")
ok("a deck printing none borrows rather than blocking the matchup")


# ---------------------------------------------------------------------------
print("\n[22] the Champion Legend is a source, and 315.1.b recharges it")
# A legend is a Game Object (174) but NOT a Permanent (175): no row, no
# location, cannot be killed or moved, never leaves the Legend Zone (107.4.d).
# It nonetheless prints activated abilities that are available from turn 1 of
# every game, which is a third kind of ability source.
from rl.engine.effects import LEGEND_ABILITIES, legend_abilities_for
from rl.engine.state import legend_src, is_legend_src, legend_src_seat

BASHFUL = T.id_of("Lillia - Bashful Bloom")     # {4}, Exhaust: 3-Might Sprite
SPRITE_TOK = T.id_of("Sprite (274) // Buff")

if not is_legend_src(legend_src(1)) or legend_src_seat(legend_src(1)) != 1:
    die("legend-src", "the legend source encoding must round-trip")
# The three source bands must not overlap, or `fire` reads the wrong table.
for _v in (0, 1, 47, -1, bf_src(0), bf_src(1)):
    if is_legend_src(_v):
        die("legend-src", f"{_v} reads as a legend source; the sentinel bands "
                          f"for rows, battlefields and legends must be disjoint")
for _v in (legend_src(0), legend_src(1)):
    if is_bf_src(_v):
        die("legend-src", f"{_v} reads as a battlefield source too")
ok("row / battlefield / legend source bands are disjoint and round-trip")


def with_legend(card, ready=True, runes=6, sprites=0):
    """A board with `card` in the Legend Zone and `runes` TOTAL ready runes.

    `fresh` takes runes PER DOMAIN across six domains, so its `runes=2` is
    twelve runes and pays for anything -- which is how the first version of the
    unaffordability assertion below passed while measuring nothing. Total is
    what an energy cost actually spends, so that is what this takes.
    """
    s = fresh(runes=0)
    s.runes_ready[0, 0] = runes
    s.legend[0] = card
    s.legend_ready[0] = int(ready)
    for _ in range(sprites):
        s.add_permanent(SPRITE_TOK, 0, base_loc(0), is_unit=True)
    return s


def legend_acts(s):
    return [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_ACTIVATE and A.is_legend_activate(a.arg)]


s = with_legend(BASHFUL)
if len(legend_acts(s)) != 1:
    die("legend", "a ready legend with an affordable ability must offer it")
if legend_acts(with_legend(BASHFUL, ready=False)):
    die("legend", "an EXHAUSTED legend must offer nothing -- the Exhaust cost "
                  "is what makes the ability once per turn rather than free")
if legend_acts(with_legend(BASHFUL, runes=3)):
    die("legend", "{4 energy} is unaffordable on 3 runes, so it must not be "
                  "offered at all")
ok("offered only while ready and affordable; exhaustion is the once-per-turn gate")

# The discount is the whole card: three friendly [Temporary] units make the
# 4-cost ability cost 1, so it becomes castable on runes that could not pay
# the printed price.
# Three friendly [Temporary] units take the 4-cost ability to 1, so the very
# board that could not pay a moment ago now can. Measured against the
# `runes=3` control directly above: without it, "affordable" could just mean
# the discount is being ignored and the cost was payable all along.
if not legend_acts(with_legend(BASHFUL, runes=3, sprites=3)):
    die("legend", "'costs {1 energy} less for each friendly unit with "
                  "[Temporary]' must make it affordable on 3 runes with 3 out")
ok("...and the printed discount scales with the board, off the legend's own table")

# End to end: activating it exhausts the legend and makes a Sprite.
s = with_legend(BASHFUL)
n_before = int(s.n_perms)
A.apply(s, T, V1, legend_acts(s)[0])
drain_all(s)
made = [i for i in range(int(s.n_perms))
        if int(s.perms[i, P_CARD]) == SPRITE_TOK and s.perms[i, P_ALIVE] == 1]
if not made:
    die("legend", "activating Lillia - Bashful Bloom must produce a Sprite")
if int(s.legend_ready[0]) != 0:
    die("legend", "the Exhaust cost must actually exhaust the legend")
if not s.perms[made[0], P_READY]:
    die("legend", "the token is played READY -- 'play a READY 3 Might Sprite'")
ok("activating it exhausts the legend and plays a ready Sprite token")

# 315.1.b -- Awaken readies "all Game Objects they control", legend included.
# This is what makes a legend an engine rather than a one-shot, so it is the
# assertion that matters most.
phases.awaken(s, T)
if int(s.legend_ready[0]) != 1:
    die("legend", "315.1.b readies every Game Object the turn player controls, "
                  "and 107.4.c makes the Champion Legend one of them")
ok("the Awaken Phase recharges it (315.1.b), once per turn, every turn")

# ...and only the TURN PLAYER's. Awaken is the turn player's task.
s.legend_ready[:] = 0
s.active = 1
phases.awaken(s, T)
if int(s.legend_ready[1]) != 1 or int(s.legend_ready[0]) != 0:
    die("legend", "Awaken is the TURN PLAYER's task; the opponent's legend "
                  "stays exhausted through it")
ok("...for the turn player alone, which is what makes exhausting it a real cost")

# The tables stay disjoint, the same guard the battlefield tables have.
for _nm in LEGEND_ABILITIES:
    if _nm in ABILITIES or _nm in BF_ABILITIES:
        die("legend", f"{_nm} is in more than one ability table")
    if not legend_abilities_for(T, T.id_of(_nm)):
        die("legend", f"{_nm} is unreachable through legend_abilities_for")
ok("legend abilities live in exactly one table, reachable only as a legend")

# -- Hall of Legends, the card this whole section unblocks. It is the most
#    played battlefield in the corpus (14 of 108 slots) and was inexpressible
#    while `state.legend` was a field nothing wrote and nothing read.
HALL = T.id_of("Hall of Legends")


def conquer_hall(legend_ready, accept, runes=6):
    s = fresh(runes=0)
    s.runes_ready[0, 0] = runes
    s.bf_card[0] = HALL
    s.legend[0] = BASHFUL
    s.legend_ready[0] = int(legend_ready)
    s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
    combat._establish_control(s, T, V1, 0)
    for _ in range(30):
        if s.n_chain == 0 and s.n_trig == 0 and s.pend_may < 0 \
                and s.pend_slot < 0:
            break
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        want = A.A_ACCEPT if accept else A.A_DECLINE
        pick = next((a for a in legal if a.kind == want),
                    next((a for a in legal if a.kind == A.A_PASS), legal[0]))
        A.apply(s, T, V1, pick)
    return s


s = conquer_hall(legend_ready=False, accept=True)
if int(s.legend_ready[0]) != 1:
    die("hall", "'you may pay {1 energy} to ready your legend' must ready it")
if int(s.total_ready_runes(0)) != 5:
    die("hall", f"the {{1 energy}} must actually be paid; "
                f"{int(s.total_ready_runes(0))} runes left of 6")
ok("Hall of Legends readies an exhausted legend for {1 energy}")

s = conquer_hall(legend_ready=False, accept=False)
if int(s.legend_ready[0]) != 0 or int(s.total_ready_runes(0)) != 6:
    die("hall", "383.3.a.2 -- declining removes the ability from the chain, so "
                "nothing is readied and nothing is paid")
ok("...and declining costs nothing, which is what makes 'you may' a choice")

# A second activation in one turn is the entire point of paying for this.
s = conquer_hall(legend_ready=False, accept=True)
if not legend_acts(s):
    die("hall", "the readied legend must be activatable again this turn -- a "
                "second use is what the {1 energy} buys")
ok("the readied legend can be used again the same turn")


# ---------------------------------------------------------------------------
print("\n[23] four more battlefields, and the three shapes they needed")
from rl.engine.effects import ST_NO_PLAY
SAND_SOLDIER = T.id_of("Sand Soldier")


def conquer_bf(name, prefer=(), runes=6, extra_units=0):
    """Conquer battlefield 0 with `name` on it, then drain."""
    s = fresh(runes=0)
    s.runes_ready[0, 0] = runes
    s.bf_card[0] = T.id_of(name)
    s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
    for _ in range(extra_units):
        s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
    combat._establish_control(s, T, V1, 0)
    # The conquer happened outside an action, so nothing has drained the
    # trigger queue yet. `_settle` is what `apply` would have called.
    A._settle(s, T, V1)
    for _ in range(30):
        if s.n_chain == 0 and s.n_trig == 0 and s.pend_may < 0 \
                and s.pend_slot < 0:
            break
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        if not legal:
            die("bf23", f"{name}: seat to act with no legal action")
        a = next((x for x in legal if x.kind in prefer),
                 next((x for x in legal if x.kind == A.A_PASS), legal[0]))
        A.apply(s, T, V1, a)
    return s


# -- Emperor's Dais: "you may pay {1} AND return a unit you control here. If
#    you do, play a Sand Soldier here." Pickpocket's shape -- one "you may", so
#    accepting performs both halves and "if you do" needs no condition.
s = conquer_bf("Emperor's Dais", prefer=(A.A_ACCEPT, A.A_TARGET))
if int(s.n_hand[0]) != 1:
    die("dais", "the chosen unit must return to its owner's HAND")
if int(s.total_ready_runes(0)) != 5:
    die("dais", "the {1 energy} is a cost and must actually be paid")
ss = [i for i in range(int(s.n_perms))
      if int(s.perms[i, P_CARD]) == SAND_SOLDIER and s.perms[i, P_ALIVE] == 1]
if len(ss) != 1 or int(s.perms[ss[0], P_LOC]) != bf_loc(0):
    die("dais", "the Sand Soldier is played HERE, replacing what was bounced")
ok("Emperor's Dais bounces a unit and replaces it with a Sand Soldier here")

s = conquer_bf("Emperor's Dais", prefer=(A.A_DECLINE,))
if int(s.n_hand[0]) or int(s.total_ready_runes(0)) != 6:
    die("dais", "declining must cost nothing and bounce nothing")
ok("...and declining pays nothing, bounces nothing, makes nothing")

# "HERE" is the battlefield's own location, and that is the whole reason
# `same_loc_as_source` had to learn about battlefield sources: it tested
# `source < 0`, which is true of every sentinel, so the slot found no
# candidates at all and 355.8 kept the ability off the Chain silently.
_s = fresh(runes=0)
_s.runes_ready[0, 0] = 6
_s.bf_card[0] = T.id_of("Emperor's Dais")
_here = _s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
_away = _s.add_permanent(PLAIN2, 0, base_loc(0), is_unit=True)
combat._establish_control(_s, T, V1, 0)
A._settle(_s, T, V1)
A.apply(_s, T, V1, next(a for a in A.legal_actions(_s, T, V1, 0)
                        if a.kind == A.A_ACCEPT))
_opts = {a.arg for a in A.legal_actions(_s, T, V1, 0) if a.kind == A.A_TARGET}
if _opts != {_here}:
    die("dais", f"'a unit you control HERE' must offer only the unit at the "
                f"battlefield; offered {_opts}, wanted {{{_here}}} and not the "
                f"one at base ({_away})")
ok("...and 'here' means the battlefield itself, never a unit back at base")

# -- The Arena's Greatest: a battlefield watching the BEGINNING PHASE, which
#    needed a firing site of its own -- no permanent is involved at all.
s = fresh(runes=0)
s.bf_card[0] = T.id_of("The Arena's Greatest")
s.turn = 1
before = int(s.points[0])
phases.start_turn(s, T, V1)
A._settle(s, T, V1)          # what `apply` does after start_turn in real play
drain_all(s)
if int(s.points[0]) != before + 1:
    die("arena", "each player gains 1 point on their FIRST Beginning Phase")
ok("The Arena's Greatest scores on the first Beginning Phase, off no permanent")

s.turn = 4
before = int(s.points[0])
phases.start_turn(s, T, V1)
A._settle(s, T, V1)
drain_all(s)
if int(s.points[0]) != before:
    die("arena", "'FIRST Beginning Phase' is once, not every turn -- otherwise "
                 "the battlefield simply ends the game")
ok("...and never again, which is the difference between a bonus and a clock")

# -- Rockfall Path: the first static that REMOVES a permission.
s = fresh(runes=6)
s.bf_card[0] = T.id_of("Rockfall Path")
s.bf_card[1] = T.id_of("Trifarian War Camp")
s.bf_ctrl[0] = 0
s.bf_ctrl[1] = 0
dests = A.play_destinations(s, T, V1, 0, PLAIN2)
if bf_loc(0) in dests:
    die("rockfall", "'units can't be played here' must remove the destination")
if bf_loc(1) not in dests or base_loc(0) not in dests:
    die("rockfall", f"it must remove only ITS OWN battlefield; got {dests}")
ok("Rockfall Path removes itself as a play destination, and nothing else")

# It must narrow the WIDENED set too -- a printed permission is still a play.
amb = [c for c in range(T.n) if T.is_type(c, "Unit") and T.has(c, "Ambush")]
if amb:
    s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
    if bf_loc(0) in A.play_destinations(s, T, V1, 0, amb[0]):
        die("rockfall", "[Ambush] widens 806.3, but an Ambushed unit is still a "
                        "unit being played here")
    ok("...including for [Ambush], which widens 806.3 but is still a play")

# -- Forbidding Waste: a static gated on a live COMBAT ROLE, not on a keyword.
def waste_might(defender_alone):
    s = fresh(runes=0)
    s.bf_card[0] = T.id_of("Forbidding Waste")
    d = s.add_permanent(PLAIN2, 1, bf_loc(0), is_unit=True)
    if not defender_alone:
        s.add_permanent(PLAIN2, 1, bf_loc(0), is_unit=True)
    s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
    base = combat.might(s, T, d)
    s.showdown_bf = 0
    s.attacker = 0                       # seat 1 is therefore defending
    return base, combat.might(s, T, d)


base, alone = waste_might(True)
if alone != base - 2:
    die("waste", f"a lone defender here has -2 Might; {base} -> {alone}")
ok("Forbidding Waste: -2 Might while defending alone")

base, paired = waste_might(False)
if paired != base:
    die("waste", "740.2.a -- a second friendly unit here means not alone, and "
                 "the penalty must switch off live")
ok("...and a second friendly unit turns it off, read live rather than snapshot")

# Out of combat there is no defender at all.
_s = fresh(runes=0)
_s.bf_card[0] = T.id_of("Forbidding Waste")
_d = _s.add_permanent(PLAIN2, 1, bf_loc(0), is_unit=True)
if combat.might(_s, T, _d) != int(T.might[PLAIN2]):
    die("waste", "with no combat running nothing is DEFENDING, so the penalty "
                 "must not apply")
ok("...and outside a combat nobody is defending, so it does not apply at all")


# ---------------------------------------------------------------------------
print("\n[24] Void Gate, Ravenbloom Conservatory, Targon's Peak")
from rl.engine.effects import ST_DAMAGE_BONUS

# -- Void Gate: a damage MODIFIER, hooked at the one path spell and ability
#    damage goes through. Combat damage is assigned in the damage step and
#    writes P_DMG directly, so it must be untouched -- the card says "spells
#    and abilities", and a hook in the wrong place would buff every attack.
BIG = plain(5)


def void_marked(bf_name, loc_fn, amount=2):
    s = fresh(runes=0)
    s.bf_card[0] = T.id_of(bf_name)
    u = s.add_permanent(BIG, 0, loc_fn(0), is_unit=True)
    combat.mark_damage(s, T, u, amount)
    return int(s.perms[u, P_DMG])


if void_marked("Void Gate", bf_loc) != 3:
    die("void", "2 damage from a spell becomes 3 on Void Gate")
if void_marked("Rockfall Path", bf_loc) != 2:
    die("void", "another battlefield adds nothing")
if void_marked("Void Gate", base_loc) != 2:
    die("void", "'units HERE' is the battlefield, not a base across the board")
ok("Void Gate adds 1 to each instance of spell/ability damage dealt there")

# A 0-damage event is not an instance of damage to increase. Turning it into 1
# would make 143.2.a lethal where the rules say nothing happened.
if void_marked("Void Gate", bf_loc, amount=0) != 0:
    die("void", "a zero-damage event must stay zero -- otherwise Might "
                "reduction becomes removal on this battlefield")
ok("...and never turns a zero-damage event into a real one")

# The negative control that matters: COMBAT damage must NOT be bonused. Void
# Gate says "spells and abilities", and combat damage travels a different path
# (`_assign` writes P_DMG directly) -- which is exactly why the hook went into
# `mark_damage` and not into a shared helper.
#
# A 3-Might attacker into a 5-Might defender leaves 3 marked, not 4. Asserted
# against a plain battlefield as a control so that "3" cannot mean the damage
# step silently did nothing.
def combat_marks(bf_name):
    """(damage marked on the defender, the attacker's effective Might)."""
    s = fresh(runes=0)
    s.bf_card[0] = T.id_of(bf_name)
    a = s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
    d = s.add_permanent(BIG, 1, bf_loc(0), is_unit=True)    # survives the hit
    s.showdown_bf = 0
    s.attacker = 0
    # Against EFFECTIVE Might, not the printed number: PLAIN2 is Daring Poro,
    # which has [Assault 1] and so hits for 3 rather than 2. A control written
    # against the corner number tests the wrong thing and fails honestly.
    pool = combat.might(s, T, a)
    combat._assign(s, T, pool, [d])
    return int(s.perms[d, P_DMG]), pool


_plain_marks, _pool = combat_marks("Rockfall Path")
if _plain_marks != _pool:
    die("void", f"the control is wrong: a {_pool}-Might attacker should mark "
                f"that much, marked {_plain_marks}")
if combat_marks("Void Gate")[0] != _plain_marks:
    die("void", "combat damage must be untouched -- 'spells and abilities' is "
                "not every source of damage, and combat writes P_DMG directly")
ok("...and leaves combat damage alone, which is what 'spells and abilities' means")

# -- Ravenbloom Conservatory: a battlefield watching a COMBAT ROLE, firing once
#    for the DEFENDING PLAYER rather than once per defending unit.
RAVEN = T.id_of("Ravenbloom Conservatory")
SPELL = next(c for c in range(T.n) if T.is_type(c, "Spell"))


def raven(top_is_spell, n_defenders=1):
    s = fresh(runes=0)
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN2
    if top_is_spell:
        s.deck[1, 0] = SPELL
    s.bf_card[0] = RAVEN
    for _ in range(n_defenders):
        s.add_permanent(PLAIN2, 1, bf_loc(0), is_unit=True)
    s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
    hand0, deck0 = int(s.n_hand[1]), int(s.deck_ptr[1])
    combat.open_showdown(s, T, 0, 0)          # seat 0 attacks, so seat 1 defends
    queued = int(s.n_trig)
    A._settle(s, T, V1)
    for _ in range(30):
        if s.n_chain == 0 and s.n_trig == 0 and s.pend_look < 0 \
                and s.pend_slot < 0:
            break
        who = A.acting_seat(s)
        if who < 0:
            break
        legal = A.legal_actions(s, T, V1, who)
        if not legal:
            die("raven", "seat to act with no legal action")
        a = next((x for x in legal if x.kind in (A.A_PICK, A.A_PICK_NONE)),
                 next((x for x in legal if x.kind == A.A_PASS), legal[0]))
        A.apply(s, T, V1, a)
    return (int(s.n_hand[1]) - hand0, int(s.deck_ptr[1]) - deck0, queued)


got = raven(top_is_spell=True)
if got[:2] != (1, 1):
    die("raven", f"a spell on top goes to HAND; got hand {got[0]}, deck {got[1]}")
ok("Ravenbloom: defending reveals the top card, and a spell goes to hand")

got = raven(top_is_spell=False)
if got[:2] != (0, 1):
    die("raven", f"anything else is RECYCLED, not kept; got hand {got[0]}")
ok("...and anything else is recycled instead, with no choice either way")

# Once for the PLAYER, not once per defending unit -- the same rule the conquer
# and hold sites follow, and invisible in a test with one defender.
one = raven(top_is_spell=True, n_defenders=1)[2]
two = raven(top_is_spell=True, n_defenders=3)[2]
if one != two:
    die("raven", f"'when YOU defend here' fired {one} time with one defender "
                 f"and {two} with three; a battlefield fires once for the "
                 f"player, however many units are standing there")
ok("...and fires once for the defending player, not once per defending unit")

# -- Targon's Peak: the pool's only DELAYED effect.
s = fresh(runes=0)
s.bf_card[0] = T.id_of("Targon's Peak")
s.runes_spent[0, 0] = 4
s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
combat._establish_control(s, T, V1, 0)
A._settle(s, T, V1)
drain_all(s)
if int(s.total_ready_runes(0)) != 0:
    die("targon", "'at the end of THIS turn' -- the runes must NOT ready now; "
                  "readying immediately refunds the wrong turn")
if int(s.pending_ready_runes[0]) != 2:
    die("targon", "the promise must be banked where it can be seen")
ok("Targon's Peak banks the refund instead of paying it immediately")

phases.ending(s)
if int(s.total_ready_runes(0)) != 2 or int(s.pending_ready_runes[0]) != 0:
    die("targon", "the end of the turn pays it out, once, and clears it")
ok("...and the end of the turn pays it out exactly once")

# It must be visible: a promise the policy cannot see is a card that does
# nothing until the runes silently appear.
_a = fresh(runes=0)
_b = _a.clone()
_b.pending_ready_runes[0] = 2
_enc = Encoder(T, V1)
if _enc.encode(_a, 0, A.legal_actions(_a, T, V1, 0)).public_bytes() == \
        _enc.encode(_b, 0, A.legal_actions(_b, T, V1, 0)).public_bytes():
    die("targon", "banked runes must reach the observation -- they change what "
                  "tapping out costs, which is the decision runes drive")
ok("...and the banked refund is visible to the policy")


# ---------------------------------------------------------------------------
print("\n[25] 315.2 -- the Beginning STEP finishes before the Scoring STEP")
# The bug this pins was silent for a long time and is not a card bug. 315.2.a
# (start-of-phase effects) and 315.2.b (Scoring) are SEPARATE STEPS, so a
# trigger from the first must fully resolve -- through real priority windows --
# before anything Holds. `start_turn` ran both without stopping and drained the
# trigger queue afterwards, putting every start-of-Beginning ability AFTER the
# scoring it is printed to precede. The comment in `phases.py` claimed the
# opposite, which is why nothing caught it: the triggers were QUEUED before
# scoring and RESOLVED after.
LAB = T.id_of("Dusk Rose Lab")


def dusk(accept, n_units):
    """Returns (cards drawn, units left here, points gained)."""
    s = fresh(runes=0)
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN2
    s.bf_card[0] = LAB
    s.bf_ctrl[0] = 0
    for _ in range(n_units):
        s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
    h0, pts0 = int(s.n_hand[0]), int(s.points[0])
    phases.start_turn(s, T, V1)
    A._settle(s, T, V1)
    want = A.A_ACCEPT if accept else A.A_DECLINE
    for _ in range(30):
        seat = A.acting_seat(s)
        if seat < 0:
            break
        legal = A.legal_actions(s, T, V1, seat)
        if not legal:
            die("dusk", "seat to act with no legal action mid-Beginning-Phase")
        a = next((x for x in legal if x.kind == want),
                 next((x for x in legal if x.kind == A.A_TARGET),
                      next((x for x in legal if x.kind == A.A_PASS), None)))
        if a is None:
            break
        A.apply(s, T, V1, a)
        if int(s.pend_phase) < 0 and int(s.phase) == MAIN:
            break
    return (int(s.n_hand[0]) - h0, len(s.units_at(bf_loc(0), 0)),
            int(s.points[0]) - pts0)


# The turn must actually suspend, or the rest of this is measuring nothing.
_s = fresh(runes=0)
_s.n_deck[:] = 20
_s.deck[:, :20] = PLAIN2
_s.bf_card[0] = LAB
_s.bf_ctrl[0] = 0
_s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
phases.start_turn(_s, T, V1)
if int(_s.pend_phase) < 0:
    die("dusk", "a Beginning-Step trigger must SUSPEND the turn; running "
                "straight to the Scoring Step is the bug itself")
if int(_s.points[0]):
    die("dusk", "nothing may Hold while the Beginning Step is unfinished")
ok("a Beginning-Step trigger suspends the turn before the Scoring Step")

# Everything below is measured AGAINST THE DECLINE CONTROL rather than against
# absolute numbers. The turn resumes all the way into the Draw Step, so every
# case draws one card that has nothing to do with this battlefield; comparing
# to the control subtracts it, and cannot drift if the phase order changes
# again.
_dec1 = dusk(accept=False, n_units=1)
_dec2 = dusk(accept=False, n_units=2)
if _dec1[2] != 1 or _dec1[1] != 1:
    die("dusk", f"the control is wrong: declining must keep the unit and the "
                f"Hold, got {_dec1}")
ok("declining keeps the unit and the Hold -- the control the rest measures from")

# The trade, and the whole card. Killing your ONLY unit there costs the Hold:
# 190.4.c, and `control_cleanup` runs before `score_holds`.
_acc1 = dusk(accept=True, n_units=1)
if _acc1[0] != _dec1[0] + 1:
    die("dusk", f"accepting must draw exactly one more than declining; "
                f"{_acc1[0]} vs {_dec1[0]}")
if _acc1[1] != 0 or _acc1[2] != 0:
    die("dusk", f"killing your only unit here must empty the battlefield AND "
                f"cost the Hold; got {_acc1[1]} unit(s) and {_acc1[2]} point(s)")
ok("...so killing your last unit here draws a card and loses the point")

# ...and with a spare unit the battlefield is still garrisoned, so you get both.
_acc2 = dusk(accept=True, n_units=2)
if _acc2[0] != _dec2[0] + 1 or _acc2[1] != 1 or _acc2[2] != 1:
    die("dusk", f"with a spare unit the Hold survives; got {_acc2}")
ok("...while a spare unit keeps the Hold, which is what makes it a decision")

# The suspend must not leak: a turn that suspends has to reach Main.
_s = fresh(runes=0)
_s.n_deck[:] = 20
_s.deck[:, :20] = PLAIN2
_s.bf_card[0] = LAB
_s.bf_ctrl[0] = 0
_s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
phases.start_turn(_s, T, V1)
A._settle(_s, T, V1)
for _ in range(30):
    if int(_s.pend_phase) < 0:
        break
    seat = A.acting_seat(_s)
    if seat < 0:
        die("dusk", "the turn suspended and then nobody could act -- a "
                    "deadlock, which is what an unresumed phase looks like")
    legal = A.legal_actions(_s, T, V1, seat)
    if not legal:
        die("dusk", "suspended mid-phase with no legal action")
    A.apply(_s, T, V1, next((x for x in legal if x.kind == A.A_DECLINE), legal[0]))
if int(_s.pend_phase) >= 0 or int(_s.phase) != MAIN:
    die("dusk", f"a suspended turn must resume all the way to Main; ended in "
                f"phase {int(_s.phase)} with pend_phase {int(_s.pend_phase)}")
ok("a suspended turn always resumes, through Channel and Draw, into Main")


# ---------------------------------------------------------------------------
print("\n[26] a watcher states which SIDE of an event it wants")

# `fire_watchers` used to be called for the dying unit's controller alone, so
# "when an ENEMY unit dies" had no firing site at all. A death now fires for
# both seats and each watcher matches on the subject's side -- which means the
# default (`subject_enemy=False`) has to keep meaning "friendly", or every
# existing death watcher would double.
from rl.engine.state import P_CTRL
from rl.engine.effects import TR_BEGINNING

PYKE = T.id_of("Pyke - Returned")        # once/turn, an ENEMY unit dies -> Gold
VIKTOR = T.id_of("Viktor - Leader")      # another FRIENDLY non-Recruit dies
GOLD = T.id_of("Gold // Buff")


def golds(s, seat=0):
    return sum(1 for i in range(s.n_perms)
               if int(s.perms[i, P_CARD]) == GOLD
               and s.perms[i, P_ALIVE] == 1
               and int(s.perms[i, P_CTRL]) == seat)


def pyke_board(loc, victim_seat):
    s = fresh(hand=[])
    s.add_permanent(PYKE, 0, loc, is_unit=True)
    victim = s.add_permanent(PLAIN2, victim_seat, bf_loc(0), is_unit=True)
    return s, victim


s, victim = pyke_board(bf_loc(0), victim_seat=1)
combat.destroy(s, T, victim)
drain_all(s)
if golds(s) != 1:
    die("enemy death", f"an enemy death must pay Pyke once, got {golds(s)}")
ok("'when an ENEMY unit dies' fires from the other seat's death")

s, victim = pyke_board(bf_loc(0), victim_seat=0)
combat.destroy(s, T, victim)
drain_all(s)
if golds(s):
    die("enemy death", "a FRIENDLY death fired an enemy-only watcher")
ok("...and never for one of your own, which is a different card")

# "While I'm at a battlefield" is about PYKE, not about where the enemy died.
s, victim = pyke_board(base_loc(0), victim_seat=1)
combat.destroy(s, T, victim)
drain_all(s)
if golds(s):
    die("enemy death", "Pyke in a base must collect nothing")
ok("...and only while HE is at a battlefield, wherever the death happened")

# "Once each turn", and the stamp must be spent only on an event he wanted:
# a friendly death first, an enemy death second, and he must still be paid.
s = fresh(hand=[])
s.add_permanent(PYKE, 0, bf_loc(0), is_unit=True)
mine = s.add_permanent(PLAIN2, 0, bf_loc(0), is_unit=True)
theirs = s.add_permanent(PLAIN2, 1, bf_loc(0), is_unit=True)
combat.destroy(s, T, mine)
drain_all(s)
combat.destroy(s, T, theirs)
drain_all(s)
if golds(s) != 1:
    die("once each turn", "a friendly death spent the turn's one use of an "
                          "ability that never wanted it")
ok("...and the once-per-turn stamp is spent only by a matching event")

# Two enemy deaths in one turn pay once.
s = fresh(hand=[])
s.add_permanent(PYKE, 0, bf_loc(0), is_unit=True)
a = s.add_permanent(PLAIN2, 1, bf_loc(0), is_unit=True)
b = s.add_permanent(PLAIN2, 1, bf_loc(0), is_unit=True)
combat.destroy(s, T, a)
drain_all(s)
combat.destroy(s, T, b)
drain_all(s)
if golds(s) != 1:
    die("once each turn", f"two enemy deaths paid {golds(s)} times, not once")
ok("...while a second enemy death in the same turn pays nothing")

# The control: an existing friendly-death watcher must be unaffected by the
# extra firing pass, and must not fire on an enemy death either.
RECRUIT_TOK = T.id_of("Recruit (271) // Buff")


def viktor_sees(victim_seat):
    """Recruits Viktor makes when a unit of `victim_seat` dies."""
    s = fresh(hand=[])
    s.add_permanent(VIKTOR, 0, bf_loc(0), is_unit=True)
    victim = s.add_permanent(PLAIN2, victim_seat, bf_loc(0), is_unit=True)
    combat.destroy(s, T, victim)
    drain_all(s)
    return sum(1 for i in range(s.n_perms)
               if int(s.perms[i, P_CARD]) == RECRUIT_TOK
               and s.perms[i, P_ALIVE] == 1)


if viktor_sees(0) != 1:
    die("friendly death", "a friendly-death watcher stopped firing, or fired "
                          "twice now that the death fires for both seats")
if viktor_sees(1):
    die("friendly death", "a friendly-death watcher fired on an enemy death "
                          "-- the default side must still be 'friendly'")
ok("...and a friendly-death watcher still fires once, on friends only")


# ---------------------------------------------------------------------------
print("\n[27] a play watcher can name the KIN it watches for")

GEM = T.id_of("Gentle Gemdragon")        # play me OR another Dragon -> ready 2
DRAGON = next(c for c in range(T.n) if T.is_type(c, "Unit")
              and "Dragon" in T.tags[c] and c != GEM and not T.is_token(c)
              and int(T.energy[c]) <= 4)


def spent_after(played, with_gem):
    """Exhausted runes left after seat 0 plays `played`.

    Measured against the SAME play without a Gemdragon on the board, because
    the play itself exhausts runes and the two numbers only mean something
    against each other.
    """
    s = fresh(hand=[played], runes=6)
    s.runes_spent[0, 0] = 4
    if with_gem:
        s.add_permanent(GEM, 0, base_loc(0), is_unit=True)
    play(s, V1, 0, base_loc(0))
    drain_all(s)
    return int(s.runes_spent[0].sum())


if spent_after(DRAGON, False) - spent_after(DRAGON, True) != 2:
    die("kin", "another Dragon must wake the Gemdragon and ready 2 runes")
ok("'or another Dragon' fires on a play of the kin it names")

if spent_after(PLAIN2, False) - spent_after(PLAIN2, True) != 0:
    die("kin", "a non-Dragon fired a Dragon watcher")
ok("...and on nothing else, which is what the tag restriction is for")

# Her own arrival is TR_PLAY_ME. The watcher would ALSO see it -- one play, two
# abilities reading the same sentence -- and `subject_not_self` is what makes
# the card pay once. Counted as abilities put in flight, since the two would be
# indistinguishable in runes.
s = fresh(hand=[GEM], runes=6)
s.runes_spent[0, 0] = 4
play(s, V1, 0, base_loc(0))
in_flight = int(s.n_chain) + int(s.n_trig)
if in_flight != 1:
    die("kin", f"playing her put {in_flight} abilities in flight, not 1 -- "
               f"'me OR another Dragon' is one payout for one play")
paid = int(s.runes_spent[0].sum())      # her own cost is already exhausted
drain_all(s)
if paid - int(s.runes_spent[0].sum()) != 2:
    die("kin", "her own arrival readies 2, the same as any other Dragon's")
ok("...and her own arrival pays once, not once per reading of the sentence")


# ---------------------------------------------------------------------------
print("\n[28] snapshots: what was true when it happened")

# "[Deathknell] If I was [Mighty], draw 2." 740.2 makes Mighty 5+ EFFECTIVE
# Might, so a combat trick supplies it -- and expires while the Deathknell is
# still waiting on the Chain. The answer has to be taken as he dies.
HERO = T.id_of("Unsung Hero")


def unsung(bonus):
    s = fresh(hand=[])
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN2
    row = s.add_permanent(HERO, 0, bf_loc(0), is_unit=True)
    if bonus:
        combat.set_might_mod(s, T, row, bonus)
    before = int(s.n_hand[0])
    combat.destroy(s, T, row)
    chain.place(s, T, V1, 0)          # flush the queue onto the Chain (808)
    drain(s, V1)
    return int(s.n_hand[0]) - before


need = 5 - int(T.might[HERO])
if unsung(0) != 0:
    die("was mighty", "a body under 5 Might is not Mighty and draws nothing")
ok("Unsung Hero below 5 Might draws nothing")

if unsung(need) != 2:
    die("was mighty", "5+ EFFECTIVE Might is Mighty (740.2) -- a buff counts")
ok("...and a BUFF to 5 Might makes him Mighty, read as he dies")


# "If you control fewer runes than an opponent at the start of your Beginning
# Phase." A comparison between two boards, not a threshold.
BACCAI = T.id_of("Forsaken Baccai")


def baccai(mine, theirs):
    s = fresh(hand=[])
    s.runes_ready[:, :] = 0
    s.runes_ready[0, 0] = mine
    s.runes_ready[1, 0] = theirs
    row = s.add_permanent(BACCAI, 0, base_loc(0), is_unit=True)
    before = combat.might(s, T, row)
    chain_mod.fire_watchers(s, T, 0, TR_BEGINNING)
    drain_all(s)
    return combat.might(s, T, row) - before


if baccai(mine=2, theirs=5) != 1:
    die("fewer runes", "behind on runes, the catch-up clause pays")
ok("'fewer runes than an opponent' pays while you are behind")

if baccai(mine=5, theirs=5) != 0:
    die("fewer runes", "level on runes is not FEWER -- the clause is strict")
ok("...and stops the moment the counts level, unlike a fixed threshold")


# ---------------------------------------------------------------------------
print("\n[29] two more transcriptions, each on machinery already here")

# Fretful Feline: "when I become ready" is the same TR_READIED that Awaken
# fires, narrowed to herself.
FELINE = T.id_of("Fretful Feline")
before, after = after_awaken(FELINE, ready=False)
if after != before + 2:
    die("feline", "an exhausted Feline wakes up +2")
before, after = after_awaken(FELINE, ready=True)
if after != before:
    die("feline", "a unit already ready has not BECOME ready")
ok("Fretful Feline grows on the transition, not on the flag")

# Corina Veraza: "when I move TO a battlefield, play three Recruits HERE" --
# `here` is where she arrived (T_CTX2), and a retreat to base fires nothing.
CORINA = T.id_of("Corina Veraza")
RECRUIT = T.id_of("Recruit (271) // Buff")


def corina_to(dest, start):
    s = fresh(hand=[])
    row = s.add_permanent(CORINA, 0, start, is_unit=True)
    s.bf_ctrl[:] = -1
    A.apply(s, T, V1, A.Action(A.A_DECLARE, dest))
    A.apply(s, T, V1, A.Action(A.A_ADD, row))
    A.apply(s, T, V1, A.Action(A.A_COMMIT))
    drain_all(s)
    return s, [i for i in range(s.n_perms)
               if int(s.perms[i, P_CARD]) == RECRUIT
               and s.perms[i, P_ALIVE] == 1]


st, made = corina_to(bf_loc(0), base_loc(0))
if len(made) != 3:
    die("corina", f"expected 3 Recruits on arrival, got {len(made)}")
if any(int(st.perms[i, P_LOC]) != bf_loc(0) for i in made):
    die("corina", "'here' on a move trigger is where she ARRIVED (T_CTX2), "
                  "not the base she left")
ok("Corina's three Recruits arrive with her, at the battlefield she moved to")

st, made = corina_to(base_loc(0), bf_loc(0))
if made:
    die("corina", "a retreat to base is not a move TO A BATTLEFIELD")
ok("...and a retreat to base makes none, which is the printed condition")

# Sona: "at the end of your turn, IF I'M AT A BATTLEFIELD, ready up to 4
# friendly runes." Holding ground is the price of the refund.
#
# Driven through the real A_END_TURN, because the interesting half is the
# PHASE, not the card: 317's triggers need a priority window, and `end_turn`
# runs straight into `compact_permanents`, which refuses to run with a trigger
# still queued. The Ending Phase therefore suspends the same way the Beginning
# Phase does. Until this landed, TR_END_OF_TURN had no firing site anywhere and
# both cards that use it were quietly dead.
SONA = T.id_of("Sona, Harmonious")


def sona_at(loc):
    s = fresh(hand=[])
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN2
    s.runes_spent[0, 0] = 4
    s.add_permanent(SONA, 0, loc, is_unit=True)
    A.apply(s, T, V1, A.Action(A.A_END_TURN, 0))
    drain_all(s)
    return 4 - int(s.runes_spent[0].sum())


if sona_at(bf_loc(0)) != 4:
    die("sona", "at a battlefield she readies 4 at the end of your turn")
ok("Sona refunds four runes, fired by the Ending Phase itself")

if sona_at(base_loc(0)) != 0:
    die("sona", "back at base the condition fails and nothing is readied")
ok("...and only while she is at a battlefield, which is what she costs")

# The turn must still END. A suspension that never resumes is a deadlock, and
# it looks exactly like a card that did nothing.
s = fresh(hand=[])
s.n_deck[:] = 20
s.deck[:, :20] = PLAIN2
s.runes_spent[0, 0] = 4
s.add_permanent(SONA, 0, bf_loc(0), is_unit=True)
A.apply(s, T, V1, A.Action(A.A_END_TURN, 0))
drain_all(s)
if int(s.pend_phase) >= 0:
    die("sona", "the Ending Phase suspended and never resumed")
if int(s.active) != 1 or int(s.phase) != MAIN:
    die("sona", f"the turn did not pass: active={int(s.active)} "
                f"phase={int(s.phase)}")
ok("...and the turn resumes through the cleanup and passes to the opponent")

# The legend half of the same trigger: "at the end of your turn, ready 2
# runes" is printed on Annie - Dark Child, who has no `perms` row at all.
ANNIE = T.id_of("Annie - Dark Child")
s = fresh(hand=[])
s.n_deck[:] = 20
s.deck[:, :20] = PLAIN2
s.legend[0] = ANNIE
s.runes_spent[0, 0] = 4
A.apply(s, T, V1, A.Action(A.A_END_TURN, 0))
drain_all(s)
if 4 - int(s.runes_spent[0].sum()) != 2:
    die("annie", "a LEGEND's end-of-turn ability fires too -- it has no row "
                 "to walk, so it is asked separately")
ok("...and a legend's end-of-turn ability fires from the same step")


# ---------------------------------------------------------------------------
print("\n[30] a printed OPTIONAL ADDITIONAL COST, and the clause it buys")

# 805.2 -- an Optional Additional Cost is paid as the card is played, so it
# belongs to the destination decision rather than a later one; `A_PLAY_AT_FAST`
# already carried [Accelerate] and now carries these six too. What differs is
# what paying BUYS: [Accelerate] buys entering ready (805.6), a printed cost
# buys a clause in the card's own text.
from rl.config import DOMAINS as _DOMAINS
DOM_BODY = _DOMAINS.index("Body")

KEEPER = T.id_of("Clockwork Keeper")     # {Calm rune} -> draw 1
PYKE_D = T.id_of("Pyke - Dockside Butcher")   # {Fury rune} -> ready me, +2


def play_paying(card, pay, runes=6):
    s = fresh(hand=[card], runes=runes)
    s.n_deck[:] = 20
    s.deck[:, :20] = PLAIN2
    A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
    kind = A.A_PLAY_AT_FAST if pay else A.A_PLAY_AT
    legal = A.legal_actions(s, T, V1, A.acting_seat(s))
    act = next((a for a in legal if a.kind == kind and a.arg == base_loc(0)),
               None)
    if act is None:
        die("add cost", f"{T.names[card]!r} was not offered "
                        f"{'the paid' if pay else 'the plain'} play")
    A.apply(s, T, V1, act)
    drain_all(s)
    row = next(i for i in range(s.n_perms)
               if int(s.perms[i, P_CARD]) == card and s.perms[i, P_ALIVE] == 1)
    return s, row


s, _ = play_paying(KEEPER, pay=True)
if int(s.n_hand[0]) != 1:
    die("add cost", f"paying {{Calm rune}} draws 1; hand is {int(s.n_hand[0])}")
ok("paying the printed additional cost turns its clause on")

s, _ = play_paying(KEEPER, pay=False)
if int(s.n_hand[0]) != 0:
    die("add cost", "declining must draw nothing -- the clause is conditional")
ok("...and declining plays the same card without it")

# The runes: the paid play really costs more. Measured against the plain play
# of the same card, because the card's own cost is in both numbers -- and
# measured on the rune BOARD, not on what is exhausted: {Calm rune} is Power,
# and Power is paid by RECYCLING a rune to the bottom of the Rune Deck
# (416.1.b). The cost shows up as a smaller board, not as a spent column.
def board(st):
    return int(st.runes_ready[0].sum() + st.runes_spent[0].sum())


paid, _ = play_paying(KEEPER, pay=True)
free, _ = play_paying(KEEPER, pay=False)
if board(paid) != board(free) - 1:
    die("add cost", f"a Power cost costs a rune off the board: paid "
                    f"{board(paid)} vs plain {board(free)}")
ok("...and it is a real cost -- one rune of attrition, not a free rider")

# A printed cost must NOT make the unit enter ready -- that is [Accelerate]'s
# payload and conflating the two would hand six units haste they never printed.
s, row = play_paying(PYKE_D, pay=False)
if s.perms[row, P_READY]:
    die("add cost", "359.2.c -- a unit enters exhausted")
s, row = play_paying(PYKE_D, pay=True)
if not s.perms[row, P_READY]:
    die("add cost", "Pyke's OWN clause readies him -- 'ready me and +2 Might'")
if combat.might(s, T, row) != int(T.might[PYKE_D]) + 2:
    die("add cost", "...and the second half of the same clause is the +2")
ok("Pyke's readying is his printed clause, not [Accelerate]'s replacement")

# Unaffordable means not offered: 355.8's cousin for costs. Energy is generic
# (163.1.a) so any two runes pay the card itself, but {Calm rune} is Power and
# 163.2 binds it to its domain -- with no Calm rune on the board there is
# nothing to recycle for it.
s = fresh(hand=[KEEPER], runes=0)
s.runes_ready[0, DOM_BODY] = 3
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
kinds = {a.kind for a in A.legal_actions(s, T, V1, A.acting_seat(s))}
if A.A_PLAY_AT_FAST in kinds:
    die("add cost", "an unaffordable additional cost must not be offered")
if A.A_PLAY_AT not in kinds:
    die("add cost", "...while the card itself is still perfectly playable")
ok("an unaffordable additional cost is not offered, and the card still is")


# ---------------------------------------------------------------------------
print("\n[leaves the board] Treasure Trove -- wider than [Deathknell]")
# "When this leaves the board, draw 1 and channel 1 rune exhausted."
# "{Chaos rune}, Exhaust: Kill this."
#
# The point of the card is that it is NOT a Deathknell. A Deathknell is denied
# by a Banish (427.2.a -- "Banish is not a subset of Kill") and by a bounce;
# "leaves the board" is denied by neither, so all three exits pay out.
from rl.engine.effects import (CardSpec as _CS, Op as _Op, TargetSpec as _TS,
                               OP_RETURN_TO_HAND as _OP_BOUNCE,
                               SPEED_MAIN as _SPEED_MAIN, W_ANY as _W_ANY)
from rl.engine import resolve as _rsv
from rl.engine.state import bf_loc as _bf_loc

_TROVE = T.id_of("Treasure Trove")
_BOUNCE = _CS(speed=_SPEED_MAIN,
              targets=(_TS(who=_W_ANY, card_type=("Gear",)),),
              ops=(_Op(_OP_BOUNCE, target=0),))


def _trove_on_board():
    st = fresh()
    st.rune_deck[0, :12] = 2          # a full Chaos rune deck to channel from
    st.rune_left[0] = 12
    return st, st.add_permanent(_TROVE, 0, _bf_loc(0))


def _drain(st):
    for _ in range(10):
        if int(st.n_trig):
            chain.place(st, T, V1, 0)
        elif int(st.n_chain):
            chain.finalize(st, 0)
            chain.resolve_top(st, T, V1)
        else:
            break


for _label, _exit in (("killed", "kill"), ("banished", "banish"),
                      ("bounced", "bounce")):
    _s, _row = _trove_on_board()
    _h0 = int(_s.n_hand[0])
    _r0 = int(_s.runes_ready[0].sum() + _s.runes_spent[0].sum())
    if _exit == "kill":
        _combat.destroy(_s, T, _row)
    elif _exit == "banish":
        _combat.banish(_s, T, _row)
    else:
        _rsv.resolve(_s, T, V1, _BOUNCE, 0, [_row], -1, False)
    _drain(_s)
    if _s.perms[_row, P_ALIVE]:
        die("leaves", f"the {_label} gear is still on the board")
    # A bounce also puts the card itself back in hand, so the draw is +1 on top.
    _want_draw = 2 if _exit == "bounce" else 1
    if int(_s.n_hand[0]) - _h0 != _want_draw:
        die("leaves", f"a {_label} Treasure Trove must still draw 1 "
                      f"(hand moved {int(_s.n_hand[0]) - _h0}, "
                      f"expected {_want_draw})")
    if int(_s.runes_ready[0].sum() + _s.runes_spent[0].sum()) - _r0 != 1:
        die("leaves", f"a {_label} Treasure Trove must still channel 1")
ok("kill, banish AND bounce each pay out -- 427.2.a cannot deny this one")

# The activated half: {Chaos rune}, Exhaust: Kill this -- which then triggers
# the half above, so the card cashes itself in.
_s, _row = _trove_on_board()
_s.runes_ready[:, :] = 0
_s.runes_ready[0, 2] = 2                       # Chaos only
if not [a for a in A.legal_actions(_s, T, V1, 0) if a.kind == A.A_ACTIVATE]:
    die("leaves", "with a Chaos rune ready the ability must be offered")
_s2, _row2 = _trove_on_board()
_s2.runes_ready[:, :] = 0                      # no runes at all
if [a for a in A.legal_actions(_s2, T, V1, 0) if a.kind == A.A_ACTIVATE]:
    die("leaves", "{Chaos rune} is a real cost -- unaffordable means unoffered")
ok("...and its activated ability costs a Chaos rune, checked before it is offered")


# ---------------------------------------------------------------------------
print("\n[combat ends] Mournful Witness -- and only a COMBAT counts")
# "When a combat that I was in ends, empower me.  [Empowered][>] I have +2
# Might." 344.2 opens a NON-Combat Showdown that closes through the same code,
# and a card that says "combat" must not be paid by one.
from rl.engine.state import F_EMPOWERED as _F_EMP2, SD_PRIORITY as _SD_PRI

_MW = T.id_of("Mournful Witness")


def _witness(bf=0, at=0):
    st = fresh()
    row = st.add_permanent(_MW, 0, bf_loc(at))
    st.showdown_bf = bf
    st.attacker = 1
    st.showdown_step = _SD_PRI
    return st, row


def _drain2(st):
    for _ in range(12):
        if int(st.n_trig):
            chain.place(st, T, V1, 0)
        elif int(st.n_chain):
            chain.finalize(st, 0)
            chain.resolve_top(st, T, V1)
        else:
            break


# A Combat that she was in.
_s, _w = _witness()
_s.showdown_combat = 1
_combat.advance_combat(_s, T, V1)
_drain2(_s)
if not _s.has_flag(_w, _F_EMP2):
    die("witness", "a Combat she was in ended and did not Empower her")
if _combat.might(_s, T, _w) != int(T.might[_MW]) + 2:
    die("witness", "the Empowered clause is +2 Might")
ok("a Combat she was in ends: Empowered, and +2 Might follows the status")

# A NON-Combat Showdown (344.2) closing through the same code must not.
_s, _w = _witness()
_s.showdown_combat = 0
_combat.advance_combat(_s, T, V1)
_drain2(_s)
if _s.has_flag(_w, _F_EMP2):
    die("witness", "344.2's Non-Combat Showdown is not a combat, and this "
                   "card says combat")
ok("...but a Non-Combat Showdown closing the same way does not")

# "That I was in" -- a witness standing at the OTHER battlefield is not in it.
_s, _w = _witness(bf=0, at=1)
_s.showdown_combat = 1
_combat.queue_combat_ends(_s, T, 0)
if int(_s.n_trig):
    die("witness", "a unit at a different battlefield was not in this combat")
ok("...and a witness at another battlefield was not in it")


# ---------------------------------------------------------------------------
print("\n[Blitzcrank - Impassive] a trigger NARROWED to a battlefield play")
# "[Tank] When you play me to a battlefield, you may move an enemy unit to
# here.  When I hold, return me to my owner's hand."
#
# `at_battlefield` narrows the TRIGGER (359.3.f) where Mischievous Marai gates
# the OP with COND_SELF_AT_BF. The difference is the "you MAY": Marai's ability
# is not optional, so firing and fizzling on a base play costs nothing, while
# this one would open a question the player cannot act on.
from rl.engine.effects import TR_HOLD as _TR_HOLD, TR_PLAY_ME as _TR_PLAY_ME

_BC = T.id_of("Blitzcrank - Impassive")
_ENEMY_UNIT = T.id_of("First Mate")

_s = fresh()
_b = _s.add_permanent(_BC, 0, bf_loc(0))
_foe = _s.add_permanent(_ENEMY_UNIT, 1, base_loc(1))
if chain.fire(_s, T, V1, _TR_PLAY_ME, _b) != 1:
    die("blitz", "played to a battlefield, the play trigger must fire")
A._advance_pending(_s, T, V1)
if {a.kind for a in A.legal_actions(_s, T, V1, 0)} != {A.A_ACCEPT, A.A_DECLINE}:
    die("blitz", "383.3.a -- 'you may' is accepted or declined at finalization")
A.apply(_s, T, V1, A.Action(A.A_ACCEPT))
A.apply(_s, T, V1, A.Action(A.A_TARGET, _foe))
for _ in range(6):
    _st = A.acting_seat(_s)
    if _st < 0 or (not _s.n_chain and not _s.n_trig):
        break
    A.apply(_s, T, V1, A.legal_actions(_s, T, V1, _st)[0])
if int(_s.perms[_foe, P_LOC]) != bf_loc(0):
    die("blitz", "the enemy unit is dragged to where Blitzcrank landed")
ok("played to a battlefield: the 'you may' opens and drags an enemy here")

# Played to a BASE the trigger must not fire AT ALL -- not fire and fizzle.
_s2 = fresh()
_b2 = _s2.add_permanent(_BC, 0, base_loc(0))
_s2.add_permanent(_ENEMY_UNIT, 1, base_loc(1))
if chain.fire(_s2, T, V1, _TR_PLAY_ME, _b2):
    die("blitz", "a base play must not reach the Chain at all -- an optional "
                 "ability that fires and fizzles asks a meaningless question")
ok("...and a base play never reaches the Chain, so no empty 'you may'")

# "When I hold, return me to my owner's hand" -- a drawback, not an upside.
_s3 = fresh()
_b3 = _s3.add_permanent(_BC, 0, bf_loc(0))
_hand = int(_s3.n_hand[0])
chain.fire(_s3, T, V1, _TR_HOLD, _b3)
for _ in range(8):
    _st = A.acting_seat(_s3)
    if _st < 0 or (not _s3.n_chain and not _s3.n_trig):
        break
    A.apply(_s3, T, V1, A.legal_actions(_s3, T, V1, _st)[0])
if _s3.perms[_b3, P_ALIVE]:
    die("blitz", "holding returns him to hand, so he leaves the board")
if int(_s3.n_hand[0]) != _hand + 1:
    die("blitz", "...and lands in his OWNER's hand")
ok("...and holding a battlefield bounces him back to hand")


# ---------------------------------------------------------------------------
print("\n[Undertitan] 'other' units, and a trigger from the LOOK BUFFER")
# "When you play me, give your other units +2 Might this turn.
#  As I'm revealed from your deck, [Add] {2 energy}."
from rl.engine.effects import (CardSpec as _CS2, Op as _Op2, OP_LOOK_TOP as _OP_LOOK,
                               SPEED_MAIN as _SM2, TR_PLAY_ME as _TR_PM)
from rl.engine import resolve as _rsv2

_UT = T.id_of("Undertitan")
_OTHER = T.id_of("First Mate")

_s = fresh()
_u = _s.add_permanent(_UT, 0, bf_loc(0))
_ally = _s.add_permanent(_OTHER, 0, bf_loc(0))
_foe = _s.add_permanent(_OTHER, 1, bf_loc(0))
chain.fire(_s, T, V1, _TR_PM, _u)
for _ in range(6):
    _st = A.acting_seat(_s)
    if _st < 0 or (not _s.n_chain and not _s.n_trig):
        break
    A.apply(_s, T, V1, A.legal_actions(_s, T, V1, _st)[0])
if _combat.might(_s, T, _u) != int(T.might[_UT]):
    die("undertitan", "'your OTHER units' must not include himself")
if _combat.might(_s, T, _ally) != int(T.might[_OTHER]) + 2:
    die("undertitan", "a friendly unit gets +2")
if _combat.might(_s, T, _foe) != int(T.might[_OTHER]):
    die("undertitan", "'your' units, never the opponent's")
ok("'your other units' excludes himself and the opponent alike")

# The second clause fires while he is in the LOOK BUFFER -- off the deck, in no
# zone, with no permanent row to hang a Chain Item on.
_s2 = fresh()
_s2.n_deck[0] = 3
_s2.deck[0, :3] = [_UT, _OTHER, _OTHER]
_s2.deck_ptr[0] = 0
_before = int(_s2.pool_energy[0])
from rl.engine.effects import LOOK_REVEAL_ALL as _LRA
_rsv2.resolve(_s2, T, V1, _CS2(speed=_SM2, ops=(_Op2(_OP_LOOK, n=2, reveal=_LRA),)),
              0, [], -1, False)
if int(_s2.pool_energy[0]) != _before + 2:
    die("undertitan", "'as I'm revealed from your deck, [Add] {2 energy}' must "
                      "pay out while he sits in the look buffer")
ok("...and being revealed from the deck adds {2 energy} from the buffer")

# Looking is not revealing (RiftJudge #12051): a plain "look at" pays nothing.
_s2b = fresh()
_s2b.n_deck[0] = 3
_s2b.deck[0, :3] = [_UT, _OTHER, _OTHER]
_s2b.deck_ptr[0] = 0
_rsv2.resolve(_s2b, T, V1, _CS2(speed=_SM2, ops=(_Op2(_OP_LOOK, n=2),)),
              0, [], -1, False)
if int(_s2b.pool_energy[0]):
    die("undertitan", "looking at the top of the deck reveals nothing")
ok("...but merely LOOKING at him adds nothing")

# Not revealed, not paid: a card still under the cut does nothing.
_s3 = fresh()
_s3.n_deck[0] = 3
_s3.deck[0, :3] = [_OTHER, _OTHER, _UT]
_s3.deck_ptr[0] = 0
_before3 = int(_s3.pool_energy[0])
_rsv2.resolve(_s3, T, V1, _CS2(speed=_SM2, ops=(_Op2(_OP_LOOK, n=2),)),
              0, [], -1, False)
if int(_s3.pool_energy[0]) != _before3:
    die("undertitan", "a card deeper than the look does not trigger")
ok("...and a copy deeper in the deck than the look does not")


# ---------------------------------------------------------------------------
print("\n[Nocturne - Horrifying] playing a unit OUT of the look buffer")
# "When you look at cards from the top of your deck (and don't draw them) and
# see me, you may play me for {any rune}."
#
# The third zone a permanent can be played from, and the only one where the
# play happens INSIDE another decision -- the look stays suspended around it.
_NOC = T.id_of("Nocturne - Horrifying")

def _look3(cards, runes=6):
    """A seat mid-look at `cards`, with the buffer already filled."""
    s = fresh(runes=runes)
    s.n_deck[0] = len(cards)
    s.deck[0, :len(cards)] = cards
    s.deck_ptr[0] = 0
    _rsv2.resolve(s, T, V1, _CS2(speed=_SM2, ops=(_Op2(_OP_LOOK, n=len(cards)),)),
                  0, [], -1, False)
    return s

_s = _look3([_NOC, _OTHER, _OTHER])
_acts = A.legal_actions(_s, T, V1, 0)
_offer = [a for a in _acts if a.kind == A.A_PLAY]
if [a.arg for a in _offer] != [0]:
    die("nocturne", "the permission must be offered for HIS buffer slot and no "
                    f"other, got {[a.arg for a in _offer]}")
# The look's own pick is still on the table -- the permission is an EXTRA
# action, not a replacement for the instruction that revealed him.
if not [a for a in _acts if a.kind == A.A_PICK]:
    die("nocturne", "his permission must not displace the look's own pick")
ok("he is offered alongside the look's pick, and only for his own slot")

_in_play = int(_s.runes_in_play(0).sum())
_ring = int(_s.rune_left[0])
A.apply(_s, T, V1, _offer[0])
# A destination choice, exactly as a play from hand gets -- 806.3 is not
# waived, so it is his controller's base or a battlefield they control.
_dsts = A.legal_actions(_s, T, V1, 0)
if not _dsts or {a.kind for a in _dsts} != {A.A_PLAY_AT}:
    die("nocturne", f"a destination must be asked for, got {_dsts}")
A.apply(_s, T, V1, _dsts[0])

_rows = [p for p in range(_s.n_perms)
         if int(_s.perms[p, P_CARD]) == _NOC and _s.perms[p, P_ALIVE]]
if len(_rows) != 1:
    die("nocturne", "he should be on the board exactly once")
# {any rune} is [A] -- POWER, so a rune is RECYCLED (164.2.b), not exhausted.
if int(_s.runes_in_play(0).sum()) != _in_play - 1:
    die("nocturne", "{any rune} must cost a rune off the board, not a tap")
if int(_s.rune_left[0]) != _ring + 1:
    die("nocturne", "the rune he cost belongs back in the Rune Deck (416.1.b)")
# ...and NOT his printed {4 energy}{1 power}: the permission replaces the cost.
if int(_s.runes_ready[0].sum()) < int(_s.runes_in_play(0).sum()) - 1:
    die("nocturne", "he was charged his printed cost on top of [A]")
ok("...and playing him costs one RECYCLED rune, not his printed cost")

# He leaves the buffer, so the look's instruction never reaches him: 2 cards
# left to pick from, and the pick indices have closed up behind him.
if int(_s.n_look) != 2 or _NOC in [int(_s.look_cards[i]) for i in range(2)]:
    die("nocturne", "a played Nocturne must be out of the buffer before the "
                    "look's 'put the rest' reaches it")
_picks = [a.arg for a in A.legal_actions(_s, T, V1, 0) if a.kind == A.A_PICK]
if _picks != [0, 1]:
    die("nocturne", f"the buffer should have compacted, got picks {_picks}")
ok("...and the look resumes over what is left, never over him")

# The look closes out normally afterwards.
A.apply(_s, T, V1, A.Action(A.A_PICK, 0))
if _s.pend_look >= 0 or int(_s.n_look) != 0:
    die("nocturne", "the look must still finish after he is played")
ok("...and the look still lands the rest of the buffer")

# He was the ONLY card seen: the buffer empties on the play, so nothing is left
# to pick and the look has to close itself out rather than pend on nothing.
_s2 = _look3([_NOC])
A.apply(_s2, T, V1, next(a for a in A.legal_actions(_s2, T, V1, 0)
                         if a.kind == A.A_PLAY))
A.apply(_s2, T, V1, A.legal_actions(_s2, T, V1, 0)[0])
if _s2.pend_look >= 0 or _s2.pend_play_look >= 0:
    die("nocturne", "emptying the buffer must close the look, not leave it "
                    "pending on zero cards")
if not A.legal_actions(_s2, T, V1, 0):
    die("nocturne", "the turn must go on once the look is closed")
ok("...and taking the buffer's last card closes the look instead of stalling")

# The offer is a COST, so it is withheld when the cost cannot be paid. A board
# with no runes at all has no Power and nothing to recycle.
_s3 = _look3([_NOC, _OTHER], runes=0)
if [a for a in A.legal_actions(_s3, T, V1, 0) if a.kind == A.A_PLAY]:
    die("nocturne", "with no rune to recycle, [A] is unpayable and the "
                    "permission must not be offered")
ok("...and with no rune on the board the permission is not offered at all")


# ---------------------------------------------------------------------------
print("\n[TR_NTH_CARD] 'your first card each turn', and a promise with no source")
from rl.engine import cost as _cost

_HERON = T.id_of("Astral Heron")
_DARIUS = T.id_of("Darius - Trifarian")
# A cheap spell to spend plays on. Its own text does not matter here; what
# matters is that playing it is a CARD PLAY.
_CHEAP = T.id_of("Stupefy")


def _drain_triggers(s, limit=12):
    for _ in range(limit):
        st = A.acting_seat(s)
        if st < 0 or (not s.n_chain and not s.n_trig):
            return
        A.apply(s, T, V1, A.legal_actions(s, T, V1, st)[0])


# She only watches from a battlefield (359.3.f), so a Heron at base is not a
# Heron that triggers -- and the narrowing is on the TRIGGER, so nothing
# reaches the Chain at all.
_s = fresh(hand=(PLAIN2, PLAIN2))
_s.add_permanent(_HERON, 0, base_loc(0))
play(_s, V1, 0, base_loc(0))
if _s.n_trig or _s.n_chain:
    die("heron", "a Heron at base must not trigger at all")
if int(_s.next_discount[0, 0]) or int(_s.next_discount[0, 1]):
    die("heron", "...and must promise nothing")
ok("'if I'm at a battlefield' keeps a based Heron off the Chain entirely")

_s = fresh(hand=(PLAIN2, PLAIN2))
_s.bf_ctrl[0] = 0
_s.add_permanent(_HERON, 0, bf_loc(0))
play(_s, V1, 0, base_loc(0))          # the FIRST card of the turn
_drain_triggers(_s)
if (int(_s.next_discount[0, 0]), int(_s.next_discount[0, 1])) != (2, 2):
    die("heron", "the first card must promise {2 energy}{any rune}{any rune} "
                 f"less, got {_s.next_discount[0]}")
# 356.4.d -- a discount per COMPONENT, so both halves of the next card's cost
# come down, and neither below zero.
_next = int(_s.hand[0, 0])
if (_cost.effective_energy(_s, T, 0, _next)
        != max(0, int(T.energy[_next]) - 2)):
    die("heron", "the promised Energy discount must reach the next card")
if (_cost.effective_power(_s, T, 0, _next)
        != max(0, int(T.power[_next]) - 2)):
    die("heron", "...and the Power half with it")
ok("the first card of the turn promises a discount the NEXT card collects")

# The promise outlives its source. She is the only cost modification in the
# pool that can: every other one is read off a permanent that has to still be
# standing, and hers is held on the player.
_row = next(p for p in range(_s.n_perms) if int(_s.perms[p, P_CARD]) == _HERON)
_s.perms[_row, P_ALIVE] = 0
if (_cost.effective_energy(_s, T, 0, _next)
        != max(0, int(T.energy[_next]) - 2)):
    die("heron", "the promise is held on the PLAYER, so killing her in "
                 "response must not take the discount back")
ok("...and killing her afterwards does not take it back")

# Spent by the next card PLAYED, exactly once.
_s.perms[_row, P_ALIVE] = 1
play(_s, V1, 0, base_loc(0))
_drain_triggers(_s)
if int(_s.next_discount[0, 0]) or int(_s.next_discount[0, 1]):
    die("heron", "the promise must be spent by the next card, not linger")
ok("...and the next card spends it, leaving nothing for the one after")

# `subject_nth` is an exact match, not a threshold: she promises on the first
# card and stays quiet on the third.
_s2 = fresh(hand=(PLAIN2, PLAIN2, PLAIN2))
_s2.bf_ctrl[0] = 0
_s2.add_permanent(_HERON, 0, bf_loc(0))
for _ in range(3):
    play(_s2, V1, 0, base_loc(0))
    _drain_triggers(_s2)
if int(_s2.next_discount[0, 0]):
    die("heron", "only the FIRST card each turn triggers her, so the third "
                 "must leave no promise standing")
ok("...and only the first card fires her, never the third")

# Darius shares the trigger at a different ordinal -- which is the whole
# reason the number is a field rather than a trigger of its own.
_s3 = fresh(hand=(PLAIN2, PLAIN2))
_d = _s3.add_permanent(_DARIUS, 0, bf_loc(0))
_s3.perms[_d, P_READY] = 0
play(_s3, V1, 0, base_loc(0))
_drain_triggers(_s3)
if int(_s3.perms[_d, P_READY]) == 1:
    die("darius", "his clause is the SECOND card, so the first must not "
                  "ready him")
play(_s3, V1, 0, base_loc(0))
_drain_triggers(_s3)
if int(_s3.perms[_d, P_READY]) != 1:
    die("darius", "the second card readies him")
if combat.might(_s3, T, _d) != int(T.might[_DARIUS]) + 2:
    die("darius", "...and gives him +2 Might this turn")
ok("Darius reads the same trigger at ordinal 2: nothing, then ready and +2")


# ---------------------------------------------------------------------------
print("\n[Brynhir Thundersong] a lock on CARDS, which is wider than spells")
# "When you play me, opponents can't play cards this turn."
#
# Lilting Lullaby's `no_spells` was the only play lock, and 337.2 keeps units
# off the Chain entirely -- so a spell lock never touched a unit. This one has
# to stop every play path there is, and still leave Hide alone (811.1.c.1).
_BRYNHIR = T.id_of("Brynhir Thundersong")

_s = fresh(hand=(_BRYNHIR,))
_s.hand[1, 0] = PLAIN2                    # a unit
_s.hand[1, 1] = T.id_of("Stupefy")        # ...and a [Reaction] spell
_s.n_hand[1] = 2
play(_s, V1, 0, base_loc(0))
_drain_triggers(_s)
if not int(_s.no_cards[1]):
    die("brynhir", "playing him must lock the opponent out")
if int(_s.no_cards[0]):
    die("brynhir", "'OPPONENTS' -- his own controller keeps playing")

# The lock is checked at the offer site, on both play paths.
_s.active, _s.priority = 1, 1
if [a for a in A.legal_actions(_s, T, V1, 1) if a.kind == A.A_PLAY]:
    die("brynhir", "a locked seat must be offered no play at all -- unit or "
                   "spell")
ok("he locks the opponent out of units AND spells, and only the opponent")

# 811.1.c.1 -- Hide is not a subset of Play, so the lock does not reach it.
# This is most of what a locked player has left to do with a turn.
_s.bf_ctrl[0] = 1
_s.hand[1, 0] = T.id_of("Back Off")       # a [Hidden] card
if not [a for a in A.legal_actions(_s, T, V1, 1) if a.kind == A.A_HIDE]:
    die("brynhir", "811.1.c.1 -- Hide is not a Play, so a card lock must "
                   "leave it alone")
ok("...but Hide is not a Play (811.1.c.1), so that still works")

# "this turn" -- it lifts with every other turn-scoped restriction.
from rl.engine import phases as _ph2
_ph2.end_turn(_s, V1)
if int(_s.no_cards[1]) or int(_s.no_cards[0]):
    die("brynhir", "'this turn' -- the lock must be gone by the next turn")
ok("...and 'this turn' means it is gone once the turn ends")


# ---------------------------------------------------------------------------
print("\n[Attachment] 716-719 / 818-819: Equip, Quick-Draw, and Inactive text")
# Attachment needed no new zone and no new object -- an Equipment is already a
# gear permanent -- so the whole mechanism is one column, `P_ATTACHED_TO`.
# What these check is the four rules that ride on it, because each one is a
# place an Attached card behaves unlike the gear it otherwise is.
from rl.engine.state import P_ATTACHED_TO

_SWORD = T.id_of("Long Sword")        # [Quick-Draw] [Equip] {Fury rune}
_CAPE = T.id_of("Forgefire Cape")     # [Equip] {any rune}, no Quick-Draw

# 818.1.c.2 -- "[Cost]: Attach this gear to a unit you control", synthesised
# from the keyword rather than transcribed on each of the 39 cards that print
# it. The cost is read off the text, since the export has no cost field.
if (int(T.equip_energy[_SWORD]), int(T.equip_power[_SWORD])) != (0, 1):
    die("equip", "Long Sword's [Equip] cost is one Fury rune")
_eq = [a for a in abilities_for(T, _SWORD) if a.trigger == A.TR_ACTIVATED]
if len(_eq) != 1:
    die("equip", "818.1.c.2 -- exactly one activated ability, from the keyword")
ok("[Equip] synthesises one activated ability, with the printed cost")

# The gear attaches, and 719.3 drags it to the unit's location. 149.2 normally
# pins gear to base; attaching is the one thing that overrides that.
s = fresh()
s.bf_ctrl[0] = 0
u = s.add_permanent(PLAIN2, 0, bf_loc(0))
g = s.add_permanent(_CAPE, 0, base_loc(0), is_unit=False)
act = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not act:
    die("equip", "a gear with [Equip] and a friendly unit must offer it")
A.apply(s, T, V1, act[0])
tgt = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
if [a.arg for a in tgt] != [u]:
    die("equip", f"'a unit you control' -- only {u} qualifies, got {tgt}")
A.apply(s, T, V1, tgt[0])
for _ in range(8):
    if not s.n_chain and not s.n_trig:
        break
    A.apply(s, T, V1, A.PASS)
if int(s.perms[g, P_ATTACHED_TO]) != u:
    die("equip", "the gear must be Attached to the unit it chose")
if int(s.perms[g, P_LOC]) != bf_loc(0):
    die("equip", "719.3 -- Attached cards are at the Top-Most card's location, "
                 "which overrides gear's base-only rule (149.2)")
ok("...and attaching drags the gear to its unit, overriding 149.2")

# 719.3.a -- it moves with the unit, and 718.5.c says never separately.
s.set_location(u, base_loc(0))
if int(s.perms[g, P_LOC]) != base_loc(0):
    die("equip", "719.3.a -- Attached cards change location with the Top-Most")
ok("...and follows it wherever it goes (719.3.a)")

# 718.2 / 721.2 -- its printed Rules Text is Inactive while Attached. Read
# through `row_abilities`, which is what every board walk now uses.
from rl.engine.effects import row_abilities, row_statics
if row_abilities(s, T, g) != ():
    die("equip", "718.2 -- an Attached card's printed text is Inactive, so it "
                 "offers no abilities at all")
if [a for a in A.legal_actions(s, T, V1, 0)
        if a.kind == A.A_ACTIVATE and A.unpack_activate(int(a.arg))[0] == g]:
    die("equip", "721.2 -- an Inactive ability cannot be activated. That the "
                 "reading is right is why [Weaponmaster] exists (821.1.b)")
ok("...and its own text goes Inactive: no abilities, nothing to activate")

# 722.1 -- but the text is still PRESENT. Its keywords stay visible.
if not T.has(_CAPE, "Equip"):
    die("equip", "722.1 -- Inactive text still has keywords for anything that "
                 "asks whether the card has them")
ok("...while 722.1 keeps its keywords visible to anything that asks")

# 719.5 -- the unit leaves, the gear DETACHES and stays on the board. This is
# what makes Equipment recoverable, and the reason a gear is a permanent in
# its own right rather than a modifier on a unit.
combat.destroy(s, T, u)
if s.perms[g, P_ALIVE] != 1:
    die("equip", "719.5 -- the Equipment stays on the board; only the "
                 "Top-Most card changed zones")
if int(s.perms[g, P_ATTACHED_TO]) != -1:
    die("equip", "719.5 -- it must Detach when its unit leaves")
if row_abilities(s, T, g) == ():
    die("equip", "...and its text goes Active again the moment it detaches")
ok("...and a killed unit DROPS it: detached, still on the board, text live")

# `compact_permanents` renumbers rows, and P_ATTACHED_TO is a row index living
# inside `perms` -- the one case the function's own warning does not cover.
s2 = fresh()
s2.bf_ctrl[0] = 0
dead = s2.add_permanent(PLAIN2, 0, bf_loc(0))
u2 = s2.add_permanent(PLAIN2, 0, bf_loc(0))
g2 = s2.add_permanent(_CAPE, 0, base_loc(0), is_unit=False)
s2.attach(g2, u2)
s2.perms[dead, P_ALIVE] = 0            # a hole BELOW both, so both shift down
s2.compact_permanents()
moved_g = next(i for i in range(s2.n_perms)
               if int(s2.perms[i, P_CARD]) == _CAPE)
moved_u = next(i for i in range(s2.n_perms)
               if int(s2.perms[i, P_CARD]) == PLAIN2)
if int(s2.perms[moved_g, P_ATTACHED_TO]) != moved_u:
    die("equip", "compacting must REMAP the attachment, not leave it pointing "
                 "at whatever now occupies the old row")
ok("...and compaction remaps the link instead of re-pointing it")

# 137.3 -- the Might Bonus. The number comes from the "Attached:" band that
# `data/errata.json` supplies, because upstream never carried the field.
if int(T.might_bonus[_SWORD]) != 2:
    die("equip", "Long Sword gives +2 Might while attached (137.3)")
s3 = fresh()
u3 = s3.add_permanent(PLAIN2, 0, base_loc(0))
g3 = s3.add_permanent(_SWORD, 0, base_loc(0), is_unit=False)
_base_might = combat.might(s3, T, u3)
s3.attach(g3, u3)
if combat.might(s3, T, u3) != _base_might + 2:
    die("equip", "718.4 -- an Attached card's Might Bonus modulates the "
                 "Top-Most card's Might")
# 137.3.a -- "stops applying as soon as the card is no longer Attached", which
# is why it is computed per call rather than written into P_MIGHT_MOD.
s3.detach(g3)
if combat.might(s3, T, u3) != _base_might:
    die("equip", "137.3.a -- the bonus stops the instant it detaches")
ok("...and 137.3's Might Bonus applies while attached and stops when it is not")

# 722.2 uses Spinning Axe as its worked example: its printed [Temporary] does
# not trigger while it is attached, even though 722.1 keeps the keyword visible.
_AXE = T.id_of("Spinning Axe")
s4 = fresh()
s4.active = 0
u4 = s4.add_permanent(PLAIN2, 0, base_loc(0))
g4 = s4.add_permanent(_AXE, 0, base_loc(0), is_unit=False)
s4.attach(g4, u4)
_ph2.expire_temporary(s4, T)
if s4.perms[g4, P_ALIVE] != 1:
    die("equip", "722.2 -- an ATTACHED Spinning Axe's [Temporary] must not "
                 "trigger; the rulebook uses this exact card as the example")
if not T.has(_AXE, "Temporary"):
    die("equip", "722.1 -- the keyword is still there for anything that asks")
# Detached, it expires as printed.
s4.detach(g4)
_ph2.expire_temporary(s4, T)
if s4.perms[g4, P_ALIVE] == 1:
    die("equip", "...and once detached its [Temporary] is Active again")
ok("...and 722.2's worked example holds: attached, [Temporary] sleeps")

# The coverage metric credits an Equipment whose band is nothing but a Might
# Bonus, and withholds one that also grants an ABILITY -- 718.3's append is
# not implemented, so that clause would be silently dropped.
from rl.decks import plays_as_printed as _pap
if not _pap(T, _SWORD):
    die("equip", "Long Sword's band is '+2 Might' and nothing else, which the "
                 "engine executes in full")
# ...and a band whose ability is NOT transcribed is still withheld. Every
# band in the pool is transcribed now, so the guard is checked by taking one
# transcription away: The Zero Drive's "[Deathknell] -- Banish me".
from rl.engine import effects as _eff_band
_zd = _eff_band.EQUIP_ABILITIES.pop("The Zero Drive")
_withheld = not _pap(T, T.id_of("The Zero Drive"))
_eff_band.EQUIP_ABILITIES["The Zero Drive"] = _zd
if not _withheld:
    die("equip", "718.3 -- an untranscribed band must keep the card out of "
                 "the coverage number")
ok("...and coverage splits on 718.3: a transcribed band counts, a bare one does not")


# ---------------------------------------------------------------------------
print("\n[Attachment 718.3] a keyword the Equipment gives its UNIT")
# 718.3: "Abilities in the card's Effect Text are appended to the Rules Text of
# the Top-Most Card." 136.2.c fixes the direction -- Effect Text's "I" means
# the object it is attached to -- so Doran's Shield's "[Tank] (I must be
# assigned combat damage first.)" makes the UNIT a Tank, not the gear.
_SHIELD = T.id_of("Doran's Shield")       # Attached: +1 Might. [Tank]
_DIRK = T.id_of("Serrated Dirk")          # Attached: +0 Might. [Assault 2]

if T.attached_kw[_SHIELD] != (("Tank", 1),):
    die("718.3", f"the band should parse to Tank 1, got {T.attached_kw[_SHIELD]}")
if T.attached_kw[_DIRK] != (("Assault", 2),):
    die("718.3", f"[Assault 2]'s VALUE has to survive, got {T.attached_kw[_DIRK]}")
ok("the 'Attached:' band parses to (keyword, value), value included")

s = fresh()
u = s.add_permanent(PLAIN2, 0, base_loc(0))
if combat.perm_kw(s, T, u, "Tank"):
    die("718.3", "the control unit must not already be a Tank")
g = s.add_permanent(_SHIELD, 0, base_loc(0), is_unit=False)
s.attach(g, u)
if not combat.perm_kw(s, T, u, "Tank"):
    die("718.3", "the UNIT gains [Tank] from the Equipment attached to it")
if combat.perm_kw(s, T, g, "Tank"):
    die("718.3", "136.2.c -- 'I' in Effect Text is the Top-Most card, so the "
                 "GEAR does not gain it")
ok("...and the unit gains it while the gear does not (136.2.c)")

# It goes when the Equipment does -- 718.4's Might Bonus and 718.3's abilities
# both last exactly as long as the Attached state.
s.detach(g)
if combat.perm_kw(s, T, u, "Tank"):
    die("718.3", "the grant lasts only while Attached")
ok("...and it stops the moment it detaches")

# Two Equipment stack, for the reason `static_keyword` sums: 807.1.c makes
# [Assault X] short for an ability, and two abilities both apply.
s2 = fresh()
u2 = s2.add_permanent(PLAIN2, 0, base_loc(0))
# Relative to the unit's own printed value: `PLAIN2` is chosen for having no
# rules text, which does not make it free of [Assault].
_base_a = combat.perm_kw(s2, T, u2, "Assault")
for _ in range(2):
    s2.attach(s2.add_permanent(_DIRK, 0, base_loc(0), is_unit=False), u2)
if combat.perm_kw(s2, T, u2, "Assault") != _base_a + 4:
    die("718.3", f"two [Assault 2] swords add 4, got "
                 f"{combat.perm_kw(s2, T, u2, 'Assault') - _base_a}")
ok("...and two of them stack, value and all (807.1.c)")

# Coverage: a band that is nothing but an IMPLEMENTED keyword is fully
# executed and counts; one carrying prose 718.3 would have to append does not.
from rl.decks import plays_as_printed as _pap2
if not _pap2(T, _SHIELD):
    die("718.3", "a keyword-only band the engine reads is played as printed")
_zd2 = _eff_band.EQUIP_ABILITIES.pop("The Zero Drive")
_withheld2 = not _pap2(T, T.id_of("The Zero Drive"))
_eff_band.EQUIP_ABILITIES["The Zero Drive"] = _zd2
if not _withheld2:
    die("718.3", "an untranscribed prose band stays withheld")
ok("...and coverage credits a keyword-only band, never a prose one")


# ---------------------------------------------------------------------------
print("\n[Attachment 718.3] an ABILITY appended to the Top-Most card")
# "Abilities in the card's Effect Text are appended to the Rules Text of the
# Top-Most Card." So Trinity Force's "When I hold, score 1 point" is the
# UNIT's ability, fired from the UNIT's row -- 136.2.c makes "I" the object it
# is attached to, never the Equipment.
from rl.engine.effects import (EQUIP_ABILITIES, appended_abilities,
                               TR_CONQUER as _TR_CONQ)
from rl.engine import phases as _ph3

_TRINITY = T.id_of("Trinity Force")       # When I hold, score 1 point.
_RING = T.id_of("Doran's Ring")           # When I conquer, discard 1 then draw 1.

s = fresh()
u = s.add_permanent(PLAIN2, 0, bf_loc(0))
if appended_abilities(s, T, u):
    die("718.3", "an unequipped unit has nothing appended")
g = s.add_permanent(_TRINITY, 0, base_loc(0), is_unit=False)
s.attach(g, u)
app = appended_abilities(s, T, u)
if len(app) != 1 or app[0][0] != _TRINITY:
    die("718.3", f"the band's ability belongs to the UNIT's row, carrying the "
                 f"EQUIPMENT's card for lookup; got {app}")
ok("the ability is appended to the unit's row, tagged with the gear's card")

# It fires from the unit. A Hold is scored in the Beginning Phase, and the
# battlefield has to be held for it.
s.bf_ctrl[0] = 0
_pts = int(s.points[0])
_ph3.score_holds(s, V1, T)
_drain_triggers(s)
if int(s.points[0]) <= _pts:
    die("718.3", "'When I hold, score 1 point' must pay out from the unit's "
                 "hold, not from the gear sitting at base")
ok("...and it fires on the UNIT's hold, scoring the point")

# **The Chain Item has to find its way back to the right table.** `C_SRC` is
# the unit's row and `C_CARD` the Equipment's, which is the only case where
# those two disagree apart from a borrowed ability -- and getting the
# discriminator wrong resolved Heimerdinger's borrow out of the wrong table.
s2 = fresh()
u2 = s2.add_permanent(PLAIN2, 0, bf_loc(0))
s2.bf_ctrl[0] = 0
g2 = s2.add_permanent(_RING, 0, base_loc(0), is_unit=False)
s2.attach(g2, u2)
s2.hand[0, 0] = PLAIN2
s2.n_hand[0] = 1
# Tapped out, so the card in hand is discard fodder and not a play the settle
# loop can spend before the trigger resolves. (It did, the first time.)
s2.runes_ready[0, :] = 0
chain.queue(s2, _TR_CONQ, u2, bf_loc(0))


def _settle(st, limit=20):
    """Place queued triggers and pass them down -- never PLAY anything.

    `drain` returns the moment the Chain is empty, which with a trigger still
    queued is too early; and taking the first legal action instead would spend
    the very hand card the discard is supposed to find.
    """
    for _ in range(limit):
        if not st.n_chain and not st.n_trig:
            return
        seat = A.acting_seat(st)
        if seat < 0:
            return
        legal = A.legal_actions(st, T, V1, seat)
        pick = next((a for a in legal if a.kind == A.A_ORDER), None) \
            or next((a for a in legal if a.kind == A.A_PASS), legal[0])
        A.apply(st, T, V1, pick)
    die("718.3", "the appended trigger never settled")


_settle(s2)
if int(s2.n_hand[0]) != 1:
    die("718.3", "discard 1 then draw 1 leaves the hand the same size, and "
                 "both halves must have run")
if int(s2.n_trash[0]) != 1:
    die("718.3", "the discard must actually reach the trash")
ok("...and a two-op band resolves in order off the unit's conquer")

# 718.4 and 718.3 end together: detaching takes the ability with it.
s3 = fresh()
u3 = s3.add_permanent(PLAIN2, 0, bf_loc(0))
s3.bf_ctrl[0] = 0
g3 = s3.add_permanent(_TRINITY, 0, base_loc(0), is_unit=False)
s3.attach(g3, u3)
s3.detach(g3)
_pts3 = int(s3.points[0])
_ph3.score_holds(s3, V1, T)
_drain_triggers(s3)
if int(s3.points[0]) != _pts3 + 1:
    die("718.3", "a detached Trinity Force appends nothing, so the hold should "
                 "score only the battlefield's own point")
ok("...and detaching takes the appended ability with it")


# ---------------------------------------------------------------------------
print("\n[Attachment 718.3] a STATIC appended, and the one pronoun that isn't the unit")
# Brutalizer: "If this was attached to me this turn, I have an additional +2
# Might." Two pronouns in one sentence pointing at two different cards --
# "this" is the gear, "me" is the unit (136.2.c) -- which is why
# `row_statics_sourced` carries both rows.
_BRUT = T.id_of("Brutalizer")
_SOUL = T.id_of("Soul Sword")

s = fresh()
s.ply = 5
u = s.add_permanent(PLAIN2, 0, bf_loc(0))
_m0 = combat.might(s, T, u)
g = s.add_permanent(_BRUT, 0, base_loc(0), is_unit=False)
s.attach(g, u)
if combat.might(s, T, u) != _m0 + int(T.might_bonus[_BRUT]) + 2:
    die("brutalizer", "attached THIS turn: the Might Bonus and the extra +2")
ok("attached this turn, the unit gets the bonus and the conditional +2")

# The window is one turn. `P_ATTACH_TURN` is a stamp, so nothing has to
# remember to clear it.
s.ply = 6
if combat.might(s, T, u) != _m0 + int(T.might_bonus[_BRUT]):
    die("brutalizer", "next turn the conditional +2 is gone and only 137.3's "
                      "Might Bonus remains")
ok("...and next turn only 137.3's flat bonus is left")

# "THIS" is the gear naming itself, so a second Equipment attached later does
# not switch Brutalizer back on. The stamp is per attached card, not per unit.
s2 = fresh()
s2.ply = 5
u2 = s2.add_permanent(PLAIN2, 0, bf_loc(0))
_m2 = combat.might(s2, T, u2)
b2 = s2.add_permanent(_BRUT, 0, base_loc(0), is_unit=False)
s2.attach(b2, u2)
s2.ply = 6
other = s2.add_permanent(T.id_of("B.F. Sword"), 0, base_loc(0), is_unit=False)
s2.attach(other, u2)                 # a DIFFERENT gear, attached this turn
_expect = _m2 + int(T.might_bonus[_BRUT]) + int(T.might_bonus[T.id_of("B.F. Sword")])
if combat.might(s2, T, u2) != _expect:
    die("brutalizer", "'THIS was attached' asks about the gear printing the "
                      "clause, so equipping something else must not revive it")
ok("...and equipping something else does not revive it -- 'this' is the gear")

# Soul Sword's [Level 3] is a DEPENDENT keyword (727) gated on the controller's
# XP, which never resets, so it is read live.
s3 = fresh()
u3 = s3.add_permanent(PLAIN2, 0, bf_loc(0))
_m3 = combat.might(s3, T, u3)
g3 = s3.add_permanent(_SOUL, 0, base_loc(0), is_unit=False)
s3.attach(g3, u3)
if combat.might(s3, T, u3) != _m3 + int(T.might_bonus[_SOUL]):
    die("soul sword", "below 3 XP only the flat Might Bonus applies")
s3.xp[0] = 3
if combat.might(s3, T, u3) != _m3 + int(T.might_bonus[_SOUL]) + 1:
    die("soul sword", "[Level 3] turns the extra +1 on at 3 XP")
ok("Soul Sword's [Level 3] gates the appended static on live XP (727)")

# The appended static is the UNIT's: SC_SELF reaches the body, never the gear.
if combat.might(s3, T, g3) != 0:
    die("soul sword", "136.2.c -- the static reads 'I' as the Top-Most card, "
                      "so it must not pump the gear")
ok("...and SC_SELF in an appended static means the unit, not the Equipment")


# ---------------------------------------------------------------------------
print("\n[TR_BECOME_EMPOWERED] 441.1's transition, not the status")
# 441.1.b/c make re-Empowering something already Empowered a no-op, and a no-op
# is not an event -- so this fires on the CHANGE, the same reading TR_READIED
# takes of readying.
from rl.engine.effects import TR_BECOME_EMPOWERED as _TR_EMP
from rl.engine.state import F_EMPOWERED as _F_EMP, P_EMPOWER as _P_EMP

_MATRIARCH = T.id_of("Tail-Cloaked Matriarch")
_MAGE = T.id_of("Apprentice Mage")

# Empowering fires it.
s = fresh()
m = s.add_permanent(_MAGE, 0, bf_loc(0))
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("empower", "[Empower] {2 energy} must be offered on a ready board")
A.apply(s, T, V1, acts[0])
# The Empower is an ACTIVATED ability, so it is a Chain Item and nothing has
# happened yet -- the status is set when it RESOLVES, and the trigger fires off
# that. Asserting either before draining would be asserting the wrong instant.
if not s.n_chain:
    die("empower", "the [Empower] ability itself goes on the Chain (383.3)")
_drain_triggers(s, limit=20)
if not s.has_flag(m, _F_EMP):
    die("empower", "resolving it sets the status")
# His trigger is [Predict 2], which suspends on a look -- so a pending look is
# proof the trigger fired and reached resolution, not merely that it queued.
if s.pend_look < 0 and int(s.n_look) == 0:
    die("empower", "'when I become [Empowered], [Predict 2]' must have run -- "
                   "a pending look is the observable it leaves behind")
# Close the Predict with "done" -- with 436.1.a's multi pick a single A_PICK
# leaves the look OPEN, and every check below would then see only look picks
# and pass without testing anything.
A.apply(s, T, V1, A.Action(A.A_PICK_NONE))
if s.pend_look >= 0:
    die("empower", "'done' must close the Predict")
ok("Empowering sets the status and fires the trigger, in that order")

# 827.1.c.1 -- "use only if not Empowered", so there is no second Empower to
# transition on. That is what makes this a transition rather than a repeatable.
if [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]:
    die("empower", "827.1.c.1 -- an Empowered permanent is offered no second "
                   "Empower, so the trigger cannot repeat")
ok("...and 827.1.c.1 leaves no second Empower to fire it again")

# The status's own payoff is a separate static (828.1.b.1), gated live.
if combat.might(s, T, m) != int(T.might[_MAGE]) + 1:
    die("empower", "[Empowered][>] I have +1 Might applies once Empowered")
ok("...while the [Empowered] static pays out independently, read live")

# `subject_is_self` -- "when I become Empowered" must not fire for a DIFFERENT
# permanent being Empowered. Without the flag every Mage on the board would
# Predict off anyone's Empower.
s2 = fresh()
watcher = s2.add_permanent(_MAGE, 0, bf_loc(0))
other = s2.add_permanent(_MAGE, 0, bf_loc(0))
s2.perms[watcher, _P_EMP] = 1
s2.set_flag(watcher, _F_EMP)          # already Empowered: no second transition
chain.fire_empowered(s2, T, other)
srcs = {int(s2.trig[i, 1]) for i in range(int(s2.n_trig))}
if watcher in srcs:
    die("empower", "'when I BECOME Empowered' is about this permanent, so "
                   "another one's Empower must not fire it")
if other not in srcs:
    die("empower", "...and the one that actually became Empowered does fire")
ok("...and `subject_is_self` keeps it off every other copy on the board")

# The Matriarch replays a unit from her own trash when she Empowers -- the
# same machinery Spectral Matron uses, on a trigger instead of a play.
s3 = fresh()
mat = s3.add_permanent(_MATRIARCH, 0, bf_loc(0))
cheap = next(c for c in range(T.n)
             if T.is_type(c, "Unit") and not T.is_token(c)
             and int(T.energy[c]) <= 3 and int(T.power[c]) <= 1
             and not T.residual_text(c))
s3.trash[0, 0] = cheap
s3.n_trash[0] = 1
chain.fire_empowered(s3, T, mat)
if not s3.n_trig:
    die("matriarch", "her Empower must queue the replay trigger")
ok("Tail-Cloaked Matriarch queues her trash replay off the same trigger")


# ---------------------------------------------------------------------------
print("\n[Kharox] a choice made AFTER an earlier op filled the pile")
# "When I become [Empowered], choose an opponent. They [Burn 3]. Then you may
# do this: Choose a unit in their trash and play it, ignoring its cost."
#
# The ordering is the card. A target slot is chosen at finalization (355.8),
# which is before the Burn runs -- so it would read the opponent's trash as it
# stood BEFORE the mill, and would refuse the ability outright against an
# empty one. That is precisely the opponent Kharox is best against.
_KHAROX = T.id_of("Kharox")

s = fresh()
k = s.add_permanent(_KHAROX, 0, bf_loc(0))
# The opponent's deck holds units and their trash is EMPTY -- so anything he
# digs up can only have come from his own Burn.
s.n_deck[1] = 6
s.deck[1, :6] = PLAIN2
s.deck_ptr[1] = 0
s.n_trash[1] = 0
chain.fire_empowered(s, T, k)
_drain_triggers(s, limit=25)

if int(s.n_trash[1]) + 1 < 3:
    die("kharox", f"[Burn 3] should have milled three into their trash, "
                  f"found {int(s.n_trash[1])}")
if s.pend_grave < 0:
    die("kharox", "the dig must SUSPEND and ask, after the Burn has run")
if int(s.pend_grave) != 0 or int(s.pend_grave_owner) != 1:
    die("kharox", "seat 0 chooses, but the pile is seat 1's -- the chooser "
                  "and the owner are different seats here")
picks = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK]
if not picks:
    die("kharox", "the units his own Burn just buried must be choosable")
ok("the Burn runs first, then the dig opens over the pile it just filled")

# 108.2 -- a trash is public, so naming a card in the opponent's leaks nothing,
# and `pick_card` has to decode this fourth offer site or the encoder reads an
# index into the wrong zone.
if A.pick_card(s, picks[0].arg) != int(s.trash[1, picks[0].arg]):
    die("kharox", "`pick_card` must decode an A_PICK arg against the OWNER's "
                  "trash at this site")
ok("...and A_PICK's fourth meaning decodes against the owner's trash")

_before = s.n_perms
A.apply(s, T, V1, picks[0])
mine = [i for i in range(s.n_perms)
        if s.perms[i, P_ALIVE] == 1 and int(s.perms[i, P_CTRL]) == 0
        and int(s.perms[i, P_CARD]) == PLAIN2]
if not mine:
    die("kharox", "the unit is played under YOUR control, not its owner's -- "
                  "the effect says 'you may play it'")
ok("...and the unit arrives under the digger's control, not its owner's")

# "You may" -- declining is always available, and leaves the Burn done.
s2 = fresh()
k2 = s2.add_permanent(_KHAROX, 0, bf_loc(0))
s2.n_deck[1] = 6
s2.deck[1, :6] = PLAIN2
s2.deck_ptr[1] = 0
chain.fire_empowered(s2, T, k2)
_drain_triggers(s2, limit=25)
if A.A_PICK_NONE not in {a.kind for a in A.legal_actions(s2, T, V1, 0)}:
    die("kharox", "'you MAY do this' -- declining must always be offered")
_n_before = int(s2.n_trash[1])
A.apply(s2, T, V1, A.Action(A.A_PICK_NONE))
if s2.pend_grave >= 0:
    die("kharox", "declining closes the decision")
if int(s2.n_trash[1]) != _n_before:
    die("kharox", "...and leaves the milled cards where the Burn put them")
ok("...and declining closes it, with the Burn already paid for")


# ---------------------------------------------------------------------------
print("\n[P_OWNER] control is not ownership (718.5.e/f)")
# The engine used P_CTRL for both until Kharox played a card out of the
# OPPONENT's trash. The per-seat conservation gate caught it in a real-deck
# fuzz -- totals went [39, 39] -> [40, 38], which reads as a card changing
# hands and is exactly what that gate exists to refuse.
from rl.engine.state import P_OWNER as _P_OWN

s = fresh()
k = s.add_permanent(T.id_of("Kharox"), 0, bf_loc(0))
s.n_deck[1] = 6
s.deck[1, :6] = PLAIN2
s.deck_ptr[1] = 0
chain.fire_empowered(s, T, k)
_drain_triggers(s, limit=25)
pick = next(a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK)
A.apply(s, T, V1, pick)
dug = next(i for i in range(s.n_perms)
           if s.perms[i, P_ALIVE] == 1 and int(s.perms[i, P_CARD]) == PLAIN2)
if int(s.perms[dug, P_CTRL]) != 0:
    die("owner", "the digger controls it -- 'you may play it'")
if int(s.perms[dug, _P_OWN]) != 1:
    die("owner", "...but it is still the OPPONENT's card; playing a card from "
                 "someone else's zone does not make it yours")
ok("a dug unit is controlled by the digger and owned by the opponent")

# 108.2 -- each player has their own trash, so it goes back to ITS OWNER's.
_mine, _theirs = int(s.n_trash[0]), int(s.n_trash[1])
combat.destroy(s, T, dug)
if int(s.n_trash[1]) != _theirs + 1:
    die("owner", "108.2 -- it dies to its OWNER's trash")
if int(s.n_trash[0]) != _mine:
    die("owner", "...and must not be laundered into the digger's pile")
ok("...and when it dies it returns to its owner's trash, not the digger's")

# The conservation gate's own arithmetic: per-seat totals unchanged.
from rl.tests.fuzz import cards_owned as _owned
s2 = fresh()
k2 = s2.add_permanent(T.id_of("Kharox"), 0, bf_loc(0))
s2.n_deck[1] = 6
s2.deck[1, :6] = PLAIN2
s2.deck_ptr[1] = 0
_before = [_owned(s2, T, k) for k in range(2)]
chain.fire_empowered(s2, T, k2)
_drain_triggers(s2, limit=25)
A.apply(s2, T, V1, next(a for a in A.legal_actions(s2, T, V1, 0)
                        if a.kind == A.A_PICK))
_after = [_owned(s2, T, k) for k in range(2)]
if _before != _after:
    die("owner", f"cards are conserved per OWNER across a dig: "
                 f"{_before} -> {_after}")
ok("...so per-seat card totals are conserved across the whole play")


# ---------------------------------------------------------------------------
print("\n[441.2] Disempower spent as a COST, not an effect")
# "Disempower this, Exhaust: Draw 1." The status is the fuel, so these cards
# are a CYCLE and not an engine -- each use spends the Empower, which has to be
# bought back before the payoff is available again.
_TOME = T.id_of("Questionable Tome")

s = fresh()
g = s.add_permanent(_TOME, 0, base_loc(0), is_unit=False)
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
# Only the [Empower] is available: the draw costs a status she does not hold.
if len(acts) != 1:
    die("disempower", f"441.2 -- you cannot spend a status you do not have, "
                      f"so only [Empower] is offered; got {len(acts)}")
ok("the payoff is withheld until the permanent is actually Empowered")

A.apply(s, T, V1, acts[0])
_drain_triggers(s, limit=12)
if not s.empower_count(g):
    die("disempower", "the [Empower] ability sets the status")
# Both halves Exhaust, and a permanent exhausts once -- so the draw has to wait
# for it to ready. That gap is the card's whole rate limit.
if [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]:
    die("disempower", "it exhausted to Empower, so nothing is offered until "
                      "it readies")
ok("...and exhausting to Empower rate-limits the payoff to the next turn")

s.perms[g, P_READY] = 1
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("disempower", "readied and Empowered, the draw must be offered")
_hand = int(s.n_hand[0])
A.apply(s, T, V1, acts[-1])
_drain_triggers(s, limit=12)
if int(s.n_hand[0]) != _hand + 1:
    die("disempower", "the ability draws 1")
if s.empower_count(g):
    die("disempower", "441.2 -- paying the cost SPENDS the status")
if s.has_flag(g, _F_EMP):
    die("disempower", "...and the flag moves with the count, or the two "
                      "disagree about whether it is Empowered")
ok("...and paying it spends the status, flag and count together")

# Spent, so it is withheld again -- the cycle closes.
s.perms[g, P_READY] = 1
if len(
        [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]) != 1:
    die("disempower", "with the status spent only [Empower] is offered again")
ok("...and the cycle closes: [Empower] again before the next payoff")


# ---------------------------------------------------------------------------
print("\n[Miss Fortune - Captain] 'the FIRST time', and a target that must be exhausted")
_MFC = T.id_of("Miss Fortune - Captain")

s = fresh()
s.bf_ctrl[0] = 0
mf = s.add_permanent(_MFC, 0, base_loc(0))
tired = s.add_permanent(PLAIN2, 0, base_loc(0))
awake = s.add_permanent(PLAIN2, 0, base_loc(0))
s.perms[tired, P_READY] = 0
s.perms[awake, P_READY] = 1
foe = s.add_permanent(PLAIN2, 1, base_loc(1))
s.perms[foe, P_READY] = 0

combat.queue_move_trigger(s, T, mf, base_loc(0), bf_loc(0))
s.set_location(mf, bf_loc(0))
# Placed and accepted DIRECTLY rather than by walking `legal_actions`: in a
# Neutral Open the turn player is also offered declarations and plays, and a
# generic "take the first legal action" loop starts a Move that reshapes the
# board before the trigger is ever read. (It did.)
chain.place(s, T, V1, 0)
for _ in range(8):
    if s.pend_may >= 0 or s.pend_slot >= 0:
        break
    seat = A.acting_seat(s)
    legal = A.legal_actions(s, T, V1, seat)
    pick = next((a for a in legal if a.kind == A.A_PASS), None)
    if pick is None:
        die("mf captain", f"expected a pass while the ability finalizes, "
                          f"got {[a.kind for a in legal]}")
    A.apply(s, T, V1, pick)
if s.pend_may < 0:
    die("mf captain", "the printed 'you may' is decided at finalization "
                      "(383.3.a), so it opens before the target slot")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
if s.pend_slot < 0:
    die("mf captain", "accepting the 'you may' must open its target slot")

opts = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET}
if awake in opts:
    die("mf captain", "'that's EXHAUSTED' -- a ready permanent is not a legal "
                      "choice, and readying it would be a no-op")
if tired not in opts:
    die("mf captain", "an exhausted friendly permanent is a legal choice")
# No ownership word on the card, so the slot reaches both players. Targets
# scope by omission -- only "enemy"/"your" narrow one.
if foe not in opts:
    die("mf captain", "'something else' prints no ownership word, so the "
                      "opponent's exhausted permanent is legal too")
if mf in opts:
    die("mf captain", "'something ELSE' excludes her")
ok("the slot takes any exhausted permanent but her, either player's")

A.apply(s, T, V1, A.Action(A.A_TARGET, tired))
drain(s, V1)
if not int(s.perms[tired, P_READY]):
    die("mf captain", "the chosen permanent is readied")
ok("...and readying it works")

# "The FIRST time each turn" -- a second move the same turn fires nothing.
# Without this [Ganking] would make her a free untapper every hop.
s.perms[tired, P_READY] = 0
combat.queue_move_trigger(s, T, mf, bf_loc(0), base_loc(0))
if s.n_trig:
    die("mf captain", "'the first time I move EACH TURN' -- the second move "
                      "in the same turn must not queue anything")
ok("...and a second move the same turn fires nothing (once_each_turn)")


# ---------------------------------------------------------------------------
print("\n[Insightful Investigator] 383.3.b -- a price on the CHOICE, not the ability")
_INV = T.id_of("Insightful Investigator")

# No XP: the reveal still happens, and the pick is simply not offered.
s = fresh()
s.xp[0] = 0
inv = s.add_permanent(_INV, 0, base_loc(0))
s.hand[1, 0] = PLAIN2
s.hand[1, 1] = PLAIN2
s.n_hand[1] = 2
chain.fire(s, T, V1, TR_PLAY_ME, inv)
_drain_triggers(s, limit=20)
if int(s.pend_reveal[0]) < 0:
    die("investigator", "the reveal is unconditional -- it happens whether or "
                        "not the XP can be paid")
kinds = {a.kind for a in A.legal_actions(s, T, V1, 0)}
if A.A_PICK in kinds:
    die("investigator", "383.3.b -- the pick is only offered when its cost "
                        "can be paid")
if A.A_PICK_NONE not in kinds:
    die("investigator", "...and declining is always available")
ok("with no XP the hand is still revealed, but nothing may be chosen")

A.apply(s, T, V1, A.Action(A.A_PICK_NONE))
if int(s.n_hand[1]) != 2:
    die("investigator", "'IF YOU DO' -- declining discards nothing")
if int(s.xp[0]) != 0:
    die("investigator", "...and costs nothing")
ok("...and declining costs nothing and discards nothing")

# With the XP, the pick is offered, paid for, and THEY draw the replacement.
s2 = fresh()
s2.xp[0] = 3
inv2 = s2.add_permanent(_INV, 0, base_loc(0))
s2.hand[1, 0] = PLAIN2
s2.n_hand[1] = 1
s2.n_deck[1] = 10
s2.deck[1, :10] = PLAIN2
s2.deck_ptr[1] = 0
chain.fire(s2, T, V1, TR_PLAY_ME, inv2)
_drain_triggers(s2, limit=20)
picks = [a for a in A.legal_actions(s2, T, V1, 0) if a.kind == A.A_PICK]
if not picks:
    die("investigator", "with 3 XP the pick must be offered")
_trash_before = int(s2.n_trash[1])
A.apply(s2, T, V1, picks[0])
if int(s2.xp[0]) != 1:
    die("investigator", f"2 XP is paid on the pick, got {int(s2.xp[0])} left")
if int(s2.n_trash[1]) != _trash_before + 1:
    die("investigator", "'they DISCARD that card' -- to their own trash")
# "and draw 1" -- THEY draw, replacing what they lost. That is what makes the
# card tempo rather than card advantage, and it is why the follow-up needs
# `who=W_ENEMY`: a follow-up runs for the chooser by default.
if int(s2.n_hand[1]) != 1:
    die("investigator", "...and THEY draw 1, so their hand is the same size "
                        "again -- not the caster")
ok("paying 2 XP discards from their hand and gives THEM the replacement draw")


# ---------------------------------------------------------------------------
print("\n[3956] 'Recycle N from your trash' as a COST, and Equip's full price")
_GRABBER = T.id_of("Garbage Grabber")
_VI = T.id_of("Vi, Destructive")
_BLADE = T.id_of("Blade of the Ruined King")
_RITES = T.id_of("Last Rites")

# Unaffordable means not offered: two cards cannot pay a recycle-3.
s = fresh()
g = s.add_permanent(_GRABBER, 0, base_loc(0), is_unit=False)
s.trash[0, :2] = PLAIN2
s.n_trash[0] = 2
if [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]:
    die("recycle cost", "two cards in the trash cannot pay 'Recycle 3'")
ok("with too few cards in the trash the ability is not offered")

# Three copies DO pay it -- counted as copies, though they collapse to one
# choice (108.2.c: the trash is unordered).
s.trash[0, 2] = PLAIN2
s.n_trash[0] = 3
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("recycle cost", "three identical cards pay 'Recycle 3'")
A.apply(s, T, V1, acts[0])
picks = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK]
if len(picks) != 1:
    die("recycle cost", f"identical copies collapse to one choice, got {len(picks)}")
_hand, _deck = int(s.n_hand[0]), int(s.n_deck[0])
for _ in range(3):
    A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, 0)
                           if a.kind == A.A_PICK))
if int(s.n_trash[0]) != 0:
    die("recycle cost", "all three are recycled out of the trash")
if int(s.n_deck[0]) != _deck + 3:
    die("recycle cost", "416.1.c -- recycled to the bottom of the owner's deck")
drain(s, V1)
if int(s.n_hand[0]) != _hand + 1:
    die("recycle cost", "...and then the ability resolves and draws 1")
ok("three copies pay it, collapse to one choice, and land on the deck bottom")

# The choice is REAL when the trash differs: two distinct cards, two options.
s2 = fresh()
s2.add_permanent(_VI, 0, base_loc(0))
_spell = T.id_of("Stupefy")
s2.trash[0, 0] = PLAIN2
s2.trash[0, 1] = _spell
s2.n_trash[0] = 2
A.apply(s2, T, V1, next(a for a in A.legal_actions(s2, T, V1, 0)
                        if a.kind == A.A_ACTIVATE))
choices = {A.pick_card(s2, a.arg) for a in A.legal_actions(s2, T, V1, 0)
           if a.kind == A.A_PICK}
if choices != {PLAIN2, _spell}:
    die("recycle cost", f"3956 -- the player chooses WHICH card; got {choices}")
ok("...and distinct cards are distinct choices, decoded by `pick_card`")

# **The discount bug.** `_equip_abilities` read only the rune run, so Blade of
# the Ruined King equipped for a lone {Order rune} without killing anything.
blade_eq = next(a for a in abilities_for(T, _BLADE) if a.trigger == A.TR_ACTIVATED)
if blade_eq.cost_kill is None:
    die("equip cost", "Blade's [Equip] must charge 'Kill a friendly unit' -- "
                      "without it the card equips strictly cheaper than printed")
rites_eq = next(a for a in abilities_for(T, _RITES) if a.trigger == A.TR_ACTIVATED)
if rites_eq.cost_recycle_trash != 2:
    die("equip cost", "Last Rites' [Equip] must charge 'Recycle 2 cards'")
ok("[Equip] now charges its non-resource half: Blade kills, Last Rites recycles")

# And Last Rites is not offered to a seat with an empty trash, which is the
# observable consequence of charging the full price.
s3 = fresh()
s3.add_permanent(PLAIN2, 0, base_loc(0))
s3.add_permanent(_RITES, 0, base_loc(0), is_unit=False)
s3.n_trash[0] = 0
if [a for a in A.legal_actions(s3, T, V1, 0) if a.kind == A.A_ACTIVATE]:
    die("equip cost", "with an empty trash Last Rites' [Equip] is unpayable "
                      "and must not be offered")
ok("...so with an empty trash Last Rites cannot be equipped at all")


# ---------------------------------------------------------------------------
print("\n[436.1.a] [Predict N] recycles ANY NUMBER of the N")
# Apprentice Mage was first transcribed with a single optional pick, which
# capped the recycle at one card. 436.1.a: "looks at that many cards and
# Recycles any number of them before putting the rest back on top".
from rl.engine.state import DEST_RECYCLE as _DR, DEST_TOP as _DT
from rl.engine.effects import CardSpec as _CS9, Op as _Op9, OP_LOOK_TOP as _OL9, SPEED_MAIN as _SM9

_A, _B, _C = PLAIN2, T.id_of("Stupefy"), T.id_of("Lecturing Yordle")
s = fresh()
s.n_deck[0] = 3
s.deck[0, :3] = [_A, _B, _C]
s.deck_ptr[0] = 0
_rsv2.resolve(s, T, V1, _CS9(speed=_SM9, ops=(_Op9(_OL9, n=2, pick_optional=True,
              pick_multi=True, pick_dest=_DR, rest_dest=_DT),)), 0, [], -1, False)
if int(s.n_look) != 2:
    die("predict", "Predict 2 looks at two cards")
# Recycle BOTH -- impossible with a single pick.
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if s.pend_look < 0 or int(s.n_look) != 1:
    die("predict", "a multi pick moves one card and keeps the look open")
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if s.pend_look >= 0:
    die("predict", "taking the last card closes the look")
# Both went to the bottom; the untouched third card is now on top.
_top = int(s.deck[0, int(s.deck_ptr[0])])
if _top != _C:
    die("predict", f"with both recycled the third card should be on top, got "
                   f"{T.names[_top]}")
if [int(x) for x in s.deck[0, int(s.n_deck[0]) - 2:int(s.n_deck[0])]] != [_A, _B]:
    die("predict", "the two recycled cards are on the bottom (416.1.c)")
ok("Predict 2 can recycle BOTH cards, which a single pick could not")

# Recycle one, keep one: 'done' puts the kept card back on top.
s2 = fresh()
s2.n_deck[0] = 3
s2.deck[0, :3] = [_A, _B, _C]
s2.deck_ptr[0] = 0
_rsv2.resolve(s2, T, V1, _CS9(speed=_SM9, ops=(_Op9(_OL9, n=2, pick_optional=True,
              pick_multi=True, pick_dest=_DR, rest_dest=_DT),)), 0, [], -1, False)
A.apply(s2, T, V1, A.Action(A.A_PICK, 0))        # recycle _A
A.apply(s2, T, V1, A.Action(A.A_PICK_NONE))      # done: keep _B
if int(s2.deck[0, int(s2.deck_ptr[0])]) != _B:
    die("predict", "the kept card goes back on TOP")
if int(s2.deck[0, int(s2.n_deck[0]) - 1]) != _A:
    die("predict", "...and the recycled one is on the bottom")
ok("...or recycle one and keep one, with 'done' putting the rest back on top")


# ---------------------------------------------------------------------------
print("\n[359.2.d] gear that 'enters exhausted', and what that buys")
_EGG = T.id_of("Platewyrm Egg")
_HONEY = T.id_of("Honeyfruit")
_BLOOM = T.id_of("Scryer's Bloom")

# Played from hand it lands EXHAUSTED -- 359.2.d's default is ready, and this
# is the printed exception, read at every play site.
s = fresh(hand=(_EGG,))
play(s, V1, 0, base_loc(0))
egg = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == _EGG)
if int(s.perms[egg, P_READY]):
    die("enters exhausted", "'This enters exhausted.' overrides 359.2.d")
# ...so its Exhaust abilities are not available the turn it lands.
if [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE
        and A.unpack_activate(int(a.arg))[0] == egg]:
    die("enters exhausted", "an exhausted gear offers no Exhaust ability")
ok("it lands exhausted, so nothing it prints is usable the turn it arrives")

# A gear WITHOUT the sentence still enters ready -- the default is untouched.
_PLAIN_GEAR = T.id_of("Treasure Trove")
s1 = fresh(hand=(_PLAIN_GEAR,))
play(s1, V1, 0, base_loc(0))
pg = next(i for i in range(s1.n_perms) if int(s1.perms[i, P_CARD]) == _PLAIN_GEAR)
if not int(s1.perms[pg, P_READY]):
    die("enters exhausted", "an ordinary gear still enters READY (359.2.d)")
ok("...while an ordinary gear still enters ready")

# Platewyrm Egg: "[Add] {1 energy}. If this is [Empowered], [Add] {2 energy}
# INSTEAD." A partition, so the Empowered egg adds 2 -- not 1 + 2.
def _egg_add(empowered):
    st = fresh()
    e = st.add_permanent(_EGG, 0, base_loc(0), is_unit=False)
    if empowered:
        st.perms[e, _P_EMP] = 1
        st.set_flag(e, _F_EMP)
    before = int(st.pool_energy[0])
    act = [a for a in A.legal_actions(st, T, V1, 0) if a.kind == A.A_ACTIVATE
           and A.unpack_activate(int(a.arg))[0] == e]
    add = next(a for a in act
               if A.unpack_activate(int(a.arg))[2] == 1)
    A.apply(st, T, V1, add)
    return int(st.pool_energy[0]) - before

if _egg_add(False) != 1:
    die("platewyrm", "un-Empowered it adds {1 energy}")
if _egg_add(True) != 2:
    die("platewyrm", "Empowered it adds {2 energy} INSTEAD -- not 1 + 2")
ok("Platewyrm Egg adds 1, or 2 'instead' once Empowered -- never 3")

# Honeyfruit: the Level 6 ability is offered only at 6+ XP.
s3 = fresh()
h = s3.add_permanent(_HONEY, 0, base_loc(0), is_unit=False)
def _honey_offers(st):
    return len([a for a in A.legal_actions(st, T, V1, 0)
                if a.kind == A.A_ACTIVATE
                and A.unpack_activate(int(a.arg))[0] == h])
s3.xp[0] = 5
if _honey_offers(s3) != 1:
    die("honeyfruit", "below 6 XP only the base [Add] is offered")
s3.xp[0] = 6
if _honey_offers(s3) != 2:
    die("honeyfruit", "'use this ability only while you have 6+ XP' -- at 6 "
                      "both are offered")
ok("Honeyfruit's [Level 6] ability is gated on XP, not paid for with it")
if int(s3.xp[0]) != 6:
    die("honeyfruit", "...and the gate spends no XP")

# Scryer's Bloom: kill itself as a COST, Predict 2, THEN draw 1 and gain 1 XP.
s4 = fresh()
b = s4.add_permanent(_BLOOM, 0, base_loc(0), is_unit=False)
_hand, _xp = int(s4.n_hand[0]), int(s4.xp[0])
A.apply(s4, T, V1, next(a for a in A.legal_actions(s4, T, V1, 0)
                        if a.kind == A.A_ACTIVATE))
for _ in range(10):
    if s4.pend_look >= 0:
        break
    # Both seats pass in turn -- priority moves to the opponent after seat 0.
    _st = A.acting_seat(s4)
    A.apply(s4, T, V1, next(a for a in A.legal_actions(s4, T, V1, _st)
                            if a.kind == A.A_PASS))
if s4.perms[b, P_ALIVE]:
    die("scryer's bloom", "'Kill this' is a cost, paid before it resolves")
if s4.pend_look < 0:
    die("scryer's bloom", "the Predict opens a look")
if int(s4.n_hand[0]) != _hand:
    die("scryer's bloom", "the draw comes AFTER the Predict, not before")
A.apply(s4, T, V1, A.Action(A.A_PICK_NONE))
if int(s4.n_hand[0]) != _hand + 1 or int(s4.xp[0]) != _xp + 1:
    die("scryer's bloom", "'then draw 1. Gain 1 XP.' runs once the look closes")
ok("Scryer's Bloom kills itself, Predicts, and only then draws and gains XP")


# ---------------------------------------------------------------------------
print("\n[466.3] TR_WIN_COMBAT -- the one player with units left won")
from rl.engine.effects import TR_WIN_COMBAT as _TRW
_NID = T.id_of("Nidalee - Cat Form")
_DRA = T.id_of("Draven - Audacious")


def _resolve_combat(st, bf, attacker):
    st.showdown_bf = bf
    st.showdown_combat = 1
    st.attacker = attacker
    return combat.resolution_step(st, T, V1, bf, attacker, {})


def _queued(st, trigger):
    return [int(st.trig[i, 1]) for i in range(int(st.n_trig))
            if int(st.trig[i, 0]) == trigger]


# Only seat 0 remains -> seat 0 won, and Nidalee (still standing) wins too.
s = fresh()
nid = s.add_permanent(_NID, 0, bf_loc(0))
_resolve_combat(s, 0, 0)
if nid not in _queued(s, _TRW):
    die("win combat", "466.3.a/c -- the sole survivor's units won the combat")
ok("the player with units left wins, and 466.3.c hands it to their units")

# Both sides still present -> "No Result" (466.3.d): nobody won.
s = fresh()
nid = s.add_permanent(_NID, 1, bf_loc(0))
s.add_permanent(PLAIN2, 0, bf_loc(0))
s.perms[nid, P_READY] = 1
_resolve_combat(s, 0, 0)
if _queued(s, _TRW):
    die("win combat", "466.3.d -- both players present is No Result, no win")
ok("...and a No Result (both sides still there) wins nothing")

# A NON-Combat Showdown is not a combat at all.
s = fresh()
nid = s.add_permanent(_NID, 0, bf_loc(0))
s.showdown_bf = 0
s.showdown_combat = 0
combat.resolution_step(s, T, V1, 0, 0, {})
if _queued(s, _TRW):
    die("win combat", "a non-Combat Showdown has no combat to win")
ok("...and a non-Combat Showdown is not a combat")

# Draven - Audacious: the FIRST win each turn scores; the second does not.
# `once_each_turn` is stamped at this direct queueing site.
s = fresh()
dr = s.add_permanent(_DRA, 0, bf_loc(0))
_resolve_combat(s, 0, 0)
first = _queued(s, _TRW).count(dr)
s.n_trig = 0
s.set_location(dr, bf_loc(1))         # the same Draven wins a second combat
_resolve_combat(s, 1, 0)
if first != 1 or dr in _queued(s, _TRW):
    die("draven", "'the FIRST time I win a combat each turn' -- once, not twice")
ok("Draven - Audacious fires on the first win only (once_each_turn)")

# "When I die IN COMBAT, they score" -- the snapshot distinguishes a death in
# a Combat from a death to a spell.
from rl.engine.state import F_DIED_IN_COMBAT as _FDIC, P_FLAGS
s = fresh()
dr = s.add_permanent(_DRA, 0, bf_loc(0))
s.showdown_bf, s.showdown_combat = 0, 1
combat.destroy(s, T, dr)
if not (int(s.perms[dr, P_FLAGS]) & _FDIC):
    die("draven", "a death during a Combat he is in is snapshotted")
s2 = fresh()
dr2 = s2.add_permanent(_DRA, 0, bf_loc(0))
combat.destroy(s2, T, dr2)                 # no Combat open
if int(s2.perms[dr2, P_FLAGS]) & _FDIC:
    die("draven", "a death outside combat is not 'in combat'")
_pts = int(s2.points[1])
_drain_triggers(s2, limit=12)
if int(s2.points[1]) != _pts:
    die("draven", "'died_in_combat' keeps a spell kill from scoring the opponent")
_pts1 = int(s.points[1])
_drain_triggers(s, limit=12)
if int(s.points[1]) != _pts1 + 1:
    die("draven", "dying in combat scores the OPPONENT 1 point")
ok("...and dying IN combat scores the opponent, while a spell kill does not")


# ---------------------------------------------------------------------------
print("\n[369-370] Guardian Angel -- a replacement in an Equipment's band")
_ANGEL = T.id_of("Guardian Angel")
from rl.engine.effects import NON_UNIT_TOKENS

s = fresh()
u = s.add_permanent(PLAIN2, 0, bf_loc(0))
ang = s.add_permanent(_ANGEL, 0, bf_loc(0), is_unit=False)
s.attach(ang, u)
s.perms[u, P_READY] = 1
combat.mark_damage(s, T, u, 50)
if not s.perms[u, P_ALIVE]:
    die("guardian angel", "'If I would die, kill Guardian Angel INSTEAD' -- the "
                          "unit survives")
if s.perms[ang, P_ALIVE]:
    die("guardian angel", "...and the Angel is killed in its place")
if int(s.perms[u, P_DMG]) or int(s.perms[u, P_READY]) \
        or int(s.perms[u, P_LOC]) != base_loc(0):
    die("guardian angel", "'Heal me, exhaust me, and recall me' -- all three")
ok("the attached Angel dies instead, and the unit is healed, exhausted, recalled")

# It guards ONLY the unit it is attached to (136.2.c): "I" is that unit.
s2 = fresh()
u1 = s2.add_permanent(PLAIN2, 0, bf_loc(0))
u2 = s2.add_permanent(PLAIN2, 0, bf_loc(0))
ang2 = s2.add_permanent(_ANGEL, 0, bf_loc(0), is_unit=False)
s2.attach(ang2, u1)
combat.destroy(s2, T, u2)
if s2.perms[u2, P_ALIVE] or not s2.perms[ang2, P_ALIVE]:
    die("guardian angel", "a DIFFERENT friendly unit is not protected -- unlike "
                          "Zhonya's, the Angel guards only its Top-Most card")
ok("...and guards only its own unit, where Zhonya's guards any friendly one")

# Unattached, its band is inert: 718.3 appends it only while attached.
s3 = fresh()
u3 = s3.add_permanent(PLAIN2, 0, bf_loc(0))
s3.add_permanent(_ANGEL, 0, base_loc(0), is_unit=False)
combat.destroy(s3, T, u3)
if s3.perms[u3, P_ALIVE]:
    die("guardian angel", "an unattached Angel protects nothing")
ok("...and an unattached Angel protects nothing")

# The token-op-last assertion skips NON_UNIT_TOKENS by NAME, because effects.py
# has no table at import. Hold that list to the compiled truth here.
for _tn in NON_UNIT_TOKENS:
    if T.is_type(T.id_of(_tn), "Unit"):
        die("tokens", f"{_tn!r} is listed as a non-unit token but is a unit -- "
                      f"it would slip past Zilean's last-op assertion")
ok("every NON_UNIT_TOKENS entry really is a non-unit in the compiled table")


# ---------------------------------------------------------------------------
print("\n[828.1.d] Dame the Despoiler -- a dependent trigger that doesn't exist un-Empowered")
from rl.engine.effects import TR_ATTACK_OR_DEFEND as _TRAD
_DAME = T.id_of("Dame the Despoiler")
_HUGE = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
             and int(T.might[c]) >= 8 and not T.residual_text(c))

# Not Empowered: the trigger never reaches the Chain -- so the player is never
# asked to "choose a unit here" for an effect that would then fizzle.
s = fresh()
dame = s.add_permanent(_DAME, 0, bf_loc(0))
s.add_permanent(_HUGE, 1, bf_loc(0))
s.showdown_bf, s.showdown_combat, s.attacker = 0, 1, 0
chain.queue(s, _TRAD, dame, bf_loc(0))
chain.place(s, T, V1, 0)
if s.n_chain:
    die("dame", "828.1.d -- un-Empowered, the dependent trigger does not exist")
ok("un-Empowered, her trigger never reaches the Chain")

# Empowered: she rises to the biggest unit here, then +1.
s = fresh()
dame = s.add_permanent(_DAME, 0, bf_loc(0))
big = s.add_permanent(_HUGE, 1, bf_loc(0))
s.perms[dame, _P_EMP] = 1
s.set_flag(dame, _F_EMP)
s.showdown_bf, s.showdown_combat, s.attacker = 0, 1, 0
chain.queue(s, _TRAD, dame, bf_loc(0))
chain.place(s, T, V1, 0)
if not s.n_chain:
    die("dame", "Empowered, the trigger is put on the Chain")
for _ in range(10):
    if s.pend_slot >= 0:
        break
    _st = A.acting_seat(s)
    A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, _st)
                           if a.kind == A.A_PASS))
A.apply(s, T, V1, A.Action(A.A_TARGET, big))
drain(s, V1)
if combat.might(s, T, dame) != combat.might(s, T, big) + 1:
    die("dame", f"'increase my Might to its Might, then +1' -- expected "
                f"{combat.might(s, T, big) + 1}, got {combat.might(s, T, dame)}")
ok("...Empowered, she matches the chosen unit's Might and then goes one higher")

# "INCREASE to" only raises: a smaller choice leaves her at print, then +1.
s = fresh()
dame = s.add_permanent(_DAME, 0, bf_loc(0))
small = s.add_permanent(PLAIN2, 1, bf_loc(0))
s.perms[dame, _P_EMP] = 1
s.set_flag(dame, _F_EMP)
s.showdown_bf, s.showdown_combat, s.attacker = 0, 1, 0
_before = combat.might(s, T, dame)
chain.queue(s, _TRAD, dame, bf_loc(0))
chain.place(s, T, V1, 0)
for _ in range(10):
    if s.pend_slot >= 0:
        break
    _st = A.acting_seat(s)
    A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, _st)
                           if a.kind == A.A_PASS))
A.apply(s, T, V1, A.Action(A.A_TARGET, small))
drain(s, V1)
if combat.might(s, T, dame) != _before + 1:
    die("dame", "a smaller target does not SHRINK her -- 'increase' only raises")
ok("...and choosing something smaller never shrinks her -- just the +1")


# ---------------------------------------------------------------------------
print("\n['only while I'm at a battlefield'] an activation gate on the source")
_XER = T.id_of("Xerath - Freed")
_CAIT = T.id_of("Caitlyn - Patrolling")


def _activations(st, row):
    return [a for a in A.legal_actions(st, T, V1, 0) if a.kind == A.A_ACTIVATE
            and A.unpack_activate(int(a.arg))[0] == row]


s = fresh()
x = s.add_permanent(_XER, 0, base_loc(0))
s.add_permanent(PLAIN2, 1, bf_loc(0))
if _activations(s, x):
    die("at battlefield", "at base the ability is not offered")
s.set_location(x, bf_loc(0))
s.bf_ctrl[0] = 0
if not _activations(s, x):
    die("at battlefield", "at a battlefield it is")
ok("Xerath's ability is offered at a battlefield and withheld at base")

# Caitlyn: damage equal to HER effective Might, read at resolution.
s = fresh()
c = s.add_permanent(_CAIT, 0, bf_loc(0))
victim = s.add_permanent(T.id_of("Undertitan"), 1, bf_loc(0))
from rl.engine.state import P_MIGHT_MOD as _PMM3
s.perms[c, _PMM3] = 2                     # pumped before she fires
_want = combat.might(s, T, c)
A.apply(s, T, V1, _activations(s, c)[0])
A.apply(s, T, V1, A.Action(A.A_TARGET, victim))
drain(s, V1)
if int(s.perms[victim, P_DMG]) != _want:
    die("caitlyn", f"'damage equal to my Might' is her EFFECTIVE Might "
                   f"({_want}), got {int(s.perms[victim, P_DMG])}")
ok("Caitlyn deals damage equal to her effective Might, pumps included")

# ...and "I must be assigned combat damage last" is [Backline] as prose.
if not combat.perm_kw(s, T, c, "Backline"):
    die("caitlyn", "the reminder-only sentence grants [Backline]")
ok("...and her un-bracketed 'assigned combat damage last' is [Backline]")


# ---------------------------------------------------------------------------
print("\n[batch] enters ready, occupied enemy battlefields, and five statics")
from rl.engine.state import F_BUFFED as _FB
_DRAKE_H = T.id_of("Eager Drakehound")
_DIREWING = T.id_of("Direwing")
_DEADBLOOM = T.id_of("Deadbloom Predator")

s = fresh(hand=(_DRAKE_H,))
play(s, V1, 0, base_loc(0))
dh = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == _DRAKE_H)
if not int(s.perms[dh, P_READY]):
    die("enter ready", "'I enter ready.' overrides 359.2.c")
ok("'I enter ready' units enter ready")

s = fresh(hand=(_DIREWING,))
play(s, V1, 0, base_loc(0))
dw = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == _DIREWING)
if int(s.perms[dw, P_READY]):
    die("direwing", "with no other Dragon he enters exhausted")
s = fresh(hand=(_DIREWING,))
s.add_permanent(T.id_of("Ocean Drake"), 0, base_loc(0))
play(s, V1, 0, base_loc(0))
dw = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == _DIREWING)
if not int(s.perms[dw, P_READY]):
    die("direwing", "with another Dragon in play he enters ready")
ok("Direwing enters ready only if you already control another Dragon")

# 170.11.a -- OCCUPIED means a unit is present; ENEMY means they control it.
s = fresh(hand=(_DEADBLOOM,))
s.bf_ctrl[0] = 1
s.add_permanent(PLAIN2, 1, bf_loc(0))
s.bf_ctrl[1] = -1
s.add_permanent(PLAIN2, 1, bf_loc(1))          # enemy unit, nobody controls it
dests = A.play_destinations(s, T, V1, 0, _DEADBLOOM)
if bf_loc(0) not in dests:
    die("deadbloom", "an enemy-controlled battlefield with a unit is a destination")
if bf_loc(1) in dests:
    die("deadbloom", "an UNcontrolled battlefield is not an 'enemy battlefield'")
ok("Deadbloom Predator reaches an occupied ENEMY battlefield, not an uncontrolled one")

# Statics.
s = fresh()
we = s.add_permanent(T.id_of("Wizened Elder"), 0, base_loc(0))
_m = combat.might(s, T, we)
s.set_flag(we, _FB)
if combat.might(s, T, we) != _m + 2:
    die("wizened elder", "buffed: +1 from the Buff and +1 'additional'")
ok("Wizened Elder gains the Buff's +1 and an additional +1")

s = fresh()
my = s.add_permanent(T.id_of("Master Yi - Meditative"), 0, base_loc(0))
s.runes_ready[0, :] = 0
s.runes_ready[0, 0] = 7
_m = combat.might(s, T, my)
s.runes_spent[0, 1] = 1                         # an EXHAUSTED rune still counts
if combat.might(s, T, my) != _m + 4:
    die("master yi", "8 runes -- ready or exhausted -- turns on +4 Might")
ok("Master Yi - Meditative counts exhausted runes toward 8+")

s = fresh()
tr = s.add_permanent(T.id_of("Trusty Ramhound"), 0, bf_loc(0))
_m = combat.might(s, T, tr)
s.add_permanent(PLAIN2, 1, bf_loc(0))
if combat.might(s, T, tr) != _m:
    die("ramhound", "an ENEMY unit here is not 'another unit you have'")
s.add_permanent(PLAIN2, 0, bf_loc(0))
if combat.might(s, T, tr) != _m + 1:
    die("ramhound", "a friendly unit here turns on +1")
ok("Trusty Ramhound counts only YOUR other units here")

s = fresh()
ds = s.add_permanent(T.id_of("Draven, Showboat"), 0, base_loc(0))
_m = combat.might(s, T, ds)
s.points[0] = 3
if combat.might(s, T, ds) != _m + 3:
    die("showboat", "'My Might is increased by your points'")
ok("Draven, Showboat grows with his controller's score")

s = fresh()
gc = s.add_permanent(T.id_of("Garen - Commander"), 0, bf_loc(0))
here = s.add_permanent(PLAIN2, 0, bf_loc(0))
there = s.add_permanent(PLAIN2, 0, base_loc(0))
foe = s.add_permanent(PLAIN2, 1, bf_loc(0))
_base = int(T.might[PLAIN2])
if (combat.might(s, T, here), combat.might(s, T, there), combat.might(s, T, foe)) \
        != (_base + 1, _base, _base) or combat.might(s, T, gc) != int(T.might[T.id_of("Garen - Commander")]):
    die("garen", "+1 to OTHER FRIENDLY units HERE only")
ok("Garen - Commander pumps other friendly units at his location only")


# ---------------------------------------------------------------------------
print("\n[batch] Yasuo, Dropboarder, Jinx")
_YAS = T.id_of("Yasuo - Remorseful")
s = fresh()
y = s.add_permanent(_YAS, 0, bf_loc(0))
e = s.add_permanent(T.id_of("Undertitan"), 1, bf_loc(0))
s.showdown_bf, s.showdown_combat, s.attacker = 0, 1, 0
chain.queue(s, _TRAD, y, bf_loc(0))
chain.place(s, T, V1, 0)
for _ in range(10):
    if s.pend_slot >= 0:
        break
    A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, A.acting_seat(s))
                           if a.kind == A.A_PASS))
A.apply(s, T, V1, A.Action(A.A_TARGET, e))
# 359.3.f.2's own example: moved back to base in response, "here" no longer
# holds the target and the trigger mistargets.
s.set_location(y, base_loc(0))
drain(s, V1)
if int(s.perms[e, P_DMG]):
    die("yasuo", "moved to base before it resolved, 'here' no longer holds the "
                 "target -- the rulebook's example says it mistargets")
# The positive case, so the zero above cannot be a trigger that never resolved.
s = fresh()
y = s.add_permanent(_YAS, 0, bf_loc(0))
e = s.add_permanent(T.id_of("Undertitan"), 1, bf_loc(0))
s.showdown_bf, s.showdown_combat, s.attacker = 0, 1, 0
chain.queue(s, _TRAD, y, bf_loc(0))
chain.place(s, T, V1, 0)
for _ in range(10):
    if s.pend_slot >= 0:
        break
    A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, A.acting_seat(s))
                           if a.kind == A.A_PASS))
A.apply(s, T, V1, A.Action(A.A_TARGET, e))
_ymight = combat.might(s, T, y)
drain(s, V1)
if int(s.perms[e, P_DMG]) != _ymight and s.perms[e, P_ALIVE]:
    die("yasuo", f"left in place, he deals his Might ({_ymight}) to the target")
ok("Yasuo's trigger mistargets if he is moved away before it resolves (359.3.f.2)")

_DROP = T.id_of("Dropboarder")
for n_gear, want in ((1, 0), (2, 1)):
    s = fresh()
    for _ in range(n_gear):
        s.add_permanent(T.id_of("Treasure Trove"), 0, base_loc(0), is_unit=False)
    d = s.add_permanent(_DROP, 0, base_loc(0))
    s.perms[d, P_READY] = 0
    chain.fire(s, T, V1, TR_PLAY_ME, d)
    _drain_triggers(s, limit=10)
    if int(s.perms[d, P_READY]) != want:
        die("dropboarder", f"with {n_gear} gear, readied={want}")
ok("Dropboarder readies himself only with two or more gear")


# ---------------------------------------------------------------------------
print("\n[movement] a retreat is a Move -- and some units can't make one to base")
from rl.engine.state import F_NO_MOVE as _FNM

# Vex's "they can't move it this turn". The retreat offer never asked
# `can_move`, so a locked unit simply walked home out of the lock.
s = fresh()
u = s.add_permanent(PLAIN2, 0, bf_loc(0))
s.bf_ctrl[0] = 0
s.set_flag(u, _FNM)
if any(a.kind == A.A_RETREAT and a.arg == u for a in A.legal_actions(s, T, V1, 0)):
    die("retreat", "a unit that can't move this turn must not be offered a retreat")
ok("a move-locked unit is not offered a retreat (Vex's lock holds)")

# Determined Sentry: "I can't move to base."
s = fresh()
sentry = s.add_permanent(T.id_of("Determined Sentry"), 0, bf_loc(0))
other = s.add_permanent(PLAIN2, 0, bf_loc(0))
s.bf_ctrl[0] = 0
offered = {a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_RETREAT}
if sentry in offered or other not in offered:
    die("sentry", "only the Sentry is stopped from retreating")
ok("Determined Sentry cannot retreat, while his neighbour can")

# Minotaur Reckoner: "Units can't move to base" -- everyone's, both sides.
s = fresh()
s.add_permanent(T.id_of("Minotaur Reckoner"), 1, base_loc(1))
mine = s.add_permanent(PLAIN2, 0, bf_loc(0))
s.bf_ctrl[0] = 0
if any(a.kind == A.A_RETREAT for a in A.legal_actions(s, T, V1, 0)):
    die("reckoner", "an OPPONENT's Reckoner stops my units retreating too")
ok("Minotaur Reckoner stops every player's units moving to base")

# ...but a Recall is not a Move (456.1): losing a combat still sends them home.
s.showdown_bf, s.showdown_combat, s.attacker = 0, 1, 0
s.add_permanent(PLAIN2, 1, bf_loc(0))
combat.resolution_step(s, T, V1, 0, 0, {})
if int(s.perms[mine, P_LOC]) != base_loc(0):
    die("reckoner", "456.1 -- a Recall is not a Move, so the attacker is still "
                    "recalled after a combat it did not win")
ok("...but a Recall is not a Move, so combat still recalls attackers")


# ---------------------------------------------------------------------------
print("\n[349] a unit played BY AN EFFECT is still played -- and 'enters ready' grants")
_SM = T.id_of("Spectral Matron")
_DHK = T.id_of("Eager Drakehound")


def _run_all(st, limit=20):
    for _ in range(limit):
        seat = A.acting_seat(st)
        if seat < 0 or (not st.n_chain and not st.n_trig and st.pend_slot < 0
                        and st.pend_may < 0):
            return
        L = A.legal_actions(st, T, V1, seat)
        pick = (next((a for a in L if a.kind == A.A_ACCEPT), None)
                or next((a for a in L if a.kind == A.A_TARGET), None)
                or next(a for a in L if a.kind in (A.A_PASS, A.A_ORDER)))
        A.apply(st, T, V1, pick)


# Spectral Matron replays Eager Drakehound ("I enter ready") from the trash.
# This used to add the permanent and stop: it entered exhausted and was never
# counted as played.
s = fresh()
s.trash[0, 0] = _DHK
s.n_trash[0] = 1
m = s.add_permanent(_SM, 0, base_loc(0))
_played = int(s.cards_played[0])
chain.fire(s, T, V1, TR_PLAY_ME, m)
_run_all(s)
dh = [i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == _DHK]
if not dh:
    die("trash play", "the unit is replayed from the trash")
if not int(s.perms[dh[0], P_READY]):
    die("trash play", "its own 'I enter ready' applies when an effect plays it")
if int(s.cards_played[0]) != _played + 1:
    die("trash play", "349 -- it was PLAYED, so it counts toward [Legion]")
ok("a unit replayed from the trash honours 'I enter ready' and counts as played")

# Magma Wurm: "Other friendly units enter ready."
s = fresh(hand=(PLAIN2,))
s.add_permanent(T.id_of("Magma Wurm"), 0, base_loc(0))
play(s, V1, 0, base_loc(0))
p2 = [i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == PLAIN2]
if not int(s.perms[p2[0], P_READY]):
    die("magma wurm", "a friendly unit played while he stands enters ready")
ok("Magma Wurm makes your other units enter ready")

# Renata Glasc - Industrialist: "Your tokens enter ready." -- token UNITS.
from rl.engine.effects import CardSpec as _CSR, Op as _OpR, OP_CREATE_TOKEN as _OCT, SPEED_MAIN as _SMR
s = fresh()
s.add_permanent(T.id_of("Renata Glasc - Industrialist"), 0, base_loc(0))
_rsv2.resolve(s, T, V1, _CSR(speed=_SMR, ops=(_OpR(_OCT, target=-1, n=1,
              token="Sand Soldier"),)), 0, [], -1, False)
tok = [i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == T.id_of("Sand Soldier")]
if not tok or not int(s.perms[tok[0], P_READY]):
    die("renata", "a token unit made while she stands enters ready")
ok("Renata Glasc - Industrialist makes your token units enter ready")


# ---------------------------------------------------------------------------
print("\n[batch 4] sweeps, promises, discounts, and 'here'")
from rl.engine import cost as _cost4
_ANG = T.id_of("Angler Beast")

s = fresh()
a = s.add_permanent(_ANG, 0, base_loc(0))
small_mine = s.add_permanent(PLAIN2, 0, bf_loc(0))
small_theirs = s.add_permanent(PLAIN2, 1, bf_loc(0))
pumped = s.add_permanent(PLAIN2, 1, bf_loc(1))
from rl.engine.state import P_MIGHT_MOD as _PMM4
s.perms[pumped, _PMM4] = 1                      # 3 Might now: out of range
gear = s.add_permanent(T.id_of("Iron Ballista"), 1, base_loc(1), is_unit=False)
chain.fire(s, T, V1, TR_PLAY_ME, a)
_drain_triggers(s, limit=10)
if s.perms[small_mine, P_ALIVE] or s.perms[small_theirs, P_ALIVE]:
    die("angler", "every player's 2-Might unit returns")
if not s.perms[pumped, P_ALIVE] or not s.perms[gear, P_ALIVE] or not s.perms[a, P_ALIVE]:
    die("angler", "a unit pumped past 2, a gear, and the 5-Might Beast all stay")
ok("Angler Beast bounces every 2-or-less unit by EFFECTIVE Might, and no gear")

# Confront: a promise held on the player for the rest of the turn.
_CONF = T.id_of("Confront")
s = fresh(hand=(_CONF, PLAIN2))
A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, 0)
                       if a.kind == A.A_PLAY and int(s.hand[0, a.arg]) == _CONF))
drain(s, V1)
play(s, V1, next(i for i in range(int(s.n_hand[0])) if int(s.hand[0, i]) == PLAIN2),
     base_loc(0))
u = [i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == PLAIN2]
if not u or not int(s.perms[u[0], P_READY]):
    die("confront", "a unit played after Confront this turn enters ready")
phases.end_turn(s, V1)
s.active = 0
if combat.granted_enters_ready(s, T, 0, PLAIN2):
    die("confront", "'this turn' -- the promise expires with the turn")
ok("Confront readies units played later that turn, and only that turn")

# Battering Ram: {1} less per card played this turn, floored at 1.
_RAM = T.id_of("Battering Ram")
s = fresh()
_full = _cost4.effective_energy(s, T, 0, _RAM)
s.cards_played[0] = 2
if _cost4.effective_energy(s, T, 0, _RAM) != _full - 2:
    die("battering ram", "two cards played -> {2 energy} less")
s.cards_played[0] = 50
if _cost4.effective_energy(s, T, 0, _RAM) != 1:
    die("battering ram", "'to a minimum of {1 energy}'")
ok("Battering Ram costs {1} less per card played this turn, never below 1")

# Herald of Scales: your DRAGONS cost {2} less, min 1 -- and nothing else.
s = fresh()
s.add_permanent(T.id_of("Herald of Scales"), 0, base_loc(0))
_drag, _non = T.id_of("Ocean Drake"), T.id_of("Undertitan")
if _cost4.effective_energy(s, T, 0, _drag) != int(T.energy[_drag]) - 2:
    die("herald", "a Dragon costs {2 energy} less")
if _cost4.effective_energy(s, T, 0, _non) != int(T.energy[_non]):
    die("herald", "a non-Dragon is unaffected")
if _cost4.effective_energy(s, T, 1, _drag) != int(T.energy[_drag]):
    die("herald", "'YOUR Dragons' -- the opponent's are not discounted")
ok("Herald of Scales discounts your Dragons only")

# Nasus: an ENEMY unit dying HERE, once each turn.
_NAS = T.id_of("Nasus, Guardian of Knowledge")
s = fresh()
n = s.add_permanent(_NAS, 0, bf_loc(0))
there = s.add_permanent(PLAIN2, 1, bf_loc(1))
combat.destroy(s, T, there)
if n in [int(s.trig[i, 1]) for i in range(int(s.n_trig))]:
    die("nasus", "an enemy dying at ANOTHER battlefield is not 'here'")
here1 = s.add_permanent(PLAIN2, 1, bf_loc(0))
here2 = s.add_permanent(PLAIN2, 1, bf_loc(0))
combat.destroy(s, T, here1)
combat.destroy(s, T, here2)
if [int(s.trig[i, 1]) for i in range(int(s.n_trig))].count(n) != 1:
    die("nasus", "once each turn -- two deaths here fire it once")
ok("Nasus fires for an enemy dying HERE, once each turn")


# ---------------------------------------------------------------------------
print("\n['this turn'] stamps are per PLAYER turn (ply), not per round (turn)")
# `state.turn` only advances when the second seat ends, so it names a ROUND.
# Keyed on it, "once each turn" covered the opponent's following turn as well.
# This checks the real turn boundary, through `end_turn`, rather than bumping a
# counter by hand -- bumping `turn` is exactly how the old tests encoded the bug.
_NAS2 = T.id_of("Nasus, Guardian of Knowledge")
s = fresh()
s.active = 0
n = s.add_permanent(_NAS2, 0, bf_loc(0))
v1 = s.add_permanent(PLAIN2, 1, bf_loc(0))
combat.destroy(s, T, v1)                       # seat 0's turn: fires, stamps
s.n_trig = 0
phases.end_turn(s, V1)                         # -> seat 1's turn, SAME round
if int(s.turn) != 1 or int(s.active) != 1:
    die("ply", "fixture: seat 1's turn in the same round")
v2 = s.add_permanent(PLAIN2, 1, bf_loc(0))
combat.destroy(s, T, v2)
if n not in [int(s.trig[i, 1]) for i in range(int(s.n_trig))]:
    die("ply", "'once EACH TURN' re-arms on the opponent's turn; keyed on the "
               "round counter it stayed spent through their whole turn")
ok("'once each turn' re-arms on the opponent's turn in the same round")

# Brutalizer's "attached this turn" ends with THIS player's turn.
s = fresh()
s.active = 0
u = s.add_permanent(PLAIN2, 0, bf_loc(0))
b = s.add_permanent(T.id_of("Brutalizer"), 0, bf_loc(0), is_unit=False)
s.attach(b, u)
_with = combat.might(s, T, u)
phases.end_turn(s, V1)                         # opponent's turn, same round
if combat.might(s, T, u) != _with - 2:
    die("ply", "'attached THIS turn' -- on the opponent's turn the +2 is gone")
ok("Brutalizer's 'attached this turn' ends with the player's own turn")


# ---------------------------------------------------------------------------
print("\n[batch 5] partitions, a count of statuses, tags, and an uncounterable spell")
from rl.engine.state import F_STUNNED as _FST, F_BUFFED as _FBF

_CHIEF = T.id_of("Solari Chief")
for stunned in (True, False):
    s = fresh()
    c = s.add_permanent(_CHIEF, 0, base_loc(0))
    e = s.add_permanent(PLAIN2, 1, bf_loc(0))
    if stunned:
        s.stun(e)
    chain.fire(s, T, V1, TR_PLAY_ME, c)
    for _ in range(12):
        if s.pend_slot >= 0:
            break
        A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, A.acting_seat(s))
                               if a.kind in (A.A_PASS, A.A_ORDER)))
    A.apply(s, T, V1, A.Action(A.A_TARGET, e))
    drain(s, V1)
    if stunned and s.perms[e, P_ALIVE]:
        die("solari chief", "a STUNNED enemy is killed")
    if not stunned and (not s.perms[e, P_ALIVE]
                        or not (int(s.perms[e, P_FLAGS]) & _FST)):
        die("solari chief", "an unstunned enemy is stunned, not killed")
ok("Solari Chief kills a stunned enemy and stuns an unstunned one -- never both")

_SETT = T.id_of("Sett - Kingpin")
s = fresh()
st = s.add_permanent(_SETT, 0, bf_loc(0))
b1 = s.add_permanent(PLAIN2, 0, bf_loc(0))
b2 = s.add_permanent(PLAIN2, 0, bf_loc(1))
_m0 = combat.might(s, T, st)
s.set_flag(b1, _FBF)
s.set_flag(b2, _FBF)                      # buffed, but at ANOTHER battlefield
if combat.might(s, T, st) != _m0 + 1:
    die("sett", "+1 per buffed friendly unit at HIS battlefield only")
ok("Sett - Kingpin counts buffed friendly units at his battlefield, by status")

s = fresh()
bm = s.add_permanent(T.id_of("Breakneck Mech"), 0, base_loc(0))
mech = s.add_permanent(T.id_of("Mech"), 0, bf_loc(0))
plain = s.add_permanent(PLAIN2, 0, bf_loc(0))
if not combat.perm_kw(s, T, mech, "Ganking") or combat.perm_kw(s, T, plain, "Ganking"):
    die("breakneck", "'your MECHS have [Ganking]' -- the Mech does, a plain unit does not")
ok("Breakneck Mech grants its keywords to your Mechs and nobody else")

# ---------------------------------------------------------------------------
print("\n[XP/Buff] XP gains, the gained-this-turn stamp, and buff payoffs")

from rl.engine.effects import (TR_CONQUER as _TRC, TR_PLAY_ME as _TRP)
from rl.engine.state import F_BUFFED as _FB, P_FLAGS as _PF


def _to_decision(s):
    """Pass/order until a target or may-decision is open (or all is done)."""
    for _ in range(40):
        if s.pend_slot >= 0 or s.pend_may >= 0:
            return True
        if s.n_chain == 0 and s.n_trig == 0:
            return False
        who = A.acting_seat(s)
        legal = A.legal_actions(s, T, V1, who)
        if s.n_trig and not any(a.kind == A.A_ORDER for a in legal):
            chain_mod.place(s, T, V1, 0)       # queued outside an action
            continue
        A.apply(s, T, V1, next(a for a in legal
                               if a.kind in (A.A_PASS, A.A_ORDER)))
    return False


def _settle(s):
    """`drain_all`, but a QUEUED trigger is placed (A_ORDER) rather than
    passed over -- passing with a trigger in the queue ends the turn."""
    for _ in range(60):
        if s.n_chain == 0 and s.n_trig == 0 and s.pend_slot < 0 \
                and s.pend_may < 0:
            return
        who = A.acting_seat(s)
        if who < 0:
            return
        legal = A.legal_actions(s, T, V1, who)
        if s.n_trig and not any(a.kind == A.A_ORDER for a in legal):
            # Queued directly by the test, outside an action: nothing has
            # offered the placement yet.
            chain_mod.place(s, T, V1, 0)
            continue
        A.apply(s, T, V1, next((a for a in legal if a.kind == A.A_ORDER),
                               next((a for a in legal if a.kind == A.A_PASS),
                                    legal[0])))


def _buffed(s, r):
    return bool(int(s.perms[r, _PF]) & _FB)


ROOT = T.id_of("Mister Root")
for dest, want in ((bf_loc(0), 2), (base_loc(0), 0)):
    s = fresh()
    r = s.add_permanent(ROOT, 0, bf_loc(1) if dest == base_loc(0) else base_loc(0))
    frm = int(s.perms[r, P_LOC])
    s.set_location(r, dest)
    combat.queue_move_trigger(s, T, r, frm, dest)
    _settle(s)
    if int(s.xp[0]) != want:
        die("mister root", f"move to {dest}: want {want} XP, got {int(s.xp[0])}")
ok("Mister Root gains 2 XP moving to a battlefield, nothing moving to base")

s = fresh()
snap = s.add_permanent(T.id_of("Vicious Snapjaws"), 0, base_loc(0))
f = s.add_permanent(PLAIN2, 0, base_loc(0))
e = s.add_permanent(PLAIN2, 1, base_loc(1))
combat.destroy(s, T, e)
_settle(s)
if int(s.xp[0]) != 0:
    die("snapjaws", "an ENEMY death gains nothing")
combat.destroy(s, T, f)
_settle(s)
if int(s.xp[0]) != 1:
    die("snapjaws", "another friendly unit dying gains 1 XP")
ok("Vicious Snapjaws gains XP when another FRIENDLY unit dies")

SERG = T.id_of("Scrutinizing Sergeant")
NEWT = T.id_of("Wily Newtfish")
s = fresh(hand=[SERG], runes=12)
nw = s.add_permanent(NEWT, 0, base_loc(0))
s.add_permanent(PLAIN2, 0, base_loc(0))
s.add_permanent(PLAIN2, 1, base_loc(1))
m0 = combat.might(s, T, nw)
if combat.perm_kw(s, T, nw, "Ganking"):
    die("newtfish", "no XP gained yet -> no Ganking")
play(s, V1, 0, base_loc(0))
_settle(s)
if int(s.xp[0]) != 3:
    die("sergeant", f"Newtfish + plain + Sergeant = 3 friendly units, got {int(s.xp[0])} XP")
if combat.might(s, T, nw) != m0 + 1 or not combat.perm_kw(s, T, nw, "Ganking"):
    die("newtfish", "XP gained this turn -> +1 Might and Ganking")
s.ply += 1
if combat.might(s, T, nw) != m0 or combat.perm_kw(s, T, nw, "Ganking"):
    die("newtfish", "the stamp is per turn -- next turn it is gone")
ok("Scrutinizing Sergeant counts friendly units (itself too); Wily Newtfish reads this turn's gain")

POPPY = T.id_of("Poppy - Paragon")
for near in (True, False):
    s = fresh()
    p = s.add_permanent(POPPY, 0, base_loc(0), ready=False)
    s.points[1] = s.victory_score - 3 if near else s.victory_score - 4
    chain.fire(s, T, V1, _TRP, p)
    _settle(s)
    if near != (int(s.xp[0]) == 3 and int(s.perms[p, P_READY]) == 1):
        die("poppy", f"near={near}: xp={int(s.xp[0])} ready={int(s.perms[p, P_READY])}")
ok("Poppy - Paragon readies and gains 3 XP only when an opponent is within 3")

ROSE = T.id_of("Blood Rose")
s = fresh(hand=[PLAIN2])
rose = s.add_permanent(ROSE, 0, base_loc(0))
play(s, V1, 0, base_loc(0))
if not _to_decision(s) or s.pend_may < 0:
    die("blood rose", "playing a unit offers the optional {1} for 1 XP")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_settle(s)
if int(s.xp[0]) != 1:
    die("blood rose", "accepting pays and gains 1 XP")
s.xp[0] = 2
tired = s.add_permanent(PLAIN2, 0, base_loc(0), ready=False)
if any(a.kind == A.A_ACTIVATE for a in A.legal_actions(s, T, V1, 0)):
    die("blood rose", "2 XP cannot pay 'Spend 3 XP'")
s.xp[0] = 3
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("blood rose", "3 XP and a ready Rose -> the ability is offered")
A.apply(s, T, V1, acts[0])
if _to_decision(s) and s.pend_slot >= 0:
    A.apply(s, T, V1, A.Action(A.A_TARGET, tired))
_settle(s)
if int(s.xp[0]) != 0 or int(s.perms[tired, P_READY]) != 1 or int(s.perms[rose, P_READY]):
    die("blood rose", "spent 3 XP, exhausted the Rose, readied the unit")
ok("Blood Rose sells XP for {1} on unit plays and spends 3 XP to ready a unit")

s, w = played(T.id_of("Cithria of Cloudfield"), PLAIN2)
if not _buffed(s, w):
    die("cithria", "playing another unit buffs her")
ok("Cithria of Cloudfield buffs herself when you play another unit")

s = fresh()
monk = s.add_permanent(T.id_of("Kinkou Monk"), 0, base_loc(0))
u1 = s.add_permanent(PLAIN2, 0, base_loc(0))
u2 = s.add_permanent(PLAIN2, 0, bf_loc(0))
chain.fire(s, T, V1, _TRP, monk)
for u in (u1, u2):
    if not _to_decision(s):
        break
    if monk in [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]:
        die("kinkou monk", "'OTHER friendly units' -- never himself")
    A.apply(s, T, V1, A.Action(A.A_TARGET, u))
_settle(s)
if not (_buffed(s, u1) and _buffed(s, u2)) or _buffed(s, monk):
    die("kinkou monk", "buffs the two chosen others")
ok("Kinkou Monk buffs up to two other friendly units")

PEAK = T.id_of("Peak Guardian")
for at_bf in (True, False):
    loc = bf_loc(0) if at_bf else base_loc(0)
    s = fresh()
    g = s.add_permanent(PEAK, 0, loc)
    fr = s.add_permanent(PLAIN2, 0, loc)
    en = s.add_permanent(PLAIN2, 1, loc)
    chain.fire(s, T, V1, _TRP, g)
    _settle(s)
    if not _buffed(s, g) or _buffed(s, en) or _buffed(s, fr) != at_bf:
        die("peak guardian", f"at_bf={at_bf}: self={_buffed(s, g)} "
                             f"friend={_buffed(s, fr)} enemy={_buffed(s, en)}")
ok("Peak Guardian buffs itself, then other FRIENDLY units only at a battlefield")

HERDER = T.id_of("Poro Herder")
for poro in (True, False):
    s = fresh()
    h = s.add_permanent(HERDER, 0, base_loc(0))
    if poro:
        s.add_permanent(T.id_of("Lonely Poro"), 0, base_loc(0))
    else:
        s.add_permanent(T.id_of("Lonely Poro"), 1, base_loc(1))  # theirs
    hand0 = int(s.n_hand[0])
    chain.fire(s, T, V1, _TRP, h)
    _settle(s)
    if _buffed(s, h) != poro or (int(s.n_hand[0]) - hand0 == 1) != poro:
        die("poro herder", f"poro={poro}")
ok("Poro Herder buffs and draws only if YOU control a Poro")

SETT = T.id_of("Sett, Brawler")
s = fresh()
st_ = s.add_permanent(SETT, 0, base_loc(0))
if any(a.kind == A.A_ACTIVATE for a in A.legal_actions(s, T, V1, 0)):
    die("sett brawler", "no buff -> nothing to spend")
chain.fire(s, T, V1, _TRP, st_)
_settle(s)
m_b = combat.might(s, T, st_)
if not _buffed(s, st_) or m_b != int(T.might[SETT]) + 1:
    die("sett brawler", "play buffs him")
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("sett brawler", "buffed -> spend offered")
A.apply(s, T, V1, acts[0])
_settle(s)
if _buffed(s, st_) or combat.might(s, T, st_) != int(T.might[SETT]) + 4:
    die("sett brawler", f"buff spent, +4 this turn: might={combat.might(s, T, st_)}")
chain.fire(s, T, V1, _TRC, st_, bf_loc(0))
_settle(s)
if not _buffed(s, st_):
    die("sett brawler", "conquering buffs him again")
ok("Sett, Brawler buffs on play and conquer, and spends the buff for +4 Might")

ADAPT = T.id_of("Adaptatron")
for kill in (True, False):
    s = fresh()
    ad = s.add_permanent(ADAPT, 0, bf_loc(0))
    s.bf_ctrl[0] = 0          # already his, so Cleanup does not conquer AGAIN
    gear = s.add_permanent(ROSE, 1, base_loc(1))
    chain.fire(s, T, V1, _TRC, ad, bf_loc(0))
    if _to_decision(s) and s.pend_slot >= 0:
        # 355.14 -- an optional slot is declined with a TARGET of -1.
        A.apply(s, T, V1, A.Action(A.A_TARGET, gear if kill else -1))
    _settle(s)
    if _buffed(s, ad) != kill or bool(s.perms[gear, P_ALIVE]) == kill:
        die("adaptatron", f"kill={kill}: buffed={_buffed(s, ad)}")
ok("Adaptatron buffs only if it actually killed a gear")

HELM = T.id_of("Vanguard Helm")
for buffed in (True, False):
    s = fresh()
    s.add_permanent(HELM, 0, base_loc(0))
    dying = s.add_permanent(PLAIN2, 0, base_loc(0))
    other = s.add_permanent(PLAIN2, 0, base_loc(0))
    if buffed:
        s.set_flag(dying, _FB)
    combat.destroy(s, T, dying)
    if _to_decision(s) and s.pend_slot >= 0:
        A.apply(s, T, V1, A.Action(A.A_TARGET, other))
    _settle(s)
    if _buffed(s, other) != buffed:
        die("vanguard helm", f"dying buffed={buffed}: other buffed={_buffed(s, other)}")
ok("Vanguard Helm answers only a BUFFED friendly unit's death")

# ---------------------------------------------------------------------------
print("\n[batch 7] stun watchers, optional exhausts, opponent's-turn plays, "
      "an Equipment's Deathknell")

from rl.engine import resolve as _rsv
from rl.engine.effects import (SPECS as _SPECS, TR_PLAY_SPELL as _TRPS,
                               TR_CHOSEN as _TRCH, TR_COMBAT_ENDS as _TRCE,
                               TR_ATTACK_OR_DEFEND as _TRAD,
                               CardSpec as _CS, TargetSpec as _TS, Op as _Op,
                               OP_STUN as _OPSTUN, W_ENEMY as _WE,
                               W_FRIENDLY as _WF)
from rl.engine.state import (F_DAMAGED_TURN as _FDT, C_UID as _CUID,
                             P_DMG as _PDMG, P_MIGHT_MOD as _PMM)
from rl.engine.cost import energy_discounts as _edisc

_STUN_SPEC = _CS(speed=0, targets=(_TS(who=_WE),), ops=(_Op(_OPSTUN, target=0),))

s = fresh()
hz = s.add_permanent(T.id_of("Eclipse Herald"), 0, base_loc(0), ready=False)
en = s.add_permanent(PLAIN2, 1, base_loc(1))
m_h = combat.might(s, T, hz)
_rsv.resolve(s, T, V1, _STUN_SPEC, 0, [en], -1, True)
_settle(s)
if int(s.perms[hz, P_READY]) != 1 or combat.might(s, T, hz) != m_h + 1:
    die("eclipse herald", "stunning an enemy readies him and gives +1")
s.perms[hz, P_READY] = 0
_rsv.resolve(s, T, V1, _STUN_SPEC, 0, [en], -1, True)   # already stunned
_settle(s)
if int(s.perms[hz, P_READY]) != 0:
    die("eclipse herald", "a redundant stun is not an event (423.1.a.1)")
ok("Eclipse Herald fires on a real stun of an enemy, never on a redundant one")

VIK = T.id_of("Viktor, Innovator")
for opp in (True, False):
    s = fresh()
    s.add_permanent(VIK, 0, base_loc(0))
    s.active = s.priority = 1 if opp else 0
    n0 = int(s.n_perms)
    s.cards_played[0] += 1
    chain_mod.card_played(s, T, 0)
    _settle(s)
    made = int(s.n_perms) - n0
    if made != (1 if opp else 0):
        die("viktor innovator", f"opp_turn={opp}: made {made} Recruits")
ok("Viktor, Innovator makes a Recruit for a card played on the OPPONENT's turn only")

CASK = T.id_of("Chemtech Cask")
for opp, ready in ((True, True), (True, False), (False, True)):
    s = fresh()
    s.active = s.priority = 1 if opp else 0
    ck = s.add_permanent(CASK, 0, base_loc(0), ready=ready)
    n0 = int(s.n_perms)
    chain_mod.queue(s, _TRPS, ck, base_loc(0))
    asked = _to_decision(s) and s.pend_may >= 0
    if asked != opp:
        die("chemtech cask", f"opp={opp}: asked={asked}")
    if asked:
        kinds = {a.kind for a in A.legal_actions(s, T, V1, 0)}
        if (A.A_ACCEPT in kinds) != ready:
            die("chemtech cask", "accept is offered exactly when it can exhaust")
        A.apply(s, T, V1, A.Action(A.A_ACCEPT if ready else A.A_DECLINE))
    _settle(s)
    if opp and ready and (int(s.n_perms) != n0 + 1 or int(s.perms[ck, P_READY])):
        die("chemtech cask", "accepting exhausts it and makes a Gold")
ok("Chemtech Cask asks only on the opponent's turn, and only offers what it can pay")

LUX = T.id_of("Lux - Illuminated")
for spell, want in (("Progress Day", 3), ("Dredge Up", 0)):
    s = fresh(hand=[T.id_of(spell)], runes=10)
    lx = s.add_permanent(LUX, 0, base_loc(0))
    m0 = combat.might(s, T, lx)
    A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
    _settle(s)
    if combat.might(s, T, lx) - m0 != want:
        die("lux", f"{spell}: +{combat.might(s, T, lx) - m0}, want +{want}")
ok("Lux - Illuminated grows only for a spell costing {5 energy} or more")

BEANS = T.id_of("Fresh Beans")
for sd in (True, False):
    s = fresh()
    fb = s.add_permanent(BEANS, 0, base_loc(0))
    u = s.add_permanent(PLAIN2, 0, bf_loc(0))
    s.showdown_bf = 0 if sd else -1
    chain_mod.fire_play_unit(s, T, 0, PLAIN2, u)
    if int(s.n_trig) != (1 if sd else 0):
        die("fresh beans", f"showdown={sd}: queued {int(s.n_trig)}")
    s.showdown_bf = -1
    h0 = int(s.n_hand[0])
    if sd:
        _to_decision(s)
        A.apply(s, T, V1, A.Action(A.A_ACCEPT))
        _settle(s)
        if int(s.n_hand[0]) != h0 + 1 or int(s.perms[fb, P_READY]):
            die("fresh beans", "accepting exhausts it and draws 1")
ok("Fresh Beans watches unit plays during a showdown only")

WHEEL = T.id_of("Spirit Wheel")
for kind in ("unit", "gear"):
    s = fresh()
    wh = s.add_permanent(WHEEL, 0, base_loc(0))
    subj = s.add_permanent(PLAIN2 if kind == "unit" else ROSE, 0, base_loc(0))
    chain_mod.fire_watchers(s, T, 0, _TRCH, subj=subj)
    if int(s.n_trig) != (1 if kind == "unit" else 0):
        die("spirit wheel", f"choosing a friendly {kind}: queued {int(s.n_trig)}")
    if kind == "unit":
        e0 = int(s.runes_ready[0].sum())
        h0 = int(s.n_hand[0])
        _to_decision(s)
        A.apply(s, T, V1, A.Action(A.A_ACCEPT))
        _settle(s)
        if (int(s.n_hand[0]) != h0 + 1 or int(s.perms[wh, P_READY])
                or int(s.runes_ready[0].sum()) != e0 - 1):
            die("spirit wheel", "pays {1}, exhausts, draws 1")
ok("Spirit Wheel pays {1} and exhausts to draw when a friendly UNIT is chosen")

for hurt in (False, True):
    s = fresh()
    ap = s.add_permanent(T.id_of("Affectionate Poro"), 0, bf_loc(0))
    if hurt:
        s.set_flag(ap, _FDT)
    h0 = int(s.n_hand[0])
    chain_mod.queue(s, _TRCE, ap, bf_loc(0))
    _settle(s)
    if (int(s.n_hand[0]) - h0 == 1) == hurt:
        die("affectionate poro", f"hurt={hurt}")
s = fresh()
u = s.add_permanent(PLAIN2, 1, base_loc(1))
combat.mark_damage(s, T, u, 1)
s.perms[u, P_DMG] = 0                                    # healed again
if not int(s.perms[u, _PF]) & _FDT:
    die("affectionate poro", "marking damage records it for the turn, heal or not")
ok("Affectionate Poro draws after combat only if it was not dealt damage this turn")

s = fresh()
demo = s.add_permanent(T.id_of("Noxian Demolitionist"), 0, bf_loc(0))
cheap = s.add_permanent(ROSE, 1, base_loc(1))                     # 1 energy
dear = s.add_permanent(T.id_of("Vanguard Helm"), 1, base_loc(1))  # 2 energy
spec = abilities_for(T, T.id_of("Noxian Demolitionist"))[0]
opts = _rsv.legal_targets(s, T, spec, 0, 0, [], -1, source=demo)
if cheap not in opts or dear in opts:
    die("demolitionist", f"cap is his Might (1): offered {opts}")
s.perms[demo, _PMM] = 1                                           # now 2 Might
if dear not in _rsv.legal_targets(s, T, spec, 0, 0, [], -1, source=demo):
    die("demolitionist", "the cap is his EFFECTIVE Might")
ok("Noxian Demolitionist can reach only gear costing no more than his Might")

CHAL = T.id_of("Imposing Challenger")
BIG = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
           and not T.residual_text(c) and int(T.might[c]) >= int(T.might[CHAL]))
s = fresh()
ch = s.add_permanent(CHAL, 0, bf_loc(0))
small = s.add_permanent(PLAIN2, 1, bf_loc(0))
big = s.add_permanent(BIG, 1, bf_loc(0))
combat.queue_move_trigger(s, T, ch, base_loc(0), bf_loc(0))
if not _to_decision(s) or s.pend_may < 0:
    die("imposing challenger", "an eligible enemy -> the 'may' is asked")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
offered = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
if small not in offered or big in offered:
    die("imposing challenger", f"only LESS Might than him: {offered}")
A.apply(s, T, V1, A.Action(A.A_TARGET, small))
dests = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
if dests != [bf_loc(1)]:
    die("imposing challenger", f"a DIFFERENT battlefield only: {dests}")
A.apply(s, T, V1, A.Action(A.A_TARGET, bf_loc(1)))
_settle(s)
if int(s.perms[small, P_LOC]) != bf_loc(1):
    die("imposing challenger", "the smaller enemy is moved away")
ok("Imposing Challenger moves a smaller enemy from here to a different battlefield")

s = fresh()
fp = s.add_permanent(T.id_of("Fae Porter"), 0, bf_loc(0))
pal = s.add_permanent(PLAIN2, 0, base_loc(0))
combat.queue_move_trigger(s, T, fp, base_loc(0), bf_loc(0))
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_TARGET, pal))
_settle(s)
if int(s.perms[pal, P_LOC]) != bf_loc(0):
    die("fae porter", "the friendly unit joins him at the battlefield")
ok("Fae Porter pays {Chaos} to bring a friendly unit to his battlefield")

MONCH = T.id_of("Monch")
for stunned in (True, False):
    s = fresh()
    e = s.add_permanent(PLAIN2, 1, base_loc(1))
    if stunned:
        s.stun(e)
    disc = sum(a for a, _f in _edisc(s, T, 0, MONCH))
    rdy = combat.permanent_enters_ready(s, T, 0, MONCH, True)
    if (disc == 2) != stunned or rdy != stunned:
        die("monch", f"stunned={stunned}: discount={disc} ready={rdy}")
ok("Monch costs {2} less and enters ready while an opponent controls a stunned unit")

# Staged at a BASE: at a battlefield the Cleanup after resolution would open
# a real combat and its Resolution Step would heal the 2 away before the check.
s = fresh()
host = s.add_permanent(PLAIN2, 0, base_loc(0))
bow = s.add_permanent(T.id_of("Recurve Bow"), 0, base_loc(0))
s.attach(bow, host)
foe = s.add_permanent(BIG, 1, base_loc(0))
chain_mod.queue(s, _TRAD, host, base_loc(0), subj=host)
if _to_decision(s) and s.pend_slot >= 0:
    A.apply(s, T, V1, A.Action(A.A_TARGET, foe))
_settle(s)
if int(s.perms[foe, _PDMG]) != 2:
    die("recurve bow", f"the unit it is attached to deals 2: dmg={int(s.perms[foe, _PDMG])}")
ok("Recurve Bow's attack trigger is the attached unit's, dealing 2 to an enemy there")

s = fresh()
host = s.add_permanent(PLAIN2, 0, base_loc(0))
shears = s.add_permanent(T.id_of("Sacred Shears"), 0, base_loc(0))
s.attach(shears, host)
h0 = int(s.n_hand[0])
combat.destroy(s, T, host)
_settle(s)
if int(s.n_hand[0]) != h0 + 1:
    die("sacred shears", "the equipped unit's Deathknell draws 1 even though "
                         "719.5 detached the gear as it died")
if not s.perms[shears, P_ALIVE] or s.is_attached(shears):
    die("sacred shears", "the gear stays on the board, unattached")
h1 = int(s.n_hand[0])
combat.destroy(s, T, s.add_permanent(PLAIN2, 0, base_loc(0)))
_settle(s)
if int(s.n_hand[0]) != h1:
    die("sacred shears", "an UNattached Shears gives nobody a Deathknell")
ok("Sacred Shears' Deathknell survives the detach 719.5 performs at death")

SHROUD = _SPECS["Twilight Shroud"]
s = fresh()
mine = s.add_permanent(PLAIN2, 0, base_loc(0))
_rsv.resolve(s, T, V1, SHROUD, 0, [mine], -1, True)
if mine in _rsv.legal_targets(s, T, _STUN_SPEC, 0, 1, [], -1):
    die("twilight shroud", "enemy spells cannot choose it this turn")
own = _CS(speed=0, targets=(_TS(who=_WF),), ops=(_Op(_OPSTUN, target=0),))
if mine not in _rsv.legal_targets(s, T, own, 0, 0, [], -1):
    die("twilight shroud", "...its own controller still can")
ok("Twilight Shroud makes a unit unchoosable by ENEMY spells for the turn")

ISO = _SPECS["Isolate"]
for extra in (False, True):
    s = fresh()
    a1 = s.add_permanent(PLAIN2, 1, bf_loc(0))
    s.add_permanent(PLAIN2, 1, bf_loc(0))
    if extra:
        s.add_permanent(PLAIN2, 1, bf_loc(0))
    h0 = int(s.n_hand[0])
    _rsv.resolve(s, T, V1, ISO, 0, [a1], -1, True)
    if int(s.perms[a1, P_LOC]) != base_loc(1):
        die("isolate", "the enemy goes to ITS base")
    if (int(s.n_hand[0]) - h0 == 1) == extra:
        die("isolate", f"extra={extra}: draw only if ONE enemy is left there")
ok("Isolate draws when the enemy left behind is alone at that battlefield")

SANDS = _SPECS["Crumbling Sands"]
for n_opp_spells, want_countered in ((1, False), (2, True)):
    s = fresh(hand=[T.id_of("Dredge Up")], seat=1)
    s.active = s.priority = 1
    s.spells_played[1] = n_opp_spells
    item = chain_mod.push(s, T.id_of("Dredge Up"), 1)
    chain_mod.finalize(s, item)
    uid = int(s.chain[item, _CUID])
    log = _rsv.resolve(s, T, V1, SANDS, 0, [uid], -1, True)
    if bool(log.get("countered_spell")) != want_countered:
        die("crumbling sands", f"{n_opp_spells} opposing spells: {log}")
ok("Crumbling Sands needs ANOTHER opposing spell besides the one it counters")

# ---------------------------------------------------------------------------
print("\n[batch 8a] duels and doubles, sweeps with scope, statics that read "
      "the combat, and a player-wide damage shield")

from rl.engine.effects import TR_BUFFED as _TRB, OP_BUFF as _OPBUFF
from rl.engine.state import F_EMPOWERED as _FEMP, P_ATTACHED_TO as _PAT

# PLAIN2 is Daring Poro -- printed [Assault] and a Poro tag, both of which this
# section counts. Shipyard Skulker has no text at all.
P3 = T.id_of("Shipyard Skulker")

_BUFF_SPEC = _CS(speed=0, targets=(_TS(who=_WF),), ops=(_Op(_OPBUFF, target=0),))

s = fresh()
u = s.add_permanent(P3, 0, base_loc(0), ready=False)
_rsv.resolve(s, T, V1, _SPECS["Perfect Execution"], 0, [u], -1, True)
if int(s.perms[u, P_READY]) != 1 or combat.perm_kw(s, T, u, "Assault") != 3:
    die("perfect execution", "ready + [Assault 3]")
_rsv.resolve(s, T, V1, _SPECS["Vault Breaker"], 0, [u], -1, True)
if combat.perm_kw(s, T, u, "Assault") != 5 or not combat.perm_kw(s, T, u, "Ganking"):
    die("vault breaker", "[Assault 2] adds to the 3 already granted, plus Ganking")
ok("Perfect Execution and Vault Breaker grant stacking Assault values")

s = fresh()
mine = s.add_permanent(P3, 0, bf_loc(0))
theirs = s.add_permanent(P3, 1, bf_loc(1))
spec = _SPECS["Twilight Step"]
d_mine = _rsv.legal_targets(s, T, spec, 1, 0, [mine], -1)
d_theirs = _rsv.legal_targets(s, T, spec, 1, 0, [theirs], -1)
if sorted(d_mine) != sorted([base_loc(0), bf_loc(1)]):
    die("twilight step", f"my unit: its own base or the other battlefield, got {d_mine}")
if sorted(d_theirs) != sorted([base_loc(1), bf_loc(0)]):
    die("twilight step", f"their unit goes to THEIR base, got {d_theirs}")
ok("a move's destination offers only the mover's own base, never where it stands")

s = fresh()
u = s.add_permanent(P3, 0, base_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Last Stand"], 0, [u], -1, True)
if combat.might(s, T, u) != 6 or not combat.perm_kw(s, T, u, "Temporary"):
    die("last stand", "doubled to 6 and Temporary")
ok("Last Stand doubles effective Might and gives a lasting [Temporary]")

s = fresh()
f = s.add_permanent(BIG, 0, base_loc(0), ready=False)
e = s.add_permanent(BIG, 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Last Breath"], 0, [f, e], -1, True)
if int(s.perms[f, P_READY]) != 1 or s.perms[e, P_ALIVE]:
    die("last breath", "ready, then its Might in damage kills an equal body")
if int(s.perms[f, _PDMG]) != 0:
    die("last breath", "one-way damage -- not a fight")
ok("Last Breath readies a friendly unit and deals its Might one way")

s = fresh()
f = s.add_permanent(P3, 0, base_loc(0))
e = s.add_permanent(BIG, 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Gentlemen's Duel"], 0, [f, e], -1, True)
if int(s.perms[e, _PDMG]) != 6 or int(s.perms[f, _PDMG]) != int(T.might[BIG]):
    die("gentlemen's duel", f"+3 first, then a simultaneous exchange: "
                            f"{int(s.perms[e, _PDMG])}/{int(s.perms[f, _PDMG])}")
ok("Gentlemen's Duel pumps before the exchange")

for emp, might_mod, dies in ((True, 0, True), (False, 2, False)):
    s = fresh()
    u = s.add_permanent(P3, 1, bf_loc(0))
    if emp:
        s.set_flag(u, _FEMP)
    s.perms[u, _PMM] = might_mod
    _rsv.resolve(s, T, V1, _SPECS["Lacerate"], 0, [u], -1, True)
    if bool(s.perms[u, P_ALIVE]) == dies:
        die("lacerate", f"emp={emp} might={2 + might_mod}")
ok("Lacerate kills at 3 Might or less, stripping Empowered on the way")

s = fresh()
f = s.add_permanent(P3, 0, bf_loc(0))
e1 = s.add_permanent(P3, 1, bf_loc(0))
e2 = s.add_permanent(P3, 1, bf_loc(1))
_rsv.resolve(s, T, V1, _SPECS["Siphon Power"], 0, [bf_loc(0)], -1, True)
if (combat.might(s, T, f), combat.might(s, T, e1), combat.might(s, T, e2)) != (4, 2, 3):
    die("siphon power", "friendly +1, enemy -1 floored at 1, other battlefield untouched")
ok("Siphon Power splits one battlefield by side")

s = fresh()
f = s.add_permanent(P3, 0, base_loc(0))
e1 = s.add_permanent(P3, 1, bf_loc(1))
e2 = s.add_permanent(BIG, 1, bf_loc(1))
mine_there = s.add_permanent(P3, 0, bf_loc(1))
_rsv.resolve(s, T, V1, _SPECS["Stormbringer"], 0, [f, bf_loc(1)], -1, True)
if s.perms[e1, P_ALIVE] or int(s.perms[e2, _PDMG]) != 3 \
        or int(s.perms[mine_there, _PDMG]) or int(s.perms[f, P_LOC]) != bf_loc(1):
    die("stormbringer", "its Might to each enemy there, then it moves in")
ok("Stormbringer sweeps enemies there with its Might and then moves in")

s = fresh()
f = s.add_permanent(P3, 0, base_loc(0))
e = s.add_permanent(P3, 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Void Assault"], 0,
             [f, bf_loc(1), e, bf_loc(1)], -1, True)
if int(s.perms[f, P_LOC]) != bf_loc(1) or int(s.perms[e, P_LOC]) != bf_loc(1):
    die("void assault", "both move")
ok("Void Assault moves a friendly unit and an enemy unit")

s = fresh()
e = s.add_permanent(BIG, 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Unyielding Spirit"], 1, [], -1, True)
_rsv.resolve(s, T, V1, _SPECS["Shock Blast"], 0, [e], -1, True)
if int(s.perms[e, _PDMG]):
    die("unyielding spirit", "spell damage is prevented this turn")
s.ply += 1
_rsv.resolve(s, T, V1, _SPECS["Shock Blast"], 0, [e], -1, True)
if int(s.perms[e, _PDMG]) != 4:
    die("unyielding spirit", "...and only this turn")
ok("Unyielding Spirit prevents spell damage for the turn, for both players")

s = fresh()
u = s.add_permanent(P3, 0, base_loc(0))
for tag_card in ("Lonely Poro", "Bird"):
    s.add_permanent(T.id_of(tag_card), 0, base_loc(0))
s.add_permanent(T.id_of("Lonely Poro"), 0, base_loc(0))       # a second Poro
s.add_permanent(T.id_of("Lonely Poro"), 1, base_loc(1))       # not mine
_rsv.resolve(s, T, V1, _SPECS["Friendship"], 0, [u], -1, True)
if combat.might(s, T, u) != 5:
    die("friendship", f"Poro + Bird = 2 distinct tags, got +{combat.might(s, T, u) - 3}")
ok("Friendship counts distinct animal tags among YOUR units")

for card, setup in (("Production Surge", "mech"), ("Shock Blast", "emp"),
                    ("Spoils of War", "died")):
    c = T.id_of(card)
    s = fresh()
    before = sum(a for a, _ in _edisc(s, T, 0, c))
    if setup == "mech":
        s.add_permanent(T.id_of("Mech"), 0, base_loc(0))
    elif setup == "emp":
        s.set_flag(s.add_permanent(P3, 0, base_loc(0)), _FEMP)
    else:
        combat.destroy(s, T, s.add_permanent(P3, 1, base_loc(1)))
    after = sum(a for a, _ in _edisc(s, T, 0, c))
    if (before, after) != (0, 2):
        die(card.lower(), f"discount {before} -> {after}")
s = fresh()
combat.destroy(s, T, s.add_permanent(P3, 0, base_loc(0)))
if sum(a for a, _ in _edisc(s, T, 0, T.id_of("Spoils of War"))):
    die("spoils of war", "a FRIENDLY death is not an enemy one")
ok("conditional self-discounts: a Mech, something Empowered, an enemy death")

s = fresh()
e = s.add_permanent(P3, 1, bf_loc(0))
if combat.permanent_enters_ready(s, T, 0, T.id_of("Vayne - Hunter"), True):
    die("vayne", "no opposing battlefield -> exhausted")
s.bf_ctrl[1] = 1
if not combat.permanent_enters_ready(s, T, 0, T.id_of("Vayne - Hunter"), True):
    die("vayne", "an opponent controls a battlefield -> ready")
if combat.permanent_enters_ready(s, T, 0, T.id_of("Towering Pairofant"), True):
    die("pairofant", "nothing died")
combat.destroy(s, T, e)
if not combat.permanent_enters_ready(s, T, 0, T.id_of("Towering Pairofant"), True):
    die("pairofant", "any unit dying this turn readies it")
ok("Vayne - Hunter and Towering Pairofant read the board and the turn as they enter")

s = fresh()
vy = s.add_permanent(T.id_of("Vayne - Hunter"), 0, bf_loc(0))
s.bf_ctrl[0] = 0
chain.fire(s, T, V1, _TRC, vy, bf_loc(0))
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_settle(s)
if s.perms[vy, P_ALIVE] or T.id_of("Vayne - Hunter") not in list(s.hand[0, :int(s.n_hand[0])]):
    die("vayne", "paying {1} returns her to hand")
ok("Vayne - Hunter may pay {1} on conquer to go back to hand")

s = fresh()
ww = s.add_permanent(T.id_of("Warwick - Hunter"), 0, bf_loc(0))
hurt = s.add_permanent(BIG, 1, bf_loc(0))
fine = s.add_permanent(BIG, 1, bf_loc(0))
elsewhere = s.add_permanent(BIG, 1, bf_loc(1))
own = s.add_permanent(BIG, 0, bf_loc(0))
for r in (hurt, elsewhere, own):
    s.perms[r, _PDMG] = 1
spec = abilities_for(T, T.id_of("Warwick - Hunter"))[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=ww)
alive = [bool(s.perms[r, P_ALIVE]) for r in (hurt, fine, elsewhere, own)]
if alive != [False, True, True, True]:
    die("warwick", f"only DAMAGED ENEMY units HERE: {alive}")
ok("Warwick - Hunter kills damaged enemies at his battlefield and nothing else")

s = fresh()
mg = s.add_permanent(T.id_of("Morgana, Vindictive"), 0, bf_loc(0))
e = s.add_permanent(BIG, 1, bf_loc(0))
s.perms[e, _PDMG] = 2
spec = abilities_for(T, T.id_of("Morgana, Vindictive"))[0]
_rsv.resolve(s, T, V1, spec, 0, [e], -1, False, source=mg)
if int(s.perms[e, _PDMG]) != 4:
    die("morgana", "deals damage equal to what is already marked")
ok("Morgana, Vindictive doubles the damage marked on a unit")

s = fresh()
cd = s.add_permanent(T.id_of("Chakram Dancer"), 0, bf_loc(0))
pal = s.add_permanent(P3, 0, bf_loc(0))
far = s.add_permanent(P3, 0, base_loc(0))
foe = s.add_permanent(P3, 1, bf_loc(0))
spec = abilities_for(T, T.id_of("Chakram Dancer"))[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=cd)
got = [bool(combat.perm_kw(s, T, r, "Shield")) for r in (cd, pal, far, foe)]
if got != [False, True, False, False]:
    die("chakram dancer", f"OTHER FRIENDLY units HERE: {got}")
ok("Chakram Dancer's sweep grant reaches only her other units at her location")

s = fresh()
wr = s.add_permanent(T.id_of("Walking Roost"), 0, base_loc(0))
n0 = int(s.n_perms)
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Walking Roost"))[0], 0, [],
             -1, False, source=wr)
bird = n0
if int(s.n_perms) != n0 + 1 or int(s.perms[bird, P_CTRL]) != 1 \
        or int(s.perms[bird, P_LOC]) != base_loc(1):
    die("walking roost", "the OPPONENT plays the Bird, at their base")
ok("Walking Roost gives the opponent a Bird at their own base")

s = fresh()
sa = s.add_permanent(T.id_of("Simian Ancestor"), 0, base_loc(0), ready=False)
mf = s.add_permanent(T.id_of("Mistfall"), 0, base_loc(0))
other = s.add_permanent(P3, 0, base_loc(0), ready=False)
_rsv.resolve(s, T, V1, _BUFF_SPEC, 0, [sa], -1, True)
_to_decision(s)
if s.pend_may >= 0:        # Mistfall asks about the Ancestor too; let it decline
    A.apply(s, T, V1, A.Action(A.A_DECLINE))
_settle(s)
if int(s.perms[sa, P_READY]) != 1:
    die("simian ancestor", "buffing him readies him")
_rsv.resolve(s, T, V1, _BUFF_SPEC, 0, [other], -1, True)
if not _to_decision(s) or s.pend_may < 0:
    die("mistfall", "buffing a friendly unit offers the ready")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_settle(s)
if int(s.perms[other, P_READY]) != 1 or int(s.perms[mf, P_READY]):
    die("mistfall", "pays and exhausts to ready the buffed unit")
_rsv.resolve(s, T, V1, _BUFF_SPEC, 0, [other], -1, True)     # already buffed
if int(s.n_trig):
    die("mistfall", "a buff that adds nothing is no event")
ok("Simian Ancestor and Mistfall answer a real buff, never a redundant one")

s = fresh()
# At a base: at a battlefield the Cleanup after resolution opens a combat.
kn = s.add_permanent(T.id_of("Kennen, Keeper of Balance"), 0, base_loc(0))
e = s.add_permanent(P3, 1, base_loc(0))
m0 = combat.might(s, T, kn)
chain.fire(s, T, V1, _TRP, kn)
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_TARGET, e))
_settle(s)
if not int(s.perms[e, _PF]) & _FST or combat.might(s, T, kn) != m0 + 2:
    die("kennen", "pays {2} to stun, and grows while a stunned enemy is here")
ok("Kennen stuns for {2} and is +2 beside a stunned enemy")

s = fresh()
lee = s.add_permanent(T.id_of("Lee Sin - Centered"), 0, bf_loc(0))
b_here = s.add_permanent(P3, 0, bf_loc(0))
u_here = s.add_permanent(P3, 0, bf_loc(0))
b_far = s.add_permanent(P3, 0, bf_loc(1))
for r in (b_here, b_far, lee):
    s.set_flag(r, _FB)
got = [combat.might(s, T, r) for r in (b_here, u_here, b_far)]
if got != [6, 3, 4]:
    die("lee sin centered", f"only other BUFFED units at his battlefield: {got}")
ok("Lee Sin - Centered pumps other buffed units at his battlefield")

s = fresh()
g = s.add_permanent(T.id_of("Galio - Indefatigable"), 0, bf_loc(0))
vm = s.add_permanent(T.id_of("Vilemaw"), 1, bf_loc(0))
small = s.add_permanent(BIG, 0, bf_loc(0))
huge = s.add_permanent(T.id_of("Mountain Drake"), 0, bf_loc(0))
got = [combat.might_for_pool(s, T, r) for r in (g, small, huge, vm)]
if got[0] or got[1] or not got[2] or not got[3]:
    die("no combat damage", f"Galio 0; Vilemaw blanks smaller enemies only: {got}")
ok("Galio and Vilemaw take units out of the damage pool, Vilemaw by Might")

s = fresh()
sp = s.add_permanent(T.id_of("Sacred Protector"), 0, bf_loc(0))
if combat.might_for_pool(s, T, sp):
    die("sacred protector", "alone -> no combat damage")
s.add_permanent(P3, 0, bf_loc(0))
if not combat.might_for_pool(s, T, sp):
    die("sacred protector", "exactly one other friendly unit -> deals damage")
ok("Sacred Protector deals combat damage only beside exactly one ally")

s = fresh()
aw = s.add_permanent(T.id_of("Alpha Wildclaw"), 0, bf_loc(0))
small = s.add_permanent(P3, 0, bf_loc(0))
far = s.add_permanent(P3, 0, bf_loc(1))
opts = _rsv.legal_targets(s, T, _STUN_SPEC, 0, 1, [], -1)
if small in opts or far not in opts or aw not in opts:
    die("alpha wildclaw", f"smaller units HERE are shielded, he is not: {opts}")
ok("Alpha Wildclaw shields smaller friendly units at his location")

s = fresh()
rs = s.add_permanent(T.id_of("Repair Specialist"), 0, base_loc(0))
if combat.perm_kw(s, T, rs, "Assault"):
    die("repair specialist", "no gear -> no Assault")
s.add_permanent(ROSE, 0, base_loc(0))
s.add_permanent(T.id_of("Vanguard Helm"), 0, base_loc(0))
if combat.perm_kw(s, T, rs, "Assault") != 2:
    die("repair specialist", "Assault equal to gear controlled")
awm = s.add_permanent(T.id_of("Ancient Warmonger"), 0, bf_loc(0))
s.add_permanent(P3, 1, bf_loc(0))
s.add_permanent(P3, 1, bf_loc(0))
s.add_permanent(P3, 0, bf_loc(0))
if combat.perm_kw(s, T, awm, "Assault") != 2:
    die("ancient warmonger", "Assault equal to ENEMY units here")
ok("counted keywords: Repair Specialist by gear, Ancient Warmonger by enemies here")

s = fresh(hand=[P3, P3])
soul = s.add_permanent(T.id_of("Raging Soul"), 0, base_loc(0))
if combat.perm_kw(s, T, soul, "Ganking"):
    die("raging soul", "nothing discarded")
_phs_discard = __import__("rl.engine.phases", fromlist=["discard"]).discard
_phs_discard(s, T, 0, 1)
if not combat.perm_kw(s, T, soul, "Ganking") or not combat.perm_kw(s, T, soul, "Assault"):
    die("raging soul", "a discard this turn -> Assault and Ganking")
ok("Raging Soul reads whether you discarded this turn")

s = fresh()
pg = s.add_permanent(T.id_of("Crimson Pigeons"), 0, bf_loc(0))
ww2 = s.add_permanent(T.id_of("Wielder of Water"), 1, bf_loc(0))
s.add_permanent(P3, 1, bf_loc(0))
base_pg, base_ww = combat.might(s, T, pg), combat.might(s, T, ww2)
s.showdown_bf, s.attacker = 0, 0
if combat.might(s, T, pg) != base_pg:
    die("crimson pigeons", "attacking ALONE is not attacking with another unit")
if combat.might(s, T, ww2) != base_ww:
    die("wielder of water", "defending with a partner is not alone")
s.add_permanent(P3, 0, bf_loc(0))
s.perms[2, P_ALIVE] = 0                               # Wielder now defends alone
if combat.might(s, T, pg) != base_pg + 2 or combat.might(s, T, ww2) != base_ww + 2:
    die("combat-shape statics", "Pigeons with a partner, Wielder alone: +2 each")
s.showdown_bf = -1
if combat.might(s, T, pg) != base_pg:
    die("crimson pigeons", "outside a combat nothing is attacking")
ok("Crimson Pigeons and Wielder of Water read the shape of the combat they are in")

s = fresh()
al = s.add_permanent(T.id_of("Allay, Eager Admirer"), 0, base_loc(0))
pal = s.add_permanent(P3, 0, base_loc(0))
if combat.perm_kw(s, T, pal, "Deflect"):
    die("allay", "at base -> nothing")
s.set_location(al, bf_loc(0))
s.set_location(pal, bf_loc(0))
ds = s.add_permanent(T.id_of("Disciple of Shen"), 0, bf_loc(1))
if not combat.perm_kw(s, T, pal, "Deflect"):
    die("allay", "at a battlefield her other units there have Deflect")
if combat.perm_kw(s, T, ds, "Shield"):
    die("disciple of shen", "no other unit here")
s.add_permanent(P3, 0, bf_loc(1))
if combat.perm_kw(s, T, ds, "Shield") != 3:
    die("disciple of shen", "exactly one other -> [Shield 3]")
pm = s.add_permanent(T.id_of("Petricite Monument"), 0, base_loc(0))
if not combat.perm_kw(s, T, ds, "Deflect") or combat.perm_kw(
        s, T, s.add_permanent(P3, 1, base_loc(1)), "Deflect"):
    die("petricite monument", "friendly units only")
ok("Allay, Disciple of Shen and Petricite Monument grant keywords by position")

s = fresh(hand=[P3])
_rsv.resolve(s, T, V1, _SPECS["Bushwhack"], 0, [], -1, True)
play(s, V1, 0, base_loc(0))
if int(s.perms[int(s.n_perms) - 1, P_READY]) != 1:
    die("bushwhack", "units played this turn enter ready")
ok("Bushwhack makes the turn's units enter ready")

s = fresh()
ez = s.add_permanent(T.id_of("Ezreal - Dashing"), 0, bf_loc(0))
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("ezreal dashing", "the {Mind} escape is offered")
A.apply(s, T, V1, acts[0])
_settle(s)
if int(s.perms[ez, P_LOC]) != base_loc(0):
    die("ezreal dashing", "moves himself to base")
ok("Ezreal - Dashing can pay {Mind} to move himself home")

# ---------------------------------------------------------------------------
print("\n[batch 8b] ability-level conditions, spent Energy, Deflect ignored, "
      "cost counts over the board")

s = fresh()
e = s.add_permanent(T.id_of("Galio - Indefatigable"), 1, bf_loc(0))   # Deflect
body = s.add_permanent(T.id_of("Vanguard Sergeant"), 1, bf_loc(0))
spec = _SPECS["Decree of Insight"]
opts = _rsv.legal_targets(s, T, spec, 0, 0, [], -1, card=T.id_of("Decree of Insight"))
if _rsv.deflect_cost(s, T, 0, [e], spec) != 0:
    die("decree of insight", "Deflect is ignored while paying")
dom_ok = [bool(int(T.domain_mask[int(s.perms[r, P_CARD])]) & 1) for r in (e, body)]
if any((r in opts) != d for r, d in zip((e, body), dom_ok)):
    die("decree of insight", f"Body units only: opts={opts} body-domain={dom_ok}")
ok("Decree of Insight ignores Deflect and reaches only Body units")

s = fresh()
small = s.add_permanent(P3, 0, base_loc(0))
big = s.add_permanent(T.id_of("Mountain Drake"), 0, base_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Convergent Mutation"], 0, [small, big], -1, True)
if combat.might(s, T, small) != 10 or combat.might(s, T, big) != 10:
    die("convergent mutation", "the chosen unit rises to the other's Might")
_rsv.resolve(s, T, V1, _SPECS["Convergent Mutation"], 0, [big, small], -1, True)
if combat.might(s, T, big) != 10:
    die("convergent mutation", "only INCREASES -- a smaller reference changes nothing")
ok("Convergent Mutation raises one friendly unit to another's Might")

s = fresh()
f = s.add_permanent(P3, 0, base_loc(0))
s.active = s.priority = 1
item = chain_mod.push(s, T.id_of("Progress Day"), 1)
chain_mod.finalize(s, item)
uid = int(s.chain[item, _CUID])
log = _rsv.resolve(s, T, V1, _SPECS["Riposte"], 0, [f, uid], -1, True)
if not log.get("countered_spell") or combat.might(s, T, f) != 3 + int(T.energy[T.id_of("Progress Day")]):
    die("riposte", f"counter + Might equal to its Energy cost: {log}")
ok("Riposte counters a spell and pumps by its Energy cost")

s = fresh()
c = T.id_of("Sky Splitter")
s.add_permanent(P3, 0, base_loc(0))
s.add_permanent(T.id_of("Mountain Drake"), 0, base_loc(0))
s.add_permanent(T.id_of("Mountain Drake"), 1, base_loc(1))
if sum(a for a, _ in _edisc(s, T, 0, c)) != 10:
    die("sky splitter", "reduced by the highest Might among MY units")
c2 = T.id_of("Jaull-Fish")
if sum(a for a, _ in _edisc(s, T, 0, c2)) != 2:
    die("jaull-fish", "{2} per Mighty unit (one Drake)")
c3 = T.id_of("Daisy!")
s.add_permanent(T.id_of("Lonely Poro"), 0, base_loc(0))
s.add_permanent(T.id_of("Bird"), 0, base_loc(0))
if sum(a for a, _ in _edisc(s, T, 0, c3)) != 2:
    die("daisy", "{1} per animal tag present (Poro, Bird)")
ok("Sky Splitter, Jaull-Fish and Daisy! count the board for their discounts")

s = fresh()
kl = T.id_of("Keeper of Law")
s.bf_ctrl[0] = 0
s.add_permanent(P3, 0, bf_loc(0))
if _edisc(s, T, 0, kl) and sum(a for a, _ in _edisc(s, T, 0, kl)):
    die("keeper of law", "one unit is not two")
s.add_permanent(P3, 1, bf_loc(0))
if sum(a for a, _ in _edisc(s, T, 0, kl)) != 2:
    die("keeper of law", "exactly two units (either side) at a battlefield you control")
ok("Keeper of Law's discount wants exactly two units on a battlefield you control")

s = fresh()
e1 = s.add_permanent(P3, 1, bf_loc(0))
e2 = s.add_permanent(P3, 1, bf_loc(1))
spec = _SPECS["Dragon's Rage"]
third = _rsv.legal_targets(s, T, spec, 2, 0, [e1, bf_loc(1)], -1)
if third != [e2]:
    die("dragon's rage", f"another enemy AT THE DESTINATION: {third}")
_rsv.resolve(s, T, V1, spec, 0, [e1, bf_loc(1), e2], -1, True)
if s.perms[e1, P_ALIVE] or s.perms[e2, P_ALIVE]:
    die("dragon's rage", "moved, then an even trade kills both")
ok("Dragon's Rage moves an enemy into another and makes them fight")

s = fresh()
s.deck[0, :4] = [T.id_of("Dredge Up"), T.id_of("Progress Day"), P3,
                 T.id_of("Shock Blast")]
fw = s.add_permanent(T.id_of("Fate Weaver"), 0, base_loc(0))
chain.fire(s, T, V1, _TRP, fw)
_to_decision(s)
picks = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK]
names = sorted(T.names[int(s.look_cards[i])] for i in picks)
if names != ["Progress Day"]:
    die("fate weaver", f"only a spell costing {{4}} or more: {names}")
ok("Fate Weaver's pick is a spell with Energy cost 4 or more")

s = fresh()
pf = s.add_permanent(T.id_of("Ravenbloom Prefect"), 0, base_loc(0))
g = s.add_permanent(ROSE, 1, base_loc(1))
chain_mod.fire_play_unit(s, T, 1, ROSE, g)
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_settle(s)
if s.perms[pf, P_ALIVE] or s.perms[g, P_ALIVE]:
    die("ravenbloom prefect", "banishes himself to banish the gear")
if T.id_of("Ravenbloom Prefect") not in list(s.banished[0, :int(s.n_banished[0])]):
    die("ravenbloom prefect", "the cost is a banish, not a kill")
ok("Ravenbloom Prefect trades himself for an opposing gear, by banishment")

s = fresh()
hw = s.add_permanent(T.id_of("Hungry Wolf"), 0, base_loc(0), ready=False)
def _wolf_acts():
    return [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if _wolf_acts():
    die("hungry wolf", "no enemy chosen this turn -> not offered")
s.chose_enemy_ply[0] = s.ply
acts = _wolf_acts()
if not acts:
    die("hungry wolf", "an enemy was chosen -> offered")
A.apply(s, T, V1, acts[0])
_settle(s)
if int(s.perms[hw, P_READY]) != 1 or _wolf_acts():
    die("hungry wolf", "ready +1, and only once each turn")
ok("Hungry Wolf is gated on choosing an enemy and on once each turn")

s = fresh(hand=[T.id_of("Shock Blast")], runes=8)
e = s.add_permanent(P3, 1, bf_loc(0))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_TARGET, e))
if int(s.chose_enemy_ply[0]) != int(s.ply):
    die("hungry wolf", "choosing an enemy unit with a spell records the turn")
ok("choosing an enemy unit is recorded for the turn")

for full in (True, False):
    s = fresh()
    dz = s.add_permanent(T.id_of("Daisy!"), 0, base_loc(0))
    for tag_card in ("Lonely Poro", "Bird") + (("Stalking Wolf",) if full else ()):
        s.add_permanent(T.id_of(tag_card), 0, base_loc(0))
    if full:
        cat = next(c for c in range(T.n) if "Cat" in T.tags[c] and T.is_type(c, "Unit"))
        s.add_permanent(cat, 0, base_loc(0))
    foe = s.add_permanent(P3, 1, base_loc(0))
    chain.fire(s, T, V1, _TRAD, dz, base_loc(0), subj=dz)
    if (int(s.n_chain) > 0) != full:
        die("daisy", f"all four tags={full}: chain={int(s.n_chain)}")
ok("Daisy!'s attack trigger exists only while all four animal tags are present")

for runes in (7, 6):
    s = fresh(runes=0)
    s.runes_ready[0, 0] = runes
    tb = s.add_permanent(T.id_of("Tomb-Raider Barbara"), 0, base_loc(0))
    s.add_permanent(ROSE, 1, base_loc(1))
    chain.fire(s, T, V1, _TRP, tb)
    if (int(s.n_chain) > 0) != (runes >= 7):
        die("tomb-raider barbara", f"{runes} runes")
s = fresh()
emp_g = s.add_permanent(ROSE, 1, base_loc(1))
plain_g = s.add_permanent(ROSE, 1, base_loc(1))
s.set_flag(emp_g, _FEMP)
spec = abilities_for(T, T.id_of("Tomb-Raider Barbara"))[0]
_rsv.resolve(s, T, V1, spec, 0, [emp_g], -1, False)
_rsv.resolve(s, T, V1, spec, 0, [plain_g], -1, False)
if not s.perms[emp_g, P_ALIVE] or int(s.perms[emp_g, _PF]) & _FEMP or s.perms[plain_g, P_ALIVE]:
    die("tomb-raider barbara", "Empowered -> disempowered and kept; otherwise killed")
ok("Tomb-Raider Barbara needs 7 runes, and disempowers OR kills")

for spell, want_ready in (("Progress Day", True), ("Dredge Up", False)):
    s = fresh(hand=[T.id_of(spell)], runes=10)
    rv = s.add_permanent(T.id_of("Revna the Lorekeeper"), 0, base_loc(0), ready=False)
    pn = s.add_permanent(T.id_of("Prepared Neophyte"), 0, base_loc(0))
    m0 = combat.might(s, T, pn)
    A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
    _settle(s)
    if bool(int(s.perms[rv, P_READY])) != want_ready:
        die("revna", f"{spell}: ready={int(s.perms[rv, P_READY])}")
    if (combat.might(s, T, pn) == m0 + 4) != want_ready:
        die("prepared neophyte", f"{spell}: +4 only after a {{4}}+ spell")
ok("Revna and Prepared Neophyte read the Energy actually spent on a spell")

# ---------------------------------------------------------------------------
print("\n[batch 9] spent buffs, moved enemies, a second Deathknell, and "
      "promises about the next spell")

from rl.engine.state import D_ANY as _DANY

s = fresh()
ye = s.add_permanent(T.id_of("Yordle Explorer"), 0, base_loc(0))
for card, want in (("Progress Day", 0), ("Premonition", 1)):
    h0 = int(s.n_hand[0])
    s.cards_played[0] += 1
    chain_mod.card_played(s, T, 0, T.id_of(card))
    _settle(s)
    if int(s.n_hand[0]) - h0 != want:
        die("yordle explorer", f"{card} (power {int(T.power[T.id_of(card)])}): "
                               f"drew {int(s.n_hand[0]) - h0}")
ok("Yordle Explorer draws for a card with Power cost 2 or more")

s = fresh()
bc = s.add_permanent(T.id_of("Blast Cone"), 0, base_loc(0))
e = s.add_permanent(P3, 1, bf_loc(0))
chain.fire(s, T, V1, _TRP, bc)
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_TARGET, e))
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_TARGET, bf_loc(1)))
if not _to_decision(s) or s.pend_may < 0:
    die("blast cone", "moving an enemy unit offers the stun")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_settle(s)
if int(s.perms[e, P_LOC]) != bf_loc(1) or not int(s.perms[e, _PF]) & _FST \
        or int(s.perms[bc, P_READY]):
    die("blast cone", "moved, then exhausted to stun it")
ok("Blast Cone moves an enemy on play and stuns what you move")

s = fresh()
host = s.add_permanent(P3, 1, bf_loc(0))
cut = s.add_permanent(T.id_of("Jagged Cutlass"), 1, bf_loc(0))
s.attach(cut, host)
move = _CS(speed=0, targets=(_TS(who=_WE),
                             _TS(kind=_rsv.TK_LOCATION, move_dest_of=0)),
           ops=(_Op(_rsv.OP_MOVE_TO, target=0, target_b=1),))
_rsv.resolve(s, T, V1, move, 0, [host, bf_loc(1)], -1, True)
if int(s.perms[host, P_LOC]) != bf_loc(0):
    die("jagged cutlass", "an ENEMY spell cannot move the equipped unit")
own_move = move._replace(targets=(_TS(who=_WF),) + move.targets[1:])
_rsv.resolve(s, T, V1, own_move, 1, [host, bf_loc(1)], -1, True)
if int(s.perms[host, P_LOC]) != bf_loc(1):
    die("jagged cutlass", "...its controller's can")
ok("Jagged Cutlass stops enemy effects from moving the unit it is attached to")

s = fresh()
lu = s.add_permanent(T.id_of("Lucian - Gunslinger"), 0, base_loc(0))
foe = s.add_permanent(T.id_of("Mountain Drake"), 1, base_loc(0))
s.kw_grant_turn[lu, 0] = 2                                  # +[Assault 2]
spec = abilities_for(T, T.id_of("Lucian - Gunslinger"))[0]
_rsv.resolve(s, T, V1, spec, 0, [foe], -1, False, source=lu)
if int(s.perms[foe, _PDMG]) != 3:
    die("lucian", f"printed [Assault] 1 + granted 2 = 3, dealt {int(s.perms[foe, _PDMG])}")
ok("Lucian - Gunslinger deals damage equal to his total [Assault]")

s = fresh()
jh = s.add_permanent(T.id_of("Jhin - Murderous Artist"), 0, base_loc(0))
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Jhin - Murderous Artist"))[0],
             0, [], -1, False, source=jh)
if int(s.pool_energy[0]) != 1 or int(s.pool_power[0, _DANY]) != 1:
    die("jhin", "adds {1 energy} and one wild Power")
ok("Jhin - Murderous Artist adds Energy and a wild rune on a move")

s = fresh(hand=[T.id_of("Progress Day"), T.id_of("Stupefy")])
rf = s.add_permanent(T.id_of("Raging Firebrand"), 0, base_loc(0))
from rl.engine.cost import effective_energy as _eff
pd, stp, unit = T.id_of("Progress Day"), T.id_of("Stupefy"), P3
before = _eff(s, T, 0, pd)
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Raging Firebrand"))[0], 0,
             [], -1, False, source=rf)
if _eff(s, T, 0, pd) != before - 5 or _eff(s, T, 0, unit) != int(T.energy[unit]):
    die("raging firebrand", "the next SPELL costs 5 less; a unit does not")
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
_settle(s)
if _eff(s, T, 0, pd) != before or int(s.next_spell_discount[0]):
    die("raging firebrand", "spent by the spell that used it")
ok("Raging Firebrand's discount reaches only the next spell, once")

s = fresh()
a = s.add_permanent(T.id_of("Spiderling"), 0, bf_loc(0))
m1 = combat.might(s, T, a)
s.add_permanent(T.id_of("Spiderling"), 0, bf_loc(0))
s.add_permanent(T.id_of("Spiderling"), 0, bf_loc(1))
s.add_permanent(T.id_of("Spiderling"), 1, bf_loc(0))
if combat.might(s, T, a) != m1 + 1:
    die("spiderling", "+1 per OTHER Spiderling you control HERE")
ok("Spiderling counts other friendly Spiderlings at its location")

s = fresh()
fd = s.add_permanent(T.id_of("Fae Dragon"), 0, base_loc(0))
u1 = s.add_permanent(P3, 0, base_loc(0))
u2 = s.add_permanent(P3, 0, base_loc(0))
ws = s.add_permanent(T.id_of("Wildclaw Shaman"), 0, base_loc(0), ready=False)
s.set_flag(u1, _FB)
n0 = int(s.n_perms)
spec = abilities_for(T, T.id_of("Wildclaw Shaman"))[0]
if _rsv.legal_targets(s, T, spec, 0, 0, [], -1, source=ws) != [u1]:
    die("wildclaw shaman", "only a BUFFED friendly unit can pay")
_rsv.resolve(s, T, V1, spec, 0, [u1], -1, False, source=ws)
_settle(s)
if _buffed(s, u1) or not _buffed(s, ws) or int(s.perms[ws, P_READY]) != 1:
    die("wildclaw shaman", "spend u1's buff; buff and ready me")
if int(s.n_perms) != n0 + 1 or T.names[int(s.perms[n0, P_CARD])] != "Gold // Buff":
    die("fae dragon", "spending a buff makes a Gold")
ok("Wildclaw Shaman spends another unit's buff, and Fae Dragon pays out a Gold")

s = fresh()
s.add_permanent(T.id_of("Karthus - Eternal"), 0, base_loc(0))
sen = s.add_permanent(SENTRY, 0, base_loc(0))          # Deathknell: draw 1
h0 = int(s.n_hand[0])
combat.destroy(s, T, sen)
_settle(s)
if int(s.n_hand[0]) - h0 != 2:
    die("karthus", f"Deathknell twice, drew {int(s.n_hand[0]) - h0}")
s2 = fresh()
s2.add_permanent(T.id_of("Karthus - Eternal"), 1, base_loc(1))   # theirs
sen = s2.add_permanent(SENTRY, 0, base_loc(0))
h0 = int(s2.n_hand[0])
combat.destroy(s2, T, sen)
_settle(s2)
if int(s2.n_hand[0]) - h0 != 1:
    die("karthus", "an OPPONENT's Karthus doubles nothing of yours")
ok("Karthus - Eternal makes your Deathknells trigger twice")

s = fresh(hand=[T.id_of("Arachnoid Horror"), P3])
s.add_permanent(P3, 1, bf_loc(0))
s.add_permanent(P3, 1, bf_loc(1))
s.add_permanent(P3, 1, bf_loc(1))
d_h = A.play_destinations(s, T, V1, 0, T.id_of("Arachnoid Horror"))
d_u = A.play_destinations(s, T, V1, 0, P3)
if bf_loc(0) not in d_h or bf_loc(1) in d_h or bf_loc(0) in d_u:
    die("arachnoid horror", f"self: a lone enemy only ({d_h}); others need the grant ({d_u})")
s.add_permanent(T.id_of("Arachnoid Horror"), 0, base_loc(0))
if bf_loc(0) not in A.play_destinations(s, T, V1, 0, P3):
    die("arachnoid horror", "on the board it grants the same to friendly units")
ok("Arachnoid Horror can be played onto a lone enemy, and lets your units follow")

# ---------------------------------------------------------------------------
print("\n[batch 10] Level 'instead', paid costs that buy readiness, a one-shot "
      "delayed trigger, and ability discounts")

from rl.engine.state import F_LEGION as _FLEG, BEGINNING as _BEG

s = fresh()
u = s.add_permanent(P3, 0, base_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Combat Experience"], 0, [u], -1, True)
if combat.might(s, T, u) != 4:
    die("combat experience", "below Level 6: +1")
s.xp[0] = 6
_rsv.resolve(s, T, V1, _SPECS["Combat Experience"], 0, [u], -1, True)
if combat.might(s, T, u) != 7:
    die("combat experience", "Level 6: +3 INSTEAD, never +4")
ok("Combat Experience gives +1, or +3 instead at Level 6")

s = fresh()
c = T.id_of("Concentrate")
got = []
for xp in (0, 6, 11):
    s.xp[0] = xp
    got.append(sum(a for a, _ in _edisc(s, T, 0, c)))
if got != [0, 2, 4]:
    die("concentrate", f"discounts by level: {got}")
yi = T.id_of("Master Yi - Unstoppable")
from rl.engine.cost import effective_power as _effp
s.xp[0] = 11
if sum(a for a, _ in _edisc(s, T, 0, yi)) != 6 or _effp(s, T, 0, yi) != int(T.power[yi]) - 3:
    die("master yi", "Level 11: {6 energy} and three Calm less")
ok("Concentrate and Master Yi - Unstoppable step their discounts by Level")

for fd in (False, True):
    s = fresh()
    e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
    if fd:
        s.fd_owner[1] = 0
    _rsv.resolve(s, T, V1, _SPECS["Monster Harpoon"], 0, [e], -1, True)
    if int(s.perms[e, _PDMG]) != (4 if fd else 2):
        die("monster harpoon", f"facedown={fd}: {int(s.perms[e, _PDMG])}")
ok("Monster Harpoon deals 4 instead of 2 while you control a facedown card")

for attacking in (False, True):
    s = fresh()
    e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
    s.add_permanent(P3, 0, bf_loc(0))
    if attacking:
        s.showdown_bf, s.attacker = 0, 1
    _rsv.resolve(s, T, V1, _SPECS["Sudden Storm"], 0, [e], -1, True)
    if int(s.perms[e, _PDMG]) != (4 if attacking else 2):
        die("sudden storm", f"attacking={attacking}")
ok("Sudden Storm deals 4 instead to an attacking unit")

s = fresh()
e = s.add_permanent(P3, 1, bf_loc(0))
s.add_permanent(P3, 0, bf_loc(0))
# 807.1.d -- "attacking" needs a COMBAT Showdown, not just a Showdown.
s.showdown_bf, s.attacker, s.showdown_combat = 0, 1, 1
_rsv.resolve(s, T, V1, _SPECS["Existential Dread"], 0, [e], -1, True)
if not s.perms[e, P_ALIVE] or not int(s.perms[e, _PF]) & _FST:
    die("existential dread", "first: stun")
_rsv.resolve(s, T, V1, _SPECS["Existential Dread"], 0, [e], -1, True)
if s.perms[e, P_ALIVE] or P3 not in list(s.hand[1, :int(s.n_hand[1])]):
    die("existential dread", "already stunned: return it instead")
ok("Existential Dread stuns, and returns a unit that is already stunned")

s = fresh()
cc = T.id_of("Consuming Curse")
s.trash[0, :2] = cc
s.n_trash[0] = 2
e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Consuming Curse"], 0, [e], -1, True, card=cc)
if int(s.perms[e, _PDMG]) != 4:
    die("consuming curse", "2 + 1 per copy in your trash")
ok("Consuming Curse grows with its own copies in your trash")

s = fresh()
me = s.add_permanent(T.id_of("Mountain Drake"), 0, base_loc(0))
small = s.add_permanent(P3, 1, bf_loc(0))
big = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Stare Down"], 0, [me, bf_loc(0)], -1, True)
if int(s.perms[small, P_LOC]) != base_loc(1) or int(s.perms[big, P_LOC]) != bf_loc(0) \
        or int(s.xp[0]) != 1:
    die("stare down", "smaller enemies go to THEIR base; +1 XP")
ok("Stare Down sends smaller enemies home and gains 1 XP")

s = fresh()
s.trash[0, 0] = T.id_of("Shadow Assassin")
s.n_trash[0] = 1
if not combat.permanent_enters_ready(s, T, 0, T.id_of("Shadow Assassin"), True) \
        or combat.permanent_enters_ready(s, T, 1, T.id_of("Shadow Assassin"), True):
    die("shadow assassin", "ready only with its name in YOUR trash")
ok("Shadow Assassin enters ready with a copy in your trash")

s = fresh(hand=[T.id_of("Crescent Guardian")], runes=6)
fast = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY]
A.apply(s, T, V1, fast[0])
if any(a.kind == A.A_PLAY_AT_FAST for a in A.legal_actions(s, T, V1, 0)):
    die("crescent guardian", "no spell played this turn -> no additional cost")
s = fresh(hand=[T.id_of("Crescent Guardian")], runes=6)
s.spells_played[0] = 1
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
fasts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT_FAST]
if not fasts:
    die("crescent guardian", "after a spell the Chaos cost is offered")
A.apply(s, T, V1, fasts[0])
cg = int(s.n_perms) - 1
if int(s.perms[cg, P_READY]) != 1:
    die("crescent guardian", "paying makes it enter ready")
ok("Crescent Guardian's additional cost opens after a spell and buys readiness")

s = fresh()
nm = s.add_permanent(T.id_of("Nami - Headstrong"), 0, base_loc(0))
e = s.add_permanent(P3, 1, base_loc(1))
chain.fire(s, T, V1, _TRP, nm)
if int(s.n_chain):
    die("nami", "unpaid -> the stun never triggers")
s.set_flag(nm, _rsv.F_PAID_ADDITIONAL if hasattr(_rsv, "F_PAID_ADDITIONAL")
           else __import__("rl.engine.state", fromlist=["F_PAID_ADDITIONAL"]).F_PAID_ADDITIONAL)
chain.fire(s, T, V1, _TRP, nm)
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_TARGET, e))
_settle(s)
if not int(s.perms[e, _PF]) & _FST:
    die("nami", "paid -> stun an enemy unit")
from rl.engine.effects import TR_HOLD as _TRH
chain.fire(s, T, V1, _TRH, nm)
_settle(s)
t1 = s.add_permanent(P3, 0, base_loc(0), ready=False)
t2 = s.add_permanent(P3, 0, base_loc(0), ready=False)
chain_mod.fire_play_unit(s, T, 0, P3, t1)
chain_mod.fire_play_unit(s, T, 0, P3, t2)
_settle(s)
if not (int(s.perms[t1, P_READY]) and _buffed(s, t1)) or int(s.perms[t2, P_READY]) or _buffed(s, t2):
    die("nami", "hold arms ONE ready-and-buff for the next unit only")
t3 = s.add_permanent(P3, 0, base_loc(0), ready=False)
chain_mod.fire_play_unit(s, T, 0, P3, t3)
_settle(s)
if int(s.perms[t3, P_READY]):
    die("nami", "spent after the first unit")
ok("Nami - Headstrong: a paid stun, and a hold that readies and buffs the next unit once")

s = fresh(runes=0)
s.runes_ready[0, 0] = 5
fm = s.add_permanent(T.id_of("Frostcoat Mother"), 0, base_loc(0))
if any(a.kind == A.A_ACTIVATE for a in A.legal_actions(s, T, V1, 0)):
    die("frostcoat mother", "5 runes: 12-5 = 7 energy, unaffordable")
s.runes_ready[0, 0] = 6
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("frostcoat mother", "6 runes pay 12-6 = 6")
m0 = combat.might(s, T, fm)
A.apply(s, T, V1, acts[0])
_settle(s)
if int(s.runes_ready[0].sum()) != 0 or combat.might(s, T, fm) != m0 + 3:
    die("frostcoat mother", "paid all six and is +3 while Empowered")
s = fresh(runes=0)
s.runes_ready[0, 0] = 4
bs = s.add_permanent(T.id_of("Baccai Sandspinner"), 0, base_loc(0))
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("baccai sandspinner", "4 runes: 5-3 = 2")
A.apply(s, T, V1, acts[0])
_settle(s)
if int(s.runes_ready[0].sum()) != 2 or combat.perm_kw(s, T, bs, "Assault") != 2:
    die("baccai sandspinner", "paid 2; Empowered gives [Assault 2]")
ok("Frostcoat Mother and Baccai Sandspinner discount their own [Empower] by runes")

for phase_mine, want in ((True, 2), (False, 1)):
    s = fresh()
    lb = s.add_permanent(T.id_of("LeBlanc - Fragmented"), 0, base_loc(0))
    h0 = int(s.n_hand[0])
    combat.destroy(s, T, lb)
    # The Deathknell reads the phase as it RESOLVES, so resolve it directly
    # inside the phase rather than walking a whole Beginning Phase.
    s.n_trig = 0
    if phase_mine:
        s.phase = _BEG
    _rsv.resolve(s, T, V1, abilities_for(T, T.id_of("LeBlanc - Fragmented"))[0],
                 0, [], -1, False)
    if int(s.n_hand[0]) - h0 != want:
        die("leblanc", f"beginning={phase_mine}: drew {int(s.n_hand[0]) - h0}")
ok("LeBlanc - Fragmented draws 2 instead during your Beginning Phase")

for legion in (False, True):
    s = fresh(hand=[P3, P3, P3])
    sc = s.add_permanent(T.id_of("Scrapyard Champion"), 0, base_loc(0))
    if legion:
        s.set_flag(sc, _FLEG)
    chain.fire(s, T, V1, _TRP, sc)
    if (int(s.n_chain) > 0) != legion:
        die("scrapyard champion", f"legion={legion}")
ok("Scrapyard Champion's loot exists only with [Legion]")

s = fresh()
dx = s.add_permanent(T.id_of("Darius - Executioner"), 0, bf_loc(0))
pal = s.add_permanent(P3, 0, bf_loc(0))
if combat.might(s, T, pal) != 4 or combat.might(s, T, dx) != int(T.might[T.id_of("Darius - Executioner")]):
    die("darius executioner", "other friendly units here +1")
ok("Darius - Executioner pumps other friendly units at his location")

s = fresh()
s.xp[0] = 3
mt = s.add_permanent(T.id_of("Megatusk"), 0, bf_loc(0))
pal = s.add_permanent(P3, 0, bf_loc(0))
far = s.add_permanent(P3, 0, bf_loc(1))
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
A.apply(s, T, V1, acts[0])
_settle(s)
if not combat.perm_kw(s, T, pal, "Ganking") or combat.perm_kw(s, T, far, "Ganking") \
        or int(s.xp[0]) != 0:
    die("megatusk", "3 XP: Ganking to your units HERE")
ok("Megatusk spends 3 XP to give his location Ganking")

s = fresh()
kz = s.add_permanent(T.id_of("Kha'Zix - Mutating Horror"), 0, base_loc(0))
e1 = s.add_permanent(P3, 1, base_loc(0))
chain.fire(s, T, V1, _TRAD, kz, base_loc(0), subj=kz)
_settle(s)
if int(s.xp[0]) != 2:
    die("kha'zix mutating", "a lone enemy here -> +2 and 2 XP")
s.add_permanent(P3, 1, base_loc(0))
chain.fire(s, T, V1, _TRAD, kz, base_loc(0), subj=kz)
if int(s.n_chain):
    die("kha'zix mutating", "two enemies -> no trigger")
ok("Kha'Zix - Mutating Horror feeds on a lone enemy")

for xp in (2, 3):
    s = fresh()
    s.xp[0] = xp
    kh = s.add_permanent(T.id_of("Kha'Zix, Evolving Hunter"), 0, base_loc(0))
    e = s.add_permanent(T.id_of("Mountain Drake"), 1, base_loc(0))
    chain.fire(s, T, V1, _TRAD, kh, base_loc(0), subj=kh)
    _to_decision(s)
    kinds = {a.kind for a in A.legal_actions(s, T, V1, 0)}
    if (A.A_ACCEPT in kinds) != (xp >= 3):
        die("kha'zix evolving", f"xp={xp}: accept offered={A.A_ACCEPT in kinds}")
    if xp >= 3:
        A.apply(s, T, V1, A.Action(A.A_ACCEPT))
        _to_decision(s)
        A.apply(s, T, V1, A.Action(A.A_TARGET, e))
        _settle(s)
        if int(s.xp[0]) != 0 or int(s.perms[e, _PDMG]) != int(T.might[T.id_of("Kha'Zix, Evolving Hunter")]):
            die("kha'zix evolving", "spends 3 XP to deal his Might")
ok("Kha'Zix, Evolving Hunter's strike costs 3 XP and is offered only when payable")

s = fresh()
host = s.add_permanent(P3, 0, base_loc(0))
gh = s.add_permanent(T.id_of("Gearhead"), 0, base_loc(0))
for r in (host, gh):
    g = s.add_permanent(T.id_of("Jagged Cutlass"), 0, base_loc(0))
    s.attach(g, r)
if combat.might(s, T, host) != 5 or combat.might(s, T, gh) != int(T.might[T.id_of("Gearhead")]) + 4:
    die("gearhead", "doubles the +2 on himself only")
ok("Gearhead doubles the Might bonus of his own Equipment")

s = fresh()
pal = s.add_permanent(P3, 0, bf_loc(0))
eon = s.add_permanent(T.id_of("Edge of Night"), 0, bf_loc(0))
s.set_flag(eon, __import__("rl.engine.state", fromlist=["F_FROM_HIDDEN"]).F_FROM_HIDDEN)
chain.fire(s, T, V1, _TRP, eon)
_to_decision(s)
if s.pend_slot >= 0:
    A.apply(s, T, V1, A.Action(A.A_TARGET, pal))
_settle(s)
if int(s.perms[eon, _PAT]) != pal:
    die("edge of night", "played from face down, it attaches to a unit here")
ok("Edge of Night attaches itself when played from face down")

s = fresh()
ah = s.add_permanent(T.id_of("Ahri - Alluring"), 0, base_loc(0))   # no conquer at Cleanup
chain.fire(s, T, V1, _TRH, ah)
_settle(s)
if int(s.points[0]) != 1:
    die("ahri alluring", "hold scores 1")
ok("Ahri - Alluring scores a point on hold")

# ---------------------------------------------------------------------------
print("\n[Weaponmaster] 821.1.c, and Equipment conquer/hold triggers on the real "
      "scoring path")

from rl.engine.effects import weaponmaster_cost as _wmc

# 821.1.c.3 -- only an [A] in the Equip cost is discounted.
s = fresh()
u = s.add_permanent(P3, 0, base_loc(0))
dom = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))       # {Fury rune}
anyr = s.add_permanent(T.id_of("Spinning Axe"), 0, base_loc(0))    # {any rune}
if _wmc(s, T, 0, dom) != (0, 1, 0) or _wmc(s, T, 0, anyr) != (0, 0, 0):
    die("weaponmaster", f"domain rune kept, [A] removed: {_wmc(s, T, 0, dom)} "
                        f"{_wmc(s, T, 0, anyr)}")
ok("Weaponmaster discounts [A] only (821.1.c.3)")

s = fresh(hand=[T.id_of("Combat Chef")], runes=0)
s.runes_ready[0, :] = 1                   # 6 runes, one per domain
axe = s.add_permanent(T.id_of("Spinning Axe"), 0, base_loc(0))
other = s.add_permanent(P3, 0, base_loc(0))
s.attach(axe, other)                      # "even if it's already attached"
play(s, V1, 0, base_loc(0))
chef = int(s.n_perms) - 1
if not _to_decision(s) or s.pend_may < 0:
    die("weaponmaster", "playing a Weaponmaster unit offers the equip")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_to_decision(s)
opts = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
if opts != [axe]:
    die("weaponmaster", f"the attached Axe is choosable: {opts}")
A.apply(s, T, V1, A.Action(A.A_TARGET, axe))
_settle(s)
if int(s.perms[axe, _PAT]) != chef:
    die("weaponmaster", "the Axe moves to the Weaponmaster unit")
ok("Combat Chef's Weaponmaster moves an attached Equipment onto itself")

s = fresh(runes=0)
sword = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
ch = s.add_permanent(T.id_of("Combat Chef"), 0, base_loc(0))
spec = abilities_for(T, T.id_of("Combat Chef"))[-1]
if _rsv.legal_targets(s, T, spec, 0, 0, [], -1, source=ch):
    die("weaponmaster", "no Fury rune -> the Long Sword is not payable, not offered")
ok("an Equipment whose Equip cost cannot be paid is not offered")

# The scoring path itself, not a hand-queued trigger.
s = fresh()
u = s.add_permanent(P3, 0, bf_loc(0))
tf = s.add_permanent(T.id_of("Trinity Force"), 0, bf_loc(0))
s.attach(tf, u)
s.bf_ctrl[0] = 0
from rl.engine import phases as _ph2
_ph2.score_holds(s, V1, T)
if int(s.n_trig) != 1:
    die("718.3", "an attached Trinity Force's hold trigger is queued by scoring")
ok("score_holds queues an Equipment's 'When I hold' through the unit")

s = fresh()
u = s.add_permanent(P3, 0, bf_loc(0))
wa = s.add_permanent(T.id_of("Warmog's Armor"), 0, bf_loc(0))
s.attach(wa, u)
luc = s.add_permanent(T.id_of("Lucian - Merciless"), 0, bf_loc(0), ready=False)
combat._establish_control(s, T, V1, 0)
srcs = sorted(int(s.trig[t, 1]) for t in range(int(s.n_trig))
              if int(s.trig[t, 0]) == _TRC)
if srcs != sorted([u, luc]):
    die("718.3", f"conquer queues the equipped unit's Warmog trigger and Lucian: {srcs}")
_settle(s)
if not _buffed(s, u) or int(s.perms[luc, P_READY]) != 1:
    die("conquer", "Warmog buffs the unit; Lucian readies")
s.perms[luc, P_READY] = 0
s.set_location(luc, bf_loc(1))
s.n_trig = 0
combat._establish_control(s, T, V1, 1)
if any(int(s.trig[t, 1]) == luc for t in range(int(s.n_trig))):
    die("lucian merciless", "only the FIRST conquer each turn")
ok("conquer queues Equipment triggers through the unit, and Lucian - Merciless once a turn")

s = fresh()
rv = s.add_permanent(T.id_of("Riven, Shattered"), 0, base_loc(0))
for _ in range(2):
    g = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
    s.attach(g, rv)
e = s.add_permanent(T.id_of("Mountain Drake"), 1, base_loc(0))
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Riven, Shattered"))[0], 0, [e],
             -1, False, source=rv)
if int(s.perms[e, _PDMG]) != 4:
    die("riven", "2 per attached Equipment")
ok("Riven, Shattered deals 2 per Equipment attached to her")

s = fresh()
jx = s.add_permanent(T.id_of("Jax - Unrelenting"), 0, base_loc(0))
sw = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
h0 = int(s.n_hand[0])
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Long Sword"))[0], 0,
             [jx], -1, False, source=sw)
if not _to_decision(s) or s.pend_may < 0:
    die("jax unrelenting", "attaching to him offers the draw")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_settle(s)
if int(s.n_hand[0]) != h0 + 1:
    die("jax unrelenting", "pay {1}: draw 1")
ok("Jax - Unrelenting draws when an Equipment attaches to him")

s = fresh()
orn = s.add_permanent(T.id_of("Ornn - Forge God"), 0, bf_loc(0))
m0 = combat.might(s, T, orn)
s.add_permanent(ROSE, 0, base_loc(0))
s.add_permanent(ROSE, 1, base_loc(1))
if combat.might(s, T, orn) != m0 + 1:
    die("ornn", "+1 per FRIENDLY gear anywhere")
ok("Ornn - Forge God counts friendly gear")

# ---------------------------------------------------------------------------
print("\n[batch 12] one-turn replacements: recall instead of dying, kill on "
      "the next damage, Soraka's guard, Otterpus")

s = fresh()
u = s.add_permanent(P3, 0, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Tactical Retreat"], 0, [u], -1, True)
s.perms[u, _PDMG] = 1
combat.destroy(s, T, u)
if not s.perms[u, P_ALIVE] or int(s.perms[u, P_LOC]) != base_loc(0) \
        or int(s.perms[u, P_READY]) or int(s.perms[u, _PDMG]):
    die("tactical retreat", "healed, exhausted, recalled instead of dying")
combat.destroy(s, T, u)
if s.perms[u, P_ALIVE]:
    die("tactical retreat", "only the NEXT death")
s = fresh()
u = s.add_permanent(P3, 0, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Highlander"], 0, [u], -1, True)
s.ply += 1
combat.destroy(s, T, u)
if s.perms[u, P_ALIVE]:
    die("highlander", "only THIS turn")
ok("Tactical Retreat / Highlander replace the next death this turn, once")

s = fresh()
e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Noxian Guillotine"], 0, [e], -1, True)
if not s.perms[e, P_ALIVE]:
    die("noxian guillotine", "no Legion -> not killed yet")
if combat.lethal_cost(s, T, e) != 1:
    die("noxian guillotine", "any damage is lethal now")
combat.mark_damage(s, T, e, 1)
if s.perms[e, P_ALIVE]:
    die("noxian guillotine", "the next damage kills it")
s = fresh()
e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
s.cards_played[0] = 2
_rsv.resolve(s, T, V1, _SPECS["Noxian Guillotine"], 0, [e], -1, True)
if s.perms[e, P_ALIVE]:
    die("noxian guillotine", "[Legion] -> kill it now")
ok("Noxian Guillotine kills on the next damage, or now with [Legion]")

s = fresh()
sk = s.add_permanent(T.id_of("Soraka - Wanderer"), 0, bf_loc(0))
small = s.add_permanent(P3, 0, bf_loc(0))
big = s.add_permanent(T.id_of("Mountain Drake"), 0, bf_loc(0))
far = s.add_permanent(P3, 0, bf_loc(1))
for r in (small, big, far):
    combat.destroy(s, T, r)
alive = [bool(s.perms[r, P_ALIVE]) for r in (small, big, far)]
if alive != [True, False, False] or int(s.perms[small, P_LOC]) != base_loc(0):
    die("soraka", f"guards smaller allies HERE only: {alive}")
if not combat.perm_kw(s, T, sk, "Backline"):
    die("soraka", "assigned combat damage last")
ok("Soraka - Wanderer recalls smaller allies at her location instead of letting them die")

from rl.engine import phases as _ph3
s = fresh()
s.add_permanent(T.id_of("Otterpus"), 1, base_loc(1))
s.add_permanent(P3, 0, bf_loc(0))
s.bf_ctrl[0] = 0
s.turn = 2
h0 = int(s.n_hand[0])
_ph3.score_holds(s, V1, T)
if int(s.points[0]) != 0 or int(s.n_hand[0]) != h0 + 1:
    die("otterpus", "a hold point on turn 2 becomes a draw")
s.bf_scored[:] = 0
s.turn = 3
_ph3.score_holds(s, V1, T)
if int(s.points[0]) != 1:
    die("otterpus", "turn 3 scores normally")
ok("Otterpus turns early conquer/hold points into draws, for either player")

# ---------------------------------------------------------------------------
print("\n[batch 13] Delayed Abilities about one unit, move counts, a tie that "
      "recalls everyone")

s = fresh(runes=0)
s.runes_ready[0, 0] = 3                    # fewer than 7 runes
s.rune_left[0] = 5                         # something left to channel
e = s.add_permanent(P3, 1, bf_loc(0))
card = T.id_of("Siphoning Strike")
_rsv.resolve(s, T, V1, _SPECS["Siphoning Strike"], 0, [e], -1, True, card=card)
if s.perms[e, P_ALIVE]:
    die("siphoning strike", "4 damage kills a 3-Might unit")
runes0 = int(s.runes_in_play(0).sum())
_settle(s)
if int(s.runes_in_play(0).sum()) != runes0 + 1:
    die("siphoning strike", "its death this turn channels a rune -- the mark "
                            "precedes the damage, so this very kill counts")
ok("Siphoning Strike's delayed channel fires for the unit it kills")

s = fresh()
e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
card = T.id_of("Deadly Flourish")
_rsv.resolve(s, T, V1, _SPECS["Deadly Flourish"], 0, [e], -1, True, card=card)
n0 = int(s.n_perms)
other = s.add_permanent(P3, 1, bf_loc(1))
combat.destroy(s, T, other)                 # a DIFFERENT unit dying
_settle(s)
if int(s.n_perms) != n0 + 1:
    die("deadly flourish", "another unit's death pays nothing")
combat.destroy(s, T, e)
_settle(s)
if int(s.n_perms) != n0 + 2 or T.names[int(s.perms[n0 + 1, P_CARD])] != "Gold // Buff":
    die("deadly flourish", "the marked unit's death makes a Gold")
ok("Deadly Flourish pays a Gold only for the unit it marked")

s = fresh()
f = s.add_permanent(P3, 0, bf_loc(0))
card = T.id_of("Grim Resolve")
_rsv.resolve(s, T, V1, _SPECS["Grim Resolve"], 0, [f], -1, True, card=card)
combat.queue_win_combat(s, T, 0, bf_loc(0))
_settle(s)
if int(s.xp[0]) != 2 or combat.might(s, T, f) != 6:
    die("grim resolve", "+3, and 2 XP when it wins a combat")
ok("Grim Resolve pays XP when its unit wins a combat")

s = fresh()
ya = s.add_permanent(T.id_of("Yasuo - Windrider"), 0, base_loc(0))
s.bf_ctrl[:] = 0            # already his: no conquer point muddies the count
for hop, (a, b) in enumerate(((base_loc(0), bf_loc(0)), (bf_loc(0), bf_loc(1)),
                              (bf_loc(1), bf_loc(0)))):
    s.set_location(ya, b)
    combat.queue_move_trigger(s, T, ya, a, b)
    _settle(s)
    if int(s.points[0]) != (1 if hop == 2 else 0):
        die("yasuo windrider", f"move {hop + 1}: points {int(s.points[0])}")
ok("Yasuo - Windrider scores on his third move of the turn")

s = fresh()
ky = s.add_permanent(T.id_of("Kayn - Unleashed"), 0, base_loc(0))
for a, b in ((base_loc(0), bf_loc(0)), (bf_loc(0), bf_loc(1))):
    s.set_location(ky, b)
    combat.queue_move_trigger(s, T, ky, a, b)
s.perms[ky, _PDMG] = 0
combat.mark_damage(s, T, ky, 99)
if not s.perms[ky, P_ALIVE] or int(s.perms[ky, _PDMG]):
    die("kayn", "moved twice -> takes no damage")
s.ply += 1
combat.mark_damage(s, T, ky, 1)
if int(s.perms[ky, _PDMG]) != 1:
    die("kayn", "a new turn resets the count")
ok("Kayn - Unleashed takes no damage after moving twice this turn")

s = fresh()
sh = s.add_permanent(T.id_of("Shen, Leader of the Kinkou Order"), 0, bf_loc(0))
s.bf_ctrl[:] = 0
chain.fire(s, T, V1, _TRH, sh)
_settle(s)
if int(s.points[0]):
    die("shen leader", "alone -> no point")
s.add_permanent(P3, 0, bf_loc(0))
chain.fire(s, T, V1, _TRH, sh)
_settle(s)
if int(s.points[0]) != 1:
    die("shen leader", "exactly one other unit -> 1 point")
ok("Shen, Leader of the Kinkou Order scores holding with exactly one ally")

s = fresh()
il = s.add_permanent(T.id_of("Illaoi, Prophet of the Great Kraken"), 0, base_loc(0))
m0 = combat.might(s, T, il)
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Illaoi, Prophet of the Great Kraken"))[0],
             0, [], -1, False, source=il)
if combat.might(s, T, il) != m0 + 1:
    die("illaoi", "a Tentacle, and +1 per token unit you control")
ok("Illaoi makes Tentacles and grows with your tokens")

for sym in (True, False):
    s = fresh()
    att = s.add_permanent(T.id_of("Mountain Drake"), 0, bf_loc(0))
    dfn = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
    if sym:
        s.add_permanent(T.id_of("Symbol of the Solari"), 0, base_loc(0))
    s.showdown_bf, s.attacker, s.showdown_combat = 0, 0, 1
    combat.resolution_step(s, T, V1, 0, 0, {})
    if int(s.perms[dfn, P_LOC]) != (base_loc(1) if sym else bf_loc(0)) \
            or int(s.perms[att, P_LOC]) != base_loc(0):
        die("symbol of the solari", f"sym={sym}: a tie recalls "
                                    f"{'everyone' if sym else 'the attackers'}")
ok("Symbol of the Solari turns a tied attack into a recall of every unit")

# ---------------------------------------------------------------------------
print("\n[batch 14] permanents that rewrite a rule: when and where you may "
      "play, points, channelling, readying, bonus damage, Tank")

s = fresh(hand=[T.id_of("Ol' Poro")])
s.turn = 3
if any(a.kind == A.A_PLAY for a in A.legal_actions(s, T, V1, 0)):
    die("ol' poro", "not on your third turn")
s.turn = 4
if not any(a.kind == A.A_PLAY for a in A.legal_actions(s, T, V1, 0)):
    die("ol' poro", "playable from the fourth")
ok("Ol' Poro can't be played on your first three turns")

s = fresh(hand=[T.id_of("Perched Grimwyrm")])
if any(a.kind == A.A_PLAY for a in A.legal_actions(s, T, V1, 0)):
    die("perched grimwyrm", "nothing conquered -> unplayable")
s.bf_conquered_ply[0, 1] = s.ply
s.bf_ctrl[1] = 0
if A.play_destinations(s, T, V1, 0, T.id_of("Perched Grimwyrm")) != [bf_loc(1)]:
    die("perched grimwyrm", "only the battlefield conquered this turn, never base")
ok("Perched Grimwyrm plays only to a battlefield you conquered this turn")

s = fresh()
s.add_permanent(T.id_of("Tianna Crownguard"), 1, bf_loc(1))
s.add_permanent(P3, 0, bf_loc(0))
s.bf_ctrl[0] = 0
_ph3.score_holds(s, V1, T)
if int(s.points[0]):
    die("tianna", "an opponent's Tianna at a battlefield blocks your hold point")
_rsv.resolve(s, T, V1, _CS(speed=0, ops=(_Op(_rsv.OP_SCORE, n=1),)), 0, [], -1, True)
if int(s.points[0]):
    die("tianna", "...and effect points")
_rsv.resolve(s, T, V1, _CS(speed=0, ops=(_Op(_rsv.OP_SCORE, n=1),)), 1, [], -1, True)
if int(s.points[1]) != 1:
    die("tianna", "her controller still scores")
ok("Tianna Crownguard stops her opponents gaining points")

s = fresh()
s.rune_left[:] = 10
s.add_permanent(T.id_of("Sandstone Chimera"), 1, bf_loc(0))
from rl.engine import combat as _cmb2
if _cmb2.channel_count(s, T) != 1:
    die("sandstone chimera", "one rune per Channel Phase, both players")
ok("Sandstone Chimera cuts every Channel Phase to one rune")

s = fresh(hand=[P3])
wd = s.add_permanent(T.id_of("Mageseeker Warden"), 1, bf_loc(0))
s.add_permanent(P3, 0, bf_loc(1))
s.bf_ctrl[1] = 0
if A.play_destinations(s, T, V1, 0, P3) != [base_loc(0)]:
    die("mageseeker warden", "opponents play units only to base")
mine = s.add_permanent(P3, 0, base_loc(0), ready=False)
theirs = s.add_permanent(P3, 1, base_loc(1), ready=False)
ready = _CS(speed=0, targets=(_TS(who=_rsv.W_ANY),), ops=(_Op(_rsv.OP_READY, target=0),))
_rsv.resolve(s, T, V1, ready, 0, [mine], -1, True)
_rsv.resolve(s, T, V1, ready, 0, [theirs], -1, True)
if int(s.perms[mine, P_READY]) or not int(s.perms[theirs, P_READY]):
    die("mageseeker warden", "spells can't ready the Warden's ENEMIES")
ok("Mageseeker Warden locks opposing plays to base and stops readying them")

s = fresh()
s.add_permanent(T.id_of("Annie - Fiery"), 0, base_loc(0))
e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Shock Blast"], 0, [e], -1, True)
_rsv.resolve(s, T, V1, _SPECS["Shock Blast"], 1, [e], -1, True)   # theirs: no bonus
if int(s.perms[e, _PDMG]) != 9:
    die("annie fiery", f"your spells +1 (5), theirs not (4): {int(s.perms[e, _PDMG])}")
ok("Annie - Fiery adds 1 Bonus Damage to your spells only")

for runes in (7, 6):
    s = fresh(runes=0)
    s.runes_ready[1, 0] = runes
    eh = s.add_permanent(T.id_of("Esteemed Hierophant"), 1, bf_loc(0))
    _rsv.resolve(s, T, V1, _SPECS["Shock Blast"], 0, [eh], -1, True)
    if (int(s.perms[eh, _PDMG]) == 0) != (runes >= 7):
        die("esteemed hierophant", f"{runes} runes: dmg {int(s.perms[eh, _PDMG])}")
ok("Esteemed Hierophant ignores enemy spell damage with 7+ runes")

s = fresh()
tank = next(c for c in range(T.n) if T.is_type(c, "Unit") and T.has(c, "Tank")
            and not T.is_token(c))
t = s.add_permanent(tank, 1, bf_loc(0))
soft = s.add_permanent(P3, 1, bf_loc(0))
from rl.engine.combat import _assign as _asg
kills = _asg(s, T, 3, [t, soft], 0)
if soft in kills:
    die("dune surfer", "without him, Tank absorbs first")
s = fresh()
t = s.add_permanent(tank, 1, bf_loc(0))
soft = s.add_permanent(P3, 1, bf_loc(0))
s.add_permanent(T.id_of("Dune Surfer"), 0, bf_loc(0))
if soft not in _asg(s, T, 3, [t, soft], 0):
    die("dune surfer", "his controller ignores Tank here")
ok("Dune Surfer lets you ignore [Tank] when assigning at his battlefield")

s = fresh()
lz = s.add_permanent(T.id_of("Leona - Zealot"), 0, bf_loc(0))
big = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
small = s.add_permanent(P3, 1, bf_loc(0))
far = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(1))
for r in (big, small, far):
    s.stun(r)
if (combat.might(s, T, big), combat.might(s, T, small), combat.might(s, T, far)) != (2, 1, 10):
    die("leona zealot", "stunned enemies here -8, to a minimum of 1")
s.points[1] = s.victory_score - 3
if not combat.permanent_enters_ready(s, T, 0, T.id_of("Leona - Zealot"), True):
    die("leona zealot", "enters ready when an opponent is near victory")
ok("Leona - Zealot shrinks stunned enemies here to a floor of 1")

# ---------------------------------------------------------------------------
print("\n[modal] 'Choose one --' as a leading mode slot")

from rl.engine.effects import compose_mode as _cm, TK_MODE as _TKM

# Composition renumbers the mode's slots behind the mode slot.
fl = _SPECS["Flurry of Feathers"]
c0 = _cm(fl, 0)
if [t.kind for t in c0.targets] != [_TKM, _rsv.TK_SPELL] or c0.ops[0].target != 1:
    die("modal", "mode 0 = mode slot then the spell slot, ops shifted to 1")
ok("compose_mode puts the mode first and renumbers the mode's own slots")

# Offered modes are exactly the castable ones: with nothing on the Chain,
# Flurry's counter mode cannot be chosen, and the token mode can.
s = fresh(hand=[T.id_of("Flurry of Feathers")], runes=8)
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
modes = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
if modes != [1]:
    die("flurry of feathers", f"nothing to counter -> only the Birds: {modes}")
n0 = int(s.n_perms)
A.apply(s, T, V1, A.Action(A.A_TARGET, 1))
_settle(s)
if int(s.n_perms) != n0 + 4:
    die("flurry of feathers", "four Birds")
ok("Flurry of Feathers offers only castable modes, and the Birds mode resolves")

s = fresh(hand=[T.id_of("Flurry of Feathers")], runes=8)
s.active = s.priority = 1
item = chain_mod.push(s, T.id_of("Progress Day"), 1)
chain_mod.finalize(s, item)
s.priority = 0
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
modes = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
if modes != [0, 1]:
    die("flurry of feathers", f"a spell on the Chain -> both modes: {modes}")
A.apply(s, T, V1, A.Action(A.A_TARGET, 0))
tg = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
if tg != [int(s.chain[item, _CUID])]:
    die("flurry of feathers", f"counter mode then asks for the spell: {tg}")
A.apply(s, T, V1, A.Action(A.A_TARGET, tg[0]))
log = {}
for _ in range(6):
    if s.n_chain == 0:
        break
    who = A.acting_seat(s)
    log = A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, who)
                                 if a.kind == A.A_PASS))
if s.n_chain:
    die("flurry of feathers", "the chain should have emptied")
if T.id_of("Progress Day") not in list(s.trash[1, :int(s.n_trash[1])]):
    die("flurry of feathers", "the countered spell is in its owner's trash")
ok("Flurry of Feathers' counter mode targets and counters a spell")

s = fresh()
mb = s.add_permanent(T.id_of("Minah Swiftfoot"), 0, bf_loc(0))
s.bf_ctrl[0] = 0
h0, h1 = int(s.n_hand[0]), int(s.n_hand[1])
combat.queue_move_trigger(s, T, mb, base_loc(0), bf_loc(0))
_to_decision(s)
if sorted(a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET) != [0, 1]:
    die("minah", "a triggered ability offers its modes")
A.apply(s, T, V1, A.Action(A.A_TARGET, 1))
_settle(s)
if (int(s.n_hand[0]) - h0, int(s.n_hand[1]) - h1) != (1, 1):
    die("minah", "each player draws 1")
ok("Minah Swiftfoot's move trigger asks for a mode and resolves it")

s = fresh()
bc = s.add_permanent(T.id_of("Buhru Captain"), 0, base_loc(0))
chain.fire(s, T, V1, _TRP, bc)
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_TARGET, 1))
_settle(s)
if not _buffed(s, bc):
    die("buhru captain", "'you may draw 1 or buff me' -- buff mode")
ok("Buhru Captain: an optional ability with modes")

s = fresh(hand=[P3, P3])
bw = s.add_permanent(T.id_of("Bewitching Spirit"), 0, base_loc(0))
s.hand[1, :2] = P3
s.n_hand[1] = 2
chain.fire(s, T, V1, _TRP, bw)
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_TARGET, 1))
_settle(s)
if (int(s.n_hand[0]), int(s.n_hand[1])) != (2, 1):
    die("bewitching spirit", "the chosen player (opponent) discards")
ok("Bewitching Spirit makes the chosen player discard")

s = fresh()
jy = s.add_permanent(T.id_of("Jayce, Hammer in Hand"), 0, base_loc(0), ready=False)
from rl.engine.effects import TR_READIED as _TRRD
chain.fire(s, T, V1, _TRRD, jy, subj=jy)
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_TARGET, 2))
_settle(s)
if not combat.perm_kw(s, T, jy, "Ganking"):
    die("jayce hammer", "chose Ganking")
ok("Jayce, Hammer in Hand picks a keyword when he readies")

# The mode row in the observation carries the mode index.
from rl.obs import Encoder as _Enc
s = fresh(hand=[T.id_of("Rocket Barrage")], runes=8)
s.add_permanent(P3, 1, base_loc(1))
s.add_permanent(ROSE, 1, base_loc(1))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
enc = _Enc(T, V1)
legal = A.legal_actions(s, T, V1, 0)
rows = [enc._action_row(a, s, 0) for a in legal]
if len(rows) != 2 or (rows[0] == rows[1]).all():
    die("modal obs", "the two mode actions must encode differently")
ok("the observation tells mode actions apart")

# ---------------------------------------------------------------------------
print("\n[Unique] three Ornn Equipment")

s = fresh()
host = s.add_permanent(P3, 0, base_loc(0))
cape = s.add_permanent(T.id_of("Forgefire Cape"), 0, base_loc(0))
s.attach(cape, host)
e1 = s.add_permanent(T.id_of("Mountain Drake"), 1, base_loc(0))
e2 = s.add_permanent(T.id_of("Mountain Drake"), 1, base_loc(0))
far = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
chain_mod.queue(s, _TRAD, host, base_loc(0), subj=host)
_settle(s)
if [int(s.perms[r, _PDMG]) for r in (e1, e2, far)] != [2, 2, 0]:
    die("forgefire cape", "2 to every enemy unit where the unit is")
if combat.might(s, T, host) != 6:
    die("forgefire cape", "+3 Might bonus")
ok("Forgefire Cape: the equipped unit's attack/defend hits every enemy there")

s = fresh()
host = s.add_permanent(P3, 0, base_loc(0))
crown = s.add_permanent(T.id_of("Rabadon's Deathcrown"), 0, base_loc(0))
e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Shock Blast"], 0, [e], -1, True)
if int(s.perms[e, _PDMG]) != 4:
    die("rabadon's", "unattached: no bonus")
s.attach(crown, host)
_rsv.resolve(s, T, V1, _SPECS["Shock Blast"], 0, [e], -1, True)
if int(s.perms[e, _PDMG]) != 4 + 7:
    die("rabadon's", "attached: +3 Bonus Damage on your spells")
ok("Rabadon's Deathcrown adds 3 Bonus Damage only while attached")

s = fresh()
a = s.add_permanent(P3, 0, bf_loc(0), ready=False)
b = s.add_permanent(P3, 0, base_loc(0), ready=False)
sr = s.add_permanent(T.id_of("Shurelya's Requiem"), 0, base_loc(0))
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Shurelya's Requiem"))[0], 0,
             [], -1, False, source=sr)
if not (int(s.perms[a, P_READY]) and int(s.perms[b, P_READY])):
    die("shurelya's", "playing it readies your units")
s.attach(sr, a)
if not combat.perm_kw(s, T, a, "Ganking") or combat.perm_kw(s, T, b, "Ganking"):
    die("shurelya's", "your units HERE (the host's location) have Ganking")
pal = s.add_permanent(P3, 0, bf_loc(0))
if not combat.perm_kw(s, T, pal, "Ganking"):
    die("shurelya's", "another friendly unit at the host's battlefield has it too")
ok("Shurelya's Requiem readies on play and gives Ganking at its host's location")

# ---------------------------------------------------------------------------
print("\n[per-player walks] turn order from the first seat, and three new "
      "instructions on the same machinery")

def _walk(s, pick):
    """Answer each seat's choice with `pick(seat, candidates)`."""
    order = []
    for _ in range(6):
        if s.pend_cull < 0:
            break
        who = int(s.pend_cull)
        order.append(who)
        cands = [a.arg for a in A.legal_actions(s, T, V1, who) if a.kind == A.A_TARGET]
        A.apply(s, T, V1, A.Action(A.A_TARGET, pick(who, cands)))
    return order

for caster in (0, 1):
    s = fresh()
    s.active = s.priority = caster
    u0 = s.add_permanent(P3, 0, base_loc(0))
    u1 = s.add_permanent(P3, 1, base_loc(1))
    _rsv.resolve(s, T, V1, _SPECS["Cull the Weak"], caster, [], -1, True)
    order = _walk(s, lambda who, c: c[0])
    if order != [caster, 1 - caster] or s.perms[u0, P_ALIVE] or s.perms[u1, P_ALIVE]:
        die("cull the weak", f"caster {caster}: order {order}, both kill")
ok("Cull the Weak walks BOTH seats whoever casts it (seat 1 used to skip seat 0)")

s = fresh()
mine = s.add_permanent(P3, 0, base_loc(0))
theirs = s.add_permanent(P3, 1, base_loc(1))
_rsv.resolve(s, T, V1, _SPECS["Whirlwind"], 0, [], -1, True)
order = _walk(s, lambda who, c: theirs if who == 1 else -1)
if order != [1, 0] or not s.perms[mine, P_ALIVE] or s.perms[theirs, P_ALIVE]:
    die("whirlwind", f"next player first, 'may' allowed: {order}")
if P3 not in list(s.hand[1, :int(s.n_hand[1])]):
    die("whirlwind", "returned to its OWNER's hand")
ok("Whirlwind starts with the next player and each may return any unit")

s = fresh()
keep0 = s.add_permanent(P3, 0, base_loc(0))
lose0 = s.add_permanent(P3, 0, bf_loc(0))
keep1 = s.add_permanent(P3, 1, base_loc(1))
lose1 = s.add_permanent(P3, 1, bf_loc(1))
_rsv.resolve(s, T, V1, _SPECS["Cataclysmic Duel"], 0, [], -1, True)
_walk(s, lambda who, c: keep0 if who == 0 else keep1)
alive = [bool(s.perms[r, P_ALIVE]) for r in (keep0, lose0, keep1, lose1)]
if alive != [True, False, True, False]:
    die("cataclysmic duel", f"each keeps one, the rest die: {alive}")
ok("Cataclysmic Duel keeps each player's chosen unit and kills the rest")

s = fresh()
mine = s.add_permanent(P3, 0, base_loc(0))
theirs = s.add_permanent(P3, 1, base_loc(1))
_rsv.resolve(s, T, V1, _SPECS["King's Edict"], 0, [], -1, True)
order = _walk(s, lambda who, c: c[0])
if order != [1] or s.perms[theirs, P_ALIVE] or not s.perms[mine, P_ALIVE]:
    die("king's edict", f"only the opponent chooses, and loses it: {order}")
ok("King's Edict makes the opponent kill one of their own")

# ---------------------------------------------------------------------------
print("\n[batch 16] end-of-turn reversals, a mode spent for the turn, control "
      "changes, base Might, a Level-gated slot")

s = fresh()
u = s.add_permanent(P3, 1, base_loc(1))
_rsv.resolve(s, T, V1, _cm(_SPECS["Sanction"], 0), 0, [0, u], -1, True)
if not int(s.perms[u, _PF]) & _FEMP:
    die("sanction", "mode 0 empowers")
_ph3.ending(s)
if int(s.perms[u, _PF]) & _FEMP:
    die("sanction", "...and disempowers at end of turn")
s = fresh()
u = s.add_permanent(P3, 1, base_loc(1))
opts = _rsv.legal_targets(s, T, _SPECS["Sanction"], 0, 0, [], -1)
if opts != [0]:
    die("sanction", f"nothing Empowered -> only mode 0: {opts}")
s.set_flag(u, _FEMP)
s.perms[u, __import__("rl.engine.state", fromlist=["P_EMPOWER"]).P_EMPOWER] = 1
_rsv.resolve(s, T, V1, _cm(_SPECS["Sanction"], 1), 0, [1, u], -1, True)
if int(s.perms[u, _PF]) & _FEMP:
    die("sanction", "mode 1 disempowers")
_ph3.ending(s)
if not int(s.perms[u, _PF]) & _FEMP:
    die("sanction", "...and empowers again at end of turn")
ok("Sanction's two modes each reverse themselves at end of turn")

s = fresh(runes=8)
ud = s.add_permanent(T.id_of("Udyr - Wildman"), 0, base_loc(0), ready=False)
def _udyr_modes():
    s.set_flag(ud, _FB)
    acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
    if not acts:
        return None
    A.apply(s, T, V1, acts[0])
    return sorted(a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET)
first = _udyr_modes()
if first != [2, 3]:                 # no unit at a battlefield -> no damage/stun
    die("udyr", f"modes with targets available: {first}")
A.apply(s, T, V1, A.Action(A.A_TARGET, 2))
_settle(s)
if int(s.perms[ud, P_READY]) != 1 or _buffed(s, ud):
    die("udyr", "spent the buff, readied")
second = _udyr_modes()
if second != [3]:
    die("udyr", f"'ready me' already chosen this turn: {second}")
A.apply(s, T, V1, A.Action(A.A_TARGET, 3))
_settle(s)
if _udyr_modes() is not None:
    die("udyr", "every available mode spent -> not activatable")
s.ply += 1
if _udyr_modes() != [2, 3]:
    die("udyr", "a new turn restores the modes")
ok("Udyr - Wildman spends each mode once a turn, and stops offering itself when none remain")

s = fresh()
tw = s.add_permanent(T.id_of("Tornado Warrior"), 0, bf_loc(0))
pal = s.add_permanent(P3, 0, bf_loc(0))
s.set_flag(tw, __import__("rl.engine.state", fromlist=["F_FROM_HIDDEN"]).F_FROM_HIDDEN)
chain.fire(s, T, V1, _TRP, tw)
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_TARGET, pal))
_settle(s)
if not int(s.perms[pal, _PF]) & _FEMP:
    die("tornado warrior", "empowers something here")
_ph3.ending(s)
if int(s.perms[pal, _PF]) & _FEMP:
    die("tornado warrior", "disempowered at end of turn")
ok("Tornado Warrior's Empower lasts until end of turn")

s = fresh()
a = s.add_permanent(P3, 0, base_loc(0))
b = s.add_permanent(T.id_of("Mountain Drake"), 0, base_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Stand United"], 0, [a], -1, True)
s.set_flag(b, _FB)
if combat.might(s, T, a) != 5 or combat.might(s, T, b) != 12:
    die("stand united", "buffs give +2 this turn, to every friendly buffed unit")
s.ply += 1
if combat.might(s, T, a) != 4:
    die("stand united", "back to +1 next turn")
ok("Stand United doubles what a Buff gives for the turn")

s = fresh()
d = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Dragon Form"], 0, [d], -1, True)
s.set_flag(d, _FB)
if combat.might(s, T, d) != 6:
    die("dragon form", "base 5, buff still applies")
s.perms[d, _PDMG] = 5
_rsv.resolve(s, T, V1, _SPECS["Dragon Form"], 0, [d], -1, True)
if not s.perms[d, P_ALIVE]:
    die("dragon form", "damage below the new Might does not kill")
s2 = fresh()
d2 = s2.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
s2.perms[d2, _PDMG] = 6
_rsv.resolve(s2, T, V1, _SPECS["Dragon Form"], 0, [d2], -1, True)
if s2.perms[d2, P_ALIVE]:
    die("dragon form", "shrinking to 5 under 6 damage kills (143.2.a)")
ok("Dragon Form sets base Might to 5 for the turn, and 143.2.a still applies")

for xp, want in ((5, 2), (6, 3)):
    s = fresh()
    s.xp[0] = xp
    e = s.add_permanent(P3, 1, bf_loc(0))
    e2 = s.add_permanent(P3, 1, bf_loc(1))
    spec = _SPECS["Skyward Strike"]
    chosen = [e, base_loc(1)]
    ok_all = _rsv._can_complete(s, T, spec, 0, 0, [], -1)
    third = _rsv.legal_targets(s, T, spec, 2, 0, chosen, -1)
    if not ok_all or (len(third) > 0) != (xp >= 6):
        die("skyward strike", f"xp {xp}: stun slot options {third}")
ok("Skyward Strike's stun slot opens only at Level 6")

s = fresh()
e = s.add_permanent(P3, 1, bf_loc(1))
m1 = s.add_permanent(P3, 0, bf_loc(0))
m2 = s.add_permanent(P3, 0, bf_loc(0))
s.add_permanent(P3, 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Shadow Dash"], 0, [e, bf_loc(0)], -1, True)
if int(s.perms[e, P_LOC]) != bf_loc(0) or combat.might(s, T, m1) != 4:
    die("shadow dash", "moved in, and exactly two of yours there get +1")
ok("Shadow Dash drags an enemy onto your pair and pumps them")

s = fresh()
e = s.add_permanent(P3, 1, bf_loc(1))
s.add_permanent(P3, 1, bf_loc(0))
dests = _rsv.legal_targets(s, T, _SPECS["Temptation"], 1, 0, [e], -1)
if dests != [bf_loc(0)]:
    die("temptation", f"only where another of its controller's units is: {dests}")
ok("Temptation moves an enemy only to where its allies stand")

s = fresh()
u_bf = s.add_permanent(P3, 1, bf_loc(0))
u_base = s.add_permanent(P3, 1, base_loc(1))
g = s.add_permanent(ROSE, 1, base_loc(1))
opts = _rsv.legal_targets(s, T, _SPECS["Fading Memories"], 0, 0, [], -1)
if u_bf not in opts or g not in opts or u_base in opts:
    die("fading memories", f"a unit at a battlefield OR a gear: {opts}")
ok("Fading Memories reaches units at battlefields and gear anywhere")

s = fresh()
e = s.add_permanent(P3, 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Possession"], 0, [e], -1, True)
if int(s.perms[e, P_CTRL]) != 0 or int(s.perms[e, P_LOC]) != base_loc(0) \
        or int(s.perms[e, __import__("rl.engine.state", fromlist=["P_OWNER"]).P_OWNER]) != 1:
    die("possession", "control to you, recalled to YOUR base, owner unchanged")
_ph3.ending(s)
if int(s.perms[e, P_CTRL]) != 0:
    die("possession", "permanent")
ok("Possession takes a unit for good and recalls it to your base")

s = fresh()
e = s.add_permanent(P3, 1, bf_loc(0), ready=False)
_rsv.resolve(s, T, V1, _SPECS["Hostile Takeover"], 0, [e], -1, True)
if int(s.perms[e, P_CTRL]) != 0 or int(s.perms[e, P_LOC]) != bf_loc(0) \
        or int(s.perms[e, P_READY]) != 1:
    die("hostile takeover", "yours, ready, where it stood")
_ph3.ending(s)
if int(s.perms[e, P_CTRL]) != 1 or int(s.perms[e, P_LOC]) != base_loc(1):
    die("hostile takeover", "back to its owner, recalled, at end of turn")
ok("Hostile Takeover borrows a unit for the turn")

s = fresh()
ap = s.add_permanent(T.id_of("Aphelios - Exalted"), 0, base_loc(0))
for _ in range(2):
    sw = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
    _rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Long Sword"))[0], 0, [ap],
                 -1, False, source=sw)
    _to_decision(s)
    modes = sorted(a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET)
    A.apply(s, T, V1, A.Action(A.A_TARGET, modes[0]))
    _settle(s)
if modes != [1, 2]:
    die("aphelios", f"the second attach cannot repeat mode 0: {modes}")
ok("Aphelios - Exalted can't repeat a mode in the same turn")

# ---------------------------------------------------------------------------
print("\n[reveal] reveal the top card, keep it on a match")

for top, want_hand, want_trash in ((P3, 1, 0), (T.id_of("Progress Day"), 0, 1)):
    s = fresh()
    s.deck[0, 0] = top
    pk = s.add_permanent(T.id_of("Pakaa Protector"), 0, base_loc(0))
    h0, t0, m0 = int(s.n_hand[0]), int(s.n_trash[0]), combat.might(s, T, pk)
    _rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Pakaa Protector"))[0], 0,
                 [], -1, False, source=pk)
    if (int(s.n_hand[0]) - h0, int(s.n_trash[0]) - t0) != (want_hand, want_trash) \
            or (combat.might(s, T, pk) == m0 + 2) != bool(want_trash):
        die("pakaa protector", f"top={T.names[top]}")
ok("Pakaa Protector draws a unit, or trashes the card and gets +2")

s = fresh()
s.deck[0, 0] = P3
n0 = int(s.n_deck[0])
sm = s.add_permanent(T.id_of("Apprentice Smith"), 0, base_loc(0))
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Apprentice Smith"))[0], 0,
             [], -1, False, source=sm)
if int(s.deck[0, int(s.n_deck[0]) - 1]) != P3 or int(s.deck_ptr[0]) != 1:
    die("apprentice smith", "not a gear -> recycled to the bottom")
ok("Apprentice Smith recycles a card that is not a gear")

# ---------------------------------------------------------------------------
print("\n[discard me] abilities that fire from the trash a card was discarded to")

s = fresh(hand=[T.id_of("Mask Mother")])
pal = s.add_permanent(P3, 0, base_loc(0))
_ph3.discard(s, T, 0, 1)
if not _to_decision(s) or s.pend_may < 0:
    die("mask mother", "discarding her offers the paid pump")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_TARGET, pal))
_settle(s)
if combat.might(s, T, pal) != 5:
    die("mask mother", "+2 to the chosen friendly unit")
ok("Mask Mother pays off from the trash when discarded")

s = fresh(hand=[T.id_of("Flame Chompers")])
_ph3.discard(s, T, 0, 1)
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_TARGET, base_loc(0)))
_settle(s)
fc = T.id_of("Flame Chompers")
on_board = any(s.perms[i, P_ALIVE] and int(s.perms[i, P_CARD]) == fc
               for i in range(s.n_perms))
if not on_board or fc in list(s.trash[0, :int(s.n_trash[0])]):
    die("flame chompers", "paid Fury: played from the trash onto the board")
ok("Flame Chompers plays itself out of the trash it was discarded to")

s = fresh(hand=[T.id_of("Scrapheap"), P3])
h0 = int(s.n_hand[0])
_ph3.discard(s, T, 0, 1)                      # oldest: Scrapheap
_settle(s)
if int(s.n_hand[0]) != h0:                    # -1 discarded, +1 drawn
    die("scrapheap", "discarding it draws 1")
s = fresh(hand=[P3])
_ph3.discard(s, T, 0, 1)
if int(s.n_trig):
    die("scrapheap", "an ordinary discard queues nothing")
ok("Scrapheap draws when discarded; plain discards queue nothing")

# ---------------------------------------------------------------------------
print("\n[trash] a conquer trigger from the trash, a points-capped replay, a Flow discount")

rocket = T.id_of("Super Mega Death Rocket!")
s = fresh(hand=[P3])
s.trash[0, 0] = rocket
s.n_trash[0] = 1
u = s.add_permanent(P3, 0, bf_loc(0))
combat._establish_control(s, T, V1, 0)
if not _to_decision(s) or s.pend_may < 0:
    die("rocket", "conquering offers the return from the trash")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_settle(s)
hand = list(s.hand[0, :int(s.n_hand[0])])
if rocket not in hand or P3 in hand or rocket in list(s.trash[0, :int(s.n_trash[0])]):
    die("rocket", "discard 1 (the P3), Rocket back to hand")
s = fresh()
s.trash[0, 0] = rocket
s.n_trash[0] = 1
s.add_permanent(P3, 0, bf_loc(0))
combat._establish_control(s, T, V1, 0)
_to_decision(s)
if A.A_ACCEPT in {a.kind for a in A.legal_actions(s, T, V1, 0)}:
    die("rocket", "an empty hand can't pay the discard")
ok("Super Mega Death Rocket! returns from the trash on a conquer, for a discard")

s = fresh(runes=8)
s.points[0] = 3
cheap, dear = T.id_of("Dredge Up"), T.id_of("Shock Blast")      # 2 and 3 energy
s.trash[0, :2] = [cheap, dear]
s.n_trash[0] = 2
s.add_permanent(P3, 1, bf_loc(0))
spec = abilities_for(T, T.id_of("Kai'Sa - Evolutionary"))[0]
opts = [_rsv.unpack_trash(x)[1] for x in _rsv.legal_targets(s, T, spec, 0, 0, [], -1)]
if cheap not in opts or dear in opts:
    die("kai'sa evolutionary", f"Energy cost LESS THAN 3 points: {[T.names[c] for c in opts]}")
ok("Kai'Sa - Evolutionary replays a spell costing less than your points")

s = fresh()
from rl.engine.cost import flow_energy as _fe
dragon_form = T.id_of("Dragon Form")                      # Flow {3 energy}
if _fe(s, T, 0, dragon_form) != 3:
    die("stargazer", "baseline Flow cost")
s.add_permanent(T.id_of("Stargazer"), 0, base_loc(0))
if _fe(s, T, 0, dragon_form) != 1:
    die("stargazer", "{2} less")
s.add_permanent(T.id_of("Stargazer"), 0, base_loc(0))
if _fe(s, T, 0, dragon_form) != 1:
    die("stargazer", "to a minimum of {1}, even with two")
ok("Stargazer discounts Flow plays to a floor of 1")

# ---------------------------------------------------------------------------
print("\n[ask] another player answers, and the caster's follow-up runs")

for yes in (True, False):
    s = fresh()
    e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
    h0 = int(s.n_hand[0])
    _rsv.resolve(s, T, V1, _SPECS["Shakedown"], 0, [e], -1, True)
    if A.acting_seat(s) != 1 or s.pend_ask != 1:
        die("shakedown", "its CONTROLLER is asked")
    A.apply(s, T, V1, A.Action(A.A_ACCEPT if yes else A.A_DECLINE))
    got = (int(s.n_hand[0]) - h0, int(s.perms[e, _PDMG]))
    if got != ((2, 0) if yes else (0, 6)):
        die("shakedown", f"yes={yes}: (drawn, damage) = {got}")
ok("Shakedown: they let you draw 2, or take 6")

for yes in (True, False):
    s = fresh()
    s.rune_left[:] = 5
    h, r = (int(s.n_hand[0]), int(s.n_hand[1])), (int(s.runes_in_play(0).sum()),
                                                  int(s.runes_in_play(1).sum()))
    _rsv.resolve(s, T, V1, _SPECS["Party Favors"], 0, [], -1, True)
    A.apply(s, T, V1, A.Action(A.A_ACCEPT if yes else A.A_DECLINE))
    dh = (int(s.n_hand[0]) - h[0], int(s.n_hand[1]) - h[1])
    dr = (int(s.runes_in_play(0).sum()) - r[0], int(s.runes_in_play(1).sum()) - r[1])
    if (dh, dr) != (((1, 1), (0, 0)) if yes else ((0, 0), (1, 1))):
        die("party favors", f"yes={yes}: hands {dh} runes {dr}")
ok("Party Favors: the opponent picks Cards or Runes for both players")

for yes in (True, False):
    s = fresh()
    e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
    _rsv.resolve(s, T, V1, _SPECS["Keeper's Verdict"], 0, [e], -1, True)
    A.apply(s, T, V1, A.Action(A.A_ACCEPT if yes else A.A_DECLINE))
    drake = T.id_of("Mountain Drake")
    top = int(s.deck[1, int(s.deck_ptr[1])])
    bottom = int(s.deck[1, int(s.n_deck[1]) - 1])
    if s.perms[e, P_ALIVE] or (top == drake) != yes or (bottom == drake) == yes:
        die("keeper's verdict", f"yes={yes}: top={T.names[top]} bottom={T.names[bottom]}")
ok("Keeper's Verdict: its owner puts it on top or at the bottom")

for mine, theirs in ((True, True), (False, True), (True, False)):
    s = fresh()
    cs = s.add_permanent(T.id_of("Card Sharp"), 0, base_loc(0))
    chain.fire(s, T, V1, _TRP, cs)
    _settle_n = 0
    while s.n_chain and _settle_n < 6:
        who = A.acting_seat(s)
        if s.pend_ask >= 0:
            break
        A.apply(s, T, V1, A.Action(A.A_PASS))
        _settle_n += 1
    if s.pend_ask != 0:
        die("card sharp", "you are asked first")
    A.apply(s, T, V1, A.Action(A.A_ACCEPT if mine else A.A_DECLINE))
    if s.pend_ask != 1:
        die("card sharp", "then the opponent")
    A.apply(s, T, V1, A.Action(A.A_ACCEPT if theirs else A.A_DECLINE))
    golds = [sum(1 for i in range(s.n_perms) if s.perms[i, P_ALIVE]
                 and T.names[int(s.perms[i, P_CARD])] == "Gold // Buff"
                 and int(s.perms[i, P_CTRL]) == seat) for seat in (0, 1)]
    want = [int(mine) + int(theirs), int(theirs)]
    if golds != want:
        die("card sharp", f"mine={mine} theirs={theirs}: golds {golds}, want {want}")
ok("Card Sharp: Golds for whoever takes one, and one more for you per opponent who did")

# ---------------------------------------------------------------------------
print("\n[batch 18] doubled conquer/hold effects, a first Beginning-Phase death, "
      "a stun that pulls, and damage that always kills")

s = fresh()
rb = s.add_permanent(T.id_of("Red Brambleback"), 0, bf_loc(0))
war = s.add_permanent(P3, 0, bf_loc(0))
wa = s.add_permanent(T.id_of("Warmog's Armor"), 0, bf_loc(0))
s.attach(wa, war)
combat._establish_control(s, T, V1, 0)
srcs = sorted(int(s.trig[t, 1]) for t in range(int(s.n_trig)))
if srcs != sorted([rb, rb, war, war]):
    die("red brambleback", f"every conquer effect here twice: {srcs}")
ok("Red Brambleback makes conquer effects at its battlefield trigger twice")

s = fresh()
bs = s.add_permanent(T.id_of("Blue Sentinel"), 0, bf_loc(0))
s.bf_ctrl[0] = 0
_ph3.score_holds(s, V1, T)
if int(s.n_trig) != 2:
    die("blue sentinel", "its own hold trigger, twice")
_settle(s)
if int(s.pending_add_any[0]) != 2:
    die("blue sentinel", "two [A] owed for the next Main Phase")
s.phase = _BEG
_ph3.enter_main(s)
if int(s.pool_power[0, _DANY]) != 2:
    die("blue sentinel", "paid into the pool at the start of Main")
ok("Blue Sentinel doubles hold effects and banks [A] for the Main Phase")

s = fresh()
s.add_permanent(T.id_of("Shard of Undoing"), 0, base_loc(0))
mine1 = s.add_permanent(P3, 0, base_loc(0))
mine2 = s.add_permanent(P3, 0, base_loc(0))
foe = s.add_permanent(P3, 1, base_loc(1))
s.phase = _BEG
combat.destroy(s, T, mine1)
combat.destroy(s, T, mine2)
if int(s.n_trig) != 1:
    die("shard of undoing", "only the FIRST death each turn")
s.phase = MAIN
_settle(s)
if s.pend_cull != 1:
    die("shard of undoing", "the opponent must kill one")
A.apply(s, T, V1, A.Action(A.A_TARGET, foe))
if s.perms[foe, P_ALIVE]:
    die("shard of undoing", "their unit dies")
ok("Shard of Undoing punishes the first Beginning-Phase death once a turn")

s = fresh()
vx = s.add_permanent(T.id_of("Vex - Mocking"), 0, base_loc(0))
e = s.add_permanent(P3, 1, bf_loc(1))
e_base = s.add_permanent(P3, 1, base_loc(1))
_rsv.resolve(s, T, V1, _STUN_SPEC, 0, [e_base], -1, True)
if int(s.n_trig):
    die("vex mocking", "a stun at a BASE is not at a battlefield")
_rsv.resolve(s, T, V1, _STUN_SPEC, 0, [e], -1, True)
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
_settle(s)
if int(s.perms[vx, P_LOC]) != bf_loc(1):
    die("vex mocking", "moves to the stunned unit's battlefield")
ok("Vex - Mocking follows a stun to its battlefield")

s = fresh()
ed = s.add_permanent(T.id_of("Elder Dragon"), 0, base_loc(0))
b0 = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
b1 = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(1))
eb = s.add_permanent(T.id_of("Mountain Drake"), 1, base_loc(1))
extra = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
spec = abilities_for(T, T.id_of("Elder Dragon"))[0]
if sorted(_rsv.legal_targets(s, T, spec, 1, 0, [-1], -1)) != [eb]:
    die("elder dragon", "slot 1 is the opponent's base only")
_rsv.resolve(s, T, V1, spec, 0, [-1, eb, b0, b1], -1, False, source=ed)
if any(s.perms[r, P_ALIVE] for r in (eb, b0, b1)) or not s.perms[extra, P_ALIVE]:
    die("elder dragon", "1 damage kills each chosen enemy; one per location")
from rl.engine.combat import _assign as _asg2
s2 = fresh()
s2.add_permanent(T.id_of("Elder Dragon"), 0, bf_loc(0))
big1 = s2.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
big2 = s2.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
if sorted(_asg2(s2, T, 2, [big1, big2], 0)) != sorted([big1, big2]):
    die("elder dragon", "a combat pool of 2 kills two 10-Might enemies")
ok("Elder Dragon: any of your damage kills an enemy, in spells and in combat")

# ---------------------------------------------------------------------------
print("\n[batch 19] damage shields, banish-instead, extra turns, discard costs, "
      "XP additional costs, a clone token")

SB = _SPECS["Shock Blast"]                             # deal 4
s = fresh()
d = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Ki Barrier"], 1, [d], -1, True)
_rsv.resolve(s, T, V1, SB, 0, [d], -1, True)
_rsv.resolve(s, T, V1, SB, 0, [d], -1, True)
if int(s.perms[d, _PDMG]) != 1:
    die("ki barrier", f"prevents the next 7 in total: {int(s.perms[d, _PDMG])}")
s = fresh()
d = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Counter Strike"], 1, [d], -1, True)
_rsv.resolve(s, T, V1, SB, 0, [d], -1, True)
_rsv.resolve(s, T, V1, SB, 0, [d], -1, True)
if int(s.perms[d, _PDMG]) != 4:
    die("counter strike", "the whole NEXT instance only")
s = fresh()
d = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Lotus Trap"], 0, [d], -1, True)
_rsv.resolve(s, T, V1, SB, 0, [d], -1, True)
if int(s.perms[d, _PDMG]) != 8:
    die("lotus trap", "doubled")
ok("Ki Barrier, Counter Strike and Lotus Trap modify spell damage")

from rl.engine.combat import _assign as _asg3, lethal_cost as _lc
s = fresh()
d = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Ki Barrier"], 1, [d], -1, True)
if _lc(s, T, d) != 17 or _asg3(s, T, 16, [d], 0):
    die("ki barrier", "combat needs 10 + 7 to kill")
s = fresh()
d = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Lotus Trap"], 0, [d], -1, True)
if _lc(s, T, d) != 5 or _asg3(s, T, 5, [d], 0) != [d]:
    die("lotus trap", "5 doubled is lethal on 10")
ok("the same modifiers change what combat must assign to kill")

s = fresh()
u = s.add_permanent(P3, 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Smite"], 0, [u], -1, True)
if s.perms[u, P_ALIVE] or P3 in list(s.trash[1, :int(s.n_trash[1])]) \
        or P3 not in list(s.banished[1, :int(s.n_banished[1])]):
    die("smite", "3 kills a 3-Might unit -- banished instead of trashed")
ok("Smite banishes what it kills")

s = fresh(hand=[T.id_of("Arcane Shift")], runes=8)
f = s.add_permanent(P3, 0, bf_loc(0), ready=False)
e = s.add_permanent(P3, 1, bf_loc(1))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_TARGET, f))
A.apply(s, T, V1, A.Action(A.A_TARGET, e))
_settle(s)
if s.perms[e, P_ALIVE] or T.id_of("Arcane Shift") not in list(s.banished[0, :int(s.n_banished[0])]):
    die("arcane shift", "3 to the enemy, and the spell banishes itself")
if not any(s.perms[i, P_ALIVE] and int(s.perms[i, P_CARD]) == P3
           and int(s.perms[i, P_CTRL]) == 0 and int(s.perms[i, P_LOC]) == base_loc(0)
           for i in range(s.n_perms)):
    die("arcane shift", "the friendly unit comes back at its owner's base")
ok("Arcane Shift blinks a unit, hits an enemy, and banishes itself")

s = fresh()
f = s.add_permanent(P3, 0, base_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Thrill of the Hunt"], 0, [f, bf_loc(1)], -1, True)
if not any(s.perms[i, P_ALIVE] and int(s.perms[i, P_CARD]) == P3
           and int(s.perms[i, P_LOC]) == bf_loc(1) for i in range(s.n_perms)):
    die("thrill of the hunt", "played back to the chosen battlefield")
ok("Thrill of the Hunt replays a unit onto any battlefield")

s = fresh()
_rsv.resolve(s, T, V1, _SPECS["Time Warp"], 0, [], -1, True)
_ph3.end_turn(s, V1)
if s.active != 0:
    die("time warp", "the same player takes the next turn")
_ph3.end_turn(s, V1)
if s.active != 1:
    die("time warp", "just one extra turn")
ok("Time Warp grants one extra turn")

s = fresh(hand=[P3, T.id_of("Dredge Up")], runes=4)
mel = s.add_permanent(T.id_of("Mel, Defiant Soul"), 0, base_loc(0))
foe = s.add_permanent(P3, 1, bf_loc(0))
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
A.apply(s, T, V1, acts[0])
_settle(s)
hand = list(s.hand[0, :int(s.n_hand[0])])
if hand != [P3] or not int(s.perms[mel, _PF]) & _FEMP:
    die("mel defiant soul", "discarded the SPELL and empowered")
if s.perms[foe, P_ALIVE]:
    die("mel defiant soul", "becoming Empowered banishes a small enemy at a battlefield")
s = fresh(hand=[P3])
mel2 = s.add_permanent(T.id_of("Mel, Defiant Soul"), 0, base_loc(0))
if any(a.kind == A.A_ACTIVATE for a in A.legal_actions(s, T, V1, 0)):
    die("mel defiant soul", "no spell in hand -> no Empower")
ok("Mel, Defiant Soul pays [Empower] with a spell from hand")

s = fresh(hand=[P3])
pp = s.add_permanent(T.id_of("Punching Poro"), 0, base_loc(0))
A.apply(s, T, V1, [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE][0])
_settle(s)
if int(s.n_hand[0]) or combat.might(s, T, pp) != 3:
    die("punching poro", "discard 1 to Empower, +1 Might")
ok("Punching Poro discards to Empower")

s = fresh()
sd = s.add_permanent(T.id_of("Sun Disc"), 0, base_loc(0))
from rl.engine.state import P_ARRIVED as _P_ARR
s.perms[sd, _P_ARR] = -1          # on the board since an earlier turn
if any(a.kind == A.A_ACTIVATE for a in A.legal_actions(s, T, V1, 0)):
    die("sun disc", "[Legion]: nothing played yet")
s.cards_played[0] = 1
A.apply(s, T, V1, [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE][0])
_settle(s)
if not combat.permanent_enters_ready(s, T, 0, P3, True):
    die("sun disc", "the next unit enters ready")
t1 = s.add_permanent(P3, 0, base_loc(0))
chain_mod.fire_play_unit(s, T, 0, P3, t1)
if combat.permanent_enters_ready(s, T, 0, P3, True):
    die("sun disc", "...only the next one")
ok("Sun Disc readies the next unit you play, once")

s = fresh()
sr = s.add_permanent(T.id_of("Spirit's Refuge"), 0, base_loc(0))
plain_b = s.add_permanent(P3, 0, base_loc(0))
navori = next(c for c in range(T.n) if T.is_type(c, "Unit") and T.has(c, "Deflect")
              and not T.is_token(c))
dfl = s.add_permanent(navori, 0, base_loc(0))
for r in (plain_b, dfl):
    s.set_flag(r, _FB)
if combat.perm_kw(s, T, plain_b, "Deflect") != 1 or combat.perm_kw(s, T, dfl, "Deflect") != int(T.deflect[navori]):
    die("spirit's refuge", "Deflect for buffed units that lack it, and no stacking")
ok("Spirit's Refuge gives buffed units Deflect without stacking it")

poppy = T.id_of("Poppy - Defender of the Meek")
s = fresh(hand=[poppy], runes=0)
s.runes_ready[0, :] = 1                                  # six runes
s.xp[0] = 3
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
fast = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT_FAST]
if not fast:
    die("poppy defender", "3 XP buys the discount")
A.apply(s, T, V1, fast[0])
spent = int(s.runes_spent[0].sum())
if int(s.xp[0]) != 0 or spent != int(T.energy[poppy]) - 3:
    die("poppy defender", f"spent 3 XP and {int(T.energy[poppy]) - 3} runes: "
                          f"xp={int(s.xp[0])} runes={spent}")
ok("Poppy - Defender of the Meek trades 3 XP for {3 energy}")

for paid in (False, True):
    s = fresh()
    si = s.add_permanent(T.id_of("Safety Inspector"), 0, base_loc(0))
    mine = s.add_permanent(P3, 0, base_loc(0))
    theirs = s.add_permanent(P3, 1, base_loc(1))
    if paid:
        s.set_flag(si, __import__("rl.engine.state", fromlist=["F_PAID_ADDITIONAL"]).F_PAID_ADDITIONAL)
    chain.fire(s, T, V1, _TRP, si)
    order = []
    for _ in range(10):
        if s.pend_cull >= 0:
            who = int(s.pend_cull)
            order.append(who)
            A.apply(s, T, V1, A.Action(A.A_TARGET, mine if who == 0 else theirs))
        elif s.n_chain:
            A.apply(s, T, V1, A.Action(A.A_PASS))
        else:
            break
    if order != ([1] if paid else [0, 1]):
        die("safety inspector", f"paid={paid}: culling seats {order}")
ok("Safety Inspector: everyone kills one, unless you paid XP")

s = fresh()
zed = s.add_permanent(T.id_of("Zed, Without a Sound"), 0, bf_loc(0))
s.trash[0, 0] = P3
s.n_trash[0] = 1
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Zed, Without a Sound"))[0], 0,
             [], -1, False, source=zed)
clone = int(s.n_perms) - 1
if T.names[int(s.perms[clone, P_CARD])] != "Shadow Clone" or int(s.perms[clone, P_LOC]) != base_loc(0):
    die("zed", "conquer makes a Shadow Clone at base")
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
A.apply(s, T, V1, acts[0])
_to_decision(s)
A.apply(s, T, V1, A.Action(A.A_TARGET, clone))
_settle(s)
if int(s.perms[zed, P_LOC]) != base_loc(0) or int(s.perms[clone, P_LOC]) != bf_loc(0):
    die("zed", "Zed and his clone swap places")
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Shadow Clone"))[0], 0,
             [_rsv.pack_trash(0, P3)], -1, False, source=clone)
if combat.perm_kw(s, T, clone, "Assault") != 4 or int(s.n_banished[0]) != 1:
    die("shadow clone", "banish a unit from your trash -> Assault 4")
ok("Zed makes Shadow Clones, swaps with them, and the clones hit for Assault 4")

# ---------------------------------------------------------------------------
print("\n[batch 20] more optional additional costs, a unit that won't ready, "
      "borrowed keywords, attach toggles, and a cursed axe")

s = fresh(hand=[T.id_of("Brazen Buccaneer"), P3], runes=0)
s.runes_ready[0, :] = 1                                      # six runes
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
fast = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT_FAST]
if not fast:
    die("brazen buccaneer", "discard 1 offered with another card in hand")
A.apply(s, T, V1, fast[0])
if int(s.n_hand[0]) != 0 or P3 not in list(s.trash[0, :int(s.n_trash[0])]) \
        or int(s.runes_spent[0].sum()) != 4:
    die("brazen buccaneer", f"discarded the P3 and paid 6-2=4: spent {int(s.runes_spent[0].sum())}")
s = fresh(hand=[T.id_of("Brazen Buccaneer")], runes=8)
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
if any(a.kind == A.A_PLAY_AT_FAST for a in A.legal_actions(s, T, V1, 0)):
    die("brazen buccaneer", "nothing else to discard -> not offered")
ok("Brazen Buccaneer discards another card to cost {2} less")

s = fresh(hand=[T.id_of("Blast Corps Cadet")], runes=0)
s.runes_ready[0, :] = 1
s.add_permanent(T.id_of("Ezreal, Prodigy"), 0, base_loc(0))
from rl.engine.actions import reduced_add_cost as _rac, optional_add_cost as _oac
if _rac(s, T, 0, _oac(T, T.id_of("Blast Corps Cadet"))) != (0, 1):
    die("ezreal prodigy", "{1 energy}{Fury} becomes {Fury}")
if _rac(s, T, 0, (0, 1)) != (0, 0):
    die("ezreal prodigy", "a rune-only cost loses its rune")
ok("Ezreal, Prodigy shaves {1} or a rune off optional additional costs")

s = fresh()
s.trash[1, 0] = P3
s.n_trash[1] = 1
gm = s.add_permanent(T.id_of("Gust Monk"), 0, base_loc(0))
pal = s.add_permanent(P3, 0, base_loc(0))
chain.fire(s, T, V1, _TRP, gm)
if int(s.n_chain):
    die("gust monk", "unpaid -> no trigger")
s.set_flag(gm, __import__("rl.engine.state", fromlist=["F_PAID_ADDITIONAL"]).F_PAID_ADDITIONAL)
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Gust Monk"))[0], 0,
             [_rsv.pack_trash(1, P3), pal], -1, False, source=gm)
if combat.perm_kw(s, T, pal, "Assault") != 2 or int(s.n_trash[1]) or int(s.n_banished[1]) != 1:
    die("gust monk", "banish from ANY trash, Assault 2")
ok("Gust Monk banishes from any trash to grant Assault 2")

s = fresh()
nly = T.id_of("Needlessly Large Yordle")
s.add_permanent(P3, 0, bf_loc(0))
s.add_permanent(P3, 0, bf_loc(1))
s.bf_ctrl[:] = 0
_ph3.score_holds(s, V1, T)
if sum(a for a, _ in _edisc(s, T, 0, nly)) != 4:
    die("needlessly large yordle", "two hold points -> {4} less")
ok("Needlessly Large Yordle gets cheaper per hold point this turn")

s = fresh()
md = s.add_permanent(T.id_of("Maduli the Gatekeeper"), 0, base_loc(0), ready=False)
_ph3.awaken(s, T)
if int(s.perms[md, P_READY]):
    die("maduli", "can't be readied, not even by Awaken")
s.bf_ctrl[1] = 1
s.add_permanent(P3, 1, bf_loc(1))
spec = abilities_for(T, T.id_of("Maduli the Gatekeeper"))[0]
if _rsv.legal_targets(s, T, spec, 0, 0, [], -1, source=md) != [bf_loc(1)]:
    die("maduli", "an enemy battlefield whose units total less than his Might")
s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(1))
if _rsv.legal_targets(s, T, spec, 0, 0, [], -1, source=md):
    die("maduli", "a bigger total closes it")
ok("Maduli won't ready and can only jump onto a smaller garrison")

s = fresh()
kt = s.add_permanent(T.id_of("Kato the Arm"), 0, bf_loc(0))
pal = s.add_permanent(P3, 0, base_loc(0))
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Kato the Arm"))[0], 0, [pal],
             -1, False, source=kt)
if not combat.perm_kw(s, T, pal, "Deflect") or combat.might(s, T, pal) != 6:
    die("kato", "his Deflect and +3 Might")
ok("Kato the Arm lends his keywords and his Might")

s = fresh()
pup = s.add_permanent(T.id_of("Loyal Pup"), 0, base_loc(0))
d1 = s.add_permanent(P3, 0, bf_loc(0))
d2 = s.add_permanent(P3, 0, bf_loc(0))
s.add_permanent(P3, 1, bf_loc(0))
s.showdown_bf, s.attacker = 0, 1
combat._designate(s, T, 0, 1)
pups = [t for t in range(int(s.n_trig)) if int(s.trig[t, 1]) == pup]
if len(pups) != 1:
    die("loyal pup", f"one trigger for the defence, not one per defender: {len(pups)}")
ok("Loyal Pup watches a defence once per combat")

s = fresh()
u1 = s.add_permanent(P3, 0, base_loc(0))
u2 = s.add_permanent(P3, 0, base_loc(0))
foe_u = s.add_permanent(P3, 1, base_loc(1))
sword = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
spec = _SPECS["Angle Shot"]
if sword in _rsv.legal_targets(s, T, spec, 1, 0, [foe_u], -1):
    die("angle shot", "the Equipment must share the unit's controller")
_rsv.resolve(s, T, V1, spec, 0, [u1, sword], -1, True)
if int(s.perms[sword, _PAT]) != u1:
    die("angle shot", "attach")
_rsv.resolve(s, T, V1, spec, 0, [u1, sword], -1, True)
if int(s.perms[sword, _PAT]) != -1:
    die("angle shot", "detach when it is already on that unit")
ok("Angle Shot attaches or detaches a same-controller Equipment")

for conquered in (False, True):
    s = fresh()
    host = s.add_permanent(P3, 0, base_loc(0))
    axe = s.add_permanent(T.id_of("Blighted Battleaxe"), 0, base_loc(0))
    s.attach(axe, host)
    if conquered:
        s.conquer_ply[host] = s.ply
    from rl.engine.effects import TR_END_OF_TURN as _TREOT
    chain_mod.fire_watchers(s, T, 0, _TREOT)
    _settle(s)
    detached = int(s.perms[axe, _PAT]) == -1
    if detached == conquered or bool(s.perms[host, P_ALIVE]) != conquered:
        die("blighted battleaxe", f"conquered={conquered}: detached={detached} "
                                  f"alive={bool(s.perms[host, P_ALIVE])}")
ok("Blighted Battleaxe detaches and hits its host for 4 unless it conquered")

s = fresh(hand=[T.id_of("Shock Blast")], runes=0)
s.runes_ready[0, :] = 1                                      # six runes
irl = s.add_permanent(T.id_of("Irelia - Graceful"), 0, bf_loc(0))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_TARGET, irl))
cost = int(T.energy[T.id_of("Shock Blast")])
if int(s.runes_spent[0].sum()) != cost - 1:
    die("irelia graceful", f"a spell choosing her costs {{1}} less: spent {int(s.runes_spent[0].sum())}")
ok("Irelia - Graceful discounts your spells that choose her")

# ---------------------------------------------------------------------------
print("\n[batch 21] conditional readiness by destination, spell promises, "
      "granted Repeat, Mighty keywords, spent Power, borrowed Vision")

s = fresh(hand=[T.id_of("Shadow")], runes=8)
s.bf_ctrl[0] = 0
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, bf_loc(0)))
sh = int(s.n_perms) - 1
s2 = fresh(hand=[T.id_of("Shadow")], runes=8)
A.apply(s2, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s2, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
if int(s.perms[sh, P_READY]) != 1 or int(s2.perms[int(s2.n_perms) - 1, P_READY]):
    die("shadow", "ready at a battlefield, exhausted at base")
ok("Shadow enters ready only when played to a battlefield")

s = fresh(runes=8)
rt = s.add_permanent(T.id_of("Ravenborn Tome"), 0, base_loc(0))
A.apply(s, T, V1, [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE][0])
_settle(s)
s.hand[0, 0] = T.id_of("Shock Blast")
s.n_hand[0] = 1
e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_TARGET, e))
_settle(s)
if int(s.perms[e, _PDMG]) != 5:
    die("ravenborn tome", f"the next spell deals +1: {int(s.perms[e, _PDMG])}")
_rsv.resolve(s, T, V1, SB, 0, [e], -1, True)
if int(s.perms[e, _PDMG]) != 9:
    die("ravenborn tome", "only that one spell")
ok("Ravenborn Tome's bonus rides exactly the next spell")

from rl.engine.cost import repeat_cost as _rpc
s = fresh(runes=8)
sb = T.id_of("Shock Blast")
if _rpc(s, T, 0, sb) != (-1, -1):
    die("temporal portal", "no printed Repeat")
tp = s.add_permanent(T.id_of("Temporal Portal"), 0, base_loc(0))
A.apply(s, T, V1, [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE][0])
_settle(s)
if _rpc(s, T, 0, sb) != (int(T.energy[sb]), int(T.power[sb])):
    die("temporal portal", "Repeat equal to its cost")
s.hand[0, 0] = sb
s.n_hand[0] = 1
s.add_permanent(P3, 1, bf_loc(0))                    # something to Shock Blast
if not any(a.kind == A.A_PLAY_REPEAT for a in A.legal_actions(s, T, V1, 0)):
    die("temporal portal", "the Repeat play is offered")
ok("Temporal Portal grants the next spell a Repeat equal to its cost")

s = fresh()
sy = s.add_permanent(T.id_of("Syndra - Transcendent"), 0, bf_loc(0))
if _rpc(s, T, 0, sb) != (-1, -1):
    die("syndra", "not in a showdown")
s.showdown_bf = 0
if _rpc(s, T, 0, sb) != (2, 1) or _rpc(s, T, 1, sb) != (-1, -1):
    die("syndra", "YOUR spells get Repeat {2}{Chaos} while she is in the showdown")
ok("Syndra - Transcendent gives your spells Repeat during her showdown")

s = fresh()
fv = s.add_permanent(T.id_of("Fiora - Victorious"), 0, bf_loc(0))
if combat.perm_kw(s, T, fv, "Ganking"):
    die("fiora victorious", "4 Might is not Mighty")
s.set_flag(fv, _FB)
if not (combat.perm_kw(s, T, fv, "Ganking") and combat.perm_kw(s, T, fv, "Deflect")):
    die("fiora victorious", "buffed to 5 -> Mighty keywords")
s.showdown_bf, s.attacker = 0, 1
s.add_permanent(P3, 1, bf_loc(0))
m = combat.might(s, T, fv)           # must terminate (Shield feeds Might)
if m < 5:
    die("fiora victorious", f"defending Mighty Fiora: {m}")
ok("Fiora - Victorious gets her keywords while Mighty, without recursing on Shield")

s = fresh()
sv = s.add_permanent(T.id_of("Sivir - Mercenary"), 0, base_loc(0))
m0 = combat.might(s, T, sv)
s.note_power_spent(0, 1)
if combat.might(s, T, sv) != m0:
    die("sivir mercenary", "one Power is not two")
s.recycle_rune(0, 0)
if combat.might(s, T, sv) != m0 + 2 or not combat.perm_kw(s, T, sv, "Ganking"):
    die("sivir mercenary", "two Power spent -> +2 and Ganking")
s.ply += 1
if combat.might(s, T, sv) != m0:
    die("sivir mercenary", "resets each turn")
ok("Sivir - Mercenary reads Power spent this turn")

s = fresh()
s.hand[1, :3] = [P3, T.id_of("Progress Day"), T.id_of("Shock Blast")]
s.n_hand[1] = 3
_rsv.resolve(s, T, V1, _SPECS["Decree of Strength"], 0, [], -1, True)
picks = [T.names[int(s.hand[1, a.arg])] for a in A.legal_actions(s, T, V1, 0)
         if a.kind == A.A_PICK]
mind = [T.names[c] for c in (P3, T.id_of("Progress Day"), T.id_of("Shock Blast"))
        if int(T.domain_mask[c]) >> 4 & 1]
if sorted(picks) != sorted(mind):
    die("decree of strength", f"only Mind cards offered: {picks} vs {mind}")
ok("Decree of Strength picks only Mind cards from the revealed hand")

s = fresh()
fc = s.add_permanent(T.id_of("Forecaster"), 0, base_loc(0))
gs = s.add_permanent(T.id_of("Gemcraft Seer"), 0, base_loc(0))
mech = s.add_permanent(T.id_of("Mech"), 0, base_loc(0))
chain_mod.fire_play_unit(s, T, 0, T.id_of("Mech"), mech)
srcs = sorted(int(s.trig[t, 1]) for t in range(int(s.n_trig)))
if srcs != sorted([fc, gs]):
    die("vision grants", f"a Mech played: Forecaster and Seer both give Vision: {srcs}")
s.n_trig = 0
plain_u = s.add_permanent(P3, 0, base_loc(0))
chain_mod.fire_play_unit(s, T, 0, P3, plain_u)
if [int(s.trig[t, 1]) for t in range(int(s.n_trig))] != [gs]:
    die("vision grants", "a non-Mech: only the Seer")
ok("Forecaster and Gemcraft Seer hand out Vision on play")

# ---------------------------------------------------------------------------
print("\n[batch 22] six slots, 'any number' with a Might budget, and excess damage")

s = fresh()
d = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
spec = _SPECS["Icathian Rain"]
if d not in _rsv.legal_targets(s, T, spec, 3, 0, [d, d, d], -1):
    die("icathian rain", "the same unit may be chosen again")
_rsv.resolve(s, T, V1, spec, 0, [d] * 6, -1, True)
if s.perms[d, P_ALIVE]:
    die("icathian rain", "six 2s on one 10-Might unit kill it")
ok("Icathian Rain fills six slots and can stack them on one unit")

s = fresh()
order_units = [c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
               and int(T.domain_mask[c]) >> 5 & 1 and not T.residual_text(c)]
small = next(c for c in order_units if int(T.might[c]) <= 2)
big = next(c for c in order_units if int(T.might[c]) >= 4)
a = s.add_permanent(small, 1, bf_loc(0))
b = s.add_permanent(big, 1, bf_loc(0))
spec = _SPECS["Decree of Discord"]
second = _rsv.legal_targets(s, T, spec, 1, 0, [b], -1)
if combat.might(s, T, a) + combat.might(s, T, b) > 5 and a in second:
    die("decree of discord", "the total Might budget caps the second pick")
ok("Decree of Discord keeps its picks within total Might 5")

s = fresh()
e1 = s.add_permanent(P3, 1, bf_loc(0))
e2 = s.add_permanent(P3, 1, bf_loc(1))
_rsv.resolve(s, T, V1, _SPECS["Tricksy Tentacles"], 0, [e1, e2, -1, base_loc(1)], -1, True)
if int(s.perms[e1, P_LOC]) != base_loc(1) or int(s.perms[e2, P_LOC]) != base_loc(1):
    die("tricksy tentacles", "both to the single chosen location")
ok("Tricksy Tentacles moves several enemies to one place")

s = fresh()
m1 = s.add_permanent(P3, 0, bf_loc(0))
m2 = s.add_permanent(P3, 0, bf_loc(0))
far = s.add_permanent(P3, 0, bf_loc(1))
spec = _SPECS["Emperor's Divide"]
if far in _rsv.legal_targets(s, T, spec, 1, 0, [m1], -1):
    die("emperor's divide", "every pick at the first one's battlefield")
_rsv.resolve(s, T, V1, spec, 0, [m1, m2, -1, -1], -1, True)
if int(s.perms[m1, P_LOC]) != base_loc(0) or int(s.perms[m2, P_LOC]) != base_loc(0):
    die("emperor's divide", "home they go")
ok("Emperor's Divide recalls units from one battlefield")

from rl.engine.combat import _assign as _asg4
s = fresh()
v1 = s.add_permanent(P3, 1, bf_loc(0))
s.attacker = 0
_asg4(s, T, 8, [v1], 0)
if int(s.excess_amt[0]) != 5 or not int(s.excess_attacking[0]):
    die("excess", "8 into a 3-Might lone defender is 5 excess, as the attacker")
s2 = fresh()
w1 = s2.add_permanent(P3, 1, bf_loc(0))
w2 = s2.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
_asg4(s2, T, 8, [w1, w2], 0)
if int(s2.excess_amt[0]):
    die("excess", "a survivor soaks the leftover: nothing is excess")
ok("excess damage is what is left after every enemy took lethal")

for amt, want_gold in ((3, 2), (2, 0)):
    s = fresh()
    y = s.add_permanent(T.id_of("Yeti Brawler"), 0, base_loc(0))
    s.excess_ply[0], s.excess_amt[0] = s.ply, amt
    n0 = int(s.n_perms)
    chain.fire(s, T, V1, _TRC, y, bf_loc(0))
    _settle(s)
    if int(s.n_perms) - n0 != want_gold:
        die("yeti brawler", f"excess {amt}")
ok("Yeti Brawler pays Golds for 3+ excess damage")

for attacking, want in ((True, 1), (False, 0)):
    s = fresh()
    tr = s.add_permanent(T.id_of("Tryndamere - Barbarian"), 0, base_loc(0))
    s.excess_ply[0], s.excess_amt[0] = s.ply, 5
    s.excess_attacking[0] = int(attacking)
    chain.fire(s, T, V1, _TRC, tr, bf_loc(0))
    _settle(s)
    if int(s.points[0]) != want:
        die("tryndamere", f"attacking={attacking}")
ok("Tryndamere scores for 5+ excess only after an attack")

s = fresh()
sv = s.add_permanent(T.id_of("Sivir - Ambitious"), 0, base_loc(0))
e = s.add_permanent(T.id_of("Mountain Drake"), 1, base_loc(1))
s.excess_ply[0], s.excess_amt[0], s.excess_attacking[0] = s.ply, 6, 1
_rsv.resolve(s, T, V1, abilities_for(T, T.id_of("Sivir - Ambitious"))[0], 0, [e],
             -1, False, source=sv)
if int(s.perms[e, _PDMG]) != 6:
    die("sivir ambitious", "deals the excess amount")
ok("Sivir - Ambitious deals her excess damage again")

# ---------------------------------------------------------------------------
print("\n[hand play] effects that play a card out of your hand")

s = fresh(hand=[T.id_of("Mountain Drake"), T.id_of("Progress Day")], runes=0)
s.runes_ready[0, :] = 1                              # six runes; Drake costs more
s.bf_ctrl[1] = 0
_rsv.resolve(s, T, V1, _SPECS["Here to Help"], 0, [], -1, True)
picks = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK]
drake_cost = int(T.energy[T.id_of("Mountain Drake")])
if len(picks) != 1:
    die("here to help", f"the Drake at {{{drake_cost}}}-3 is affordable with 6 runes")
if True:
    A.apply(s, T, V1, picks[0])
    if not any(s.perms[i, P_ALIVE] and int(s.perms[i, P_LOC]) == bf_loc(1)
               for i in range(s.n_perms)):
        die("here to help", "played to the battlefield you control")
ok("Here to Help plays a unit from hand to your battlefield for {3} less")

s = fresh(hand=[T.id_of("Mountain Drake")], runes=0)
rh = s.add_permanent(T.id_of("Rift Herald"), 0, base_loc(0))
combat.destroy(s, T, rh)
_to_decision(s)
for _ in range(4):
    if s.pend_hand_play >= 0:
        break
    A.apply(s, T, V1, A.Action(A.A_PASS))
picks = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK]
if s.pend_hand_play < 0 or not picks:
    die("rift herald", "no Energy to pay and none owed: the Drake is playable")
ok("Rift Herald's Deathknell offers units playable without their Energy cost")

s = fresh(hand=[T.id_of("Long Sword"), T.id_of("Jagged Cutlass")], runes=0)
rell = s.add_permanent(T.id_of("Rell - Magnetic"), 0, base_loc(0))
spec = abilities_for(T, T.id_of("Rell - Magnetic"))[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=rell)
picks = [T.names[int(s.hand[0, a.arg])] for a in A.legal_actions(s, T, V1, 0)
         if a.kind == A.A_PICK]
want = sorted(n for n in ("Long Sword", "Jagged Cutlass")
              if int(T.energy[T.id_of(n)]) <= 2)
if not want or sorted(picks) != want:
    die("rell", f"Equipment costing {{2}} or less, for free: {picks} vs {want}")
if picks:
    A.apply(s, T, V1, [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK][0])
    g = int(s.n_perms) - 1
    if int(s.perms[g, _PAT]) != rell:
        die("rell", "the Equipment attaches to her")
ok("Rell - Magnetic plays a cheap Equipment for free and wears it")

# ---------------------------------------------------------------------------
print("\n[batch 23] optional/return costs, token moves, hand to deck, facedown")
from rl.engine.effects import compose_mode as _cm23
from rl.engine.state import F_PAID_ADDITIONAL as _FPA, P_READY as _PR23
GOLD = T.id_of("Gold // Buff")
BAR = T.id_of("Arena Bar")

s = fresh()
x1 = s.add_permanent(T.id_of("Shipyard Skulker"), 1, bf_loc(0))   # 3
x2 = s.add_permanent(PLAIN2, 1, bf_loc(0))                         # 2
x3 = s.add_permanent(T.id_of("Shipyard Skulker"), 1, bf_loc(1))
spec = _SPECS["Fox-Fire"]
if x2 in _rsv.legal_targets(s, T, spec, 1, 0, [x1], -1):
    die("fox-fire", "3 + 2 Might is over the budget of 4")
if x3 in _rsv.legal_targets(s, T, spec, 1, 0, [x2], -1):
    die("fox-fire", "every pick at the first one's battlefield")
_rsv.resolve(s, T, V1, spec, 0, [x2, -1, -1, -1], -1, True)
if s.perms[x2, P_ALIVE]:
    die("fox-fire", "kills what it chose")
ok("Fox-Fire kills units at one battlefield within total Might 4")

s = fresh(runes=0)
s.runes_spent[0, 0] = 5
u = s.add_permanent(P3, 0, base_loc(0), ready=False)
_rsv.resolve(s, T, V1, _SPECS["Acceleration Gate"], 0, [u, -1, -1, -1], -1, True)
if not int(s.perms[u, _PR23]) or int(s.runes_ready[0].sum()) != 3:
    die("acceleration gate", f"one unit and three runes: {int(s.runes_ready[0].sum())}")
ok("Acceleration Gate readies the chosen permanents and runes with the rest")

for pay in (True, False):
    s = fresh(hand=[T.id_of("Zaun Punk")])
    g = s.add_permanent(GOLD, 0, base_loc(0))
    A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
    legal = A.legal_actions(s, T, V1, 0)
    if not any(a.kind == A.A_DECLINE for a in legal):
        die("zaun punk", "the kill cost is optional")
    A.apply(s, T, V1, A.Action(A.A_TARGET, g) if pay else A.Action(A.A_DECLINE))
    A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
    punk = next(i for i in range(s.n_perms) if s.perms[i, P_ALIVE]
                and int(s.perms[i, P_CARD]) == T.id_of("Zaun Punk"))
    if bool(s.perms[g, P_ALIVE]) == pay or bool(int(s.perms[punk, _PF]) & _FPA) != pay:
        die("zaun punk", f"pay={pay}: gear dies and the clause arms only if paid")
s = fresh(hand=[T.id_of("Zaun Punk")])
if not any(a.kind == A.A_PLAY for a in A.legal_actions(s, T, V1, 0)):
    die("zaun punk", "playable with no gear to kill")
ok("Zaun Punk's gear kill is optional and arms its play trigger")

s = fresh(hand=[T.id_of("Legion Quartermaster")])
if any(a.kind == A.A_PLAY for a in A.legal_actions(s, T, V1, 0)):
    die("legion quartermaster", "a required return with no gear blocks the play")
bar = s.add_permanent(BAR, 0, base_loc(0))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_TARGET, bar))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
if s.perms[bar, P_ALIVE] or BAR not in [int(c) for c in s.hand[0, :s.n_hand[0]]]:
    die("legion quartermaster", "the gear goes back to hand")
if BAR in [int(c) for c in s.trash[0, :s.n_trash[0]]]:
    die("legion quartermaster", "returned, not killed")
ok("Legion Quartermaster returns a friendly gear as its cost")

s = fresh(hand=[PLAIN2])
sky = s.add_permanent(T.id_of("Sky Cruiser"), 0, base_loc(0), ready=True)
s.add_permanent(P3, 1, bf_loc(0))
if any(a.kind == A.A_ACTIVATE for a in A.legal_actions(s, T, V1, 0)):
    die("sky cruiser", "needs a gear to discard")
s.hand[0, 1] = BAR
s.n_hand[0] = 2
if not any(a.kind == A.A_ACTIVATE for a in A.legal_actions(s, T, V1, 0)):
    die("sky cruiser", "a gear in hand pays the cost")
ok("Sky Cruiser's ability needs a gear to discard")

s = fresh()
az = s.add_permanent(T.id_of("Azir - Sovereign"), 0, bf_loc(0))
tok = s.add_permanent(T.id_of("Mech"), 0, base_loc(0))
body = s.add_permanent(P3, 0, base_loc(0))
spec = abilities_for(T, T.id_of("Azir - Sovereign"))[0]
opts = _rsv.legal_targets(s, T, spec, 0, 0, [], -1, source=az)
if tok not in opts or body in opts:
    die("azir sovereign", f"token units only: {opts}")
_rsv.resolve(s, T, V1, spec, 0, [tok, -1, -1, -1], -1, False, source=az)
if int(s.perms[tok, P_LOC]) != bf_loc(0):
    die("azir sovereign", "the token joins him")
ok("Azir - Sovereign brings token units to his attack")

s = fresh(hand=[P3])
s.n_deck[0] = 20
altar = s.add_permanent(T.id_of("Altar of Memories"), 0, base_loc(0))
spec = abilities_for(T, T.id_of("Altar of Memories"))[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=altar)
if int(s.n_hand[0]) != 2 or s.pend_discard != 0:
    die("altar", "draw 1, then choose a hand card")
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if s.pend_look != 0 or int(s.n_hand[0]) != 1:
    die("altar", "the card leaves hand and asks top or bottom")
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if int(s.deck[0, int(s.deck_ptr[0])]) != P3:
    die("altar", "picked means on top")
ok("Altar of Memories draws, then puts a hand card on top of the deck")

s = fresh()
pack = s.add_permanent(T.id_of("Pack of Wonders"), 0, base_loc(0))
# The facedown zone is indexed by SLOT, not by battlefield: `fd_slots(1)` is
# where battlefield 1's cards live (two of them, since Bandle Tree).
_fd1 = list(fd_slots(1))[0]
s.fd_owner[_fd1], s.fd_card[_fd1], s.fd_ply[_fd1] = 0, P3, 0
spec = abilities_for(T, T.id_of("Pack of Wonders"))[0]
m1 = _cm23(spec, 1)
if _rsv.legal_targets(s, T, m1, 1, 0, [1], -1, source=pack) != [bf_loc(1)]:
    die("pack of wonders", "only the battlefield holding your facedown card")
_rsv.resolve(s, T, V1, m1, 0, [1, bf_loc(1)], -1, False, source=pack)
if int(s.fd_card[_fd1]) != -1 or int(s.hand[0, 0]) != P3:
    die("pack of wonders", "the facedown card returns to hand")
if pack in _rsv.legal_targets(s, T, _cm23(spec, 0), 1, 0, [0], -1, source=pack):
    die("pack of wonders", "another permanent, never itself")
ok("Pack of Wonders returns a permanent or a facedown card")

# ---------------------------------------------------------------------------
print("\n[batch 24] move watchers, one-on-one, discard for damage, win the game")
from rl.engine import cost as _cost24
from rl.engine.effects import TR_UNIT_MOVES as _TRUM

s = fresh()
vb = s.add_permanent(T.id_of("Volibear - Imposing"), 1, bf_loc(0))
m1 = s.add_permanent(P3, 0, base_loc(0))
m2 = s.add_permanent(P3, 0, base_loc(0))
seen = {m1, m2}
combat.queue_move_trigger(s, T, m1, base_loc(0), bf_loc(1), seen)
combat.queue_move_trigger(s, T, m2, base_loc(0), bf_loc(1), seen)
if sum(1 for i in range(s.n_trig) if int(s.trig[i][0]) == _TRUM) != 1:
    die("volibear imposing", "one Move of two units is one draw")
s.n_trig = 0
combat.queue_move_trigger(s, T, m1, base_loc(0), bf_loc(0))
if s.n_trig:
    die("volibear imposing", "moving to HIS battlefield does not count")
own = s.add_permanent(P3, 1, base_loc(1))
combat.queue_move_trigger(s, T, own, base_loc(1), bf_loc(1))
if s.n_trig:
    die("volibear imposing", "only an opponent's move")
ok("Volibear - Imposing draws when an opponent moves elsewhere, once per Move")

s = fresh()
sp = s.add_permanent(T.id_of("Stealthy Pursuer"), 0, base_loc(0))
lead = s.add_permanent(P3, 0, base_loc(0))
s.set_location(lead, bf_loc(1))
combat.queue_move_trigger(s, T, lead, base_loc(0), bf_loc(1))
_settle(s)
if int(s.perms[sp, P_LOC]) != bf_loc(1):
    die("stealthy pursuer", "follows the friendly unit that left his location")
ok("Stealthy Pursuer may move with a friendly unit leaving his location")

s = fresh()
fi = s.add_permanent(T.id_of("Fiora - Peerless"), 0, bf_loc(0))
foe = s.add_permanent(P3, 1, bf_loc(0))
s.showdown_bf = 0
spec = abilities_for(T, T.id_of("Fiora - Peerless"))[0]
m0 = combat.might(s, T, fi)
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=fi)
if combat.might(s, T, fi) != 2 * m0:
    die("fiora peerless", f"double in a one-on-one: {combat.might(s, T, fi)} vs {m0}")
s.showdown_bf = -1
if combat.might(s, T, fi) != m0:
    die("fiora peerless", "only this combat")
s = fresh()
fi = s.add_permanent(T.id_of("Fiora - Peerless"), 0, bf_loc(0))
s.add_permanent(P3, 1, bf_loc(0))
s.add_permanent(P3, 1, bf_loc(0))
s.showdown_bf = 0
m0 = combat.might(s, T, fi)
# 383.2.a.1 -- "one on one" is part of the trigger condition, asked as it
# triggers (RiftJudge #11385, #11502), so this is where two defenders stop it.
from rl.engine.chain import ability_cond_holds as _ach
if _ach(s, T, spec, 0, fi):
    die("fiora peerless", "two defenders is not one on one")
ok("Fiora - Peerless doubles her Might in a one-on-one combat, for that combat")

s = fresh(hand=[P3])
e = s.add_permanent(P3, 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Get Excited!"], 0, [e], -1, True)
if s.pend_discard != 0:
    die("get excited", "choose the discard")
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if s.perms[e, P_ALIVE]:
    die("get excited", f"Skulker's {int(T.energy[P3])} Energy kills a 3-Might unit")
ok("Get Excited! deals the discarded card's Energy cost")

du = T.id_of("Drag Under")
with _cost24.nonhand():
    cheap = _cost24.effective_energy(fresh(), T, 0, du)
if cheap != int(T.energy[du]) - 2 or _cost24.effective_energy(fresh(), T, 0, du) != int(T.energy[du]):
    die("drag under", "2 less only when played from outside the hand")
ok("Drag Under / Void Drone cost 2 less from anywhere but the hand")

s = fresh()
s.legend[1], s.legend_ready[1] = T.id_of("Rell - Magnetic"), 1
spec = abilities_for(T, T.id_of("Royal Entourage"))[0]
_rsv.resolve(s, T, V1, _cm23(spec, 3), 0, [3], -1, False)
if int(s.legend_ready[1]) != 0:
    die("royal entourage", "exhausts the opponent's legend")
ok("Royal Entourage can exhaust an opponent's legend")

for n_units, want in ((4, 0), (3, -1)):
    s = fresh(hand=[P3] * 4)
    gp = s.add_permanent(T.id_of("Gutter Palace"), 0, base_loc(0))
    for k in range(n_units):
        s.add_permanent(P3, 0, bf_loc(k % 2))
    spec = abilities_for(T, T.id_of("Gutter Palace"))[0]
    # 383.2.a.1 -- the "if exactly 4 and 4" is asked as it triggers.
    from rl.engine.chain import ability_cond_holds as _ach
    if _ach(s, T, spec, 0, gp):
        _rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=gp)
    if int(s.winner) != want:
        die("gutter palace", f"{n_units} units at battlefields")
ok("Gutter Palace wins with exactly 4 cards in hand and 4 units out")

# ---------------------------------------------------------------------------
print("\n[batch 25] spells with optional additional costs (A_PLAY_REPEAT = pay)")
from rl.engine.state import F_BUFFED as _FB25


def _cast25(s, name, paid, cost_perm=-1, targets=()):
    idx = [int(c) for c in s.hand[0, :s.n_hand[0]]].index(T.id_of(name))
    A.apply(s, T, V1, A.Action(A.A_PLAY_REPEAT if paid else A.A_PLAY, idx))
    if s.pend_cost_kill >= 0:
        A.apply(s, T, V1, A.Action(A.A_TARGET, cost_perm))
    for t in targets:
        A.apply(s, T, V1, A.Action(A.A_TARGET, t))
    drain(s, V1)


for paid, want in ((True, 5), (False, 3)):
    s = fresh(hand=[T.id_of("Ruthless Strike"), P3])
    e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
    kinds = {a.kind for a in A.legal_actions(s, T, V1, 0) if a.arg == 0}
    if A.A_PLAY_REPEAT not in kinds or A.A_PLAY not in kinds:
        die("ruthless strike", "both ways are offered")
    _cast25(s, "Ruthless Strike", paid, targets=(e,))
    if int(s.perms[e, P_DMG]) != want or int(s.n_hand[0]) != (0 if paid else 1):
        die("ruthless strike", f"paid={paid}: {int(s.perms[e, P_DMG])} damage")
s = fresh(hand=[T.id_of("Ruthless Strike")])
s.add_permanent(P3, 1, bf_loc(0))
if any(a.kind == A.A_PLAY_REPEAT for a in A.legal_actions(s, T, V1, 0)):
    die("ruthless strike", "no other card to discard, no paid option")
ok("Ruthless Strike deals 5 if a card was discarded as it was played, else 3")

for paid, want in ((True, 2), (False, 1)):
    s = fresh(hand=[T.id_of("Meditation")])
    u = s.add_permanent(P3, 0, base_loc(0), ready=True)
    _cast25(s, "Meditation", paid, cost_perm=u)
    if int(s.n_hand[0]) != want or bool(int(s.perms[u, _PR23])) == paid:
        die("meditation", f"paid={paid}: hand {int(s.n_hand[0])}")
ok("Meditation draws 2 when it exhausts a friendly unit, else 1")

for paid in (True, False):
    s = fresh(hand=[T.id_of("Rampage")])
    f = s.add_permanent(P3, 0, base_loc(0))
    e = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
    _cast25(s, "Rampage", paid, targets=(f, e))
    if int(s.perms[e, P_DMG]) != (5 if paid else 3):
        die("rampage", f"paid={paid}: the friendly unit hits for its Might")
ok("Rampage fights, +2 Might first if the rune was paid")

s = fresh(hand=[T.id_of("Call to Glory")], runes=0)
b = s.add_permanent(P3, 0, base_loc(0))
s.perms[b, _PF] |= _FB25
kinds = {a.kind for a in A.legal_actions(s, T, V1, 0)}
if A.A_PLAY_REPEAT not in kinds or A.A_PLAY in kinds:
    die("call to glory", "with no runes only the free, buff-spending play")
m0 = combat.might(s, T, b)
_cast25(s, "Call to Glory", True, cost_perm=b, targets=(b,))
if int(s.perms[b, _PF]) & _FB25 or combat.might(s, T, b) != m0 - 1 + 3:
    die("call to glory", f"buff spent, +3: {combat.might(s, T, b)} vs {m0}")
ok("Call to Glory spends a buff to be free")

s = fresh(hand=[T.id_of("Wallop")], runes=0)
b = s.add_permanent(P3, 0, base_loc(0), ready=False)
s.perms[b, _PF] |= _FB25
_cast25(s, "Wallop", True, cost_perm=b, targets=(b,))
if not int(s.perms[b, _PR23]) or int(s.runes_spent[0].sum()):
    die("wallop", "free, and readies its unit")
ok("Wallop spends a buff to ready a unit for free")

# ---------------------------------------------------------------------------
print("\n[batch 26] paid-for target widening, and a rune reveal that branches")
from rl.engine.effects import TR_RUNE_BODY as _TRB
from rl.config import DOMAINS as _DOMS

s = fresh(hand=[T.id_of("Conscription")])
big = s.add_permanent(T.id_of("Mountain Drake"), 1, bf_loc(0))
kinds = {a.kind for a in A.legal_actions(s, T, V1, 0)}
if A.A_PLAY in kinds or A.A_PLAY_REPEAT in kinds:
    die("conscription", "no 3-Might target and no XP: not playable")
s.xp[0] = 5
kinds = {a.kind for a in A.legal_actions(s, T, V1, 0)}
if A.A_PLAY in kinds or A.A_PLAY_REPEAT not in kinds:
    die("conscription", "with 5 XP only the paid play reaches the Drake")
_cast25(s, "Conscription", True, targets=(big,))
if int(s.perms[big, P_CTRL]) != 0 or int(s.perms[big, P_LOC]) != base_loc(0) \
        or int(s.perms[big, _PR23]) or int(s.xp[0]) != 0:
    die("conscription", "stolen, exhausted, recalled, 5 XP spent")
ok("Conscription widens its target when 5 XP is spent")

from rl.engine.state import P_CTRL
for dom_name, check in (("Mind", "draw"), ("Fury", "damage")):
    s = fresh()
    s.rune_deck[0, 0] = _DOMS.index(dom_name)
    s.rune_deck[0, 1] = _DOMS.index("Calm")
    s.rune_head[0], s.rune_left[0] = 0, 2
    # All at a base: at a battlefield the Cleanup opens a real combat.
    tf = s.add_permanent(T.id_of("Twisted Fate - Gambler"), 0, base_loc(0))
    e1 = s.add_permanent(T.id_of("Mountain Drake"), 1, base_loc(0))
    e2 = s.add_permanent(T.id_of("Mountain Drake"), 1, base_loc(0))
    spec = abilities_for(T, T.id_of("Twisted Fate - Gambler"))[0]
    _rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=tf)
    if int(s.rune_deck[0, int(s.rune_head[0])]) != _DOMS.index("Calm") \
            or int(s.rune_deck[0, 2]) != _DOMS.index(dom_name):
        die("twisted fate", "the revealed rune goes to the bottom")
    if int(s.trig[0][0]) != _TRB + _DOMS.index(dom_name):
        die("twisted fate", f"queues the {dom_name} branch")
    h0 = int(s.n_hand[0])
    _settle(s)
    if check == "draw" and int(s.n_hand[0]) != h0 + 1:
        die("twisted fate", "Mind draws")
    if check == "damage" and sorted((int(s.perms[e1, P_DMG]), int(s.perms[e2, P_DMG]))) != [1, 2]:
        die("twisted fate", "Fury: 2 to one, 1 to the other")
ok("Twisted Fate - Gambler reveals a rune and branches on its domain")

# ---------------------------------------------------------------------------
print("\n[batch 27] a [Repeat] that suspends, and disempower-to-empower")
from rl.engine.state import C_REPEAT as _CREP

s = fresh(hand=[T.id_of("Called Shot")])
s.deck[0, :20] = [P3, PLAIN2] * 10
kinds = {a.kind for a in A.legal_actions(s, T, V1, 0)}
if A.A_PLAY_REPEAT not in kinds:
    die("called shot", "its [Repeat] is payable")
A.apply(s, T, V1, A.Action(A.A_PLAY_REPEAT, 0))
for _ in range(10):
    if s.pend_look >= 0:
        break
    who = A.acting_seat(s)
    A.apply(s, T, V1, next(a for a in A.legal_actions(s, T, V1, who)
                           if a.kind == A.A_PASS))
if s.pend_look != 0 or int(s.pend_repeat_card) != T.id_of("Called Shot"):
    die("called shot", "first look open, second pass waiting")
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if s.pend_look != 0 or int(s.n_hand[0]) != 1:
    die("called shot", "the repeat opens a second look once the first is answered")
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if s.pend_look >= 0 or int(s.n_hand[0]) != 2 or int(s.pend_repeat_card) >= 0:
    die("called shot", "two looks, two cards drawn")
ok("Called Shot's [Repeat] runs its second look after the first is answered")

s = fresh()
s.deck[0, :3] = [PLAIN2, T.id_of("Called Shot"), P3]
_rsv.resolve(s, T, V1, _SPECS["Double Trouble"], 0, [], -1, True)
picks = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK]
if len(picks) != 2 or not any(a.kind == A.A_PICK_NONE for a in A.legal_actions(s, T, V1, 0)):
    die("double trouble", "only the units, and declining is allowed")
ok("Double Trouble looks for a unit to draw")

s = fresh()
pf = s.add_permanent(T.id_of("Profiteer"), 0, base_loc(0))
donor = s.add_permanent(P3, 0, base_loc(0))
taker = s.add_permanent(P3, 0, base_loc(0))
spec = abilities_for(T, T.id_of("Profiteer"))[0]
if _rsv.legal_targets(s, T, spec, 0, 0, [], -1, source=pf):
    die("profiteer", "nothing Empowered to disempower")
from rl.engine.state import P_EMPOWER as _PEM
s.perms[donor, _PEM] = 1
from rl.engine.state import F_EMPOWERED as _FEM
s.perms[donor, _PF] |= _FEM
_rsv.resolve(s, T, V1, spec, 0, [donor, taker], -1, False, source=pf)
if s.empower_count(donor) or not s.empower_count(taker):
    die("profiteer", "the status moves from one to the other")
ok("Profiteer moves an Empowered status")

s = fresh(hand=[T.id_of("Hard Bargain")])
s.runes_ready[1, :] = 1
vic = chain_mod.push(s, T.id_of("Vengeance"), 1, from_hand=True, bound_bf=-1)
chain_mod.finalize(s, vic)
s.priority = 0
A.apply(s, T, V1, A.Action(A.A_PLAY_REPEAT, 0))
legal = A.legal_actions(s, T, V1, 0)
A.apply(s, T, V1, next(a for a in legal if a.kind == A.A_TARGET))
# 820.2 -- the repeat makes its own choice as the spell is played, and 820.2.a
# lets it name the same spell again.
legal = A.legal_actions(s, T, V1, 0)
if not any(a.kind == A.A_TARGET for a in legal):
    die("hard bargain", "the Repeat execution chooses its own target")
A.apply(s, T, V1, next(a for a in legal if a.kind == A.A_TARGET))
asked = 0
for _ in range(20):
    if s.pend_tax >= 0:
        asked += 1
        A.apply(s, T, V1, A.Action(A.A_ACCEPT))
        continue
    who = A.acting_seat(s)
    if who < 0 or s.n_chain == 0:
        break
    legal = A.legal_actions(s, T, V1, who)
    if not any(a.kind == A.A_PASS for a in legal):
        break
    A.apply(s, T, V1, A.Action(A.A_PASS))
if asked != 2:
    die("hard bargain", f"a repeated tax is asked twice, got {asked}")
ok("Hard Bargain's [Repeat] asks for the tax a second time after the first answer")

# ---------------------------------------------------------------------------
print("\n[batch 28] reveal, banish, then play it")
from rl.engine.state import P_OWNER as _POW, P_EMPOWER as _PEM28
DRAKE = T.id_of("Mountain Drake")
VENG = T.id_of("Vengeance")

s = fresh()
s.deck[0, :5] = [VENG, DRAKE, P3, VENG, VENG]
s.bf_ctrl[1] = 0
_rsv.resolve(s, T, V1, _SPECS["Reinforce"], 0, [], -1, True)
picks = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK]
if sorted(int(s.look_cards[i]) for i in picks) != sorted([DRAKE, P3]):
    die("reinforce", "only units may be banished")
A.apply(s, T, V1, A.Action(A.A_PICK, 1))
dests = sorted(a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT)
if s.rp_seat != 0 or int(s.n_banished[0]) != 1 or dests != sorted([base_loc(0), bf_loc(1)]):
    die("reinforce", f"banished, then played to base or a controlled bf: {dests}")
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, bf_loc(1)))
d = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == DRAKE)
if int(s.perms[d, P_LOC]) != bf_loc(1) or int(s.n_banished[0]) \
        or int(s.runes_spent[0].sum()) != int(T.energy[DRAKE]) - 5:
    die("reinforce", "on the board, out of Banishment, 5 Energy cheaper")
ok("Reinforce banishes a unit from the top 5 and plays it for 5 less")

s = fresh()
s.deck[0, :5] = [VENG, T.id_of("Arena Bar"), VENG, VENG, VENG]
_rsv.resolve(s, T, V1, _SPECS["Wild Claw"], 0, [], -1, True)
A.apply(s, T, V1, A.Action(A.A_PICK, 1))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
g = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == T.id_of("Arena Bar"))
if not s.empower_count(g):
    die("wild claw", "then empower it")
ok("Wild Claw plays a gear and empowers it")

s = fresh()
s.deck[1, :3] = [P3, VENG, VENG]
_rsv.resolve(s, T, V1, _SPECS["Blind Fury"], 0, [], -1, True)
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
u = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == P3)
if int(s.perms[u, P_CTRL]) != 0 or int(s.perms[u, _POW]) != 1 or int(s.runes_spent[0].sum()):
    die("blind fury", "yours to control, theirs to own, free")
s = fresh()
e = s.add_permanent(P3, 1, base_loc(1))
s.deck[1, :3] = [VENG, P3, P3]
_rsv.resolve(s, T, V1, _SPECS["Blind Fury"], 0, [], -1, True)
if [a.kind for a in A.legal_actions(s, T, V1, 0)] != [A.A_ACCEPT]:
    die("blind fury", "a revealed spell is cast")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
A.apply(s, T, V1, A.Action(A.A_TARGET, e))
drain(s, V1)
if s.perms[e, P_ALIVE]:
    die("blind fury", "their Vengeance, cast by you")
if VENG not in [int(c) for c in s.trash[1, :s.n_trash[1]]]:
    die("blind fury", "the spell goes to its OWNER's trash")
ok("Blind Fury plays the opponent's top card, spell or unit, for free")

s = fresh()
s.deck[0, :4] = [VENG, VENG, P3, VENG]
da = s.add_permanent(T.id_of("Dazzling Aurora"), 0, base_loc(0))
spec = abilities_for(T, T.id_of("Dazzling Aurora"))[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=da)
if int(s.rp_card) != P3 or int(s.deck_ptr[0]) != 3 or \
        list(s.deck[0, int(s.n_deck[0]) - 2:int(s.n_deck[0])]) != [VENG, VENG]:
    die("dazzling aurora", "reveals to the unit, recycles what it passed")
ok("Dazzling Aurora reveals until a unit and plays it")

s = fresh()
s.deck[0, :2] = [P3, VENG]
_rsv.resolve(s, T, V1, _SPECS["Void Rush"], 0, [], -1, True)
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if int(s.n_hand[0]) != 1 or int(s.hand[0, 0]) != VENG:
    die("void rush", "draw the one not banished")
ok("Void Rush draws what it didn't banish")

s = fresh()
s.deck[0, :2] = [P3, VENG]
rk = s.add_permanent(T.id_of("Rek'Sai - Swarm Queen"), 0, bf_loc(0))
spec = abilities_for(T, T.id_of("Rek'Sai - Swarm Queen"))[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=rk)
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
dests = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT]
if bf_loc(0) not in dests:
    die("rek'sai swarm queen", "a unit may be played here")
ok("Rek'Sai - Swarm Queen may play a revealed unit where she attacks")

# ---------------------------------------------------------------------------
print("\n[batch 29] kill-then-look ceilings, follow-up targets, reveal counts")
from rl.engine.effects import TR_FOLLOWUP as _TRFU

s = fresh()
s.deck[0, :5] = [DRAKE, P3, PLAIN2, VENG, VENG]
hook = s.add_permanent(T.id_of("Baited Hook"), 0, base_loc(0), ready=True)
victim = s.add_permanent(PLAIN2, 0, base_loc(0))
spec = abilities_for(T, T.id_of("Baited Hook"))[0]
_rsv.resolve(s, T, V1, spec, 0, [victim], -1, False, source=hook)
picks = sorted(int(s.look_cards[a.arg]) for a in A.legal_actions(s, T, V1, 0)
               if a.kind == A.A_PICK)
if s.perms[victim, P_ALIVE] or picks != sorted([P3, PLAIN2]):
    die("baited hook", f"units with Might <= 2 + 1 only: {[T.names[c] for c in picks]}")
A.apply(s, T, V1, A.Action(A.A_PICK, 1))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
if int(s.runes_spent[0].sum()) or not any(
        s.perms[i, P_ALIVE] and int(s.perms[i, P_CARD]) == P3 for i in range(s.n_perms)):
    die("baited hook", "plays it free")
ok("Baited Hook's pick is capped at the killed unit's Might + 1")

POROU = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
             and "Poro" in T.tags[c])
for top, want_q in ((POROU, 1), (P3, 0)):
    s = fresh()
    s.deck[0, :3] = [top, VENG, VENG]
    iv = s.add_permanent(T.id_of("Ivern - Nurturer"), 0, base_loc(0))
    spec = abilities_for(T, T.id_of("Ivern - Nurturer"))[0]
    _rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=iv)
    A.apply(s, T, V1, A.Action(A.A_PICK, 0))
    got = sum(1 for c in s.chain[:s.n_chain] if int(c[C_ABIL]) == 2) + sum(
        1 for i in range(s.n_trig) if int(s.trig[i][0]) == _TRFU)
    if got != want_q:
        die("ivern nurturer", f"{T.names[top]}: buff follow-up {got}")
ok("Ivern - Nurturer buffs only after revealing a Bird, Cat, Dog or Poro")

HID = next(c for c in range(T.n) if T.has(c, "Hidden") and not T.is_token(c))
s = fresh()
s.deck[0, :5] = [HID, P3, HID, HID, P3]
tm = s.add_permanent(T.id_of("Teemo - Strategist"), 0, base_loc(0))
foe = s.add_permanent(DRAKE, 1, base_loc(0))
spec = abilities_for(T, T.id_of("Teemo - Strategist"))[0]
_rsv.resolve(s, T, V1, spec, 0, [foe], -1, False, source=tm)
if int(s.perms[foe, P_DMG]) != 3 or int(s.deck_ptr[0]) != 5:
    die("teemo strategist", "1 per Hidden card among the five, all recycled")
ok("Teemo - Strategist deals 1 per [Hidden] card revealed")

s = fresh()
s.hand[1, :2] = [P3, VENG]
s.n_hand[1] = 2
spec = abilities_for(T, T.id_of("Ashe - Focused"))[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False)
kinds = [a.kind for a in A.legal_actions(s, T, V1, 0)]
if A.A_PICK_NONE in kinds:
    die("ashe focused", "choosing a card is mandatory")
A.apply(s, T, V1, A.Action(A.A_PICK, 1))
if int(s.n_hand[1]) != 1 or int(s.n_banished[1]) != 1:
    die("ashe focused", "banished from their hand")
from rl.engine import phases as _ph29
s.bf_ctrl[0] = 1
s.active = 1
_ph29.score_holds(s, V1, T)
if int(s.n_hand[1]) != 2 or int(s.n_banished[1]) or int(s.hand[1, 1]) != VENG:
    die("ashe focused", "back to their hand when they hold")
ok("Ashe - Focused banishes a card from hand until its owner holds")

# ---------------------------------------------------------------------------
print("\n[batch 30] a token you may pay to ready, and a unit they must play")

for runes, want_ready, asked in ((1, True, True), (0, False, False)):
    s = fresh(runes=0)
    s.runes_ready[0, 5] = runes                 # an Order rune, or none
    _rsv.resolve(s, T, V1, _SPECS["Guards!"], 0, [base_loc(0)], -1, True)
    tok = int(s.last_token)
    if (s.pend_ask >= 0) != asked:
        die("guards", f"asked only when the rune can be paid (runes={runes})")
    if asked:
        A.apply(s, T, V1, A.Action(A.A_ACCEPT))
    if bool(int(s.perms[tok, _PR23])) != want_ready or int(s.runes_in_play(0)[5]) != 0:
        die("guards", f"paid {{Order}} readies the Sand Soldier (runes={runes})")
ok("Guards! makes a Sand Soldier and may pay an Order rune to ready it")

s = fresh()
s.hand[1, :2] = [DRAKE, VENG]
s.n_hand[1] = 2
_rsv.resolve(s, T, V1, _SPECS["Bone Skewer"], 0, [bf_loc(1)], -1, True)
picks = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK]
if picks != [0]:
    die("bone skewer", "only a unit may be chosen")
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
d = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == DRAKE)
from rl.engine.state import F_STUNNED as _FST
if int(s.perms[d, P_CTRL]) != 1 or int(s.perms[d, P_LOC]) != bf_loc(1) \
        or not int(s.perms[d, _PF]) & _FST or int(s.runes_spent[1].sum()):
    die("bone skewer", "theirs, at that battlefield, stunned, free")
ok("Bone Skewer makes the opponent play a unit from hand, stunned, where you chose")

# ---------------------------------------------------------------------------
print("\n[batch 31] Might thresholds: becoming Mighty, and 10+ empowers")
from rl.engine.effects import TR_BECOME_MIGHTY as _TRBM
from rl.engine.state import P_MIGHT_MOD as _PMM

s = fresh()
fw = s.add_permanent(T.id_of("Fiora - Worthy"), 0, base_loc(0))
big = s.add_permanent(DRAKE, 0, base_loc(0))
u = s.add_permanent(P3, 0, base_loc(0))
combat.scan_might_transitions(s, T, V1)
if s.n_trig:
    die("fiora worthy", "a unit that entered Mighty did not BECOME Mighty")
s.perms[u, _PMM] = 2                            # 3 -> 5
combat.scan_might_transitions(s, T, V1)
if not any(int(s.trig[i][0]) == _TRBM and int(s.trig[i][3]) == u
           for i in range(s.n_trig)):
    die("fiora worthy", "3 -> 5 Might becomes Mighty")
s.n_trig = 0
combat.scan_might_transitions(s, T, V1)
if s.n_trig:
    die("fiora worthy", "staying Mighty fires nothing")
ok("Fiora - Worthy watches a friendly unit become Mighty")

s = fresh()
rn = s.add_permanent(T.id_of("Renekton, Brute"), 0, base_loc(0))
s.perms[rn, _PMM] = 10 - int(T.might[T.id_of("Renekton, Brute")]) - 1
combat.scan_might_transitions(s, T, V1)
if s.empower_count(rn):
    die("renekton brute", "9 Might is not enough")
s.perms[rn, _PMM] += 1
combat.scan_might_transitions(s, T, V1)
if not s.empower_count(rn) or not combat.perm_kw(s, T, rn, "Ganking"):
    die("renekton brute", "10 Might empowers him, and Empowered he has Ganking")
ok("Renekton, Brute empowers at 10 Might and gains [Deflect]/[Ganking]")

# ---------------------------------------------------------------------------
print("\n[batch 32] who killed it: spells, abilities, combat damage")
from rl.engine.effects import TR_YOU_KILL as _TRYK

for stunned, killer, want in ((True, 0, 1), (False, 0, 0), (True, -1, 0)):
    s = fresh()
    s.add_permanent(T.id_of("Solari Shrine"), 0, base_loc(0), ready=True)
    e = s.add_permanent(P3, 1, base_loc(1))
    if stunned:
        s.stun(e)
    combat.KILLER[:] = [killer, True]
    combat.destroy(s, T, e)
    combat.KILLER[:] = [-1, False]
    if sum(1 for i in range(s.n_trig) if int(s.trig[i][0]) == _TRYK) != want:
        die("solari shrine", f"stunned={stunned} killer={killer}")
ok("Solari Shrine sees you kill a stunned enemy, and nothing else")

s = fresh(hand=[VENG])
s.trash[0, 0] = T.id_of("Immortal Phoenix")
s.n_trash[0] = 1
e = s.add_permanent(P3, 1, base_loc(1))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_TARGET, e))
_settle(s)
ph = [i for i in range(s.n_perms) if s.perms[i, P_ALIVE]
      and int(s.perms[i, P_CARD]) == T.id_of("Immortal Phoenix")]
if s.perms[e, P_ALIVE] or not ph or T.id_of("Immortal Phoenix") in \
        [int(c) for c in s.trash[0, :s.n_trash[0]]]:
    die("immortal phoenix", "a spell kill lets it rise from the trash")
ok("Immortal Phoenix returns from the trash when your spell kills a unit")

# ---------------------------------------------------------------------------
print("\n[batch 33] Main-Phase-start triggers, a discard Repeat, trash tags")
from rl.engine.effects import pack_trash as _pk33, TR_MAIN_START as _TRMS
from rl.engine.state import GRANT_IDX as _GI33

for paid, want in ((True, 8), (False, 4)):
    s = fresh(hand=[T.id_of("Square Up"), P3])
    u = s.add_permanent(P3, 0, base_loc(0))
    _cast25(s, "Square Up", paid, targets=(u,))
    if int(s.kw_grant_turn[u, _GI33["Assault"]]) != want:
        die("square up", f"paid={paid}: Assault {int(s.kw_grant_turn[u, _GI33['Assault']])}")
ok("Square Up's discard [Repeat] gives [Assault 4] twice")

for tag_unit, spent in ((PLAIN2, 0), (T.id_of("Legion Rearguard"), 2)):
    s = fresh(hand=[T.id_of("Undying Loyalty")])
    s.trash[0, 0] = tag_unit
    s.n_trash[0] = 1
    if int(T.energy[tag_unit]) > 2 or int(T.power[tag_unit]) > 1:
        die("undying loyalty", "fixture too expensive")
    r0 = int(s.runes_spent[0].sum())
    A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
    A.apply(s, T, V1, A.Action(A.A_TARGET, _pk33(0, tag_unit)))
    energy = int(s.runes_spent[0].sum()) - r0
    drain(s, V1)
    if energy < spent or (tag_unit == PLAIN2 and energy > 1):
        die("undying loyalty", f"{T.names[tag_unit]}: {energy} runes spent")
    if not any(s.perms[i, P_ALIVE] and int(s.perms[i, P_CARD]) == tag_unit
               for i in range(s.n_perms)):
        die("undying loyalty", "the unit comes back")
ok("Undying Loyalty is 2 cheaper for an animal and replays a small unit")

from rl.engine import phases as _ph33
s = fresh()
iq = s.add_permanent(T.id_of("Iascylla"), 0, bf_loc(0))
s.bf_ctrl[0] = 0
s.bf_scored[0, 0] = 1
far = s.add_permanent(P3, 1, base_loc(1))
_ph33.enter_main(s, T, V1)
if not any(int(s.trig[i][0]) == _TRMS for i in range(s.n_trig)):
    die("iascylla", "queued at Main start")
spec = abilities_for(T, T.id_of("Iascylla"))[0]
if not chain_mod.ability_cond_holds(s, T, spec, 0, iq):
    die("iascylla", "she held here this turn")
s.bf_scored[0, 0] = 0
if chain_mod.ability_cond_holds(s, T, spec, 0, iq):
    die("iascylla", "no hold, no pull")
_rsv.resolve(s, T, V1, spec, 0, [far], -1, False, source=iq)
if int(s.perms[far, P_LOC]) != bf_loc(0):
    die("iascylla", "pulls the enemy to her battlefield")
ok("Iascylla pulls an enemy to the battlefield she held, at Main start")

s = fresh()
bc = s.add_permanent(T.id_of("Bottled Constellation"), 0, base_loc(0))
fod = [s.add_permanent(P3, 0, base_loc(0)) for _ in range(3)]
spec = abilities_for(T, T.id_of("Bottled Constellation"))[0]
p0 = int(s.points[0])
_rsv.resolve(s, T, V1, spec, 0, fod, -1, False, source=bc)
if int(s.points[0]) != p0 + 1 or any(s.perms[f, P_ALIVE] for f in fod):
    die("bottled constellation", "three die, one point")
ok("Bottled Constellation trades three permanents for a point")

for n_trash, left in ((5, 2), (2, 0)):
    s = fresh()
    s.trash[0, :n_trash] = P3
    s.n_trash[0] = n_trash
    md = s.add_permanent(T.id_of("Dr. Mundo - Expert"), 0, base_loc(0))
    m0 = combat.might(s, T, md)
    if m0 != int(T.might[T.id_of("Dr. Mundo - Expert")]) + n_trash:
        die("dr mundo", "Might grows with the trash")
    from rl.engine.effects import TR_BEGINNING as _TRBG
    chain_mod.queue(s, _TRBG, md, base_loc(0))
    _settle(s)
    if s.pend_slot >= 0:
        for _ in range(3):
            legal = A.legal_actions(s, T, V1, 0)
            A.apply(s, T, V1, next(a for a in legal if a.kind == A.A_TARGET))
        _settle(s)
    if int(s.n_trash[0]) != left:
        die("dr mundo", f"{n_trash} in trash -> {int(s.n_trash[0])} left")
ok("Dr. Mundo - Expert recycles 3 from the trash (or all of a short one)")

s = fresh()
s.add_permanent(P3, 0, base_loc(0), ready=True)
s.deck[1, :2] = [T.id_of("Meditation"), P3]
_rsv.resolve(s, T, V1, _SPECS["Blind Fury"], 0, [], -1, True)
h0 = int(s.n_hand[0])
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
if s.pend_cost_kill >= 0:
    die("meditation", "a spell cast by an effect does not pay its optional cost")
drain(s, V1)
if int(s.n_hand[0]) != h0 + 1:
    die("meditation", "unpaid, it draws 1")
ok("an effect-cast Meditation plays without its optional exhaust")

# ---------------------------------------------------------------------------
print("\n[batch 34] second draws, gear plays, an immediate kill-cost add, exhaust costs")
from rl.engine.effects import TR_SECOND_DRAW as _TRSD, TR_PLAY_UNIT as _TRPU
from rl.engine.state import D_ANY as _DANY

s = fresh()
s.add_permanent(T.id_of("Frigid Jewel"), 0, base_loc(0))
s.add_permanent(P3, 0, base_loc(0))            # something to give +2 to
_ph33.draw_for(s, 0, 1)
A._settle(s, T, V1)
if s.n_trig or s.n_chain:
    die("frigid jewel", "the first draw fires nothing")
_ph33.draw_for(s, 0, 1)
A._settle(s, T, V1)
if not (s.n_chain or s.n_trig or s.pend_slot >= 0):
    die("frigid jewel", "the second draw fires it")
ok("Frigid Jewel fires on the second card drawn in a turn")

s = fresh()
jy = s.add_permanent(T.id_of("Jayce, Brilliant Inventor"), 0, base_loc(0))
gold = s.add_permanent(GOLD, 0, base_loc(0))
chain_mod.fire_play_unit(s, T, 0, GOLD, gold)
if s.n_trig:
    die("jayce brilliant inventor", "a token gear does not count")
bar = s.add_permanent(BAR, 0, base_loc(0))
chain_mod.fire_play_unit(s, T, 0, BAR, bar)
if s.n_trig != 1:
    die("jayce brilliant inventor", "a non-token gear does")
s.n_trig = 0
bar2 = s.add_permanent(BAR, 0, base_loc(0))
chain_mod.fire_play_unit(s, T, 0, BAR, bar2)
if s.n_trig:
    die("jayce brilliant inventor", "only the first each turn")
ok("Jayce, Brilliant Inventor readies on the first non-token gear each turn")

s = fresh(runes=0)
mz = s.add_permanent(T.id_of("Malzahar - Fanatic"), 0, base_loc(0), ready=True)
fod = s.add_permanent(P3, 0, base_loc(0))
act = next(a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE)
A.apply(s, T, V1, act)
A.apply(s, T, V1, A.Action(A.A_TARGET, fod))
if s.perms[fod, P_ALIVE] or int(s.pool_power[0, _DANY]) != 2 or s.n_chain:
    die("malzahar fanatic", "kill paid, two [A] added at once, nothing left on the Chain")
ok("Malzahar - Fanatic kills to add two runes without using the Chain")

s = fresh()
sg = s.add_permanent(T.id_of("Forgotten Signpost"), 0, base_loc(0), ready=True)
scout = s.add_permanent(P3, 0, bf_loc(1), ready=True)
s.bf_ctrl[1] = 0
mover = s.add_permanent(P3, 0, base_loc(0))
act = next(a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE)
A.apply(s, T, V1, act)
A.apply(s, T, V1, A.Action(A.A_TARGET, scout))
A.apply(s, T, V1, A.Action(A.A_TARGET, mover))
drain(s, V1)
if int(s.perms[mover, P_LOC]) != bf_loc(1) or int(s.perms[scout, _PR23]):
    die("forgotten signpost", "exhaust one, move another to it")
ok("Forgotten Signpost moves a unit to the one it exhausted")

# ---------------------------------------------------------------------------
print("\n[batch 35] the opponent answers a move")
s = fresh()
mine = s.add_permanent(P3, 0, base_loc(0))
theirs = s.add_permanent(P3, 1, base_loc(1))
s.bf_ctrl[0] = 0
_rsv.resolve(s, T, V1, _SPECS["Call to Battle"], 0, [mine, bf_loc(0)], -1, True)
if int(s.perms[mine, P_LOC]) != bf_loc(0) or s.pend_cull != 1:
    die("call to battle", "yours moves, then the opponent chooses")
opts = [a.arg for a in A.legal_actions(s, T, V1, 1) if a.kind == A.A_TARGET]
if opts != [theirs]:
    die("call to battle", f"one of THEIR units: {opts}")
A.apply(s, T, V1, A.Action(A.A_TARGET, theirs))
if int(s.perms[theirs, P_LOC]) != bf_loc(0) or s.pend_cull >= 0:
    die("call to battle", "theirs follows to the same battlefield")
ok("Call to Battle moves yours, then makes them move one to the same place")

s = fresh(hand=[T.id_of("Relentless Pursuit")])
u = s.add_permanent(P3, 0, base_loc(0))
sword = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_TARGET, u))
A.apply(s, T, V1, A.Action(A.A_TARGET, bf_loc(1)))
A.apply(s, T, V1, A.Action(A.A_TARGET, sword))
for _ in range(30):
    if s.n_chain == 0 and s.n_trig == 0 and s.pend_may < 0:
        break
    who = A.acting_seat(s)
    legal = A.legal_actions(s, T, V1, who)
    pick = next((a for a in legal if a.kind in (A.A_ACCEPT, A.A_ORDER, A.A_PASS)), None)
    if pick is None:
        die("relentless pursuit", f"stuck at {legal} (slot {s.pend_slot})")
    A.apply(s, T, V1, pick)
if int(s.perms[sword, _PAT]) != u:
    die("relentless pursuit", "the Equipment is attached")
if int(s.points[0]) < 1 or int(s.perms[u, P_LOC]) != base_loc(0):
    die("relentless pursuit", f"conquers, then may move home: loc {int(s.perms[u, P_LOC])}")
ok("Relentless Pursuit moves, equips, and lets the unit go home after conquering")

# ---------------------------------------------------------------------------
print("\n[batch 36] split damage, equipped units")

s = fresh()
vf = s.add_permanent(T.id_of("Volibear - Furious"), 0, base_loc(1))
a1 = s.add_permanent(P3, 1, base_loc(1))
a2 = s.add_permanent(PLAIN2, 1, base_loc(1))
far = s.add_permanent(P3, 1, bf_loc(0))
spec = abilities_for(T, T.id_of("Volibear - Furious"))[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=vf)
opts = sorted(a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET)
if opts != sorted([a1, a2]):
    die("volibear furious", f"only enemies here: {opts}")
for tgt in (a1, a1, a1, a2, a2):
    A.apply(s, T, V1, A.Action(A.A_TARGET, tgt))
if s.pend_split >= 0 or s.perms[a1, P_ALIVE] or s.perms[a2, P_ALIVE]:
    die("volibear furious", "3 and 2 kill both")
ok("Volibear - Furious splits 5 damage among enemies where he attacks")

s = fresh(hand=[T.id_of("Alpha Strike")])
hero = s.add_permanent(DRAKE, 0, base_loc(0))
v1 = s.add_permanent(P3, 1, bf_loc(0))
v2 = s.add_permanent(P3, 1, bf_loc(1))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_TARGET, hero))
drain(s, V1)
if s.pend_split != 0 or int(s.split_left) != 10:
    die("alpha strike", "the Drake's 10 Might to split")
for _ in range(10):
    if s.pend_split < 0:
        break
    opts = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
    A.apply(s, T, V1, A.Action(A.A_TARGET, v1 if int(s.split_alloc[v1]) < 3 else v2))
if s.perms[v1, P_ALIVE] or s.perms[v2, P_ALIVE] or int(s.xp[0]) != 2:
    die("alpha strike", f"two kills, two XP: xp={int(s.xp[0])}")
ok("Alpha Strike splits its unit's Might and gains XP per kill")

s = fresh()
eq = s.add_permanent(P3, 0, base_loc(0))
bare = s.add_permanent(P3, 0, base_loc(0))
sw = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
s.attach(sw, eq)
e = s.add_permanent(P3, 1, base_loc(1))
spec = _SPECS["Strike Down"]
if bare in _rsv.legal_targets(s, T, spec, 0, 0, [], -1):
    die("strike down", "only an equipped unit")
m = combat.might(s, T, eq)
_rsv.resolve(s, T, V1, spec, 0, [eq, e], -1, True)
if s.perms[e, P_ALIVE] or int(s.perms[sw, _PAT]) >= 0:
    die("strike down", f"{m} damage kills, then the sword comes off")
ok("Strike Down hits with an equipped unit, then detaches an Equipment")

# ---------------------------------------------------------------------------
print("\n[batch 37] enter-ready by score, conquering the unclaimed, spell-only energy")
from rl.engine.state import C_FINAL as _CFIN

CD = T.id_of("Corrupted Dragon")
s = fresh()
s.victory_score = 8
s.points[0] = 4
if not combat.permanent_enters_ready(s, T, 0, CD, True):
    die("corrupted dragon", "4 of 8 is not within 3: ready")
s.points[0] = 5
if combat.permanent_enters_ready(s, T, 0, CD, True):
    die("corrupted dragon", "5 of 8 is within 3")
ok("Corrupted Dragon enters ready far from victory")

s = fresh()
yo = s.add_permanent(T.id_of("Yone - Blademaster"), 0, bf_loc(0))
spec = abilities_for(T, T.id_of("Yone - Blademaster"))[0]
s.bf_prev_ctrl[0] = -1
if not chain_mod.ability_cond_holds(s, T, spec, 0, yo, bf_loc(0)):
    die("yone", "an uncontrolled battlefield counts")
s.bf_prev_ctrl[0] = 1
if chain_mod.ability_cond_holds(s, T, spec, 0, yo, bf_loc(0)):
    die("yone", "taking it from the opponent does not")
ok("Yone - Blademaster only fires for conquering unclaimed ground")

s = fresh(hand=[VENG, P3], runes=0)
lux = s.add_permanent(T.id_of("Lux, Crownguard"), 0, base_loc(0), ready=True)
s.runes_ready[0, 5] = 2                         # Order, Vengeance's domain
e = s.add_permanent(P3, 1, base_loc(1))
act = next(a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE)
A.apply(s, T, V1, act)
if int(s.pool_rstr_e[0, RK_SPELL]) != 2:
    die("lux crownguard", "2 spell-only energy")
from rl.engine.cost import plan_payment as _pp37
if _pp37(s, T, 0, VENG) is None:
    die("lux crownguard", "4-cost Vengeance: 2 runes + 2 spell energy")
if _pp37(s, T, 0, DRAKE) is not None:
    die("lux crownguard", "a unit can't use it")
ok("Lux, Crownguard adds Energy only spells may spend")

s = fresh()
s.xp[0] = 6
gh = s.add_permanent(T.id_of("Gemhand Hunter"), 0, base_loc(0))
if combat.might(s, T, gh) != int(T.might[T.id_of("Gemhand Hunter")]) + 1:
    die("gemhand hunter", "[Level 6] +1 Might")
ok("Gemhand Hunter gets +1 Might at Level 6")

from rl.engine.cost import effective_energy as _ee37, effective_power as _ep37
JH = T.id_of("Jhin - Meticulous Killer")
s = fresh()
e0, p0 = _ee37(s, T, 0, JH), _ep37(s, T, 0, JH)
s.big_spell_ply[0] = s.ply
if _ee37(s, T, 0, JH) != 0 or _ep37(s, T, 0, JH) != p0 + 1:
    die("jhin", f"for a Mind rune after a big spell: {_ee37(s, T, 0, JH)}E")
ok("Jhin - Meticulous Killer costs a Mind rune after a 4-Energy spell")

s = fresh()
f = s.add_permanent(P3, 0, bf_loc(0))
spec = _SPECS["Decree of Focus"]
if f in _rsv.legal_targets(s, T, spec, 0, 0, [], -1):
    die("decree of focus", "not threatened by Fury")
furyu = T.id_of("Armed Assailant")
s.add_permanent(furyu, 1, bf_loc(0))
s.showdown_bf = 0
if f not in _rsv.legal_targets(s, T, spec, 0, 0, [], -1):
    die("decree of focus", "in combat with an enemy Fury unit")
ok("Decree of Focus answers a Fury threat")

s = fresh()
u1 = s.add_permanent(P3, 0, bf_loc(0))
it = chain_mod.push(s, VENG, 1, from_hand=True, bound_bf=-1)
s.chain_targets[it, 0] = u1
s.chain[it, _CFIN] = 1
spec = _SPECS["Repulse"]
if len(_rsv.legal_targets(s, T, spec, 1, 0, [u1], -1)) != 1:
    die("repulse", "a spell choosing only it")
u2 = s.add_permanent(P3, 0, bf_loc(0))
if _rsv.legal_targets(s, T, spec, 1, 0, [u2], -1):
    die("repulse", "not a spell that chooses a different unit")
ok("Repulse counters what chooses only its unit")

s = fresh()
s.fd_owner[0], s.fd_card[0], s.fd_ply[0] = 1, T.id_of("Blastcone Fae"), -5
s.bf_ctrl[0] = 1
s.priority = 1
before = chain_mod.hidden_playable(s, T, V1, 1)
s.add_permanent(T.id_of("Noxus Saboteur"), 0, bf_loc(0))
after = chain_mod.hidden_playable(s, T, V1, 1)
if 0 not in before or 0 in after:
    die("noxus saboteur", f"blocks their facedown card there: {before} -> {after}")
ok("Noxus Saboteur keeps opponents' [Hidden] cards down at its battlefield")

from rl.engine.effects import TR_HOLD as _TRH37, TR_CONQUER as _TRC37
s = fresh()
hq = s.add_permanent(T.id_of("Trevor Snoozebottom") if "Trevor Snoozebottom" in T._index
                     else next(c for c in range(T.n) if any(
                         a.trigger == _TRH37 for a in abilities_for(T, c))
                         and T.is_type(c, "Unit")), 0, bf_loc(0))
sky = s.add_permanent(T.id_of("Skyfall of Areion"), 0, base_loc(0))
s.attach(sky, hq)
s.bf_ctrl[0] = 1
combat._establish_control(s, T, V1, 0)
if not any(int(s.trig[i][0]) == _TRH37 and int(s.trig[i][1]) == hq for i in range(s.n_trig)):
    die("skyfall", "its unit's hold effect fires on a conquer")
ok("Skyfall of Areion makes hold effects conquer effects")

# ---------------------------------------------------------------------------
print("\n[batch 38] buffs spent, recycles watched, Empowered wards")
from rl.engine.effects import TR_RECYCLED as _TRRC

s = fresh(runes=0)
b1 = s.add_permanent(P3, 0, base_loc(0), ready=False)
b2 = s.add_permanent(P3, 0, base_loc(0), ready=False)
plain_u = s.add_permanent(P3, 0, base_loc(0), ready=False)
for b in (b1, b2):
    s.perms[b, _PF] |= _FB25
_rsv.resolve(s, T, V1, _SPECS["Overt Operation"], 0, [b1, -1, -1, -1, -1, -1], -1, True)
if not int(s.perms[b1, _PR23]) or int(s.perms[b2, _PR23]) \
        or not all(int(s.perms[u, _PF]) & _FB25 for u in (b1, b2, plain_u)):
    die("overt operation", "spent b1's buff to ready it, then everyone buffed")
ok("Overt Operation readies for buffs spent, then buffs every friendly unit")

s = fresh(runes=0)
s.rune_deck[0, :4] = [0, 1, 2, 3]
s.rune_head[0], s.rune_left[0] = 0, 4
al = s.add_permanent(T.id_of("Albus Ferros"), 0, base_loc(0))
x1 = s.add_permanent(P3, 0, base_loc(0)); x2 = s.add_permanent(P3, 0, base_loc(0))
for b in (x1, x2):
    s.perms[b, _PF] |= _FB25
spec = abilities_for(T, T.id_of("Albus Ferros"))[0]
_rsv.resolve(s, T, V1, spec, 0, [x1, x2, -1, -1], -1, False, source=al)
if int(s.runes_spent[0].sum()) != 2 or int(s.runes_ready[0].sum()):
    die("albus ferros", "two buffs, two runes channelled exhausted")
ok("Albus Ferros channels an exhausted rune per buff spent")

s = fresh()
s.add_permanent(T.id_of("Karma - Channeler"), 0, base_loc(0))
s.recycle_card(0, P3)
A._settle(s, T, V1)
if not (s.n_chain or s.n_trig or s.pend_slot >= 0):
    die("karma", "a recycle to the Main Deck buffs")
ok("Karma - Channeler buffs when you recycle a card")

s = fresh()
mel = s.add_permanent(T.id_of("Mel, Newly Awakened"), 0, base_loc(0))
foe = s.add_permanent(DRAKE, 1, base_loc(1))
from rl.engine.effects import CardSpec as _CS38, Op as _Op38, TargetSpec as _TS38, \
    OP_MODIFY_MIGHT as _OMM, OP_STUN as _OST
shrink = _CS38(0, targets=(_TS38(),), ops=(_Op38(_OMM, target=0, n=-2),))
m0 = combat.might(s, T, foe)
_rsv.resolve(s, T, V1, shrink, 0, [foe], -1, True)
if combat.might(s, T, foe) != m0 - 2:
    die("mel", "not Empowered: -2 stays -2")
s.perms[mel, _PEM28] = 1
s.perms[mel, _PF] |= _FEM
_rsv.resolve(s, T, V1, shrink, 0, [foe], -1, True)
if combat.might(s, T, foe) != m0 - 5:
    die("mel", "Empowered: -2 becomes -3")
it = chain_mod.push(s, VENG, 0, from_hand=True, bound_bf=-1)
s.chain[it, _CFIN] = 1
if not _rsv.legal_targets(s, T, _SPECS["Hard Bargain"], 0, 1, [], -1):
    die("mel", "Empowered: 'can't be countered' is not untargetable (RiftJudge #11722)")
from rl.engine.state import C_UID as _CU38
chain_mod.counter(s, T, int(s.chain[it, _CU38]))
if chain_mod.index_of_uid(s, int(s.chain[it, _CU38])) < 0:
    die("mel", "Empowered: your spells can't be countered")
ok("Mel, Newly Awakened deepens -Might and makes your spells uncounterable")

s = fresh()
gp = s.add_permanent(T.id_of("Gangplank, Naval"), 1, base_loc(1))
s.perms[gp, _PEM28] = 1
s.perms[gp, _PF] |= _FEM
m0 = combat.might(s, T, gp)
_rsv.resolve(s, T, V1, _CS38(0, targets=(_TS38(),), ops=(_Op38(_OST, target=0),)),
             0, [gp], -1, True)
if int(s.perms[gp, _PF]) & _FST or combat.might(s, T, gp) != m0 + 3:
    die("gangplank", "a chosen stun becomes +3 Might")
ok("Gangplank, Naval turns a stun that chooses him into +3 Might")

s = fresh()
az = s.add_permanent(T.id_of("Azir - Ascendant"), 0, base_loc(0))
pal = s.add_permanent(P3, 0, bf_loc(0))
blade = s.add_permanent(T.id_of("Long Sword"), 0, base_loc(0))
s.attach(blade, pal)
spec = abilities_for(T, T.id_of("Azir - Ascendant"))[0]
if _rsv.legal_targets(s, T, spec, 1, 0, [pal], -1, source=az) != [blade]:
    die("azir ascendant", "one of ITS Equipment")
_rsv.resolve(s, T, V1, spec, 0, [pal, blade], -1, False, source=az)
if int(s.perms[az, P_LOC]) != bf_loc(0) or int(s.perms[pal, P_LOC]) != base_loc(0) \
        or int(s.perms[blade, _PAT]) != az:
    die("azir ascendant", "swap places and take the sword")
ok("Azir - Ascendant swaps with a unit and takes its Equipment")

# ---------------------------------------------------------------------------
print("\n[batch 39] pay any amount, and a legend as a cost")

s = fresh(runes=0)
s.runes_ready[0, 0] = 3
e1 = s.add_permanent(P3, 1, bf_loc(0))
e2 = s.add_permanent(PLAIN2, 1, bf_loc(0))
_rsv.resolve(s, T, V1, _SPECS["Bullet Time"], 0, [bf_loc(0)], -1, True)
if [a.arg for a in A.legal_actions(s, T, V1, 0)] != [0, 1, 2, 3]:
    die("bullet time", "any amount up to what can be paid")
A.apply(s, T, V1, A.Action(A.A_PICK, 2))
if s.perms[e2, P_ALIVE] or int(s.perms[e1, P_DMG]) != 2 or int(s.runes_in_play(0).sum()) != 1:
    die("bullet time", "paid 2, dealt 2 to each")
ok("Bullet Time pays X to deal X to every enemy there")

s = fresh(runes=0)
s.runes_ready[0, 0] = 3
hg = s.add_permanent(T.id_of("Ancient Henge"), 0, base_loc(0), ready=True)
act = next(a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE)
A.apply(s, T, V1, act)
A.apply(s, T, V1, A.Action(A.A_PICK, 2))
if int(s.pool_power[0, _DANY]) != 2 or int(s.runes_ready[0].sum()) != 1:
    die("ancient henge", "2 Energy into 2 [A]")
ok("Ancient Henge turns Energy into any-rune Power")

s = fresh(runes=0)
s.runes_ready[0, 0] = 2
hx = s.add_permanent(T.id_of("Hextech Anomaly"), 0, base_loc(0), ready=True)
act = next(a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE)
A.apply(s, T, V1, act)
A.apply(s, T, V1, A.Action(A.A_PICK, 2))
if int(s.pool_energy[0]) != 2 or int(s.runes_in_play(0).sum()) != 0:
    die("hextech anomaly", "2 [A] recycled into 2 Energy")
ok("Hextech Anomaly turns Power into Energy")

s = fresh(hand=[T.id_of("Bard - Mercurial")])
s.legend[0], s.legend_ready[0] = T.id_of("Rell - Magnetic"), 1
m1 = s.add_permanent(P3, 0, base_loc(0))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
fast = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT_FAST]
if not fast:
    die("bard", "exhausting a ready legend is offered")
A.apply(s, T, V1, fast[0])
if int(s.legend_ready[0]):
    die("bard", "the legend is exhausted")
bard = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == T.id_of("Bard - Mercurial"))
spec = abilities_for(T, T.id_of("Bard - Mercurial"))[0]
if not chain_mod.ability_cond_holds(s, T, spec, 0, bard):
    die("bard", "paid")
s.n_trig = 0
_rsv.resolve(s, T, V1, spec, 0, [bf_loc(1), m1, bard, -1, -1], -1, False, source=bard)
if int(s.perms[m1, P_LOC]) != bf_loc(1) or int(s.perms[bard, P_LOC]) != bf_loc(1):
    die("bard", "units move to the open battlefield")
ok("Bard - Mercurial exhausts your legend to move units to an open battlefield")

# ---------------------------------------------------------------------------
print("\n[batch 40] cheaper equips, free gear, burn follow-ups, armory, Ava")
from rl.engine.cost import effective_energy as _ee40

s = fresh()
jm = s.add_permanent(T.id_of("Jayce, Man of Progress"), 0, base_loc(0))
gold = s.add_permanent(GOLD, 0, base_loc(0))
spec = abilities_for(T, T.id_of("Jayce, Man of Progress"))[0]
_rsv.resolve(s, T, V1, spec, 0, [gold], -1, False, source=jm)
if _ee40(s, T, 0, BAR) != 0 or _ee40(s, T, 0, DRAKE) != int(T.energy[DRAKE]):
    die("jayce mop", "a gear is free this turn, a unit is not")
ok("Jayce, Man of Progress kills a gear to make the next gear free")

s = fresh()
s.deck[0, 0] = DRAKE
fr = s.add_permanent(T.id_of("Forgotten Relic"), 0, base_loc(0))
tgt = s.add_permanent(P3, 0, base_loc(0))
spec = abilities_for(T, T.id_of("Forgotten Relic"))[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=fr)
_settle(s)
if s.pend_slot >= 0:
    A.apply(s, T, V1, A.Action(A.A_TARGET, tgt))
    _settle(s)
if combat.might(s, T, tgt) != 3 + int(T.might[DRAKE]):
    die("forgotten relic", f"+{int(T.might[DRAKE])} from the burned Drake: {combat.might(s, T, tgt)}")
ok("Forgotten Relic burns and hands the burned unit's Might to a friend")

s = fresh(runes=0)
s.runes_ready[0, 3] = 1                          # a Fury rune
u = s.add_permanent(P3, 0, bf_loc(0))
s.armory_ply[u] = s.ply
combat.destroy(s, T, u)
if not s.perms[u, P_ALIVE] or int(s.perms[u, P_LOC]) != base_loc(0) or int(s.perms[u, _PR23]):
    die("unlicensed armory", "paid Fury: healed, exhausted, recalled")
combat.destroy(s, T, u)
if s.perms[u, P_ALIVE]:
    die("unlicensed armory", "only the next time")
ok("Unlicensed Armory saves a unit once for a Fury rune")

s = fresh(runes=0)
s.runes_ready[0, 4] = 1                          # Mind
ava = s.add_permanent(T.id_of("Ava Achiever"), 0, bf_loc(0))
s.hand[0, :2] = [T.id_of("Blastcone Fae"), P3]
s.n_hand[0] = 2
spec = abilities_for(T, T.id_of("Ava Achiever"))[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=ava)
picks = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK]
if picks != [0]:
    die("ava achiever", f"only a [Hidden] card: {picks}")
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
fae = [i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == T.id_of("Blastcone Fae")]
if not fae or int(s.perms[fae[0], P_LOC]) != bf_loc(0):
    die("ava achiever", "the unit is played here")
ok("Ava Achiever plays a [Hidden] card from hand where she attacks")

s = fresh(runes=0)
s.runes_ready[0, 3] = 2
s.runes_ready[0, 5] = 1
big = s.add_permanent(DRAKE, 0, base_loc(0))
hg = s.add_permanent(T.id_of("Hextech Gauntlets"), 0, base_loc(0))
spec = abilities_for(T, T.id_of("Hextech Gauntlets"))[0]
it = chain_mod.push(s, T.id_of("Hextech Gauntlets"), 0, from_hand=False, abil=0,
                    src=hg)
s.chain_targets[it, 0] = big
r0 = int(s.runes_ready[0].sum())
A._finalize_pending(s, T, V1, it)
if r0 - int(s.runes_ready[0].sum()) > 1:
    die("hextech gauntlets", "a 10-Might unit waives the {3 energy}")
ok("Hextech Gauntlets' Equip is cheaper by the chosen unit's Might")

# ---------------------------------------------------------------------------
print("\n[batch 41] granted plays from the trash")
DFB = T.id_of("Death from Below")
s = fresh(hand=[DFB])
small = s.add_permanent(P3, 1, bf_loc(0))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_TARGET, small))
drain(s, V1)
tr = [int(c) for c in s.trash[0, :s.n_trash[0]]]
if s.perms[small, P_ALIVE] or DFB not in tr:
    die("death from below", "kills and goes to the trash")
big = s.add_permanent(DRAKE, 1, bf_loc(0))
idx = chain_mod.flow_playable(s, T, V1, 0)
if tr.index(DFB) not in idx:
    die("death from below", "a 3-Might kill lets it be replayed from the trash")
A.apply(s, T, V1, A.Action(A.A_PLAY_FLOW, tr.index(DFB)))
A.apply(s, T, V1, A.Action(A.A_TARGET, big))
drain(s, V1)
if s.perms[big, P_ALIVE] or DFB not in [int(c) for c in s.trash[0, :s.n_trash[0]]]:
    die("death from below", "replayed, it kills and returns to the trash")
if chain_mod.flow_playable(s, T, V1, 0):
    die("death from below", "the big kill grants nothing")
ok("Death from Below can replay itself after killing a small unit")

s = fresh()
kn = s.add_permanent(T.id_of("Kennen, Storm of Shuriken"), 0, bf_loc(0))
s.trash[0, 0] = VENG
s.n_trash[0] = 1
s.add_permanent(P3, 1, base_loc(1))
spec = abilities_for(T, T.id_of("Kennen, Storm of Shuriken"))[1]
from rl.engine.effects import pack_trash as _pk41
_rsv.resolve(s, T, V1, spec, 0, [_pk41(0, VENG)], -1, False, source=kn)
if 0 not in chain_mod.flow_playable(s, T, V1, 0):
    die("kennen", "the spell gains [Flow] this turn")
s.ply += 1
if chain_mod.flow_playable(s, T, V1, 0):
    die("kennen", "only this turn")
ok("Kennen, Storm of Shuriken gives a trash spell [Flow] for a turn")

s = fresh(runes=0)
s.runes_ready[0, 1] = 2                          # Calm: not Glowstone's Order
gs = s.add_permanent(T.id_of("Glowstone"), 0, base_loc(0), ready=True)
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("glowstone", "its {any rune}{any rune} Empower is payable with Calm runes")
spec = abilities_for(T, T.id_of("Glowstone"))
s.perms[gs, _PEM28] = 1
s.perms[gs, _PF] |= _FEM
_rsv.resolve(s, T, V1, _cm23(spec[1], 1), 0, [1], -1, False, source=gs)
if int(s.perms[gs, P_CTRL]) != 1 or int(s.perms[gs, P_LOC]) != base_loc(1):
    die("glowstone", "handed to the opponent and recalled to their base")
v = s.add_permanent(P3, 1, base_loc(1))
_rsv.resolve(s, T, V1, spec[2], 1, [], -1, False, source=gs)
if s.perms[gs, P_ALIVE] or s.perms[v, P_ALIVE]:
    die("glowstone", "end of its controller's turn: it dies and hits them for 5")
ok("Glowstone can be handed to the opponent to blow up on their turn")

s = fresh(runes=0)
s.runes_ready[0, 3] = 3                          # Fury
ul = T.id_of("Undying Legion")
s.trash[0, 0] = ul
s.n_trash[0] = 1
if chain_mod.flow_playable(s, T, V1, 0):
    die("undying legion", "[Legion]: not before another card is played")
s.cards_played[0] = 1
if chain_mod.flow_playable(s, T, V1, 0) != [0]:
    die("undying legion", "playable from the trash once [Legion] holds")
A.apply(s, T, V1, A.Action(A.A_PLAY_FLOW, 0))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
if not any(s.perms[i, P_ALIVE] and int(s.perms[i, P_CARD]) == ul for i in range(s.n_perms)) \
        or int(s.n_trash[0]) or int(s.runes_in_play(0).sum()) != 2:
    die("undying legion", "out of the trash for {3}{Fury}")
ok("Undying Legion returns from the trash with [Legion]")

s = fresh(runes=1)
s.trash[0, :3] = [P3, VENG, DRAKE]
s.n_trash[0] = 3
sc = s.add_permanent(T.id_of("Cursed Sarcophagus"), 0, base_loc(0), ready=True)
spec = abilities_for(T, T.id_of("Cursed Sarcophagus"))
_rsv.resolve(s, T, V1, spec[0], 0, [], -1, False, source=sc)
if int(s.n_trash[0]) != 1 or int(s.n_sarc[0]) != 2:
    die("cursed sarcophagus", "units banished with it")
_rsv.resolve(s, T, V1, spec[1], 0, [], -1, False, source=sc)
picks = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PICK]
if [int(s.sarc_cards[0, k]) for k in picks] != [P3]:
    die("cursed sarcophagus", f"only what can be paid for: {picks}")
A.apply(s, T, V1, A.Action(A.A_PICK, picks[0]))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
if int(s.n_sarc[0]) != 1 or int(s.n_banished[0]) != 1:
    die("cursed sarcophagus", "the Skulker is played out of Banishment")
ok("Cursed Sarcophagus banishes trash units and plays them later")

# ---------------------------------------------------------------------------
print("\n[batch 42] kill costs that pay for the unit")
AT = T.id_of("Atakhan")
s = fresh(hand=[AT], runes=0)
s.runes_ready[0, 5] = 3                          # three Order runes
if any(a.kind == A.A_PLAY for a in A.legal_actions(s, T, V1, 0)):
    die("atakhan", "10 Energy with 3 runes and nothing to kill: not playable")
fod = s.add_permanent(DRAKE, 0, base_loc(0))     # 9 Energy
if not any(a.kind == A.A_PLAY for a in A.legal_actions(s, T, V1, 0)):
    die("atakhan", "killing the Drake takes 9 Energy off")
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
if [a.kind for a in A.legal_actions(s, T, V1, 0)] != [A.A_TARGET]:
    die("atakhan", "only the paying kill, no unpayable decline")
A.apply(s, T, V1, A.Action(A.A_TARGET, fod))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
if s.perms[fod, P_ALIVE] or not any(s.perms[i, P_ALIVE] and int(s.perms[i, P_CARD]) == AT
                                    for i in range(s.n_perms)):
    die("atakhan", "played for the Drake's life")
ok("Atakhan's cost drops by the killed unit's cost")

s = fresh()
atk = s.add_permanent(AT, 0, bf_loc(0))
d1 = s.add_permanent(P3, 1, bf_loc(0))
d_far = s.add_permanent(P3, 1, base_loc(1))
spec = abilities_for(T, AT)[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=atk)
if s.pend_cull != 1 or [a.arg for a in A.legal_actions(s, T, V1, 1)] != [d1]:
    die("atakhan", "the defender kills one of THEIR units HERE")
ok("Atakhan makes the defender kill a unit where he attacks")

LD = T.id_of("Commander Ledros")
s = fresh(hand=[LD], runes=0)
s.runes_ready[0, 5] = 6
us = [s.add_permanent(P3, 0, base_loc(0)) for _ in range(3)]
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
for u in us[:2]:
    A.apply(s, T, V1, A.Action(A.A_TARGET, u))
if s.pend_kill_play < 0:
    die("ledros", "still choosing after two")
A.apply(s, T, V1, A.Action(A.A_DECLINE))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
if sum(1 for u in us if s.perms[u, P_ALIVE]) != 1 or int(s.runes_in_play(0).sum()) != 6 - 2:
    die("ledros", f"two kills, two Power off: runes left {int(s.runes_in_play(0).sum())}")
ok("Commander Ledros loses an Order rune of cost per unit killed")

s = fresh()
rb = s.add_permanent(T.id_of("Rumble - Hotheaded"), 0, base_loc(0))
mech = s.add_permanent(T.id_of("Mech"), 0, base_loc(0))
if not combat.perm_kw(s, T, mech, "Assault"):
    die("rumble", "Mechs have [Assault]")
MECHC = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c)
             and "Mech" in T.tags[c])
s.trash[0, 0] = MECHC
s.n_trash[0] = 1
feed = s.add_permanent(DRAKE, 0, base_loc(0))
s.runes_ready[0, :] = 2                          # plenty of Power, cheap Energy
spec = abilities_for(T, T.id_of("Rumble - Hotheaded"))[0]
from rl.engine.effects import pack_trash as _pk43
e0 = int(s.runes_ready[0].sum())
_rsv.resolve(s, T, V1, spec, 0, [feed, _pk43(0, MECHC)], -1, False, source=rb)
if s.perms[feed, P_ALIVE] or not any(s.perms[i, P_ALIVE] and int(s.perms[i, P_CARD]) == MECHC
                                     for i in range(s.n_perms)):
    die("rumble", "recycles a unit and plays the Mech")
if e0 - int(s.runes_ready[0].sum()) > max(0, int(T.power[MECHC])):
    die("rumble", "the Drake's 10 Might covers the Mech's Energy")
ok("Rumble - Hotheaded trades a unit for a cheaper Mech from the trash")

KH = T.id_of("Kraken Hunter")
s = fresh(hand=[KH], runes=0)
s.runes_ready[0, 0] = 3                          # Body
bb = [s.add_permanent(P3, 0, base_loc(0)) for _ in range(2)]
for b in bb:
    s.perms[b, _PF] |= _FB25
if not any(a.kind == A.A_PLAY for a in A.legal_actions(s, T, V1, 0)):
    die("kraken hunter", "3E 2P with 3 runes: playable by spending buffs")
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
for b in bb:
    if s.pend_kill_play >= 0 and any(a.kind == A.A_TARGET and a.arg == b
                                     for a in A.legal_actions(s, T, V1, 0)):
        A.apply(s, T, V1, A.Action(A.A_TARGET, b))
if s.pend_kill_play >= 0:
    A.apply(s, T, V1, A.Action(A.A_DECLINE))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
if any(int(s.perms[b, _PF]) & _FB25 for b in bb) or not any(
        s.perms[i, P_ALIVE] and int(s.perms[i, P_CARD]) == KH for i in range(s.n_perms)):
    die("kraken hunter", "two buffs spent, Hunter played")
ok("Kraken Hunter spends buffs to shave its Body cost")

# ---------------------------------------------------------------------------
print("\n[batch 43] stealing a spell off the Chain")
from rl.engine.state import C_UID as _CUID43, C_CTRL as _CCTRL43

s = fresh()
mine = s.add_permanent(P3, 0, base_loc(0))
theirs = s.add_permanent(P3, 1, base_loc(1))
it = chain_mod.push(s, VENG, 1, from_hand=True, bound_bf=-1)
s.chain_targets[it, 0] = mine
s.chain[it, _CFIN] = 1
uid = int(s.chain[it, _CUID43])
_rsv.resolve(s, T, V1, _SPECS["Mystic Reversal"], 0, [uid], -1, True)
if int(s.chain[it, _CCTRL43]) != 0 or s.steal_stage != 2:
    die("mystic reversal", "control changes, then new choices are offered")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
opts = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
if theirs not in opts:
    die("mystic reversal", "any legal new target")
A.apply(s, T, V1, A.Action(A.A_TARGET, theirs))
drain(s, V1)
if s.perms[theirs, P_ALIVE] or not s.perms[mine, P_ALIVE]:
    die("mystic reversal", "their Vengeance kills their own unit")
if VENG not in [int(c) for c in s.trash[1, :s.n_trash[1]]]:
    die("mystic reversal", "the card still goes to its owner's trash")
ok("Mystic Reversal steals a spell and redirects it")

for runes, stolen in ((1, True), (0, False)):
    s = fresh(runes=runes)
    mine = s.add_permanent(P3, 0, base_loc(0))
    it = chain_mod.push(s, VENG, 1, from_hand=True, bound_bf=-1)
    s.chain_targets[it, 0] = mine
    s.chain[it, _CFIN] = 1
    uid = int(s.chain[it, _CUID43])
    _rsv.resolve(s, T, V1, _SPECS["Rebuttal"], 0, [uid], -1, True)
    if stolen:
        A.apply(s, T, V1, A.Action(A.A_ACCEPT))
        if int(s.chain[it, _CCTRL43]) != 0:
            die("rebuttal", "paid: control")
        A.apply(s, T, V1, A.Action(A.A_DECLINE))
    elif s.n_chain:
        die("rebuttal", "nothing to pay with: countered")
ok("Rebuttal steals a cheap spell for a rune, or counters it")

# ---------------------------------------------------------------------------
print("\n[batch 44] move ends, move taxes, stacked buffs")

s = fresh()
ak = s.add_permanent(T.id_of("Akali, Deadly Weapon"), 0, bf_loc(1))
there = s.add_permanent(P3, 1, bf_loc(0))
home = s.add_permanent(P3, 1, bf_loc(1))
away = s.add_permanent(P3, 1, base_loc(1))
combat.queue_move_trigger(s, T, ak, bf_loc(0), bf_loc(1))
spec = abilities_for(T, T.id_of("Akali, Deadly Weapon"))[1]
opts = _rsv.legal_targets(s, T, spec, 0, 0, [], -1, source=ak)
if sorted(opts) != sorted([there, home, ak]) and sorted(opts) != sorted([there, home]):
    die("akali deadly weapon", f"units at the battlefields she moved between: {opts}")
if away in opts:
    die("akali deadly weapon", "not at a base")
ok("Akali, Deadly Weapon strikes where she moved to or from")

s = fresh()
s.add_permanent(T.id_of("Mageseeker Investigator"), 1, bf_loc(0))
m1 = s.add_permanent(P3, 0, base_loc(0), ready=True)
m2 = s.add_permanent(P3, 0, base_loc(0), ready=True)
s.runes_ready[0, :] = 0
A.apply(s, T, V1, A.Action(A.A_DECLARE, bf_loc(0)))
A.apply(s, T, V1, A.Action(A.A_ADD, m1))
if any(a.kind == A.A_ADD for a in A.legal_actions(s, T, V1, 0)):
    die("mageseeker investigator", "a second unit costs a rune the player lacks")
ok("Mageseeker Investigator taxes moving several units in at once")

s = fresh()
lee = s.add_permanent(T.id_of("Lee Sin - Ascetic"), 0, base_loc(0), ready=True)
m0 = combat.might(s, T, lee)
spec = abilities_for(T, T.id_of("Lee Sin - Ascetic"))[0]
for _ in range(3):
    _rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=lee)
if combat.might(s, T, lee) != m0 + 3:
    die("lee sin", "three buffs, +3")
chain_mod.spend_buff(s, T, 0, lee)
if combat.might(s, T, lee) != m0 + 2:
    die("lee sin", "spending one leaves two")
ok("Lee Sin - Ascetic stacks any number of buffs")

s = fresh()
u = s.add_permanent(P3, 0, base_loc(0))
hx = s.add_permanent(T.id_of("Experimental Hexplate"), 0, base_loc(0))
s.attach(hx, u)
if "Mech" not in combat.perm_tags(s, T, u):
    die("hexplate", "the equipped unit is a Mech")
ok("Experimental Hexplate makes its unit a Mech")

s = fresh()
iv = s.add_permanent(T.id_of("Ivern - Friend to All"), 0, bf_loc(0))
spec = abilities_for(T, T.id_of("Ivern - Friend to All"))
_rsv.resolve(s, T, V1, _cm23(spec[0], 1), 0, [1], -1, False, source=iv)
if "Cat" not in combat.perm_tags(s, T, iv):
    die("ivern friend", "gains the chosen tag")
for tg in ("Bird", "Dog", "Poro"):
    c = next(c for c in range(T.n) if T.is_type(c, "Unit") and tg in T.tags[c]
             and not T.is_token(c))
    s.add_permanent(c, 0, base_loc(0))
p0 = int(s.points[0])
_rsv.resolve(s, T, V1, spec[1], 0, [], -1, False, source=iv)
if int(s.points[0]) != p0 + 1:
    die("ivern friend", "all four tags: a point")
ok("Ivern - Friend to All completes the four-animal set")

# ---------------------------------------------------------------------------
print("\n[batch 45] naming a tag or a spell")
s = fresh()
lst = s.add_permanent(T.id_of("The List"), 0, base_loc(0), ready=True)
poro = s.add_permanent(PLAIN2, 1, base_loc(1))
other = s.add_permanent(P3, 1, base_loc(1))
spec = abilities_for(T, T.id_of("The List"))
_rsv.resolve(s, T, V1, spec[0], 0, [], -1, False, source=lst)
from rl.engine.effects import tag_vocab as _tv45
names = [_tv45(T)[int(s.name_opts[a.arg])] for a in A.legal_actions(s, T, V1, 0)]
if "Poro" not in names:
    die("the list", f"the enemy's visible tags are nameable: {names}")
A.apply(s, T, V1, A.Action(A.A_PICK, names.index("Poro")))
opts = _rsv.legal_targets(s, T, spec[1], 0, 0, [], -1, source=lst)
if poro not in opts or other in opts:
    die("the list", "only units with the named tag")
ok("The List names a tag and shrinks units carrying it")

# Flickered: it leaves the board and comes back, so TR_PLAY_ME fires again and a
# NEW tag is named. Raised by the project owner. The hazard is not the rename --
# it is that `state.named` is indexed by permanent ROW and rows are recycled, so
# a reused row could inherit the last occupant's tag. `add_permanent` does not
# clear `named` (unlike `kw_grant`); `compact_permanents` is what does it, moving
# the value with the row and clearing freed rows to -1. This pins that.
combat._destroy(s, T, lst)
s.compact_permanents()
if int(s.named[s.n_perms]) != -1:
    die("the list", "compaction left a stale named tag on a freed row")
# Compaction RENUMBERS the live rows, so `poro` and `other` are stale now --
# which is the same hazard from the other side, and worth spelling out rather
# than quietly working around. Re-find them by card.
poro = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == PLAIN2)
other = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == P3)
lst2 = s.add_permanent(T.id_of("The List"), 0, base_loc(0), ready=True)
if int(s.named[lst2]) != -1:
    die("the list", f"re-entered row {lst2} inherited a named tag -- stale row")
if _rsv.legal_targets(s, T, spec[1], 0, 0, [], -1, source=lst2):
    die("the list", "targets offered before anything was named")
_rsv.resolve(s, T, V1, spec[0], 0, [], -1, False, source=lst2)
names2 = [_tv45(T)[int(s.name_opts[a.arg])] for a in A.legal_actions(s, T, V1, 0)]
A.apply(s, T, V1, A.Action(A.A_PICK, names2.index("Pirate")))
opts2 = _rsv.legal_targets(s, T, spec[1], 0, 0, [], -1, source=lst2)
if other not in opts2 or poro in opts2:
    die("the list", "renaming did not replace the previous tag restriction")
ok("...and renames on re-entry, dropping the old tag rather than inheriting it")

s = fresh(hand=[VENG])
s.trash[0, 0] = VENG                             # seen in the OPPONENT's trash
s.n_trash[0] = 1
ff = s.add_permanent(T.id_of("Fallen Feline"), 1, bf_loc(0))
spec = abilities_for(T, T.id_of("Fallen Feline"))[0]
_rsv.resolve(s, T, V1, spec, 1, [], -1, False, source=ff)
s.priority = 1
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
s.priority = 0
s.add_permanent(P3, 1, base_loc(1))
if any(a.kind == A.A_PLAY for a in A.legal_actions(s, T, V1, 0)):
    die("fallen feline", "the named spell can't be played while she is at a battlefield")
ok("Fallen Feline locks a named spell")

# ---------------------------------------------------------------------------
print("\n[batch 46] becoming a copy")
s = fresh()
big = s.add_permanent(DRAKE, 1, base_loc(1))
_rsv.resolve(s, T, V1, _SPECS["Mirror Image"], 0, [big], -1, True)
tok = int(s.last_token)
if combat.might(s, T, tok) != int(T.might[DRAKE]) or not combat.perm_kw(s, T, tok, "Temporary") \
        or int(s.perms[tok, P_CTRL]) != 0 or not T.is_token(int(s.perms[tok, P_CARD])):
    die("mirror image", "a 10-Might Temporary token copy of the Drake")
ok("Mirror Image copies a unit onto a Temporary Reflection")

s = fresh()
km = s.add_permanent(T.id_of("Keeper of Masks"), 0, bf_loc(0))
s.bf_ctrl[0] = 0
spec = abilities_for(T, T.id_of("Keeper of Masks"))[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=km)
t0 = int(s.last_token)
if int(s.last_token_n) != 2 or any(
        s.eff_card(r) != T.id_of("Keeper of Masks") or int(s.perms[r, P_LOC]) != bf_loc(0)
        for r in (t0, t0 + 1)):
    die("keeper of masks", "two Reflections here, copies of her")
ok("Keeper of Masks makes two copies of herself")

s = fresh()
host = s.add_permanent(P3, 0, base_loc(0))
model = s.add_permanent(DRAKE, 0, base_loc(0))
sp = s.add_permanent(T.id_of("Shady Spectacles"), 0, base_loc(0))
spec = abilities_for(T, T.id_of("Shady Spectacles"))[0]
_rsv.resolve(s, T, V1, spec, 0, [host], -1, False, source=sp)
if s.pend_name != 0:
    die("shady spectacles", "choose the unit to copy")
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if combat.might(s, T, host) != int(T.might[DRAKE]):
    die("shady spectacles", "the host becomes the Drake")
s.detach(sp)
if combat.might(s, T, host) != 3:
    die("shady spectacles", "only while attached")
ok("Shady Spectacles makes its unit a copy while attached")

s = fresh()
lec = s.add_permanent(T.id_of("Lecturing Yordle"), 0, base_loc(0))
sv = s.add_permanent(T.id_of("Svellsongur"), 0, base_loc(0))
s.attach(sv, lec)
from rl.engine.effects import row_abilities as _ra46
n_play = sum(1 for ab in _ra46(s, T, lec) if ab.trigger == TR_PLAY_ME)
if n_play != 2 or combat.perm_kw(s, T, lec, "Tank") != 2:
    die("svellsongur", f"the unit's text counted twice: {n_play} play triggers")
ok("Svellsongur copies its unit's text onto itself")

s = fresh(runes=0)
s.runes_ready[0, 2] = 2
u = s.add_permanent(P3, 0, base_loc(0), ready=False)
_rsv.resolve(s, T, V1, _SPECS["Dominus"], 0, [u], -1, True, card=T.id_of("Dominus"))
if combat.might(s, T, u) != 6:
    die("dominus", "double Might")
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
if not acts:
    die("dominus", "the granted '{A}{A}: Ready me' is usable")
A.apply(s, T, V1, acts[0])
drain(s, V1)
if not int(s.perms[u, _PR23]) or int(s.runes_in_play(0).sum()) != 0:
    die("dominus", "two runes paid, the unit readies")
s.ply += 1
if any(a.kind == A.A_ACTIVATE for a in A.legal_actions(s, T, V1, 0)):
    die("dominus", "only this turn")
ok("Dominus doubles a unit's Might and lets it ready itself this turn")

DG = T.id_of("Dancing Grenade")
s = fresh(hand=[DG])
theirs = s.add_permanent(DRAKE, 1, base_loc(1))
mine = s.add_permanent(DRAKE, 0, base_loc(0))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_TARGET, theirs))
for _ in range(10):
    if s.pend_ask >= 0:
        break
    A.apply(s, T, V1, A.Action(A.A_PASS))
if s.pend_ask != 1 or int(s.perms[theirs, P_DMG]) != 2:
    die("dancing grenade", "2 damage, then its controller is asked")
A.apply(s, T, V1, A.Action(A.A_ACCEPT))
opts = [a for a in A.legal_actions(s, T, V1, 1) if a.kind == A.A_TARGET]
A.apply(s, T, V1, next(a for a in opts if a.arg == mine))
for _ in range(10):
    if s.pend_ask >= 0 or s.n_chain == 0:
        break
    A.apply(s, T, V1, A.Action(A.A_PASS))
if int(s.perms[mine, P_DMG]) != 3:
    die("dancing grenade", f"the replay deals 2 + 1 bonus: {int(s.perms[mine, P_DMG])}")
ok("Dancing Grenade bounces back with growing damage")

s = fresh()
ak = s.add_permanent(T.id_of("Akshan - Mischievous"), 0, base_loc(0))
s.perms[ak, _PF] |= _FPA
blade = s.add_permanent(T.id_of("Long Sword"), 1, base_loc(1))
spec = abilities_for(T, T.id_of("Akshan - Mischievous"))[0]
_rsv.resolve(s, T, V1, spec, 0, [blade], -1, False, source=ak)
if int(s.perms[blade, P_CTRL]) != 0 or int(s.perms[blade, _PAT]) != ak:
    die("akshan", "steals the Equipment and wears it")
combat.destroy(s, T, ak)
if int(s.perms[blade, P_CTRL]) != 1 or int(s.perms[blade, P_LOC]) != base_loc(1):
    die("akshan", "it goes home when he leaves")
ok("Akshan - Mischievous borrows an enemy gear until he leaves")

CC = T.id_of("Curtain Call")
s = fresh(hand=[CC], runes=0)
s.runes_ready[0, 3] = 4
s.runes_ready[0, 4] = 4
a_bf = s.add_permanent(DRAKE, 1, bf_loc(0))
a_base = s.add_permanent(P3, 1, base_loc(1))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
modes = [a.arg for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_TARGET]
if 34 not in modes:
    die("curtain call", "all four, with every Repeat paid, is choosable")
A.apply(s, T, V1, A.Action(A.A_TARGET, 34))
for tgt in (a_bf, a_base, a_bf):
    A.apply(s, T, V1, A.Action(A.A_TARGET, tgt))
h0 = int(s.n_hand[0])
drain(s, V1)
if int(s.n_hand[0]) != h0 + 1 or int(s.perms[a_bf, P_DMG]) != 2 \
        or s.perms[a_base, P_ALIVE] or combat.might(s, T, a_bf) != int(T.might[DRAKE]) - 4:
    die("curtain call", "draw, 2 there, 3 at base, -4 there")
if int(s.runes_ready[0].sum()) + 0 > 8 - (4 + 2):
    die("curtain call", "paid its cost and all three Repeats")
ok("Curtain Call runs each mode once, paying a Repeat per extra mode")

s = fresh(hand=[T.id_of("Long Sword")])
s.add_permanent(T.id_of("Jax - Unmatched"), 0, base_loc(0))
u = s.add_permanent(P3, 0, base_loc(0))
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
for _ in range(10):
    legal = A.legal_actions(s, T, V1, A.acting_seat(s))
    tg = [a for a in legal if a.kind == A.A_TARGET and a.arg == u]
    if tg:
        A.apply(s, T, V1, tg[0])
        continue
    if s.n_chain == 0 and s.n_trig == 0:
        break
    A.apply(s, T, V1, next(a for a in legal if a.kind in (A.A_PASS, A.A_ORDER)))
sw = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == T.id_of("Long Sword"))
if int(s.perms[sw, _PAT]) != u:
    die("jax", "an Equipment played with Jax out attaches on play")
ok("Jax - Unmatched gives Equipment [Quick-Draw]'s attach")

s = fresh()
s.add_permanent(T.id_of("Rek'Sai - Breacher"), 0, base_loc(0))
s.deck[1, 0] = P3
_rsv.resolve(s, T, V1, _SPECS["Blind Fury"], 0, [], -1, True)
fast = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_PLAY_AT_FAST]
if not fast:
    die("rek'sai breacher", "a unit played from outside the hand may Accelerate")
A.apply(s, T, V1, fast[0])
u = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == P3)
if not int(s.perms[u, _PR23]):
    die("rek'sai breacher", "it enters ready")
ok("Rek'Sai - Breacher lets non-hand unit plays Accelerate")

s = fresh(runes=0)
s.runes_ready[0, 4] = 4                           # Mind
zd = s.add_permanent(T.id_of("The Zero Drive"), 0, base_loc(0), ready=True)
host = s.add_permanent(DRAKE, 0, base_loc(0))
s.attach(zd, host)
combat.destroy(s, T, host)
_settle(s)
if int(s.n_zero[0]) != 1 or DRAKE not in [int(c) for c in s.banished[0, :s.n_banished[0]]]:
    die("zero drive", "its unit is banished with it on death")
acts = [a for a in A.legal_actions(s, T, V1, 0) if a.kind == A.A_ACTIVATE]
A.apply(s, T, V1, next(a for a in acts if A.unpack_activate(a.arg)[2] == 0))
drain(s, V1)
if not any(s.perms[i, P_ALIVE] and int(s.perms[i, P_CARD]) == DRAKE for i in range(s.n_perms)) \
        or s.perms[zd, P_ALIVE]:
    die("zero drive", "the Drake returns free and the Drive is banished")
ok("The Zero Drive banishes its dead unit and later plays it back")

s = fresh()
s.add_permanent(T.id_of("Void Hatchling"), 0, base_loc(0))
s.deck[0, :6] = [DRAKE, HID, HID, P3, P3, P3]
tm = s.add_permanent(T.id_of("Teemo - Strategist"), 0, base_loc(0))
foe = s.add_permanent(DRAKE, 1, base_loc(0))
spec = abilities_for(T, T.id_of("Teemo - Strategist"))[0]
_rsv.resolve(s, T, V1, spec, 0, [foe], -1, False, source=tm,
             card=T.id_of("Teemo - Strategist"))
if s.pend_look != 0 or int(s.look_cards[0]) != DRAKE or int(s.perms[foe, P_DMG]):
    die("void hatchling", "a peek at the top card before the reveal")
A.apply(s, T, V1, A.Action(A.A_PICK, 0))          # recycle the Drake
if int(s.perms[foe, P_DMG]) != 2:
    die("void hatchling", f"then the reveal of the next five: {int(s.perms[foe, P_DMG])}")
ok("Void Hatchling peeks and may recycle before a reveal")

s = fresh()
s.deck[0, :5] = [P3, VENG, VENG, VENG, VENG]
s.deck[1, :5] = [PLAIN2, VENG, VENG, VENG, VENG]
_rsv.resolve(s, T, V1, _SPECS["Promising Future"], 0, [], -1, True)
if s.pend_look != 0:
    die("promising future", "the caster looks first")
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if s.pend_look != 1:
    die("promising future", "then the opponent")
A.apply(s, T, V1, A.Action(A.A_PICK, 0))
if s.rp_seat != 1:
    die("promising future", "the NEXT player plays first")
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(1)))
if s.rp_seat != 0:
    die("promising future", "then the caster")
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
if not (any(s.perms[i, P_ALIVE] and int(s.perms[i, P_CARD]) == PLAIN2 and int(s.perms[i, P_CTRL]) == 1
            for i in range(s.n_perms))
        and any(s.perms[i, P_ALIVE] and int(s.perms[i, P_CARD]) == P3 and int(s.perms[i, P_CTRL]) == 0
                for i in range(s.n_perms))) or s.pf_stage:
    die("promising future", "both units played by their owners")
ok("Promising Future has each player dig and play a card")

s = fresh(hand=[P3, P3, VENG], runes=1)
us = [s.add_permanent(P3, 0, base_loc(0)) for _ in range(3)]
theirs = s.add_permanent(P3, 1, base_loc(1))
_rsv.resolve(s, T, V1, _SPECS["Divine Judgment"], 0, [], -1, True)
seen_cats = []
for _ in range(40):
    if s.dj_seat < 0:
        break
    seen_cats.append((int(s.dj_seat), int(s.dj_cat)))
    legal = A.legal_actions(s, T, V1, int(s.dj_seat))
    A.apply(s, T, V1, legal[0])
alive_mine = sum(1 for u in us if s.perms[u, P_ALIVE])
if alive_mine != 2 or not s.perms[theirs, P_ALIVE] or int(s.n_hand[0]) != 2 \
        or int(s.runes_in_play(0).sum()) != 2:
    die("divine judgment", f"keep 2 of each: units {alive_mine}, hand {int(s.n_hand[0])}")
ok("Divine Judgment keeps two of each and recycles the rest")

s = fresh(hand=[P3, VENG])
s.trash[0, :2] = [P3, P3]
s.n_trash[0] = 2
er = s.add_permanent(T.id_of("Endless Riches"), 0, base_loc(0))
spec = abilities_for(T, T.id_of("Endless Riches"))[0]
_rsv.resolve(s, T, V1, spec, 0, [], -1, False, source=er)
if int(s.n_hand[0]) or int(s.n_banished[0]) != 4 or int(s.n_trash[0]) != 7:
    die("endless riches", "hand and trash banished, then Burn 7 into the trash")
idx = chain_mod.flow_playable(s, T, V1, 0)
if not idx:
    die("endless riches", "cards in the trash are playable")
u = s.add_permanent(P3, 0, base_loc(0))
combat.destroy(s, T, u)
if int(s.n_trash[0]) != 7 or int(s.n_banished[0]) != 5:
    die("endless riches", "a dying unit is banished instead of trashed")
ok("Endless Riches banishes, burns, and plays from the trash")

BARON = T.id_of("Baron Nashor")
s = fresh(hand=[BARON, BARON])
s.runes_ready[0, :] = 6
ally = s.add_permanent(P3, 0, base_loc(0))
if s.bf_present(2) or bf_loc(2) in combat.move_destinations(s, T, V1):
    die("baron nashor", "no Baron Pit until he is played")
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
bn = next(i for i in range(s.n_perms) if int(s.perms[i, P_CARD]) == BARON)
if not s.bf_present(2) or T.names[int(s.bf_card[2])] != "Baron Pit" \
        or int(s.perms[bn, P_LOC]) != bf_loc(2):
    die("baron nashor", "the Pit is added and he enters there instead")
if combat.might(s, T, ally) != 5 or bn in _rsv.legal_targets(
        s, T, _SPECS["Vengeance"], 0, 1, [], -1):
    die("baron nashor", "+2 to other friendly units, unchoosable by enemies")
_settle(s)
if int(s.bf_ctrl[2]) != 0:
    die("baron nashor", f"he takes the empty Pit: ctrl {int(s.bf_ctrl[2])}")
# "Units can move here from anywhere" -- a unit at another battlefield, no Ganking.
walker = s.add_permanent(P3, 0, bf_loc(0), ready=True)
from rl.engine.combat import can_move as _cm47
if not _cm47(s, T, V1, walker, bf_loc(2)) or _cm47(s, T, V1, walker, bf_loc(1)):
    die("baron pit", "lateral moves INTO the Pit need no Ganking; elsewhere they do")
# A second Baron: the Pit is already there, so he enters where he was played.
s2n = int(s.n_perms)
s.phase, s.active, s.priority = 3, 0, 0
from rl.engine.state import MAIN as _MAIN47
s.phase = _MAIN47
A.apply(s, T, V1, A.Action(A.A_PLAY, 0))
A.apply(s, T, V1, A.Action(A.A_PLAY_AT, base_loc(0)))
bn2 = next(i for i in range(s2n, s.n_perms) if int(s.perms[i, P_CARD]) == BARON)
if int(s.perms[bn2, P_LOC]) != base_loc(0):
    die("baron nashor", "no new Pit, no redirect")
combat.destroy(s, T, bn)
combat.destroy(s, T, bn2)
if combat.might(s, T, ally) != 3 or not s.bf_present(2):
    die("baron nashor", "his +2 ends with him; the Pit token stays")
ok("Baron Nashor adds the Baron Pit, enters it, and buffs allies while alive")
