"""Gym tests -- PLAN.md Phase 3 exit criteria plus the encoder's three claims.

Run from anywhere: python3 rl/tests/test_env.py [n_games]

  [1] **Equivalence.** The stated Phase 3 exit: a random policy driving the env
      reproduces Phase 2's random agent driving the engine directly, hash for
      hash. This is the test that catches wrapper bugs, and it catches nearly
      all of them at once.
  [2] **Auto-pass is a no-op**, and its guard is strict. v0 never reaches a
      pass-only window, so the rule is tested directly as a predicate.
  [3] **Canonicalization.** encode(s, 0) == encode(mirror(s), 1), byte for byte.
  [4] **No leak.** Rewriting the opponent's hidden information must not move a
      single bit of the policy's observation -- with a negative control, so the
      test cannot pass by encoding nothing.
  [5] **Mask hygiene**, and the A_max cap from §5.3 gotcha 4.
  [6] **The vector env is the same env**, batched and auto-resetting.
"""
import sys
from collections import Counter

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

import numpy as np

from rl.agents.greedy import greedy_agent
from rl.config import Config
from rl.engine import actions as A
from rl.engine import game
from rl.engine.cardtable import full_table
from rl.engine.effects import BF_STATICS
from rl.engine.mirror import mirror
from rl.engine.state import N_BF, fd_slots
from rl.env import RiftboundEnv, play, random_policy, should_auto_pass
from rl.obs import Encoder
from rl.vec import VecRiftbound
from rl.tests.fuzz import make_game, v0_pool

T = full_table()
CFG = Config().at_victory_score(3)


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


def deal(seed):
    """The same deal `fuzz.make_game` builds, but as arguments to `reset`."""
    rng = np.random.default_rng(seed)
    pool = v0_pool(T)
    decks = [[int(rng.choice(pool)) for _ in range(30)] for _ in range(2)]
    runes = [[int(rng.integers(6)) for _ in range(12)] for _ in range(2)]
    bfs = [c for c in range(T.n) if T.is_type(c, "Battlefield")][:2]
    return decks, runes, bfs


def run_env(seed, auto_pass, policy_seed=None, check=False):
    env = RiftboundEnv(T, CFG, auto_pass=auto_pass, check=check)
    rng = np.random.default_rng(seed if policy_seed is None else policy_seed)
    pol = random_policy(rng)
    return env, play(env, [pol, pol], seed, *deal(seed))


# ---------------------------------------------------------------------------
N = int(sys.argv[1]) if len(sys.argv) > 1 else 200

print(f"\n[1] env == engine  ({N} seeds, auto_pass off)")
enc = Encoder(T, CFG)
print(f"    shapes: {enc.shapes()}")
for seed in range(N):
    # Engine path: exactly what Phase 2's fuzz runs.
    rng = np.random.default_rng(seed)
    direct = game.play_game(T, CFG, make_game(T, CFG, seed),
                            [game.random_agent(rng)] * 2)
    # Env path: same deal, same seed, same uniform draw per decision.
    _, viaenv = run_env(seed, auto_pass=False)
    for k in ("winner", "truncated", "turns", "steps", "points", "hash"):
        if direct[k] != viaenv[k]:
            die("equivalence",
                f"seed {seed}: {k} {direct[k]!r} via engine, {viaenv[k]!r} "
                f"via env\n    engine={direct}\n    env   ={viaenv}")
ok(f"{N} games identical through the wrapper, including state hash")

# The reward vector is per seat, and the winner is the one holding +1.
for seed in range(20):
    _, r = run_env(seed, auto_pass=False)
    w, rw = r["winner"], r["rewards"]
    if w < 0:
        assert rw == (0.0, 0.0), f"seed {seed}: truncated game paid {rw}"
    elif rw[w] != 1.0 or rw[1 - w] != -1.0:
        die("reward attribution", f"seed {seed}: winner {w} got {rw}")
ok("rewards are indexed by seat and sum to zero")


# ---------------------------------------------------------------------------
print("\n[2] auto-pass is a no-op, and its guard holds")
def greedy_run(seed, auto_pass):
    env = RiftboundEnv(T, CFG, auto_pass=auto_pass)
    agent = greedy_agent(np.random.default_rng(seed))   # deterministic
    obs = env.reset(seed, *deal(seed))
    while obs is not None:
        act = agent(env.state, T, CFG, env.to_move, env.legal)
        obs = env.step(env.legal.index(act)).obs
    return env, env.summary()

collapsed = 0
saved = 0
for seed in range(60):
    e_on, r_on = greedy_run(seed, True)
    e_off, r_off = greedy_run(seed, False)
    # **`steps` is deliberately NOT compared.** Collapsing a pass-only window is
    # the whole job of the flag, so it costs the policy one decision fewer --
    # what has to be identical is the GAME, and `hash` digests every slot of it.
    for k in ("winner", "turns", "points", "hash"):
        if r_on[k] != r_off[k]:
            die("auto-pass", f"seed {seed}: {k} differs, {r_on[k]} vs {r_off[k]}")
    collapsed += e_on.auto_passes
    saved += r_off["steps"] - r_on["steps"]
ok(f"60 greedy games identical with the flag on and off (hash, winner, turns, "
   f"points), while the flag saved {saved} decisions")

# **This assertion inverted on 2026-09-27, and the old one is why.** It used to
# insist `collapsed == 0`, because `run_combat` resolved Combat without ever
# yielding priority, so v0 had no pass-only window and the number above was
# measuring nothing -- with a comment saying the day combat started yielding,
# this line should fail and force the flag to be re-measured rather than
# re-assumed. 466.6 is that day: ending a Combat now suspends at SD_CONQUER
# while the Conquer triggers resolve, and that is a real priority window even in
# v0, where nobody can act in it. So it is measured, and the number is asserted
# from the low side rather than pinned: 48 windows over these 60 games.
if collapsed < 20:
    die("auto-pass", f"only {collapsed} windows collapsed; 466.6's conquer "
                     f"window should give roughly one per conquer -- if combat "
                     f"stopped yielding, re-measure rather than lowering this")
ok(f"{collapsed} pass-only windows collapsed across the 60 games, and the game "
   f"came out identical every time -- so the flag is a no-op on PLAY, not on cost")

# So test the rule itself, which is the part that will matter.
FAKE = A.Action(A.A_PLAY, 0)
assert should_auto_pass([A.PASS]), "a lone pass is a no-op and must collapse"
assert not should_auto_pass([A.PASS, FAKE]), \
    "a window with a playable Reaction must NEVER be auto-passed (gotcha 3)"
assert not should_auto_pass([FAKE]), "only pass collapses, not any forced action"
assert not should_auto_pass([]), "an empty list is a deadlock, not a pass"
ok("the guard collapses only a literal [pass]")


# ---------------------------------------------------------------------------
print("\n[3] canonicalization: a mirrored position encodes identically")
def midgame(seed, plies):
    """Play `plies` random decisions, then stop at the next seat-0 decision.

    Stopping *at* seat 0 rather than discarding positions where seat 1 happens
    to be on move matters: seat 1's turns are where the asymmetries live (the
    going-second rune, the second-mover board), and sampling only seat-0-to-move
    positions after a fixed ply count would quietly correlate with turn parity.
    """
    env = RiftboundEnv(T, CFG, auto_pass=False)
    rng = np.random.default_rng(seed + 9000)
    obs = env.reset(seed, *deal(seed))
    for _ in range(plies + 200):
        if obs is None:
            return None
        if plies <= 0 and obs.to_move == 0:
            return env.state
        plies -= 1
        obs = env.step(int(rng.integers(obs.n_legal))).obs
    return None

