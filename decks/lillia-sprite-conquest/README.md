# Lillia — Sprite Conquest

**Legend:** Lillia - Bashful Bloom (Calm+Mind)
**Chosen Champion:** Lillia - Fae Fawn
**Current version:** `v2.txt`
**Meta toggle:** OFF — no matchup, tier, or popularity claims anywhere in this folder.

## The plan, in one sentence

Make **ready** Temporary Sprites every turn and spend them Conquering battlefields for immediate points, because a Temporary unit dies before my Scoring Step anyway — so I score without ever having to defend what I took.

## Why that works (the three rules facts it rests on)

1. Temporary kills the unit at the start of my Beginning Phase, **before** scoring (728.1.b, 515.2.a/b) — so Sprites can never Hold.
2. **Conquer scores immediately** on gaining control of a battlefield I haven't scored this turn (630.1) — Sprites score fine that way.
3. When the Sprite dies the battlefield goes uncontrolled, so **the same battlefield can be conquered again next turn**. The loop is self-resetting.

Full sequencing notes live in [patterns.md](patterns.md).

## The failure point

**Winning the showdown.** Every point in this deck comes from wiping the defenders at a battlefield while at least one attacker survives (627.3). If I can't do that, I score zero — there is no back-up income.

Cards that address it: 22 of 40 copies. **Charm ×3** sidesteps the fight entirely by moving the defender away; stun (**Back Off ×3**) turns off the defender's damage; −Might (**Smoke Screen ×2**) and +Might (**Discipline ×3**) fix the summed-Might margin; **Soul Shepherd ×3** and **Petal Pixie ×3** raise the swarm's total permanently.

## Second axis

**LeBlanc - Everywhere At Once ×3.** She switches Temporary off at her battlefield, so Sprites parked with her survive the Beginning Phase and **Hold** for points too. She converts a tempo deck into a board deck against opponents who out-grind the conquest loop.

## Version history

- **v2** — split the rune base 9 Mind / 3 Calm and added 3x Charm. **The v1 mono-Mind base rested on circular reasoning**: I cut the Calm-pip cards because the base was mono-Mind, then justified the mono-Mind base by observing there were no Calm pips left. Corrected by computing the actual cost of splitting, since channelling takes runes **off the top of a shuffled 12-card rune deck** (606.1, 103.3.b) — you don't choose, so a split really is a consistency tax and it has to be priced, not assumed away.

  | Split | ≥1 Mind by T2 | ≥2 Mind by T2 | ≥1 Calm by T2 | ≥1 Calm by T3 |
  |---|---|---|---|---|
  | 12 / 0 | 100% | 100% | — | — |
  | 9 / 3 | **100%** | **98.2%** | 74.5% | 90.9% |
  | 8 / 4 | 99.8% | 93.3% | 85.9% | 97.0% |

  At 3 Calm the tax is essentially zero — with only 3 non-Mind runes in the deck it is *arithmetically impossible* to channel four runes without hitting Mind. 8/4 is where it starts to actually cost something (≥2 Mind by T2 drops to 93.3%), which matters because Zilean + Smoke Screen in one turn wants two Mind recycles.

  Changes: **+3 Charm** (E1 P1, rated 68) — for one energy it moves an enemy defender off the battlefield regardless of its Might, which beats every damage-based answer in a deck whose only failure point is winning the showdown. **−2 Crescent Strike, −1 Smoke Screen.** Curve improved from 2:9 / 3:15 to 2:12 / 3:14; average cost 3.52 → 3.40.

  **What this costs:** the deck now has *zero* hard removal. Charm and Back Off both only delay — against a single large Deflect or Tank unit that has to actually die, v2 can't kill it, it can only keep relocating or stunning it. That's an accepted trade because the conquest loop re-scores the same battlefield every turn anyway, but it's a real hole.

