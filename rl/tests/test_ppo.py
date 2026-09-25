"""Network and PPO tests -- the first three items on PLAN.md's Phase 4 debug list.

When PPO does not learn, §4 says to check, in order: (1) action mask alignment,
(2) reward sign and seat attribution, (3) observation canonicalization, (4)
advantage normalization, (5) learning rate -- and that it is one of the first
three about 90% of the time. Canonicalization is covered in `test_env.py`; the
other two are covered here, plus the pieces that would silently poison a run
rather than crash it.

  [1] Mask alignment -- index i really is `env.legal[i]`, end to end.
  [2] Masked logits -- illegal slots get zero probability, and no NaNs.
  [3] Seat attribution and GAE -- closed-form, hand-checkable.
  [4] Entropy normalization -- invariant to the number of legal actions.
  [5] Gradients -- finite, and reaching every parameter.
  [6] An untrained net is ~50% against random, so the eval harness is sane.
  [7] Hidden information reaches neither the policy nor the shared trunk.
  [8] The procedural dealer is as REDUNDANT as a real decklist.
"""
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))

import numpy as np
import torch

from rl.config import Config
from rl.engine import game
from rl.engine.cardtable import full_table
from rl.env import RiftboundEnv
from rl.eval import duel
from rl.nets import RiftboundNet, count_params, to_torch
from rl.obs import Encoder
from rl.ppo import (HP, MAIN_DECK_SIZE, Step, Trainer, deal_stats,
                    deck_pool_deal, finish_episode, v0_deal, v1_deal)
from rl.vec import batch

T = full_table()
CFG = Config().at_victory_score(3)
DEAL = v0_deal(T)


def ok(name):
    print(f"  \033[32mPASS\033[0m {name}")


def die(name, msg):
    print(f"  \033[31mFAIL\033[0m {name}: {msg}")
    sys.exit(1)


enc = Encoder(T, CFG)
net = RiftboundNet(enc.shapes())
print(f"net: {count_params(net):,} parameters")

# ---------------------------------------------------------------------------
print("\n[1] action index i is env.legal[i], through the whole stack")
checked = 0
for seed in range(30):
    env = RiftboundEnv(T, CFG, encoder=enc)
    obs = env.reset(seed, *DEAL(seed))
    rng = np.random.default_rng(seed)
    while obs is not None:
        # The row the net scores at slot i must be the featurization of the
        # engine action the env will apply for i. Anything else and the policy
        # is learning to score one action and play another -- which trains
        # perfectly happily and never improves.
        for i, act in enumerate(env.legal):
            want = enc._action_row(act, env.state, obs.to_move)
            if not np.array_equal(obs.legal_actions[i], want):
                die("alignment", f"seed {seed}: row {i} != featurized "
                                 f"{act!r}")
        checked += len(env.legal)
        obs = env.step(int(rng.integers(obs.n_legal))).obs
ok(f"{checked} action rows matched their engine action exactly")

# And the sampler never returns a padded slot.
env = RiftboundEnv(T, CFG, encoder=enc)
obs = env.reset(0, *DEAL(0))
gen = torch.Generator().manual_seed(0)
for _ in range(300):
    if obs is None:
        obs = env.reset(1, *DEAL(1))
    t = to_torch(batch([obs]), "cpu")
    idx, logp, ent, val = net.act(t, generator=gen)
    i = int(idx.item())
    if not 0 <= i < obs.n_legal:
        die("alignment", f"sampled index {i} outside {obs.n_legal} legal actions")
    obs = env.step(i).obs
ok("300 samples all landed inside the legal prefix")


# ---------------------------------------------------------------------------
print("\n[2] masked logits carry no probability and no NaNs")
env = RiftboundEnv(T, CFG, encoder=enc)
obs = env.reset(3, *DEAL(3))
t = to_torch(batch([obs] * 4), "cpu")
logits, value, value_aux = net(t)     # two critics since the symmetric head
p = torch.softmax(logits, -1)
n = obs.n_legal
assert torch.isfinite(logits).all(), "non-finite logit"
assert torch.isfinite(value).all(), "non-finite value"
if p[:, n:].abs().max().item() > 1e-8:
    die("mask", f"illegal slots hold {p[:, n:].abs().max().item():.2e} probability")