checked = 0
for seed in range(300):
    s = midgame(seed, 2 + seed % 11)
    if s is None:
        continue
    m = mirror(s)
    if A.acting_seat(m) != 1:
        die("mirror", f"seed {seed}: mirrored acting seat is {A.acting_seat(m)}")
    a = enc.encode(s, 0, A.legal_actions(s, T, CFG, 0))
    b = enc.encode(m, 1, A.legal_actions(m, T, CFG, 1))
    if a.public_bytes() != b.public_bytes():
        for k in sorted(a.zones):
            if not np.array_equal(a.zones[k], b.zones[k]):
                d = np.argwhere(a.zones[k] != b.zones[k])
                die("mirror", f"seed {seed}: zone {k!r} differs at {d[:4].tolist()}")
        if not np.array_equal(a.globals, b.globals):
            d = np.flatnonzero(a.globals != b.globals)
            die("mirror", f"seed {seed}: globals differ at {d.tolist()}")
        die("mirror", f"seed {seed}: action features differ")
    checked += 1
if checked < 100:
    die("mirror", f"only {checked} positions checked; the sampler is broken")
ok(f"{checked} mid-game positions encode byte-identically under a seat swap")


# ---------------------------------------------------------------------------
print("\n[4] the policy cannot see hidden information")
s = None
for seed in range(300):
    s = midgame(seed, 3 + seed % 9)
    if s is not None and s.n_hand[1] >= 2 and s.n_deck[1] - s.deck_ptr[1] >= 2:
        break
assert s is not None, "no suitable position found"

# Give both seats a facedown card so the 107.3.f path is actually exercised;
# v0 has no [Hidden] plays yet, so it has to be staged by hand.
pool = v0_pool(T)
# `fd_*` is indexed by SLOT now (two per battlefield, since Bandle Tree), so
# battlefield 1's first slot is `_FD1`, not 1.
_FD0, _FD1 = list(fd_slots(0))[0], list(fd_slots(1))[0]
s.bf_ctrl[0], s.fd_owner[_FD0], s.fd_card[_FD0] = 0, 0, pool[0]
s.bf_ctrl[1], s.fd_owner[_FD1], s.fd_card[_FD1] = 1, 1, pool[1]

base = enc.encode(s, 0, A.legal_actions(s, T, CFG, 0))

hidden = s.clone()
foe_n = int(hidden.n_hand[1])
hidden.hand[1, :foe_n] = [pool[(i + 3) % len(pool)] for i in range(foe_n)]
lo, hi = int(hidden.deck_ptr[1]), int(hidden.n_deck[1])
hidden.deck[1, lo:hi] = hidden.deck[1, lo:hi][::-1]
hidden.fd_card[_FD1] = pool[7]                       # THEIR facedown card
after = enc.encode(hidden, 0, A.legal_actions(hidden, T, CFG, 0))

if base.public_bytes() != after.public_bytes():
    die("leak", "rewriting the opponent's hand, deck order or facedown card "
                "changed the policy observation")
ok("opponent hand contents, deck order and facedown identity are all invisible")

# ...except when a card says otherwise. Sabotage's "They reveal their hand" is
# the ONE way the opponent's hand reaches the policy observation, and it does
# so through the A_PICK action rows -- naming the card is the whole point of
# the effect. Asserted rather than left to pass by accident: the rule is "never
# visible unless a card revealed it", and a test that only checks the first
# half would go on passing if the second half broke.
rev = s.clone()
rev.n_hand[1] = 2
rev.hand[1, 0], rev.hand[1, 1] = pool[0], pool[1]
rev.pend_reveal[:] = (0, 1)
rev.look_type_mask = 0
a = enc.encode(rev, 0, A.legal_actions(rev, T, CFG, 0))
rev2 = rev.clone()
rev2.hand[1, 0], rev2.hand[1, 1] = pool[2], pool[3]
b = enc.encode(rev2, 0, A.legal_actions(rev2, T, CFG, 0))
if a.public_bytes() == b.public_bytes():
    die("leak", "a REVEALED hand must reach the chooser's observation -- "
                "otherwise Sabotage's choice carries no information")
ok("...and a revealed hand does reach the chooser, which is the card working")

# The revealer still cannot see anything new, and cannot act.
if A.legal_actions(rev, T, CFG, 1):
    die("leak", "only the chooser acts on a reveal")
ok("...while the revealing player has no say in what is taken")

if np.array_equal(base.privileged, after.privileged):
    die("leak", "the privileged vector did not change either -- the "
                "perturbation was a no-op and test [4] proves nothing")
ok("the same perturbation does move the critic's privileged vector")

# Scuttle Crab is the other way information can reach the policy, and it is a
# different shape from Sabotage's: a STANDING permission rather than a choice.
# Nothing is picked and nothing moves -- the entire card is that these two
# holes in the observation are filled for a turn. So the test is exactly the
# leak test above, run again with the permission granted, and it has to flip
# from invisible to visible or the card does nothing at all.
grant = s.clone()
grant.saw_hand[0] = int(grant.ply)      # a player TURN, not a round
g_base = enc.encode(grant, 0, A.legal_actions(grant, T, CFG, 0)).public_bytes()
g_hand = grant.clone()
g_hand.hand[1, :int(g_hand.n_hand[1])] = [
    pool[(i + 3) % len(pool)] for i in range(int(g_hand.n_hand[1]))]
if g_base == enc.encode(g_hand, 0,
                        A.legal_actions(g_hand, T, CFG, 0)).public_bytes():
    die("leak", "'they reveal their hand' must put the opponent's hand into "
                "the observation -- otherwise Scuttle Crab is a blank card")
ok("a standing hand-reveal permission makes the opponent's hand visible")

grant_fd = s.clone()
grant_fd.saw_fd[0] = int(grant_fd.ply)
f_base = enc.encode(grant_fd, 0,
                    A.legal_actions(grant_fd, T, CFG, 0)).public_bytes()
f_moved = grant_fd.clone()
f_moved.fd_card[_FD1] = pool[7]
if f_base == enc.encode(f_moved, 0,
                        A.legal_actions(f_moved, T, CFG, 0)).public_bytes():
    die("leak", "'look at their facedown cards this turn' must fill in the "
                "facedown identity 107.3.f otherwise hides")
ok("...and a facedown permission fills in the identity, not just the slot")

# The stamp is a TURN, so it lapses on its own rather than needing a reset.
stale = s.clone()
stale.saw_hand[0] = int(stale.ply) - 1
stale.saw_fd[0] = int(stale.ply) - 1
st_base = enc.encode(stale, 0, A.legal_actions(stale, T, CFG, 0)).public_bytes()
st_moved = stale.clone()
st_moved.hand[1, :int(st_moved.n_hand[1])] = [
    pool[(i + 3) % len(pool)] for i in range(int(st_moved.n_hand[1]))]
st_moved.fd_card[_FD1] = pool[7]
if st_base != enc.encode(st_moved, 0,
                         A.legal_actions(st_moved, T, CFG, 0)).public_bytes():
    die("leak", "a permission stamped for a PREVIOUS turn must not still see")
ok("...and both lapse by turn stamp, with nothing having to clear them")

