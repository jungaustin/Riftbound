# How the agent learns

The design decisions and their rationale live in `PLAN.md`. This is the
operating manual: what the algorithm is, how to read a run, and how to change
things and know whether you helped.

---

## 1. The algorithm: PPO

**Proximal Policy Optimization** — model-free, **on-policy**, actor-critic
**policy gradient**.

| part | what it is |
|---|---|
| actor | `π(a \| s)` — a *probability distribution* over legal actions, **sampled** |
| critic | `V(s)` — a win probability, used only as a variance-reduction baseline |
| advantage | GAE, `λ = 0.95` |
| discount | `γ = 1.0` (terminal reward only) |
| stability | clipped surrogate objective — PPO's trust region |
| opponent | self-play + a PFSP pool of frozen past selves |

### There is no Q

Nothing learns "the value of action *a* in state *s*", and nothing ever takes a
`max` over actions. That was deliberate: optimal play in a two-player
hidden-information game is generally a **mixed** strategy, and a deterministic
argmax cannot represent bluffing — it is maximally exploitable. See
`PLAN.md` and the `rl-training-design-thesis` memory for the full argument.

**The one thing that looks like Q-learning and is not.** The action head emits
one number per legal action:

```python
def logits(self, h, actions, action_mask):          # nets.py
    x = torch.cat([h.expand(...), actions], -1)
    return self.act_head(x).squeeze(-1).masked_fill(~action_mask, NEG_INF)
```

Those are **logits of a softmax**, normalized into a distribution and sampled —
never maxed. `play.py --deterministic` takes the argmax, but that is for
inspection only; training never does.

### Why the reward is only ±1 at the end

`γ = 1.0` with terminal-only reward makes the critic a **literal win
probability**, which is the deck-evaluator deliverable and what `net.win_prob()`
returns. There is no "+0.1 per point" bonus, deliberately: shaped reward teaches
the shape, not the game.

If you ever add shaping, use the **potential-based** form
(`F = Φ(s') − Φ(s)`), which provably cannot change the optimal policy. And the
potential must be **turns-to-win**, not score — see §5.

---

## 2. The network

~1,008,000 parameters. Everything is sized from `Encoder.shapes()`, so a new
observation zone reaches the network automatically.

```
per-zone card rows ──► card_enc (shared MLP)  ──► masked mean ‖ max pool ─┐
                       ONE encoder for every zone                         │
                                                                          ▼
                                                 globals (135) ──► trunk ──► h
                                                                          │
                            ┌─────────────────────────────────────────────┤
                            ▼                                             ▼
        act_head(h ‖ each legal action row) ──► logits        value_sym(h) ──► V
                                                              value_priv(h ‖ hidden) ──► diagnostic
```

Zones: `hand`, `board`, `battlefields`, `facedown`, `legends`, `chain`,
`decks`, `champions`. `row_dim` 283, `card_dim` 237, `globals` 135.

**Two properties worth knowing:**

- **DeepSets, one shared card encoder across every zone.** That is why all zones
  must share `row_dim`.
- **No card-ID one-hots.** Cards are described by attributes and behaviour, so
  the net generalizes to cards it has never seen. This is also why a rules fix
  does not invalidate a checkpoint — it changes a card's *features*, not the
  vocabulary.

### The two critics

`value_sym` sees exactly what the policy sees and **drives learning by default**.
`value_priv` additionally sees the opponent's hand and facedowns, is trained on
the same returns as a diagnostic, and is fed a **detached trunk** so it cannot
shape the features the policy reads.

`hp.privileged_critic` flips which one leads. `test_ppo` [7] enforces the
guarantee: scrambling hidden information leaves every action logit bit-identical,
and the auxiliary critic's gradient never reaches a shared tensor.

`net.win_prob()` always returns the honest, policy-side number. That is the only
value ever shown to a person.

---

## 3. Hyperparameters (`HP` in `ppo.py`)

| | | | |
|---|---|---|---|
| `gamma` | 1.0 | `clip_coef` | 0.2 |
| `gae_lambda` | 0.95 | `ent_coef` | 0.01 (on **normalized** entropy) |
| `lr` | 3e-4, annealed | `vf_coef` | 0.5 |
| `n_envs` | 64 | `max_grad_norm` | 0.5 |
| `rollout` | 2048 transitions | `privileged_critic` | **False** |
| `minibatches` | 4 | `pool_frac` | 0.5 |
| `update_epochs` | 4 | `pool_every` / `pool_capacity` | 10 / 20 |

`rollout` is **transitions per update**, not steps per env.

---

## 4. Reading a training run

```
[ 40/150] steps= 106,048 eps= 59 len= 35.0 turns= 5.6 seat0=56% trunc=0.0%
          | ent=0.236 kl=0.0031 clip=0.03 ev=+0.68 | 320 st/s
```

| field | meaning | worry when |
|---|---|---|
| `ev` | explained variance — does `V(s)` predict outcomes? | **The one to watch.** Stuck near 0 → advantages are noise → nothing can learn |
| `ent` | normalized entropy, 1.0 = uniform, 0 = deterministic | crashes to ~0 in the first few iterations = premature collapse |
| `kl` | how far the policy moved this update | spikes → step too large, lower `lr` |
| `clip` | fraction of samples hitting the PPO clip | persistently > 0.3 → steps too large |
| `trunc` | games hitting the cap (reward 0 both sides) | anything high → training on garbage |
| `seat0` | self-play first-player win rate | **not a skill measure** — see §5 |

Entropy is normalized by `log(n_legal)`, so 1.0 means "uniform" whether there
are 2 legal actions or 40. Low entropy is not automatically bad: in a solved
combat position you *want* it near 0.