assert abs(p[:, :n].sum(-1).mean().item() - 1.0) < 1e-5, "legal mass != 1"
ok(f"{p.shape[1] - n} padded slots hold <1e-8 probability; legal mass sums to 1")


# ---------------------------------------------------------------------------
print("\n[3] seat attribution and GAE inside a seat's own subsequence")
hp = HP(gamma=1.0, gae_lambda=0.95)

# Interleaved seats, zero value estimates: advantages are then pure discounted
# terminal reward, so the arithmetic is checkable by hand.
pend = [Step(obs={}, action=0, logp=0.0, value=0.0, seat=s)
        for s in (0, 1, 0, 1, 0, 1)]
finish_episode(pend, (1.0, -1.0), hp)
s0 = [s.adv for s in pend if s.seat == 0]
s1 = [s.adv for s in pend if s.seat == 1]
want0 = [0.95 ** 2, 0.95, 1.0]
if not np.allclose(s0, want0):
    die("gae", f"seat 0 advantages {s0}, expected {want0}")
if not np.allclose(s1, [-x for x in want0]):
    die("gae", f"seat 1 advantages {s1}, expected {[-x for x in want0]}")
ok("winner's advantages are positive, loser's are their exact negation")

# The opponent's value estimates must not enter a seat's bootstrap. Give seat 1
# wildly wrong values and check seat 0's advantages do not move at all.
pend2 = [Step(obs={}, action=0, logp=0.0, value=(0.0 if s == 0 else 99.0), seat=s)
         for s in (0, 1, 0, 1, 0, 1)]
finish_episode(pend2, (1.0, -1.0), hp)
if not np.allclose([s.adv for s in pend2 if s.seat == 0], want0):
    die("gae", "seat 0's advantages changed when seat 1's critic changed -- "
               "GAE is bootstrapping across the opponent's moves")
ok("seat 0's GAE is unaffected by seat 1's value estimates (gotcha 2)")

# A game nobody won pays nobody.
pend3 = [Step(obs={}, action=0, logp=0.0, value=0.0, seat=s) for s in (0, 1, 0)]
finish_episode(pend3, (0.0, 0.0), hp)
if any(s.adv != 0.0 for s in pend3):
    die("gae", "a truncated game produced non-zero advantages")
ok("a truncated game pays zero to both seats")

# One seat acting alone (possible when a game ends before the other replies).
solo = [Step(obs={}, action=0, logp=0.0, value=0.5, seat=0)]
finish_episode(solo, (1.0, -1.0), hp)
assert np.isclose(solo[0].ret, 1.0), f"single-step return {solo[0].ret}"
ok("a one-decision episode returns exactly the terminal reward")


# ---------------------------------------------------------------------------
print("\n[4] entropy is normalized by log(n_legal)")
for n in (2, 3, 5, 10, 40):
    lg = torch.zeros(1, enc.a_max)
    mask = torch.zeros(1, enc.a_max, dtype=torch.bool)
    mask[0, :n] = True
    e = RiftboundNet.entropy(lg.masked_fill(~mask, -1e9), mask).item()
    if abs(e - 1.0) > 1e-5:
        die("entropy", f"uniform over {n} actions gave {e:.4f}, expected 1.0")
ok("a uniform policy scores 1.0 whether it has 2 legal actions or 40")

lg = torch.zeros(1, enc.a_max)
lg[0, 0] = 20.0
mask = torch.zeros(1, enc.a_max, dtype=torch.bool)
mask[0, :5] = True
assert RiftboundNet.entropy(lg.masked_fill(~mask, -1e9), mask).item() < 0.05, \
    "a near-deterministic policy should score near 0"