# The permission belongs to one seat. Seat 0 holding it must not hand seat 1
# a window into seat 0's own hand -- the reveal is one-directional.
oneway = s.clone()
oneway.saw_hand[0] = int(oneway.ply)
oneway.saw_fd[0] = int(oneway.ply)
o_base = enc.encode(oneway, 1, A.legal_actions(oneway, T, CFG, 1)).public_bytes()
o_moved = oneway.clone()
o_moved.hand[0, :int(o_moved.n_hand[0])] = [
    pool[(i + 5) % len(pool)] for i in range(int(o_moved.n_hand[0]))]
o_moved.fd_card[_FD0] = pool[9]
if o_base != enc.encode(o_moved, 1,
                        A.legal_actions(o_moved, T, CFG, 1)).public_bytes():
    die("leak", "the permission is one seat's -- it must not reveal the "
                "GRANTING seat's own hand to the other player")
ok("...and it is one-directional: only the seat that earned it may look")

# **A_PICK's arg means something different at each of its three offer sites**,
# and the encoder has to make the same choice `legal_actions` did. It did not:
# it knew the look buffer and Sabotage's reveal but not Hwei's discard, so a
# hand index was read into a five-card look buffer -- an IndexError when the
# hand is longer, a silently wrong card when it is shorter. The fuzz cannot
# see either, because it never builds an observation; the first training run
# after Hwei landed died on it in 45 seconds.
pick_pool = [c for c in range(T.n) if T.is_type(c, "Unit")
             and not T.is_token(c)][:10]


def pick_state(**kw):
    st = s.clone()
    st.pend_look, st.pend_discard = -1, -1
    st.pend_reveal[:] = (-1, -1)
    st.n_look, st.look_type_mask = 0, 0
    for k, v in kw.items():
        setattr(st, k, v)
    return st


# Hwei: eight cards in hand, nothing in the look buffer.
disc = pick_state(pend_discard=0)
disc.n_hand[0] = 8
disc.hand[0, :8] = pick_pool[:8]
acts = A.legal_actions(disc, T, CFG, 0)
if len(acts) != 8:
    die("pick", f"a discard choice offers one action per card, got {len(acts)}")
enc.encode(disc, 0, acts)          # raised IndexError before the fix
if A.pick_card(disc, 7) != pick_pool[7]:
    die("pick", "a discard arg indexes the DISCARDING seat's own hand")
ok("A_PICK from a discard names the right card, and encodes without crashing")

rev = pick_state()
rev.pend_reveal[:] = (0, 1)
rev.n_hand[1] = 3
rev.hand[1, :3] = pick_pool[3:6]
if A.pick_card(rev, 2) != pick_pool[5]:
    die("pick", "a reveal arg indexes the OPPONENT's hand")
look = pick_state(pend_look=0, n_look=3)
look.look_cards[:3] = pick_pool[6:9]
if A.pick_card(look, 2) != pick_pool[8]:
    die("pick", "a look arg indexes the look BUFFER")
ok("...and the other two sites still index the hand they name, not each other")

# Negative control: MY facedown card is mine to see, so changing it must show.
seen = s.clone()
seen.fd_card[_FD0] = pool[9]
if base.public_bytes() == enc.encode(
        seen, 0, A.legal_actions(seen, T, CFG, 0)).public_bytes():
    die("leak", "changing the seat's OWN facedown card was invisible too, so "
                "the encoder is simply dropping the facedown zone")
ok("negative control: the seat's own facedown card is visible to it")


# ---------------------------------------------------------------------------
print("\n[4b] a card's BEHAVIOUR reaches the observation, not just its body")
# The failure this pins: the card feature matrix described stat lines, types,
# domains and keywords -- the card's BODY -- and nothing about what its rules
# text DOES. Battlefields have no stat line at all, so all 66 encoded
# identically and the policy could not tell which one it was playing on.
# Swapping one for another moved zero bits, which is the assertion below.
scripted_bf = [c for c in range(T.n)
               if T.is_type(c, "Battlefield") and T.names[c] in BF_STATICS]
if len(scripted_bf) < 2:
    die("behaviour", "this test needs two battlefields with encoded statics; "
                     "it is meaningless once BF_STATICS shrinks below that")
bf_a = s.clone()
bf_a.bf_card[0] = scripted_bf[0]
bf_b = s.clone()
bf_b.bf_card[0] = scripted_bf[1]
enc_a = enc.encode(bf_a, 0, A.legal_actions(bf_a, T, CFG, 0)).public_bytes()
enc_b = enc.encode(bf_b, 0, A.legal_actions(bf_b, T, CFG, 0)).public_bytes()
if enc_a == enc_b:
    die("behaviour", f"{T.names[scripted_bf[0]]} and {T.names[scripted_bf[1]]} "
                     "encode identically, so the policy cannot tell two "
                     "battlefields apart -- Bo3 selection is unlearnable")
ok("two battlefields with different statics no longer encode identically")

# The honest other half. A battlefield nothing implements has no behaviour to
# show, so it SHOULD still alias -- the features derive from the encoded
# ability, and inventing a distinction the engine does not honour would be
# worse than none. This asserts the limit rather than hiding it.
# **Unscripted means neither table.** A battlefield with a TRIGGER and no
# static is scripted: `ability_features` reads it, so it is visible and must
# not be counted here -- this list was BF_STATICS-only and started failing the
# moment the ground's triggers were written.
from rl.engine.effects import BF_ABILITIES
plain_bf = [c for c in range(T.n)
            if T.is_type(c, "Battlefield") and T.names[c] not in BF_STATICS
            and T.names[c] not in BF_ABILITIES]
feats = T.features()
if len(plain_bf) >= 2 and not np.array_equal(feats[plain_bf[0]],
                                             feats[plain_bf[1]]):
    die("behaviour", "two UNSCRIPTED battlefields differ, which means "
                     "something other than encoded behaviour is leaking into "
                     "the features -- a card id by another name")
ok(f"...and the {len(plain_bf)} unscripted ones still alias, as they must")

# The features must not be a constant column block either: a bug that returned
# zeros for every card would pass the first assertion via the context block.
n_distinct = len(np.unique(feats, axis=0))
if n_distinct <= 642:
    die("behaviour", f"{n_distinct} distinct card rows -- the behaviour block "
                     "added nothing over the body-only 642")
ok(f"{n_distinct} distinct card feature rows, up from 642 body-only")


# ---------------------------------------------------------------------------
print("\n[4c] state the engine READS must reach the observation")
# Three holes found by auditing `GameState.__slots__` against the fields
# `obs.py` actually mentions, then measuring each one over 200 real-deck games.
# Every one of them was information the engine consulted every turn and the
# policy could not see at all.
from dataclasses import replace as _replace

from rl.engine import combat as _combat
from rl.engine.state import P_ALIVE as _P_ALIVE
from rl.obs import (CHAIN_SLOTS, CX_CHAIN_DEPTH, CX_MIGHT, CX_ZONE_CHAIN,
                    ZONES)
from rl.tests.fuzz import make_deck_game

