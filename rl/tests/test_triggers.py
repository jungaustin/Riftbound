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
# An A_ACTIVATE used to be identified by its permanent alone, because
# `_activate` takes the FIRST activated ability and no card has two.
# Heimerdinger holds many, so the arg carries a packed (permanent, donor).

HEIMER = T.id_of("Heimerdinger - Inventor")
DARK_ICE = T.id_of("Heart of Dark Ice")      # Exhaust: give a unit +3 Might
HEIM_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit")
                 and not T.is_token(c) and int(T.might[c]) >= 3)

for _perm, _donor in ((0, 0), (5, 5), (3, 7), (47, 0), (0, 47)):
    if A.unpack_activate(A.pack_activate(_perm, _donor)) != (_perm, _donor):
        die("heimer", f"the packed activate arg must round-trip "
                      f"({_perm}, {_donor})")
ok("a packed (permanent, donor) activate arg round-trips")

s = GameState()
s.phase, s.active, s.priority = MAIN, 0, 0
h = s.add_permanent(HEIMER, 0, bf_loc(0))
d = s.add_permanent(DARK_ICE, 0, base_loc(0))
u = s.add_permanent(HEIM_BODY, 0, bf_loc(0))
before = _combat.might(s, T, u)

borrowed = [a for a in A.legal_actions(s, T, V1, 0)
            if a.kind == A.A_ACTIVATE and A.unpack_activate(a.arg) == (h, d)]
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
W_BODY = next(c for c in range(T.n) if T.is_type(c, "Unit") and not T.is_token(c))


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

s.turn = 2
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
    rsv_mod.resolve(s, T, V1, ABILITIES["Shen, Scourge of Shadows"][0], 0, [],
                    -1, True, source=h)
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
_, _, _fwd, _ = matchup(_A, _B)
_, _, _rev, _ = matchup(_B, _A)
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
_, _, _borrowed, _ = matchup(_EMPTY, _B)
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