ok("a near-deterministic policy scores near 0")


# ---------------------------------------------------------------------------
print("\n[5] gradients are finite and reach every parameter")
tr = Trainer(T, CFG, DEAL, HP(n_envs=8, rollout=64, minibatches=2,
                              update_epochs=1), seed=0)
roll = tr.collect()
assert roll.episodes > 0, "no episode completed in a 64-transition rollout"
before = [p.detach().clone() for p in tr.net.parameters()]
stats = tr.update(roll, 0.0)
for k, v in stats.items():
    if not np.isfinite(v):
        die("grad", f"stat {k} is {v}")
moved = sum(not torch.equal(a, b)
            for a, b in zip(before, tr.net.parameters()))
total = len(before)
if moved < total:
    stuck = [n for (n, p), b in zip(tr.net.named_parameters(), before)
             if torch.equal(p.detach(), b)]
    die("grad", f"{total - moved}/{total} parameter tensors never moved: {stuck}")
ok(f"{roll.episodes} episodes, {len(roll.steps)} transitions, "
   f"all {total} parameter tensors updated")
print(f"    stats: {({k: round(v, 4) for k, v in stats.items()})}")

# Awkward transition counts must not produce a size-1 minibatch, whose
# advantage std is undefined. That NaN'd the policy loss silently, spread to
# every parameter through one optimizer step, and did not raise.
for nmb in (2, 3, 4, 7):
    t2 = Trainer(T, CFG, DEAL, HP(n_envs=4, rollout=17, minibatches=nmb,
                                  update_epochs=1), seed=1)
    st = t2.update(t2.collect(), 0.0)
    for k, v in st.items():
        if not np.isfinite(v):
            die("grad", f"minibatches={nmb} produced {k}={v}")
ok("odd transition counts split evenly and stay finite for 2/3/4/7 minibatches")


# ---------------------------------------------------------------------------
print("\n[6] an untrained net is a coin flip against random")
rate = duel(net, game.random_agent, T, CFG, DEAL, n=60)
if not 0.35 <= rate <= 0.65:
    die("eval", f"untrained net scored {rate:.1%} vs random -- the eval harness "
                f"or the seat swap is wrong")
ok(f"untrained net {rate:.1%} vs random (seat-swapped, so ~50% is correct)")


# ---------------------------------------------------------------------------
# The claim: the agent cannot learn to play by cheating. Two halves, and both
# are architectural rather than conventional, so both can be tested directly.
print("\n[7] hidden information cannot reach the policy, or the trunk")

env = RiftboundEnv(T, CFG, encoder=enc)
t = to_torch(batch([env.reset(11, *DEAL(11))]), "cpu")
assert "privileged" in t, "the test needs the privileged field to perturb"

# (a) Rewriting what ONLY the critic sees must not move a single action score.
# `test_env` proves the observation excludes hidden information; this proves
# the network has no second path to it.
base_logits, _, _ = net(t)
cheat = {k: (v if k != "privileged" else torch.randn_like(v))
         for k, v in t.items()}
cheat_logits, _, _ = net(cheat)
if not torch.equal(base_logits, cheat_logits):
    die("cheating", "scrambling the privileged input changed the action "
                    "logits -- hidden information reaches the policy")
ok("scrambling the opponent's hand and facedowns leaves every action score identical")

# ...and the perturbation is not a no-op, or (a) proves nothing.
if torch.equal(net(t)[2], net(cheat)[2]):
    die("cheating", "the privileged critic did not move either -- the "
                    "perturbation was inert and the test above is vacuous")
ok("...while the privileged critic does move, so the control is live")