_cfg = _replace(Config().at_victory_score(5), units_only=False)
_enc = Encoder(T, _cfg)
_cd = _enc.card_dim
_n_rows = _n_might = _n_chain = _n_chain_ok = _n_xp = _n_xp_ok = 0
_worst = 0.0
for _seed in range(40):
    _s2 = make_deck_game(T, _cfg, _seed)
    _rng = np.random.default_rng(_seed ^ 0x5eed)
    for _ in range(400):
        if A.is_terminal(_s2):
            break
        _seat = A.acting_seat(_s2)
        if _seat < 0:
            break
        _legal = A.legal_actions(_s2, T, _cfg, _seat)
        if not _legal:
            break
        if len(_legal) > 1:
            _o = _enc.encode(_s2, _seat, _legal)
            # (a) A unit's TRUE Might -- printed + this-turn + Buff + statics +
            # combat role. The card block carries only the printed value, which
            # was wrong on 8.5% of board rows by up to +7.
            _rows = [i for i in range(_s2.n_perms)
                     if _s2.perms[i, _P_ALIVE] == 1]
            for _k, _i in enumerate(_rows):
                _n_rows += 1
                _got = float(_o.zones["board"][_k][_cd + CX_MIGHT]) * 5.0
                _want = float(_combat.might(_s2, T, _i))
                _worst = max(_worst, abs(_got - _want))
                _n_might += abs(_got - _want) < 1e-4
            # (b) The Chain, top-first. Was a lone `n_chain / 4.0` scalar.
            _nc = int(_s2.n_chain)
            if _nc:
                _n_chain += 1
                _n_chain_ok += (
                    int(_o.zone_mask["chain"].sum()) == min(_nc, CHAIN_SLOTS)
                    and _o.zones["chain"][0][_cd + CX_ZONE_CHAIN] == 1.0)
            # (c) XP -- 17 `COND_LEVEL` sites gate on it; it was absent.
            if int(_s2.xp[_seat]) > 0:
                _n_xp += 1
                _n_xp_ok += abs(float(_o.globals[40]) * 3.0
                                - float(_s2.xp[_seat])) < 1e-4
        A.apply(_s2, T, _cfg, _legal[int(_rng.integers(len(_legal)))])

if _n_might != _n_rows:
    die("obs-state", f"{_n_rows - _n_might} of {_n_rows} board rows misstate "
                     f"Might (worst error {_worst * 5:.1f}); the policy cannot "
                     "tell whether a unit survives combat")
ok(f"{_n_rows} board rows carry TRUE Might, not printed Might")

if not _n_chain or _n_chain_ok != _n_chain:
    die("obs-state", f"the Chain is described on only {_n_chain_ok} of "
                     f"{_n_chain} states that have one -- the counterspell "
                     "decision is being made blind")
ok(f"{_n_chain} non-empty Chains encode their contents, nearest-first")

if not _n_xp or _n_xp_ok != _n_xp:
    die("obs-state", f"XP reached the globals on {_n_xp_ok} of {_n_xp} states")
ok(f"XP reaches the globals on all {_n_xp} states that have any")

# The structural half: a zone the encoder builds must be a zone the NETWORK
# pools over. `nets.py` kept its own hardcoded tuple and missed `legends` for
# every run after a8a7bf4 -- built, batched, and silently discarded.
if tuple(_enc.shapes()["zones"]) != ZONES:
    die("obs-state", "shapes() disagrees with obs.ZONES")
_missing = [z for z in ZONES if z not in _enc.encode(
    _s2, 0, A.legal_actions(_s2, T, _cfg, 0)).zones] if not A.is_terminal(_s2) else []
if _missing:
    die("obs-state", f"zones declared but never built: {_missing}")
ok(f"all {len(ZONES)} zones are declared in one place and reach the network")


# ---------------------------------------------------------------------------
print("\n[4d] the Champion Zone: the pre-game archetype signature (108.3)")
from rl.decks import load_all, matchup
from rl.obs import CX_MINE, CX_ZONE_CHAMP, CHAMP_SLOTS

_pool = load_all(T, latest_only=True)

# 103.2 registers the Chosen Champion inside the 40-card Main Deck; 133.4 starts
# it in the Champion Zone instead. So `main` being 39 is not a card short of a
# legal deck -- it is 40 minus the one that begins elsewhere. If this ever fails
# the corpus has drifted and every deck in training is illegal by a card.
_sizes = {len(d.main) + (1 if d.champion >= 0 else 0) for d in _pool}
if _sizes != {40}:
    die("champion", f"registered deck sizes are {_sizes}, not 40")
# 103.2.b -- and three copies is the cap ACROSS both zones, not per zone.
_over = [d.name for d in _pool
         if d.champion >= 0 and d.main.count(d.champion) + 1 > 3]
if _over:
    die("champion", f"4 copies once the Champion Zone is counted: {_over}")
ok(f"{len(_pool)} decklists are 39 + a Chosen Champion = 40, 3-copy limit intact")

# 103.2.a.2 -- the Chosen Champion must share a champion tag with the Champion
# Legend. That is what makes the pair an archetype rather than two cards: seeing
# the Legend narrows the champion, and seeing the champion names the build.
_bad = []
for d in _pool:
    if d.legend < 0 or d.champion < 0:
        continue
    if not (T.tags[d.legend] & T.tags[d.champion]):
        _bad.append((d.name, T.names[d.legend], T.names[d.champion]))
if _bad:
    die("champion", f"103.2.a.2 -- champion tag does not match the Legend: {_bad[:3]}")
ok("103.2.a.2 -- every list's champion shares a tag with its Legend")

_e = Encoder(T, CFG)
_d0, _d1 = _pool[0], _pool[1 % len(_pool)]
_st = game.new_game(T, CFG, *matchup(_d0, _d1)[:3], seed=7,
                    legends=[_d0.legend, _d1.legend],
                    champions=[_d0.champion, _d1.champion])
if [int(c) for c in _st.champion] != [_d0.champion, _d1.champion]:
    die("champion", "112 -- the Chosen Champion was not placed in the zone")

# 108.3.e -- Public Information, so BOTH seats see BOTH champions. This is the
# one deck fact that needs no `deck_known`: it is public in Bo1 game 1.
for _seat in range(2):
    _o = _e.encode(_st, _seat, A.legal_actions(_st, T, CFG, _seat))
    _m, _z = _o.zone_mask["champions"], _o.zones["champions"]
    if not _m.all():
        die("champion", f"seat {_seat} cannot see both champions: {_m}")
    # Canonical order, as every other zone: this seat's own row first.
    if not (_z[0][_e.card_dim + CX_MINE] == 1.0
            and _z[1][_e.card_dim + CX_MINE] == 0.0):
        die("champion", "CX_MINE is not canonical (own champion first)")
    if not all(r[_e.card_dim + CX_ZONE_CHAMP] == 1.0 for r in _z):
        die("champion", "the zone marker is unset, so rows alias the Legend Zone")
    # Different decks, different champions -- the signal has to be a signal.
    if _d0.champion != _d1.champion and np.array_equal(_z[0], _z[1]):
        die("champion", "two different champions encode identically")
ok("108.3.e -- both champions are public to both seats, own row first")

# NOT double-counted. `_decks` reports what can still be DRAWN; a champion that
# is already on the table must not also appear as a card left in the deck.
_o0 = _e.encode(_st, 0, A.legal_actions(_st, T, CFG, 0))
_reg = [int(c) for c in _st.decklist[0][:int(_st.n_decklist[0])]]
if len(_reg) != len(_d0.main):
    die("champion", "the registered deck absorbed the champion")
if _reg.count(_d0.champion) != _d0.main.count(_d0.champion):
    die("champion", "the Champion Zone copy leaked into the Main Deck Zone")
