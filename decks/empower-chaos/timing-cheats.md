# Playing cards at speeds they don't have

Found by the user, 2026-09-10. Verified against RUP4.

## The rule

**An effect that instructs you to play a card never checks that card's timing.**

- **806.1.b** — Action "grants the corresponding card or effect **permission to be
  played or activated**". Action and Reaction are *permissions for a player to
  initiate a play*. They are not properties consulted when something else plays the
  card for you.
- **353-355 (The Process of Play)** — the play sequence is: move to chain → make
  choices → pay costs → finalize. **Timing is never re-checked at any step.**
- **354.3** — "If another Card Effect or ability is currently resolving, continue
  resolving it before proceeding with any further steps of this process." Cards are
  explicitly expected to be played *during* another resolution.

So: get a play-effect to resolve inside a Reaction window, and whatever it plays
arrives at Reaction speed regardless of its printed speed.

## Stage 1 — the Reaction-speed initiators

Only these can open the window.

- **Any card with [Hidden]** — 811.1.b grants it `[Reaction]` on the flip. This is the
  deepest well by far, and it is why Chaos/Mind are the domains for this.
- **Heedless Resurrection** `{2}{P1}` Chaos — printed `[Reaction]`, and itself a play
  effect. The one-card version.
- **Thrill of the Hunt** `{2}{P1}` Fury/Body — printed `[Reaction]`, banish-and-replay.
- **Bone Skewer** `{2}{P1}` Chaos, **Temporal Breach** `{2}{P1}` Mind — Hidden, and
  both are play effects.
- **Ava Achiever** `{5}` Mind — on attack, plays a Hidden card from hand ignoring cost.
- Any **Ambush** unit (822.1.b grants Reaction while being played to a battlefield
  where you have units).

## Stage 2 — every effect that plays a card (23 in the format)

| Domain | Cards |
|---|---|
| **Chaos (7)** | Bone Skewer, Heedless Resurrection, **Fizz - Trickster**, Tail-Cloaked Matriarch, Kharox, The Harrowing, Soulgorger |
| **Mind (6)** | Temporal Breach, Portal Rescue, The Zero Drive, Jayce Man of Progress, Ava Achiever, Kai'Sa - Evolutionary |
| **Order (5)** | Undying Loyalty, Baited Hook, Spectral Matron, Glasc Mixologist, Rift Herald |
| **Fury (2)** | Blind Fury, Rell - Magnetic |
| **Body (1)** | Dazzling Aurora |
| **Dual** | Thrill of the Hunt (Fury/Body), Arcane Shift (Mind/Chaos) |

Only two play **spells** rather than units: **Fizz - Trickster** and
**Kai'Sa - Evolutionary**. Only **Kharox** reaches an *opponent's* trash.

## The user's line, verified end to end

1. **Tornado Warrior** hidden → gains `[Reaction]` → flip it for `{0}` in response to
   something on the chain.
2. Its play effect: **empower Tail-Cloaked Matriarch**.
   *Constraint:* 811.1.d.2 restricts a hidden permanent's play-effect targets to the
   battlefield it was hidden at, and the card says "empower something **here**" — so
   **the Matriarch must be standing at that exact battlefield.** This is the hard part.
3. Matriarch: "When I become Empowered … play a unit from your trash with Energy cost
   ≤`{3}` and Power cost ≤`{any rune}`, **to your base**, ignoring its cost."
   → **Fizz - Trickster is `{3}{P1}` — he qualifies by the exact margin, on both halves.**
   *Note:* "to your base" is an explicit destination, so 811.1.d.3 does not drag Fizz to
   the battlefield (same shape as the Tideturner example under 811.1.d.2).
4. Fizz: "When you play me, you may play a spell from your trash with Energy cost
   ≤`{3}`, **ignoring its Energy cost**. Recycle that spell after."
   *Note:* Fizz was played by an ability, **not** from Hidden — so his effect carries
   **no** Hidden targeting restriction and can reach anywhere.
5. A **Neutral-speed spell resolves at Reaction speed.**

**Costs and limits:** you still pay the spell's **Power** cost (Fizz says so). 355.8
still applies — the spell must have legal targets or the play is blocked outright.
The spell is **recycled** (bottom of deck), so it does not loop.

## What is actually worth flashing in this way

The prize is **Neutral-speed** spells — the ones that can never respond to anything.
Movement is the standout, because moving a unit mid-combat is a blowout no Neutral
spell is priced to do:

| Spell | Cost | Why at Reaction speed |
|---|---|---|
| **Isolate** | `{2}` Chaos | Move an enemy unit off a battlefield — **removes an attacker or defender mid-showdown** |
| **Twilight Step** | `{2}{P1}` Chaos | Move a unit ≤3 Might, either side |
| **Temptation** | `{2}` Chaos | Move an enemy unit, with `[Repeat]` |
| **Whirlwind** | `{3}{P1}` Chaos | Each player may return a unit to hand |
| **Shadows of the Past** | `{3}{P1}` Chaos | Return 2 units from trashes |
| **Invert Timelines** | `{3}{P1}` Chaos | Each player discards hand, draws 4 |

## Other engine cards worth knowing

- **Guerilla Warfare** `{2}{P1}` **Mind/Chaos** — "Return up to two cards with [Hidden]
  from your trash to your hand. **You can hide cards ignoring costs this turn.**"
  This is the best Tornado Warrior support card in the format: it rebuys the engine
  *and* makes the re-hide free. It is dual Mind/Chaos, so **only the Mind/Chaos build
  can legally run it** (103.1.b.4).
- **Heedless Resurrection** `{2}{P1}` Chaos — the whole two-stage trick in one card, at
  Reaction speed. Kill Tornado Warrior after it has already empowered, play something
  bigger from the trash.
- **The Zero Drive** `{3}` Mind — banish units onto it over time, then
  "`{3}{Mind}`, Banish this: **Play all units banished with this**, ignoring their costs."
- **Kharox** — the only card that plays from the **opponent's** trash, and its Burn 3
  fills that trash first. It is self-fuelling.

## Judge questions

1. Does the opponent get priority between each link? **Yes** — one item resolves per
   priority round, so a four-link chain gives them three windows to respond. The line
   is not uncounterable.
2. Whether 811.1.d.3 reaches a unit played by a *separate triggered ability* that was
   merely caused by a hidden permanent's play effect. Reading says no (it binds "a play
   effect of a hidden permanent", and the Matriarch's trigger is her own ability), and
   Matriarch's explicit "to your base" makes it moot here — but confirm before relying
   on it with a different Stage-2 card.
