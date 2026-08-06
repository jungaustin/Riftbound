"""Network -- PLAN.md §6.

Three pieces, and the middle one is the whole reason this architecture was
chosen over anything standard.

**Trunk (§6.1).** Every zone is a *set* of cards, so each is encoded by the same
shared per-card MLP and pooled permutation-invariantly (DeepSets: masked mean
concatenated with masked max). One shared encoder across all four zones works
because each row carries its own zone one-hot in the context block -- so "a
2-might unit in my hand" and "a 2-might unit on a battlefield" are the same
function applied to different inputs, which is exactly the weight sharing you
want.

**Candidate-scoring action head (§6.2).** The net does not have an output neuron
per action. It scores each *featurized* legal action against the trunk state and
softmaxes over the scores. Two consequences, both load-bearing:

  - Variable action counts are native. No padding semantics to get wrong beyond
    the mask, and no fixed action vocabulary to outgrow when spells land.
  - An action involving a card the net never saw in training still gets a
    sensible score, because the action row carries the card's *attributes*, not
    its id. That is what makes the deck-evaluator framing (§1.1) reachable at
    all -- a policy indexed by card id could only ever play the decks it trained
    on.

**Asymmetric value head (§6.4).** The critic additionally sees the opponent's
hand and every facedown card. It is discarded at play time, so the policy stays
honest; during training it removes a large chunk of the variance that comes from
the critic having to guess what it is being punished for. The privileged input
is a *set* of cards too, so it gets the same DeepSets treatment.

**Entropy is normalized (§6.3).** Softmax entropy is bounded by log(n_legal),
and n_legal swings from 2 to 10+ here. A fixed coefficient would pay the policy
to steer toward high-branching states for reasons unrelated to winning, which is
a bias that looks exactly like strategy.
"""

from __future__ import annotations

import math

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

NEG_INF = -1e9   # not -inf: a fully-masked row would produce NaN in softmax


def mlp(sizes: list[int], out_act: bool = False) -> nn.Sequential:
    layers: list[nn.Module] = []
    for i in range(len(sizes) - 1):
        layers.append(nn.Linear(sizes[i], sizes[i + 1]))
        if out_act or i < len(sizes) - 2:
            layers.append(nn.ReLU())
    return nn.Sequential(*layers)


def init_(module: nn.Module, gain: float = math.sqrt(2), bias: float = 0.0):
    """Orthogonal init. The policy head gets gain 0.01 so the initial policy is
    near-uniform over legal actions -- a confidently wrong start is much harder
    for PPO to walk back than an indifferent one."""
    for m in module.modules():
        if isinstance(m, nn.Linear):
            nn.init.orthogonal_(m.weight, gain)
            nn.init.constant_(m.bias, bias)
    return module


