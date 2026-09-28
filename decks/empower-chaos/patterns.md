# Verified rulings and sequencing — Empower/Chaos

Rule numbers are RUP4 (2026-07-16, `data/rules.txt`). Do not re-derive these.

## Empower

- **827.1.c.1** — `[Empower] {Cost}` is functionally *"{Cost}: Empower this. Play only
  if not Empowered."* It is an **Activated Ability**, so it is yours to use on your turn.
- **828.1.b.1** — `[Empowered][>] <Text>` means *"While I have the Empowered status,
  this card gains '<Text>'."* The ability is **live only while the status is**.
- **828.1.d** — if that dependent ability is "When I become Empowered", it triggers
  when the source becomes Empowered.
- **441.1.b / 441.1.c** — an Empowered object cannot be Empowered; instructing it does
  nothing. **441.1.c.1** — an effect may explicitly grant permission to be Empowered
  multiple times (Kayle, Justified).
- **442.1** — Disempower removes the Empowered status. **442.1.a** — it affects only
  things currently Empowered.
- **441.3.a / 442.2.a** — both are Limited Actions; players may only do them when a
  Game Effect directs it.

**The consequence that decides card selection:** a "when I become Empowered" effect
has already resolved by the time the status is removed, so it survives the end-of-turn
disempower. A `[Empowered][>] I have <static>` ability does **not** — it switches off
with the status. Free Empowers are therefore only worth running alongside the first
kind, or as a one-turn combat trick on your own turn.

## Hidden — the engine's hard ceiling

- **811.1.b** — *"While this card is in your **hand** or in your Champion Zone on your
  turn during an Open State, you may pay `{A}` to hide this facedown at a battlefield
  you control **that doesn't already have a facedown card hidden there** for as long as
  you control that battlefield. **Beginning on the next turn**, this gains [Reaction]
  and you may play this, ignoring its base cost."*

  Four separate constraints in one sentence: it must be in **hand**; **one facedown
  per battlefield**; you must **control** that battlefield; and it is **not playable
  until the next turn**. With 486.4 setting Battlefield Count at **2** in 1v1, the
  ceiling is two facedown cards, and realistically one.
- **811.1.c.3** — playing from facedown **opens a chain**. So after it resolves you are
  back in an Open State on your own turn, and **you may hide again the same turn**.
- **811.1.d.1 / 811.1.d.2** — a hidden permanent must be played **to that battlefield**,
  and its play-effect targets must be chosen from that battlefield. Tornado Warrior's
  "empower something **here**" already matches this, so it costs nothing extra.
- **811.3** — a card with Hidden may always be hard-cast normally instead, at normal
  timing with no targeting restriction.

## The Tornado Warrior loop, in order

1. Turn N, Main, Open State: pay `{any rune}`, **hide** Tornado Warrior at a
   battlefield you control.
2. Turn N+1: **play it from facedown for `{0}`**. It enters at that battlefield.
   Empower something there. (Disempower is queued for end of turn.)
3. Same turn: **Pack of Wonders** — Exhaust, return Tornado Warrior to hand. Free, and
   the gear readies at every Awaken (315.1.b).
4. Same turn, still Open: **re-hide** Tornado Warrior. The facedown slot it just
   vacated is free.
5. Turn N+2: repeat. **Net cost: one rune of attrition per free Empower.**

**The trap in step 4.** The hide must come *after* the bounce, so Tornado Warrior has
already left the battlefield. **190.4.a/c** — you keep control only while you have
units there, and lose it at *the following cleanup*. The hide is therefore legal, but
if Tornado Warrior was your only body there you lose the battlefield at cleanup and
**811.1.b takes the facedown card with it**. Keep a second persistent body parked at
that battlefield, permanently. This is the single most likely way to throw the game.

Cheapest ways back to hand, all builds: **Pack of Wonders** `{2}` gear (free,
repeatable), **Gust** `{1}` [Reaction] (a unit ≤3 Might — Tornado Warrior is exactly 3),
**Retreat** `{1}` (Mind), **Windsinger** `{2}` (Calm/Chaos, and itself Hidden).

## Reckoner's Arena + Nasus + Sanction (Calm/Chaos)

The exact sequence, which is easy to get wrong:

1. Nasus, Ascended is at Reckoner's Arena, holding it. He is **not** Empowered — last
   turn's free Empower was stripped at end of turn.
2. Your Beginning Phase starts. The **hold** trigger goes on the chain.
3. **In response** — Sanction is a `[Reaction]`, so this window is legal — Empower
   Nasus. He now has `[Empowered][>] When I conquer, you score 1 point`.
4. The hold trigger resolves. **Reckoner's Arena**: "When you hold here, activate the
   conquer effects of units here" → Nasus's conquer effect activates → **score**.
5. You gain the hold point *and* Nasus's point.

Do **not** try this with Tornado Warrior instead of Sanction: playing from facedown
grants `[Reaction]` (811.1.b), so the timing is legal, but Tornado Warrior must be
played **to the battlefield it was hidden at**, and it empowers something **here** —
so it only works if Tornado Warrior was hidden at Reckoner's Arena specifically.

**471.2.c** — score abilities trigger only once per turn per player. One extra point
per turn, not more.

## Rules facts already recorded elsewhere that bind here

- **rules-fact 9 / 190.4.c** — an empty battlefield is a lost battlefield. These are
  *persistent-body* decks, so **hold triggers fire constantly and conquer triggers
  almost never** — the opposite of the Lillia token decks. That is the whole reason
  Reckoner's Arena is worth a slot.
- **rules-fact 7 / 471.1.b.1** — the 8th point by Conquer needs **every** battlefield
  scored that turn. **144.4** forbids battlefield→battlefield movement without
  **Ganking**, which is why the Body build runs Miss Fortune for it.
- **124.1** — a Game Object changing zones to/from a non-board zone loses all temporary
  modifications **including statuses**. So flicker (Temporal Breach, Portal Rescue)
  clears Empowered, which is a Disempower substitute that also re-buys the body.
- **707/708** — a unit "is Mighty" at **5 or more Might** (Sunken Temple).