# (b) The spare critic is fitted to the same returns, so its gradient exists --
# but it must not reach the shared trunk. Otherwise switching the privileged
# critic off would still let hidden-information gradients shape the features
# the policy reads, which is the entire point of switching it off.
net.zero_grad(set_to_none=True)
_, _, aux = net(t)
aux.sum().backward()
trunk_grad = [p.grad for p in net.trunk.parameters() if p.grad is not None]
enc_grad = [p.grad for p in net.card_enc.parameters() if p.grad is not None]
leaked = [g for g in trunk_grad + enc_grad if g.abs().sum().item() > 0.0]
if leaked:
    die("cheating", f"the auxiliary critic put gradient on {len(leaked)} shared "
                    f"trunk tensors -- `values` is not detaching it")
ok("the auxiliary critic's gradient stops at its own head; the trunk is untouched")

head_grad = sum(p.grad.abs().sum().item()
                for p in net.value_priv.parameters() if p.grad is not None)
if head_grad <= 0.0:
    die("cheating", "the auxiliary critic got no gradient at all, so the "
                    "detach test above is vacuous")
ok("...and its own weights do get gradient, so it is genuinely being trained")
net.zero_grad(set_to_none=True)

# ---------------------------------------------------------------------------
print("\n[8] the procedural dealer builds decks, not samples of a pool")
# `v1_deal` drew 39 cards one at a time from a 339-card pool and rejected a 4th
# copy, so a repeat was an accident: 36.5 distinct cards of 39, against 16.7 for
# the real corpus. Nothing failed -- and nothing tested it -- but the `decks`
# observation zone exists to condition on draw consistency, on what a trash
# implies about what is left, and on archetype, and a near-singleton deck
# misrepresents all three. Measured against the corpus, not against a guess.
_real = deal_stats(T, deck_pool_deal(T, 0.0), 120)
_proc = deal_stats(T, v1_deal(T), 300)
print(f"    real  decks: {_real['distinct_mean']:.1f} distinct of "
      f"{MAIN_DECK_SIZE}, copies 1/2/3 = {_real['copy_frac']}")
print(f"    v1_deal    : {_proc['distinct_mean']:.1f} distinct of "
      f"{MAIN_DECK_SIZE}, copies 1/2/3 = {_proc['copy_frac']}")

if _proc["max_copies"] > 3:
    die("dealer", f"103.2.b -- {_proc['max_copies']} copies of one card")
# Within 3 of the corpus mean. Loose on purpose: the target is "a deck shaped
# like a deck", not a specific number, and the spell/unit split forces two
# truncations per deck which leaves a small excess of 1-ofs.
if abs(_proc["distinct_mean"] - _real["distinct_mean"]) > 3.0:
    die("dealer", f"v1_deal runs {_proc['distinct_mean']:.1f} distinct cards "
                  f"against the corpus' {_real['distinct_mean']:.1f} -- decks "
                  f"are not redundant like real lists")
# The shape, not just the count: most of a real deck's distinct cards are maxed
# out. A dealer could hit the mean with all-2-ofs and still be wrong.
if _proc["copy_frac"][2] < 0.35:
    die("dealer", f"only {_proc['copy_frac'][2]:.0%} of distinct cards are "
                  f"3-ofs, against {_real['copy_frac'][2]:.0%} for real decks")
ok(f"{_proc['distinct_mean']:.1f} distinct of {MAIN_DECK_SIZE} "
   f"(corpus {_real['distinct_mean']:.1f}), {_proc['copy_frac'][2]:.0%} of them 3-ofs")

# The reason the old dealer was not simply replaced by the real one: spell
# density is what `v1_deal` is FOR, and it has to survive the rewrite.
if not 0.28 <= _proc["spell_frac_mean"] <= 0.67:
    die("dealer", f"spell density {_proc['spell_frac_mean']:.0%} left the "
                  f"real range 28-67%")
if _proc["deck_size"] != [MAIN_DECK_SIZE]:
    die("dealer", f"deck sizes {_proc['deck_size']}, not {MAIN_DECK_SIZE}")
ok(f"...at {_proc['spell_frac_mean']:.0%} mean spell density, every deck exactly "
   f"{MAIN_DECK_SIZE} cards")

print("\n\033[32mall ppo tests passed\033[0m")