def masked_pool(x: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    """[B, N, D] + [B, N] -> [B, 2D]: masked mean concatenated with masked max.

    Mean alone loses "is there a 5-might unit here"; max alone loses "how many".
    Both matter in this game and the pair is cheap.
    """
    m = mask.unsqueeze(-1).to(x.dtype)
    n = m.sum(1).clamp(min=1.0)
    mean = (x * m).sum(1) / n
    mx = x.masked_fill(~mask.unsqueeze(-1), NEG_INF).max(1).values
    # A zone with nothing in it pools to zeros rather than to -1e9.
    empty = ~mask.any(1, keepdim=True)
    return torch.cat([mean, torch.where(empty, torch.zeros_like(mx), mx)], -1)


class RiftboundNet(nn.Module):
    def __init__(self, shapes: dict, hidden: int = 256, card_hidden: int = 128,
                 head_hidden: int = 128) -> None:
        super().__init__()
        self.zone_names = ("hand", "board", "battlefields", "facedown")
        row_dim = shapes["row_dim"]
        card_dim = shapes["card_dim"]
        g_dim = shapes["globals"][0]
        act_dim = shapes["actions"][1]
        priv_dim = shapes["privileged"][0]

        self.card_dim = card_dim
        self.priv_slots = priv_dim // card_dim

        self.card_enc = init_(mlp([row_dim, card_hidden, card_hidden], True))
        trunk_in = 2 * card_hidden * len(self.zone_names) + g_dim
        self.trunk = init_(mlp([trunk_in, hidden, hidden], True))

        # Policy: score each candidate action against the trunk state.
        self.act_head = init_(mlp([hidden + act_dim, head_hidden, head_hidden, 1]))
        init_(self.act_head[-1], gain=0.01)

        # Critic: trunk state plus the information the policy is denied.
        self.priv_enc = init_(mlp([card_dim, card_hidden, card_hidden], True))
        self.value = init_(mlp([hidden + 2 * card_hidden, hidden, 1]))
        init_(self.value[-1], gain=1.0)

    # -- forward ---------------------------------------------------------

    def encode(self, zones, zone_mask, globals_) -> torch.Tensor:
        pooled = [masked_pool(self.card_enc(zones[z]), zone_mask[z])
                  for z in self.zone_names]
        return self.trunk(torch.cat(pooled + [globals_], -1))

    def logits(self, h: torch.Tensor, actions: torch.Tensor,
               action_mask: torch.Tensor) -> torch.Tensor:
        b, a, _ = actions.shape
        x = torch.cat([h.unsqueeze(1).expand(b, a, h.shape[-1]), actions], -1)
        return self.act_head(x).squeeze(-1).masked_fill(~action_mask, NEG_INF)

    def value_of(self, h: torch.Tensor,
                 privileged: torch.Tensor | None) -> torch.Tensor:
        if privileged is None:
            z = torch.zeros(h.shape[0], 2 * self.priv_enc[-2].out_features,
                            device=h.device, dtype=h.dtype)
        else:
            cards = privileged.view(-1, self.priv_slots, self.card_dim)
            z = masked_pool(self.priv_enc(cards), (cards != 0).any(-1))
        return self.value(torch.cat([h, z], -1)).squeeze(-1)

    def forward(self, obs: dict):
        h = self.encode(obs["zones"], obs["zone_mask"], obs["globals"])
        return (self.logits(h, obs["actions"], obs["action_mask"]),
                self.value_of(h, obs.get("privileged")))

    # -- sampling --------------------------------------------------------

    def act(self, obs: dict, deterministic: bool = False,
            generator: torch.Generator | None = None):
        """Returns (action_index, logprob, entropy, value), all [B]."""
        logits, value = self(obs)
        logp = F.log_softmax(logits, -1)
        if deterministic:
            idx = logits.argmax(-1)
        else:
            # `torch.multinomial` on the exponentiated log-probs rather than
            # Categorical(...).sample(), so the draw can take an explicit
            # generator and evaluation stays reproducible.
            idx = torch.multinomial(logp.exp(), 1, generator=generator).squeeze(-1)
        return idx, logp.gather(-1, idx.unsqueeze(-1)).squeeze(-1), \
            self.entropy(logits, obs["action_mask"]), value

    @staticmethod
    def entropy(logits: torch.Tensor, action_mask: torch.Tensor) -> torch.Tensor:
        """Entropy normalized by log(n_legal) -- §6.3.

        Unnormalized, the bonus is worth more in states with more legal actions,
        so the policy learns to keep its options open for reasons that have
        nothing to do with winning.
        """
        logp = F.log_softmax(logits, -1)
        p = logp.exp()
        ent = -(p * logp.masked_fill(~action_mask, 0.0)).sum(-1)
        n = action_mask.sum(-1).clamp(min=2).to(ent.dtype)
        return ent / n.log()

    def evaluate(self, obs: dict, idx: torch.Tensor):
        """Log-prob, entropy and value of `idx` under the current parameters."""
        logits, value = self(obs)
        logp = F.log_softmax(logits, -1)
        return (logp.gather(-1, idx.unsqueeze(-1)).squeeze(-1),
                self.entropy(logits, obs["action_mask"]), value)


# ---------------------------------------------------------------------------
# numpy <-> torch
# ---------------------------------------------------------------------------

def to_torch(b, device: str = "cpu", privileged: bool = True) -> dict:
    """A `BatchObs` (or a dict of numpy arrays) as model input."""
    t = lambda x, d=torch.float32: torch.as_tensor(x, dtype=d, device=device)
    out = {
        "zones": {k: t(v) for k, v in b.zones.items()},
        "zone_mask": {k: t(v, torch.bool) for k, v in b.zone_mask.items()},
        "globals": t(b.globals),
        "actions": t(b.legal_actions),
        "action_mask": t(b.action_mask, torch.bool),
    }
    if privileged and b.privileged is not None:
        out["privileged"] = t(b.privileged)
    return out


def count_params(net: nn.Module) -> int:
    return sum(p.numel() for p in net.parameters() if p.requires_grad)
