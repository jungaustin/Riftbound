# Kennen — Flow & wide: every card, and why

`kennen-flow-v1.txt` · Order+Chaos · 6 Order / 6 Chaos · avg 3.08 runes · attrition 18
14 of 40 cards cost ≤2 runes.

**Plan in one sentence:** play cards out of your **trash** and **facedown** zones all
game to keep Kennen Empowered, flood the board with tokens, and swing with an anthem on.

---

## First — an honest correction to the ask

You asked for *"a bunch of assault triggers at once from Kennen."* **That is capped at
one per turn**, and it is worth knowing why before you build around it.

Kennen's ability is *"[Action][>] **Disempower me, Exhaust:** Give a unit [Assault 2]
this turn."* **Exhaust is part of the cost**, and only your Awaken readies things
(315.1.b) — so the Legend can do it exactly **once per turn**.

**The one way to get a second:** **Hall of Legends** — *"When you conquer here, you may
pay `{1 energy}` to ready your legend."* I checked every card in the format; it is the
**only** card that readies a Legend. That is why it is in the battlefield slot and why
it is close to mandatory here. Conquer → ready Kennen → Assault 2 again. **Two per turn,
maximum.**

So the "swing with everything" feeling in this deck does **not** come from Kennen's
ability. It comes from **going wide with tokens and turning on an anthem** — which is
what Order is actually the best domain at. Kennen's Assault 2 is the finishing +2 you
point at whichever unit needs to win its fight.

## The Legend and Champion

**Yordle, Kennen - Heart of the Tempest** — *"When you play a card from **anywhere other
than your hand**, empower me."* Every Flow spell, every facedown flip, and every
play-from-trash effect re-arms him. Since 441.1.b stops an already-Empowered object being
Empowered again, the rhythm is: **empower once → spend it on Assault 2 → re-empower with
the next non-hand play.** The deck is built so that happens every turn.

**Kennen, Storm of Shuriken** *(Chosen Champion, `{3}{P1}` 4M)* — *"When you play me,
[Burn 2]. When I conquer, give a spell in your trash **[Flow] equal to its cost** this
turn."* Burn 2 stocks the trash; the conquer clause then lets you play **any** spell out
of it, which is another non-hand play that re-empowers the Legend.

> **Correction (user-caught).** This slot originally held **Fizz - Trickster**, on the
> reasoning that he shares the **Yordle** tag with the Legend. That is wrong.
> **133.8.b**: *"Tags used to link Legends, Champion Units, and Signature cards are known
> as **Champion Tags**."* Yordle is a species tag — it sits on 35 cards and co-occurs
> with Kennen, Poppy, Rumble, Teemo and Vex — so it cannot satisfy 103.2.a.2. The only
> legal Chosen Champions here are **Kennen, Storm of Shuriken** and **Kennen, Keeper of
> Balance**. The repo's validator shared the same bug and has been fixed
> (`riftbound/model.py: NON_CHAMPION_TAGS`, re-derivable via
> `tools/derive_champion_tags.py`). The 100-player Vendetta tournament list in
> `decks/meta/ven-4-kennen-chaos-order.txt` independently runs this exact
> configuration — Storm of Shuriken in the Champion Zone, 3x Fizz in the main deck.

**3x Fizz - Trickster** `{3}{P1}` 3M — *"When you play me, you may play a spell from your
trash with Energy cost no more than `{3}`, ignoring its Energy cost. Recycle that spell
after you play it."* Still fully legal in the **main deck** — 103.2.b lets any
colour-legal Champion Unit in; only the *Chosen* Champion needs the tag match. He does three jobs at once:
1. A free spell from the trash.
2. **That spell is itself a card played from a non-hand zone**, so it empowers Kennen —
   Fizz effectively empowers Kennen *twice* in one card if he was played from a non-hand
   zone himself.
3. He unlocks the Reaction-speed trick from `timing-cheats.md`.
*Limit:* he **recycles** the spell to the bottom of your deck, so it does not loop.

## The trash-filling package (this is the engine's fuel)

**3x Lightning Rush** `{1}` Order/Chaos — *"Look at the top 3, draw one, **put the rest
into your trash**."* The best one-drop in the deck: it digs, and it loads two Flow targets
into the trash at the same time. Everything downstream needs a stocked trash.

**2x Kennen, Storm of Shuriken** `{3}{P1}` 4M — *"When you play me, [Burn 2]. When I
conquer, **give a spell in your trash [Flow] equal to its cost this turn**."* Burn 2 fills
the trash; the conquer clause then lets you play **any** spell out of it — which is
another non-hand play, which re-empowers the Legend. At 2 because it wants to be
conquering, not sitting.

**Minefield** *(battlefield)* — self-mill 2 on conquer. Fuel for you, a cost for them.

## The Flow package — every cast empowers Kennen