ok("133.4 -- the champion is in its zone, not counted among cards left to draw")

# A random pool is not a decklist, so it has no champion to separate out (112).
# The zone must then be empty rather than holding a fabricated card.
_sv = make_game(T, CFG, 3)
_ov = _e.encode(_sv, 0, A.legal_actions(_sv, T, CFG, 0))
if _ov.zone_mask["champions"].any() or _ov.zones["champions"].any():
    die("champion", "a dealer with no decklist still produced a champion row")
ok("a random-pool deal leaves the zone empty, not fabricated")


# ---------------------------------------------------------------------------
print("\n[4f] 108.3.d -- the Chosen Champion can be PLAYED from its zone")

# Before this, the champion sat in its zone all game and every deck in the pool
# was understated by one guaranteed threat -- the one card you always have.
# 108.3.d: "can be played from here as normal, following the rules of Playing a
# Card", so it flows through the ordinary unit-play path, cost and all.
from rl.engine.state import P_ALIVE, P_CARD, P_CTRL                # noqa: E402
from rl.engine import invariants as _inv                           # noqa: E402

# The cheapest champions the corpus registers cost 3 energy and no Power, so
# the fixture grants runes rather than relying on a turn count. Picked from the corpus rather than invented: the test then
# exercises a card some deck in `decks/` actually registers.
_cheap = None
for _d in _pool:
    if _d.champion < 0:
        continue
    if int(T.energy[_d.champion]) <= 3 and int(T.power[_d.champion]) == 0:
        _cheap = _d
        break
if _cheap is None:
    die("champion-play", "no corpus champion costs <= 3 energy; pick another fixture")

_sp = game.new_game(T, CFG, *matchup(_cheap, _cheap)[:3], seed=11,
                    legends=[_cheap.legend, _cheap.legend],
                    champions=[_cheap.champion, _cheap.champion])


def _past_mulligan(st):
    """117 -- the Mulligan is the game's first decision, so skip it to reach MAIN."""
    g = 0
    while int(st.pend_mull) >= 0:
        g += 1
        assert g < 8, "the mulligan did not terminate"
        A.apply(st, T, CFG, A.Action(A.A_MULLIGAN_DONE))
    return st


_past_mulligan(_sp)
_seat = int(_sp.active)
# Give the seat enough runes that affordability is not what is being tested.
_sp.runes_ready[_seat] = 4
_legal = A.legal_actions(_sp, T, CFG, _seat)
_champ_offers = [a for a in _legal
                 if a.kind == A.A_PLAY and a.arg == A.CHAMPION_SRC]
if len(_champ_offers) != 1:
    die("champion-play",
        f"expected exactly one Champion Zone play offer, got {len(_champ_offers)}")
# The sentinel must not collide with a real hand index.
if any(a.kind == A.A_PLAY and a.arg == A.CHAMPION_SRC
       for a in _legal if a is not _champ_offers[0]):
    die("champion-play", "CHAMPION_SRC collided with a hand index")
if A.played_card(_sp, _seat, A.CHAMPION_SRC) != _cheap.champion:
    die("champion-play", "the offer does not name the champion card")
ok(f"the champion is offered as a play ({T.names[_cheap.champion]!r})")

# The ACTION ROW must describe the champion, not whatever sits at hand slot 60.
# This is the exact class of bug the `A_TARGET` and `A_PICK` overloads caused:
# a valid index into the wrong array gives meaningless features on the decision
# that needs them most.
_row_e = Encoder(T, CFG)
_ob = _row_e.encode(_sp, _seat, _legal)
_ci = _legal.index(_champ_offers[0])
_nk = len(A.KIND_NAMES)
if _ob.legal_actions[_ci][_nk] != 1.0:
    die("champion-play", "the champion's action row carries no card at all")
# Encode a lone champion offer and a lone hand play of a DIFFERENT card; the
# rows must differ, or the policy cannot tell the two apart.
_hand_plays = [a for a in _legal if a.kind == A.A_PLAY and a.arg != A.CHAMPION_SRC
               and A.played_card(_sp, _seat, a.arg) != _cheap.champion]
if _hand_plays:
    _o2 = _row_e.encode(_sp, _seat, [_champ_offers[0], _hand_plays[0]])
    if np.array_equal(_o2.legal_actions[0], _o2.legal_actions[1]):
        die("champion-play",
            "the champion's row is identical to a different card's hand row")
    ok("the action row names the champion, not hand slot CHAMPION_SRC")
else:
    ok("the action row carries the champion's card (no hand play to contrast)")

# Playing it: onto the board, and OUT of the zone. 108.3.c is why the zone must
# empty -- the champion "cannot be returned to this zone by normal means", so a
# zone that still held it would make the card playable twice.
_before = int(_sp.n_perms)
A.apply(_sp, T, CFG, _champ_offers[0])
# A unit play opens a destination choice (`pend_play`); answer it.
_guard = 0
while int(_sp.pend_play) >= 0:
    _guard += 1
    assert _guard < 8, "the champion's destination choice did not terminate"
    _nxt = A.legal_actions(_sp, T, CFG, int(_sp.pend_play_seat))
    A.apply(_sp, T, CFG, next(a for a in _nxt
                              if a.kind in (A.A_PLAY_AT, A.A_PLAY_AT_FAST)))
_inv.check(_sp)
if int(_sp.champion[_seat]) >= 0:
    die("champion-play", "108.3.c -- the Champion Zone still holds the card")
_on_board = [i for i in range(int(_sp.n_perms))
             if _sp.perms[i, P_ALIVE] == 1
             and int(_sp.perms[i, P_CARD]) == _cheap.champion
             and int(_sp.perms[i, P_CTRL]) == _seat]
if not _on_board:
    die("champion-play", "the champion was not put onto the board")
ok("playing it empties the zone and puts the champion on the board")

# ...and it is not offered a second time.
if any(a.kind == A.A_PLAY and a.arg == A.CHAMPION_SRC
       for a in A.legal_actions(_sp, T, CFG, _seat)):
    die("champion-play", "the champion is still offered after being played")
ok("...and an empty Champion Zone offers nothing")

# It costs its printed cost: an unaffordable champion is not offered. 108.3.d
# says "as normal", and 811.1.b's cost waiver is specific to the Facedown Zone.
_su = game.new_game(T, CFG, *matchup(_cheap, _cheap)[:3], seed=11,
                    legends=[_cheap.legend, _cheap.legend],
                    champions=[_cheap.champion, _cheap.champion])
_past_mulligan(_su)
_su.runes_ready[int(_su.active)] = 0
_su.pool_energy[int(_su.active)] = 0
if any(a.kind == A.A_PLAY and a.arg == A.CHAMPION_SRC
       for a in A.legal_actions(_su, T, CFG, int(_su.active))):
    die("champion-play", "a champion with no runes was offered for free")
ok("with no resources it is not offered -- the cost is real")


# ---------------------------------------------------------------------------
print("\n[4e] every engine field is read by the encoder, or classified")
import re as _re
from rl.obs import OBS_UNREAD
from rl.engine.state import GameState as _GS

