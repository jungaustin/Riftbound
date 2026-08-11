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
from rl.engine.mirror import mirror
from rl.engine.state import N_BF
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
for seed in range(60):
    e_on, r_on = greedy_run(seed, True)
    e_off, r_off = greedy_run(seed, False)
    for k in ("winner", "turns", "points", "hash", "steps"):
        if r_on[k] != r_off[k]:
            die("auto-pass", f"seed {seed}: {k} differs, {r_on[k]} vs {r_off[k]}")
    collapsed += e_on.auto_passes
ok("60 greedy games identical with the flag on and off")

# Say the quiet part out loud. `combat.run_combat` resolves Combat without ever
# yielding priority, so v0 has no pass-only window and the number above is
# measuring nothing. Assert that, so the day Reactions land this line fails and
# forces the flag to be re-measured rather than re-assumed.
if collapsed != 0:
    die("auto-pass", f"{collapsed} windows collapsed, but v0 should have none; "
                     f"combat must now be yielding priority -- re-measure")
ok("v0 exposes no pass-only window at all (combat does not yield priority yet)")

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
s.bf_ctrl[0], s.fd_owner[0], s.fd_card[0] = 0, 0, pool[0]
s.bf_ctrl[1], s.fd_owner[1], s.fd_card[1] = 1, 1, pool[1]

base = enc.encode(s, 0, A.legal_actions(s, T, CFG, 0))

hidden = s.clone()
foe_n = int(hidden.n_hand[1])
hidden.hand[1, :foe_n] = [pool[(i + 3) % len(pool)] for i in range(foe_n)]
lo, hi = int(hidden.deck_ptr[1]), int(hidden.n_deck[1])
hidden.deck[1, lo:hi] = hidden.deck[1, lo:hi][::-1]
hidden.fd_card[1] = pool[7]                       # THEIR facedown card
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

# Negative control: MY facedown card is mine to see, so changing it must show.
seen = s.clone()
seen.fd_card[0] = pool[9]
if base.public_bytes() == enc.encode(
        seen, 0, A.legal_actions(seen, T, CFG, 0)).public_bytes():
    die("leak", "changing the seat's OWN facedown card was invisible too, so "
                "the encoder is simply dropping the facedown zone")
ok("negative control: the seat's own facedown card is visible to it")


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
_decks, _runes, _bfs = deck_pool_deal(T, 0.0)(3)
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

