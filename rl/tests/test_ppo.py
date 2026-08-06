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
from rl.ppo import HP, Step, Trainer, finish_episode, v0_deal
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
logits, value = net(t)
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

print("\n\033[32mall ppo tests passed\033[0m")