# The gate that `victory_bonus` needed and did not have. Aspirant's Climb moved
# the Victory Score, `check_winner` honoured it, the observation never mentioned
# it -- so the agent aimed at the wrong finish line and nothing failed. This is
# `mirror.SEAT_AXIS`'s device applied to the encoder: a new GameState field must
# be read here or listed in OBS_UNREAD with a reason.
_src = (__import__("pathlib").Path(__file__).resolve().parents[1] / "obs.py").read_text()
_read = set(_re.findall(r"state\.(\w+)", _src))
_slots = [x for x in _GS.__slots__ if x != "rng"]
_unread = {x for x in _slots if x not in _read}

_new = sorted(_unread - set(OBS_UNREAD))
if _new:
    die("obs-coverage",
        f"{len(_new)} GameState field(s) reach neither the encoder nor "
        f"OBS_UNREAD: {_new}\n"
        f"    Either encode them, or add them to obs.OBS_UNREAD with the "
        f"reason the policy does not need them.")
_gone = sorted(set(OBS_UNREAD) - _unread)
if _gone:
    die("obs-coverage",
        f"OBS_UNREAD lists {len(_gone)} field(s) the encoder now DOES read, or "
        f"that no longer exist: {_gone}\n"
        f"    Remove them -- a stale exemption hides the next one.")
ok(f"all {len(_slots)} GameState fields accounted for "
   f"({len(_slots) - len(_unread)} encoded, {len(OBS_UNREAD)} classified)")

# The 24 that the audit found invisible. Perturb each into a LIVE value and the
# encoding must move -- the leak test, inverted. Cheap, and it is the only check
# that survives a refactor of how the globals are laid out.
import copy as _copy
_probe = make_game(T, CFG, 7)
for _ in range(40):
    if A.is_terminal(_probe): break
    _lg = A.legal_actions(_probe, T, _cfg, int(_probe.priority))
    if not _lg: break
    A.apply(_probe, T, _cfg, _lg[0])
_PLY_STAMPS = {"legend_once", "death_guard", "unit_tax_ply",
               "units_enter_ready_turn", "xp_gained_ply", "hold_points_ply"}
_AUDITED = ["victory_bonus", "extra_turns", "hold_points", "power_spent",
            "spells_played", "cards_completed", "legend_pile_n", "legend_emp",
            "legend_once", "death_guard", "riches_on", "unit_tax_ply",
            "next_spell_discount", "next_discount", "n_zero",
            "units_enter_ready_turn", "xp_gained_ply", "excess_amt",
            "draw_count", "recycled_n", "banished_n", "delayed", "n_trig",
            "passes"]
_seat = 0
_g0 = _enc.encode(_probe, _seat, A.legal_actions(_probe, T, _cfg, _seat)).globals
_blind = []
for _f in _AUDITED:
    _s2 = _copy.deepcopy(_probe)
    _v = getattr(_s2, _f)
    if isinstance(_v, np.ndarray):
        _v.reshape(-1)[:] = int(_s2.ply) if _f in _PLY_STAMPS else 3
    else:
        setattr(_s2, _f, int(_v) + 1)
    _g1 = _enc.encode(_s2, _seat, A.legal_actions(_s2, T, _cfg, _seat)).globals
    if np.array_equal(_g0, _g1):
        _blind.append(_f)
if _blind:
    die("obs-coverage", f"standing state invisible to the policy again: {_blind}")
ok(f"all {len(_AUDITED)} audited fields move the observation, incl. victory_bonus")

# The tempo feature, which is the reason victory_bonus mattered. turns-to-win is
# ceil((V - points)/2), so scores PAIR UP: at V=8, 6 and 7 are both one turn
# away and the 7th point buys no tempo at all. Moving V by one inverts which
# scores are efficient, which is why the bonus cannot be left out.
def _turns(v, pts):
    return (max(0, v - pts) + 1) // 2
if not (_turns(8, 6) == _turns(8, 7) == 1 and _turns(8, 5) == 2):
    die("obs-coverage", "turns-to-win arithmetic is wrong at V=8")
if not (_turns(9, 7) == _turns(9, 8) == 1 and _turns(9, 6) == 2):
    die("obs-coverage", "turns-to-win arithmetic is wrong at V=9")
# ...and the parity really does invert: 6 is a milestone at V=8, 7 is at V=9.
if not (_turns(8, 6) < _turns(8, 5) and _turns(9, 6) == _turns(9, 5)):
    die("obs-coverage", "the parity of (V - score) does not invert with V")
ok("471/194.3 tempo: (6,7) pair at V=8, (7,8) at V=9 -- parity inverts as it must")


# ---------------------------------------------------------------------------
print("\n[5] mask hygiene and the action cap")
hist: Counter = Counter()
for seed in range(120):
    env, _ = run_env(seed, auto_pass=True)
    hist += env.n_legal_hist
worst = max(hist)
if worst > CFG.max_actions:
    die("A_max", f"{worst} legal actions exceeds max_actions={CFG.max_actions}")

env = RiftboundEnv(T, CFG, auto_pass=True)
obs = env.reset(0, *deal(0))
for _ in range(40):
    if obs is None:
        break
    n = obs.n_legal
    assert obs.action_mask.sum() == n, "mask population != n_legal"
    assert obs.action_mask[:n].all() and not obs.action_mask[n:].any(), \
        "mask is not a prefix; the policy would sample a padded row"
    assert not obs.legal_actions[n:].any(), "padded action rows are not zero"
    assert len(env.legal) == n, "legal list and mask disagree"
    assert np.isfinite(obs.globals).all(), "non-finite value in globals"
    obs = env.step(int(np.random.default_rng(1).integers(n))).obs

p50 = np.median(list(hist.elements()))
print(f"    legal-action count: median {p50:.0f}, max {worst}, "
      f"cap {CFG.max_actions}")
ok("masks are prefix-shaped, padding is zero, and A_max holds with room")


# ---------------------------------------------------------------------------
print("\n[6] the vector env is the same env, batched")
NENV = 8
vec = VecRiftbound(T, CFG, NENV, deal, seed0=0)
b = vec.reset()
shapes = vec.shapes()
assert len(b) == NENV, "batch length != n_envs"
for k, z in b.zones.items():
    assert z.shape == (NENV,) + shapes[k], f"zone {k} is {z.shape}"
    assert b.zone_mask[k].shape == (NENV, shapes[k][0]), f"mask {k} shape"
assert b.globals.shape == (NENV, shapes["globals"][0])
assert b.legal_actions.shape == (NENV,) + shapes["actions"]
assert b.privileged.shape == (NENV, shapes["privileged"][0])
ok(f"batched shapes agree with Encoder.shapes() across {NENV} slots")

# Deterministic policy -> every episode must match the single-env result for
# the same seed, which is what proves auto-reset does not shuffle state between
# slots or leak one episode's position into the next.
agents = [greedy_agent(np.random.default_rng(0)) for _ in range(NENV)]
seen, mismatched = 0, 0
while seen < 40:
    idx = [env.legal.index(agents[i](env.state, T, CFG, env.to_move, env.legal))
           for i, env in enumerate(vec.envs)]
    b, rewards, done, infos = vec.step(idx)
    for i in np.flatnonzero(done):
        ep = infos[i]["episode"]
        w = ep["winner"]
        if w >= 0 and (rewards[i][w] != 1.0 or rewards[i][1 - w] != -1.0):
            die("vec", f"episode ended {w} but paid {rewards[i]}")
        seen += 1
    mismatched += int((~b.action_mask[np.arange(NENV), 0]).sum())
if mismatched:
    die("vec", "a batched slot reported zero legal actions")