**3x Twilight Step** `{2}{P1}` — *"Move a unit with 3 Might or less."* `[Flow] {4}{Chaos}`.
Cheap, and moving an enemy unit **off** a battlefield is how you take it.

**3x Lacerate** `{2}{P1}` — *"Choose a unit. **If it's [Empowered], disempower it.** Then
kill it if it has 3 Might or less."* `[Flow] {4}{Order}{Order}`. Your removal, and note
the disempower clause is real interaction against a mirror or any Empower deck.

**3x Up from the Deep** `{3}` — two 1-Might Tentacle tokens. `[Flow] {3}`. **The best Flow
card here** because the Flow cost equals the printed cost — no premium — and it feeds the
go-wide plan directly. Cast it, then cast it again from the trash later.

**2x Dragon Form** `{3}` — *"Choose a unit. **Its base Might becomes 5** this turn."*
`[Flow] {3}`. Turns any 1-Might Recruit token into a 5-Might attacker, and again the Flow
cost matches the printed cost. This is the card that makes a token board threatening.

**2x Stargazer** `{5}` 5M — *"Spells with [Flow] you play from your trash cost `{2}` less,
to a minimum of `{1}`."* Turns Up from the Deep and Dragon Form into `{1}` and Lacerate's
Flow into `{2}{Order}{Order}`. At 2 because it is a build-around you want one of.

## The Hidden package

**3x Tornado Warrior** `{3}` 3M Hidden — the free Empower, and **flipping it is itself a
non-hand play**, so it empowers Kennen *and* empowers a unit in the same action. The
single most efficient card in the deck for this Legend.

**2x Guards!** `{3}` Hidden — *"Play a 2 Might Sand Soldier unit token. You may pay
`{Order rune}` to ready it."* A body from the facedown zone: another non-hand play, and
a token for the wide plan. The ready clause matters — a readied token can Move and conquer.

## The go-wide package

**3x Daring Poro** `{2}` 2M **[Assault]** — a two-drop that attacks as a 3. Cheap bodies
are what an anthem multiplies.

**2x Noxian Emissary** `{2}` 2M — Empower `{1}{Order}` (the **cheapest Empower cost in
Order**) → *"[Empowered] [Deathknell] Play two 1 Might Recruit unit tokens to your base."*
Dies into two more bodies. Also a legal Tornado Warrior target if you would rather not
pay.

**3x Vanguard Captain** `{3}{P1}` 3M — *"**[Legion]** — When you play me, play two 1 Might
Recruit unit tokens here."* (Legion = you have played another card this turn, which is
trivially true in a deck of one- and two-drops.) **Three bodies at a battlefield for
`{3}`** — the best rate in the deck and the core of the wide plan.

## The payoff — anthems

Per rules-fact 5, combat damage is simultaneous and equal to Might, so equal Might means
both units die and **nobody holds**. One extra Might converts every trade into a
conquest. On a board of 1-Might Recruits, an anthem is not incremental — it is the deck.

**2x Garen - Commander** `{6}{P1}` 5M — *"Other friendly units have +1 Might **here**."*
Permanent, and it stacks with everything else.

**1x Undertitan** `{6}{P1}` 5M — *"When you play me, give your other units **+2 Might this
turn**."* The alpha-strike button: play it on the turn you swing. Also *"As I'm revealed
from your deck, [Add] `{2 energy}`"*, which is live off Lightning Rush.

**2x Aurok General** `{5}` 5M — Empower `{3}{Order}` → *"Your units that are **[Empowered]**
have +2 Might (including me)."* Narrower than the other two because it only pumps
*Empowered* units — but Tornado Warrior can empower a unit for free each turn, and Noxian
Emissary empowers itself for `{1}{Order}`.

## Battlefields

**Hall of Legends** *(neutral / mandatory)* — the only legend-readying card in the format;
doubles Kennen's Assault 2. Question 2: a generic opponent gets far less from it than you
do, since most Legends' abilities are not the deck's engine.

**Minefield** *(on the play)* — self-mill on conquer is a **cost** for nearly every deck
and **fuel** for this one.

**Seat of Power** *(on the play, vs slow decks)* — conquer the other battlefield first,
then this one, for a multi-card draw.

## What this deck does badly

- **Attrition 18** and **8 cards at 5+ runes.** It is the clunkiest of the four.
- **Anthems are `{6}`.** Before turn 6 the wide board is a pile of 1-Might tokens that
  trade with nothing.
- **Order pips are heavy** (10 Order hard pips against 6 Order runes, 1.7 per rune).
  Lacerate's Flow cost of `{4}{Order}{Order}` is often uncastable; treat it as a hard-cast
  removal spell that *occasionally* rebuys.
- **No answer to a big Deflect unit.** Lacerate caps at 3 Might; there is no burn here.
