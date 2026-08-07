"""Evaluation -- PLAN.md Phase 4 exit and §7.

Everything here is **seat-swapped on paired seeds**: each deal is played twice,
once with the network on each side. Without that, a win rate is contaminated by
whatever first-player edge the position has (measured: random-vs-random sits at
50.0% only because it is paired this way, and the first player wins 53.7% of
random games), and by which side happened to be dealt the better opening.

The opponents are the Phase 2 baselines, unchanged, so Phase 4's numbers are
directly comparable to the ones the engine was validated with.
"""

from __future__ import annotations

import numpy as np
import torch

from rl.agents.greedy import greedy_agent
from rl.config import Config
from rl.engine import game
from rl.env import RiftboundEnv
from rl.nets import to_torch
from rl.obs import Encoder
from rl.vec import batch


@torch.no_grad()
def net_choice(net, obs, device: str, deterministic: bool,
               generator=None) -> int:
    t = to_torch(batch([obs]), device)
    idx, *_ = net.act(t, deterministic=deterministic, generator=generator)
    return int(idx.item())


@torch.no_grad()
def play_one(net, opponent, table, cfg, enc: Encoder, seed: int, net_seat: int,
             deal_fn, device: str = "cpu", deterministic: bool = False,
             generator=None) -> int:
    """One game. Returns the winning seat, or -1."""
    env = RiftboundEnv(table, cfg, encoder=enc)
    obs = env.reset(seed, *deal_fn(seed))
    # `game.play_game` caps steps; this loop did not, so a livelock here hung
    # a training run silently for half an hour instead of raising. It cost more
    # to notice than to fix.
    steps = 0
    while obs is not None:
        steps += 1
        if steps > 5000:
            raise RuntimeError(
                f"eval game exceeded 5000 decisions (seed {seed}, net_seat "
                f"{net_seat}) -- livelock, not slowness")
        if obs.to_move == net_seat:
            i = net_choice(net, obs, device, deterministic, generator)
        else:
            act = opponent(env.state, table, cfg, obs.to_move, env.legal)
            i = env.legal.index(act)
        obs = env.step(i).obs
    return int(env.state.winner)


def duel(net, opponent_factory, table, cfg, deal_fn, n: int = 200,
         device: str = "cpu", seed0: int = 100_000,
         deterministic: bool = False) -> float:
    """Network win rate over `n` deals, each played from both seats."""
    enc = Encoder(table, cfg)
    gen = torch.Generator(device="cpu").manual_seed(seed0)
    wins = games = 0
    for i in range(n):
        for net_seat in (0, 1):
            opp = opponent_factory(np.random.default_rng(seed0 + i))
            w = play_one(net, opp, table, cfg, enc, seed0 + i, net_seat,
                         deal_fn, device, deterministic, gen)
            if w >= 0:
                wins += int(w == net_seat)
            games += 1
    return wins / games


def report(net, table, cfg, deal_fn, n: int = 200, device: str = "cpu") -> dict:
    """Both Phase 4 exit numbers: >=90% vs random, >=65% vs greedy."""
    net.eval()
    vs_random = duel(net, game.random_agent, table, cfg, deal_fn, n, device)
    vs_greedy = duel(net, greedy_agent, table, cfg, deal_fn, n, device)
    net.train()
    return {
        "vs_random": vs_random,
        "vs_greedy": vs_greedy,
        "pass": vs_random >= 0.90 and vs_greedy >= 0.65,
    }