- **v1** — first build. Superseded; kept for the reasoning trail. Notable departures from the raw pool ranking, and why:
  - ~~**Rune deck is 12x Mind, zero Calm.**~~ **Wrong — see v2.** The v1 argument was that all 14 Power pips were Mind so Calm runes would do nothing; that was true only because I had already cut every Calm-pip card *on the grounds that the base was mono-Mind*. Back Off (**76**) still beats Rune Prison (**70**) on its own merits — Reaction speed and a card — but Charm (**68**) and Tricksy Tentacles (**66**) were cut for a reason that didn't survive checking.
  - **Lillia - Protector of Dreams rated 82 and is not in the deck.** She's a payoff, not an engine, and she's the wrong domain for this shell. See "Open questions" below.
  - **Five cards rated 69–74 are absent** — Heimerdinger (72), Trevor Snoozebottom (71), Shadow Watcher (73), Sprite Queen (74), Wraith of Echoes (69). Every one is a genuinely strong card that competes for a curve slot the engine pieces already own. They are the add-list, in that order.
  - **Sprite Burst at 2 despite an 80.** It is the most powerful single card in the deck and the eighth 5+ cost card; a third copy makes the opening hands worse.
  - **Meditation (65) cut entirely** for Soul Shepherd's third copy and Smoke Screen's third. Meditation exhausting a spent Sprite for two cards is real, but Discipline and Smoke and Mirrors and Back Off already replace themselves — nine cantrips is enough draw.

## ⚠ Known defect in v1/v2 — the premise is wrong

Both versions were built on **"Temporary units can never Hold."** That is false. `reference/riftbound_temporary_interactions.txt` — which the skill requires be read *before* the pool pass, and which I skipped on this build — states the opposite, with rulings citations. Temporary is a **chain-using triggered ability** that can be responded to, and a Reaction-speed replacement (Hidden Sprite Call, {0 energy}) played *in response* leaves a token alive at the Scoring Step that **holds and scores**.

The conquest plan still works and is still the fastest clock, so v2 is not invalid — but it is under-built. What changes:

- **Hidden Sprite Call is a holding engine**, not just a showdown ambush. It wants to be pre-hidden on an earlier turn, every turn.
- **LeBlanc is no longer the sole route to holding.** Still the best (converts every Sprite, no per-turn card cost), but not load-bearing the way v2's README claims.
- **Dusk Rose Lab jumps from 56 to a top-tier battlefield for this deck** — it converts each doomed token into a card *and* fizzles the Temporary trigger, and with a Hidden replacement it yields +1 card, battlefield kept, and a point, every Beginning Phase.
- The **speed gate** matters: Sprite Call from hand is Action speed and cannot answer the trigger. Only pre-Hidden cards, Reaction spells, and Ambush units can.

Full corrected sequencing is in [patterns.md](patterns.md). **v3 has not been built yet** — it needs a re-rate of the affected slice (Hidden density, Sprite Call count, the battlefield trio, LeBlanc's count) rather than a card swap.

## Known open questions

1. **Is Fae Fawn the right champion?** She is the *engine* (a free Sprite every time she moves, available from the Champion Zone on turn 2, three energy). Lillia - Protector of Dreams is the *payoff* (Tank on every token, +1 Might per token played). If the intended champion is Protector of Dreams, the Sprite package survives unchanged but the shell shifts Calm: the Mind movement cards (Smoke and Mirrors, LeBlanc) give way to bodies she can shelter behind her Tanking Sprites, and the rune deck stops being mono-Mind. That is a different deck, not a swap.
2. **Is 3x Zilean too many 6-rune cards?** He's the biggest multiplier and the critique tool wants engine pieces at 3, but he only works while committed to a battlefield.
3. **Battlefields are three independent bets** — only one is used (644.5). Windswept Hillock was cut for being symmetrically dangerous on a 2-battlefield board; worth revisiting if the deck leans harder on Fae Fawn relocation.
4. Untested against anything. No play data.