# Replay a handful of those seeds single-env and compare outcomes.
for seed in range(12):
    _, single = greedy_run(seed, True)
    v = VecRiftbound(T, CFG, 1, deal, seed0=seed)
    v.reset()
    ep = None
    while ep is None:
        e = v.envs[0]
        i = e.legal.index(agents[0](e.state, T, CFG, e.to_move, e.legal))
        _, _, d, infos = v.step([i])
        if d[0]:
            ep = infos[0]["episode"]
    for k in ("winner", "turns", "points", "hash"):
        if ep[k] != single[k]:
            die("vec", f"seed {seed}: {k} {ep[k]} batched vs {single[k]} single")
ok(f"{seen} episodes auto-reset cleanly; 12 replays match the single env exactly")
print(f"    truncation rate {vec.truncation_rate:.1%} over {vec.episodes} episodes")

print("\n\033[32mall gym tests passed\033[0m")

# ---------------------------------------------------------------------------
print("\n[mulligan] 116-117: draw 4, set aside up to 2, draw, THEN recycle")

from rl.engine.game import MULLIGAN_MAX, STARTING_HAND, mulligan, new_game

from rl.ppo import deck_pool_deal
_decks, _runes, _bfs, _legends, _champs = deck_pool_deal(T, 0.0)(3)
_s = new_game(T, CFG, _decks, _runes, _bfs, seed=3)
# Seat 1 has not taken a turn, so its hand is the untouched 116 deal.
if int(_s.n_hand[1]) != STARTING_HAND or STARTING_HAND != 4:
    die("mulligan", f"116 deals 4, got {int(_s.n_hand[1])} "
                    f"(STARTING_HAND={STARTING_HAND})")
ok("116 -- each player is dealt exactly 4")

_s = new_game(T, CFG, _decks, _runes, _bfs, seed=3)
_ptr = int(_s.deck_ptr[0])
_top2 = [int(_s.deck[0, _ptr]), int(_s.deck[0, _ptr + 1])]
_before = [int(c) for c in _s.hand[0, :int(_s.n_hand[0])]]
_bottom = int(_s.n_deck[0])
_aside = mulligan(_s, 0, [0, 1])
_after = [int(c) for c in _s.hand[0, :int(_s.n_hand[0])]]

if len(_after) != len(_before):
    die("mulligan", "117.2 draws as many as were set aside, so the hand size "
                    "is unchanged")
if _after[-2:] != _top2:
    die("mulligan", "the replacements come off the TOP of the deck")
if int(_s.n_deck[0]) != _bottom + 2:
    die("mulligan", "the set-aside cards should have gone to the bottom")
ok("117.1-117.3 -- set aside, draw the replacements, recycle to the bottom")

# **The order is load-bearing.** 117.2 draws before 117.3 recycles, so a card
# put back can never be one of the replacements. Recycling first would make
# that possible -- certain, on a nearly empty deck.
if set(_aside) & (set(_after) - set(_before)):
    die("mulligan", "a recycled card came back as its own replacement -- the "
                    "draw must happen BEFORE the recycle")
ok("...and the draw precedes the recycle, so nothing replaces itself")

# "Up to two" -- zero is a legal choice, and three is not.
_s2 = new_game(T, CFG, _decks, _runes, _bfs, seed=3)
if mulligan(_s2, 0, []) != []:
    die("mulligan", "choosing zero must be legal and do nothing")
try:
    mulligan(_s2, 0, [0, 1, 2])
except AssertionError:
    pass
else:
    die("mulligan", f"117.1 caps the choice at {MULLIGAN_MAX}")
ok(f"'up to two' includes zero and refuses {MULLIGAN_MAX + 1}")

# --- the Mulligan as a DECISION, not a skipped step -------------------------
_s = new_game(T, CFG, _decks, _runes, _bfs, seed=5)
if A.acting_seat(_s) != 0 or int(_s.pend_mull) != 0:
    die("mulligan", "117 is the first decision of the game, and it is the "
                    "First Player's")
_kinds = {a.kind for a in A.legal_actions(_s, T, CFG, 0)}
if A.A_MULLIGAN not in _kinds or A.A_MULLIGAN_DONE not in _kinds:
    die("mulligan", "both choosing a card and stopping must be offered")
ok("117 -- the Mulligan is the game's first decision point, in turn order")

_deck_before = int(_s.n_deck[0])
A.apply(_s, T, CFG, A.Action(A.A_MULLIGAN, 0))
A.apply(_s, T, CFG, A.Action(A.A_MULLIGAN, 1))
if [a for a in A.legal_actions(_s, T, CFG, 0) if a.kind == A.A_MULLIGAN]:
    die("mulligan", "117.1 caps the choice at two, so a third must not be offered")
A.apply(_s, T, CFG, A.Action(A.A_MULLIGAN_DONE))
if int(_s.pend_mull) != 1:
    die("mulligan", "turn order: the second player mulligans next")
if int(_s.n_deck[0]) != _deck_before + 2 or int(_s.n_hand[0]) != STARTING_HAND:
    die("mulligan", "two cards to the bottom, two drawn to replace them")
ok("choosing two is capped, performed, and passes to the next seat")

# "Up to two" includes zero, and the game begins once both are done (118).
A.apply(_s, T, CFG, A.Action(A.A_MULLIGAN_DONE))
if int(_s.pend_mull) != -1 or int(_s.active) != 0:
    die("mulligan", "118 -- after both Mulligans the First Player takes a turn")
if A.acting_seat(_s) != 0 or not A.legal_actions(_s, T, CFG, 0):
    die("mulligan", "the game should be underway with real actions available")
ok("declining is legal, and the First Player's turn begins after both (118)")



# ---------------------------------------------------------------------------
print("\n[truncation] 408.2.b -- a game out of clock is decided on points")

# `outcome` used to pay (0, 0) on every truncation, which made stalling
# PROFITABLE: a player heading for -1 could take 0 instead by running the turn
# cap out. 408.2.b is the real rule -- a point lead of two or more wins, and
# only a lead of 0 or 1 is a draw.
_s = new_game(T, CFG, _decks, _runes, _bfs, seed=11)
_s.truncated = True
for _lead, _want, _why in (
        ((0, 0), (0.0, 0.0), "level is a draw"),
        ((3, 3), (0.0, 0.0), "level at any score is a draw"),
        ((1, 0), (0.0, 0.0), "a lead of one is still a draw"),
        ((0, 1), (0.0, 0.0), "...from either side"),
        ((2, 0), (1.0, -1.0), "a lead of two wins"),
        ((0, 2), (-1.0, 1.0), "...from either side"),
        ((5, 1), (1.0, -1.0), "and more than two, obviously"),
):
    _s.points[0], _s.points[1] = _lead
    got = A.outcome(_s, CFG)
    if got != _want:
        die("truncation", f"points {_lead}: expected {_want}, got {got} -- {_why}")
ok("a point lead of two or more wins a truncated game; less is a draw")

# The stalling incentive specifically: behind by two, a truncation must not be
# better than losing. It used to be worth a whole point of reward.
_s.points[0], _s.points[1] = (0, 2)
if A.outcome(_s, CFG)[0] >= 0.0:
    die("truncation", "a player two points behind must not profit from stalling")
ok("...so a losing player can no longer buy 0 by running the clock out")