**When it does not learn**, check in this order (`PLAN.md` §4): action mask
alignment → reward sign and seat attribution → observation canonicalization →
advantage normalization → learning rate. It is one of the first three about 90%
of the time, which is why `test_env` and `test_ppo` cover all three permanently.

---

## 5. The trap: self-play win rate is meaningless

Both seats are the same network, so self-play sits near 50% by construction and
**can never tell you whether you are improving.**

Measured twice on this project, with the opponent pool switched on the second
time:

| run | best | last | drop |
|---|---|---|---|
| Phase 4 (procedural decks) | 69.0% vs greedy | 60.2% | **8.8 pts** |
| v3 (real decks, `pool_frac=0.5`) | 54.5% vs greedy | 47.0% | **7.5 pts** |

Late training made it **worse against a fixed opponent** while `vs_random` stayed
flat. That is self-play drift, and the PFSP pool did not prevent it — the pool is
one lineage of past selves, not a population.

**Always measure against a fixed external opponent, with paired seeds swapped
across seats.** At victory 3 going first is worth ~64%, so an unpaired number is
off by ~14 points. `eval.duel` already pairs.

### The measurement ladder, weakest to strongest

1. **vs random** — sanity only. 90% just means it is not broken.
2. **vs greedy** — a fixed external heuristic. Real signal.
3. **per-deck breakdown** (`eval.per_deck`) — the aggregate cannot distinguish
   "decent at all 30 decks" from "strong at 27, hopeless at 3".
4. **vs past selves** — Elo over the pool. Catches drift.
5. **exploitability** — train a fresh policy purely to beat a frozen one; how
   much it wins by is how exploitable you were. **The only real measure, and it
   is not built yet.**

### Tempo, and why the potential must not be score

Turns-to-win is `ceil((V − points) / 2)`, so scores **pair up**: at V=8, 6 and 7
are both one turn from winning and the 7th point buys no tempo at all. What
decides which scores are efficient is the parity of `(V − s)`, so it **inverts**
when V changes parity — Aspirant's Climb (V=9) makes 7 a milestone where normally
it is the wasted point.

Two consequences:

- Shaping on score difference asserts "a point is a point, linearly", which is
  false. Use turns-to-win as the potential.
- **The victory-3 curriculum teaches the inverted parity.** Do not expect tempo
  subtlety from it; it is a warm-start for mechanics only.

This is also the arithmetic behind "is pushing a unit in for one point worth
losing it?" At 6 of 8 the point saves a turn. At 7 of 8 it saves nothing and the
unit was spent for free. Both seats' turns-to-win are now input features.

---

## 6. Changing things

### A. Change what it sees — `obs.py`. Highest leverage.

The observation is the contract: the policy can never learn what does not reach
it. Recipe:

1. Add the column or zone — bump `CTX_DIM` / `GLOBAL_DIM`, extend `ZONES`, write
   the builder.
2. `nets.py` needs **nothing** — it reads `Encoder.shapes()`.
3. Run `test_env`. Four gates catch the real mistakes: mirrored positions must
   encode byte-identically, hidden information must not reach the policy, every
   declared zone must reach the network, and **every GameState field must be read
   or classified in `OBS_UNREAD`** ([4e]).
4. Old checkpoints are now invalid — the shape changed.

`OBS_UNREAD` exists because `victory_bonus` was invisible for months and nothing
failed. Being on that list is a *claim* that the policy does not need the field.

### B. Change what it plays — `config.py` and the dealers. Underrated.

`victory_score` (anneal 3 → 5 → 8), `deck_known_prob`, `units_only`, and
`v1_deal` (procedural) vs `deck_pool_deal` (the 30 real lists). The distribution
often matters more than the algorithm.

### C. Change how it learns — `HP`, `nets.py`. **Start here last.**

Least leverage per hour and hardest to attribute; you need many seeds to
distinguish a real gain from noise.

---

## 7. Commands

```bash
# generalist, all 30 real decks, with the per-deck breakdown at the end
python3 rl/ppo.py 150 --real-decks --victory 3 --per-deck 12 --out rl/runs/NAME

# anneal the curriculum: warm-start from a finished run
python3 rl/ppo.py 150 --real-decks --victory 5 --init rl/runs/NAME/best.pt --out rl/runs/NAME5

# narrow the pool: three archetypes, or one (a mirror-match specialist)
python3 rl/ppo.py 150 --real-decks --decks akali,darius,lillia-protector
python3 rl/ppo.py  60 --real-decks --decks fae-fawn --init rl/runs/NAME/best.pt
```

`--init` asserts the checkpoint's observation layout matches. A **rules fix** with
no observation change → loads fine, warm-start it. **Any** observation change →
refuses, loudly. Checkpoints record the engine commit in `ck["engine"]`.

One iteration ≈ 2048 transitions ≈ **9 seconds** on CPU, so 150 iterations is
roughly 22 minutes plus evaluation.

---

## 8. Known gaps

- **108.3.d — the Chosen Champion cannot be played from the Champion Zone.**
  Every deck is understated by one guaranteed threat. The biggest engine gap.
- **Truncation pays 0 while losing pays −1**, so a losing player has an incentive
  to stall. Not yet biting (`trunc=0.0%`) but it will once the policy is strong,
  and victory 8 gives it far more room. Fix: decide a capped game on points.
- **No sterile-loop detection.** `state_hash` makes it cheap — an exact repeat
  with the same seat to move is provably a livelock.
- **No exploitability probe**, so "is it actually good" is still unanswered.
- **The per-deck spread conflates** agent weakness with deck strength. Needs a
  greedy-vs-greedy per-deck baseline to separate them.
