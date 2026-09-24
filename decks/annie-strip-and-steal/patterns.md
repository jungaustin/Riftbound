# Verified rulings this deck depends on

Rule numbers checked against `data/rules.txt` (RUP4, 2026-07-16) on 2026-08-20.
Do not re-derive these.

## Why mill is not a win condition — 431 Burn Out

- **431.2** — to Burn Out a player: performs as much of the action as possible →
  **recycles their trash into their Main Deck** → **chooses an opponent to gain
  1 point** → completes the action. It is not a loss.
- **431.3.a** — repeated Burn Outs (trash also empty) give a point each time
  until someone passes the Victory Score. **431.3.c.1** — that player wins
  immediately, without waiting for a cleanup. This is the only mill kill, and it
  requires emptying their trash, which the card pool cannot do.
- **440.4** — burning more cards than remain causes a Burn Out mid-effect.
- **194.3** — Victory Score is 8 by default. **194.1.d** — a Burn Out point is a
  normal point source.
- **Consequence for this deck:** never Burn your own deck. Shadow Temple and
  Minefield are downside battlefields here.

## Points and the final point — 471

- **471.1.b.1** — at 1 point from the Victory Score, a **Conquer** only scores if
  you scored *every* battlefield that turn; otherwise you just draw a card.
- **471.1.a.1** — *"points Gained from sources that are not Conquer are not
  beholden to these restrictions."* **Hold scoring and Power Nexus are both
  exempt.** This deck holds, so the usual "stall at 7" failure mode does not
  apply to it.
- **471.2.a / 471.2.b** — conquer abilities trigger on a conquered battlefield,
  hold abilities on a held one. **471.2.c** — at most once per turn per player.
- **469.1** — a conquer trigger requires *gaining* control of a battlefield you
  have not scored this turn, so it never fires while you keep the field.
  Combined with this deck's persistent bodies, **hold triggers fire far more
  often than conquer triggers** — the reverse of a token deck.

## Rune economy

- **164.2 / 416** — a Basic Rune has two independent abilities; a rune already
  exhausted for Energy can still be recycled for Power the same turn. So **runes
  needed = max(energy, power)**. Hextech Ray `{1}{P1}` is a **one-rune** spell.
- **Power is ongoing attrition, not a later cast turn.** A recycled rune goes to
  the bottom of the Rune Deck and must be re-channelled at 2/turn.
- **315.1.b / 415.3.a** — only the Turn Player readies, and only on their own
  turn. A rune exhausted on your turn stays exhausted through their entire turn.
  **Annie - Dark Child readying 2 at end of turn is the deck's answer to this,
  and it does not return recycled runes.**
- **485.7 / 486.7** — the player going second channels an extra rune on their
  first Channel Phase.

## XP — 728-733

- **XP has no default source.** It is gained only by card text. 730.1/730.2 —
  gained and spent by adjusting a tracked value; 729.2 — it is public
  information; 733 — no cap.
- **823.1.c.1** — `[Hunt N]` is functionally *"When I Conquer **or Hold**, my
  controller gains N XP."* This is why Scorchclaw is the XP engine in a hold
  deck.
- **824.1.b.1** — `[Level N]` is *"While you have N or more XP, this card gains
  ..."*, and 824.1.c makes it continuously active/inactive as XP changes.

## Stun, Deflect, Empower

- **423.1.b** — a stunned unit contributes no Might in the combat damage step.
  **423.1.c** — it must still be dealt damage equal to its **full** Might to die.
  **423.1.a.2** — it loses the status in cleanup step 3d. **Stun is tempo, not
  removal**, which is why Vex - Apathetic needs the removal suite to be a lock.
- **441.1.a / 441.1.b** — Empowered is a **binary** state and an Empowered object
  cannot be Empowered again. **Each Kharox fires its Burn 3 exactly once.**
- **809.1.c / 356.2.a.2** — Deflect makes opposing spells cost that much more
  Power as a mandatory additional cost. Because Power is priced by `max()`, the
  tax often costs them **zero extra runes** and lands entirely on attrition.
  Do not rely on Deflect as a rune-count tax.

## Zones, movement, deployment

- **190.4.a / 190.4.c** — you control a battlefield only while you have units
  there; with none, you lose control at the following cleanup. **An empty
  battlefield is a lost battlefield**, which is what makes Gust on a lone holder
  so strong.
- **190.6.a** — a battlefield's controller controls its abilities.
- **144.4 / 810** — a Standard Move is base↔battlefield only. Battlefield→
  battlefield requires **Ganking**.
- **806.3** — units may be played only to your base or a battlefield you
  **control**. **Miss Fortune - Buccaneer overrides this for the whole deck**
  ("friendly units may be played to open battlefields").
- **185.2.d** — tokens enter **exhausted** unless the text says "ready".

## Hidden and speed

- Three speeds: **Neutral** (your turn, no chain open), **Action** (your turn or
  showdowns, open state only, cannot respond), **Reaction** (the only speed that
  responds to something on the chain).
- **Hidden overrides a card's printed speed.** Bone Skewer is Neutral from hand
  and **Reaction speed for {0} from face down** — the flip is a speed upgrade,
  not just a discount. It must be pre-committed on an earlier turn.
- A Hidden card sits at a specific battlefield; **lose the battlefield, lose the
  card**. Limit 1 per battlefield, and 1v1 has 2 battlefields — so the deck's
  real cap is 2 face down at once, whatever `critique` says about copy counts.

## Deck construction

- **103.2.d.2** — every Signature card in the deck must carry the Champion tag
  matching the Legend. **With Annie, only Tibbers is legal.** Death from Below,
  Death Mark, Super Mega Death Rocket! and Spinning Axe are Chaos+Fury and
  illegal here.
- Only the **Chosen** Champion must share a tag with the Legend. Vex - Apathetic,
  Draven - Audacious, Miss Fortune - Buccaneer and Evelynn - Entrancing are all
  Champion Units legal in the **main deck**.
- **`cli.py pool` does not filter the ban list** — it printed Called Shot, Fight
  or Flight, Scrapheap, Draven - Vanquisher and Stealthy Pursuer as legal pool
  entries. Only `cli.py check` enforces bans. Never build straight off `pool`.