# A decided game ignores all of it -- `winner` wins outright even if the points
# say otherwise, which is what an OP_WIN card does.
_s.winner = 1
_s.points[0], _s.points[1] = (7, 0)
if A.outcome(_s, CFG) != (-1.0, 1.0):
    die("truncation", "a real winner outranks the point count")
ok("a game with a winner is unaffected -- 408.2.b is only for the clock")


# ---------------------------------------------------------------------------
print("\n[loop] sterile-loop detection: a repeated position ends the episode")

# Built rather than found: a livelock is by definition hard to reach on purpose,
# so the position is repeated by REWINDING the env to a state it has already
# been offered. That is exactly what a loop does, and it exercises the same code.
_env = RiftboundEnv(T, CFG, auto_pass=False)
_obs = _env.reset(*((7,) + deal(7)))
_env.steps = CFG.loop_watch_after + 1        # past the watch threshold
_seen_key = (_env.state.state_hash(), int(_obs.to_move))
_env._seen.add(_seen_key)                    # "we have been here before"
_env._check_sterile_loop()
if not _env.state.truncated:
    die("loop", "a repeated (state_hash, seat to move) must end the episode")
if _env.loop_loser != int(_obs.to_move) or len(_env.legal) != 0:
    die("loop", f"the seat to move had {len(_obs.mask)} options and chose the "
                f"loop, so it takes the loss")
if _env.final_rewards() != ((-1.0, 1.0) if _env.loop_loser == 0 else (1.0, -1.0)):
    die("loop", "the looper's reward must be -1 and the opponent's +1")
ok("a repeat with an alternative available is a loss for the looper")

# **Forced is not blamed.** With exactly one legal action the seat never made a
# choice, so attributing the loop to it would train against a decision it did
# not make. That case falls back to 408.2.b on points.
_env2 = RiftboundEnv(T, CFG, auto_pass=False)
_obs2 = _env2.reset(*((7,) + deal(7)))
_env2.steps = CFG.loop_watch_after + 1
_env2._legal = _env2._legal[:1]              # a window with no alternative
_env2._seen.add((_env2.state.state_hash(), int(_obs2.to_move)))
_env2._check_sterile_loop()
if not _env2.state.truncated:
    die("loop", "a forced loop still ends the episode")
if _env2.loop_loser != -1:
    die("loop", "a seat with one legal action was forced -- do not blame it")
if _env2.final_rewards() != A.outcome(_env2.state, CFG):
    die("loop", "a forced loop is decided by 408.2.b, like any truncation")
ok("...and a forced repeat is an ordinary truncation, decided on points")

# Nothing fires before the watch threshold, and a healthy game never reaches it
# -- that is the whole reason the 67us hash is affordable.
_env3 = RiftboundEnv(T, CFG, auto_pass=False)
_obs3 = _env3.reset(*((7,) + deal(7)))
_env3._seen.add((_env3.state.state_hash(), int(_obs3.to_move)))
_env3._check_sterile_loop()
if _env3.state.truncated or _env3.loop_loser >= 0:
    die("loop", f"nothing may be checked before step "
                f"{CFG.loop_watch_after}, or every game pays for the hash")
ok(f"the check is dormant for the first {CFG.loop_watch_after} decisions")

# A fresh episode must forget the old one's positions, or the second game in a
# reused env inherits a poisoned seen-set.
_env3.reset(*((8,) + deal(8)))
if _env3._seen or _env3.loop_loser >= 0:
    die("loop", "reset must clear the per-episode position set")
ok("reset clears the seen-set, so a reused env does not poison its next game")

# `play` stops on `done`, not on "the observation is None". A truncation leaves
# the next observation in place, so the old loop spun forever once one fired.
_env4 = RiftboundEnv(T, CFG)
_env4.cfg = _replace(CFG, decision_cap=3)
_out = play(_env4, [random_policy(np.random.default_rng(1))] * 2,
            *((9,) + deal(9)))
if not _out["truncated"] or _env4.steps > 4:
    die("loop", f"`play` must return as soon as the cap fires, got "
                f"{_env4.steps} steps truncated={_out['truncated']}")
ok("`play` returns on a truncation instead of spinning on a live observation")

print("\n\033[32mtruncation and loop tests passed\033[0m")


# ---------------------------------------------------------------------------
print("\n[overflow] MAX_PERMS costs one episode, not the run")

# Permanent rows are only reclaimed by `compact_permanents`, which is safe only
# at end of turn -- so the cap is really on rows CREATED in one turn. Measured at
# victory 8: random play peaks at 33 of 48 and greedy at 36, with one action
# adding at most 7 rows. A POLICY exceeds it, and the first victory-8 run died at
# iteration 8 doing so. It must end the episode instead.
from rl.engine.state import MAX_PERMS, BoardOverflow

_env5 = RiftboundEnv(T, CFG, auto_pass=False)
_env5.reset(*((12,) + deal(12)))
# Fill the board to the brim by hand, leaving room for exactly one more row.
_vanilla = v0_pool(T)[0]
while _env5.state.n_perms < MAX_PERMS - 1:
    _env5.state.add_permanent(_vanilla, 0, 0, ready=False)
_env5.state.add_permanent(_vanilla, 0, 0, ready=False)
if _env5.state.n_perms != MAX_PERMS:
    die("overflow", "the fixture should have filled every row")
try:
    _env5.state.add_permanent(_vanilla, 0, 0, ready=False)
except BoardOverflow:
    pass
else:
    die("overflow", "add_permanent past the cap must raise BoardOverflow")
ok(f"add_permanent raises BoardOverflow at {MAX_PERMS} rows")

# ...and it is an AssertionError, so the fuzz -- which does NOT catch it -- still
# fails loudly. There the overflow is a finding, not something to absorb.
if not issubclass(BoardOverflow, AssertionError):
    die("overflow", "the fuzz relies on this being an AssertionError")
ok("it subclasses AssertionError, so the fuzz still surfaces it as a finding")

# The env absorbs it: a truncated episode, decided on points by 408.2.b, with
# the reason recorded so `ppo`'s `ovf=` column can show a rising rate.
#
# The raise is INJECTED rather than provoked by filling the board, because what
# is under test is the handler, not the token machinery: a real overflow needs a
# specific card making a specific number of tokens on a full board, and a
# fixture built that way would silently stop exercising this the day that card's
# spec changed.
_env6 = RiftboundEnv(T, CFG, auto_pass=False)
_obs6 = _env6.reset(*((13,) + deal(13)))
_real_apply = A.apply
def _boom(*a, **k):
    raise BoardOverflow("injected")
A.apply = _boom
try:
    _r6 = _env6.step(0)
finally:
    A.apply = _real_apply
if not _r6.done or not _r6.truncated:
    die("overflow", "the episode must end, and end as a truncation")
if _r6.obs is not None:
    die("overflow", "a discarded position must not be handed back as an obs")
if not _env6.summary()["board_overflow"]:
    die("overflow", "the summary has to say WHY, or the metric cannot rise")
if _r6.rewards != A.outcome(_env6.state, CFG):
    die("overflow", "408.2.b decides it, like any other truncation")
ok("the env ends that episode, records why, and scores it on points")

# A reused env must forget it, or every later episode reports an overflow.
_env6.reset(*((14,) + deal(14)))
if _env6.summary()["board_overflow"]:
    die("overflow", "reset must clear the flag")
ok("reset clears it, so one bad episode does not tar the rest")

print("\n\033[32mboard-overflow tests passed\033[0m")
