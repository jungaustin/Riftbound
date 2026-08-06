# Verified rulings and sequencing this deck depends on

Every entry below was looked up in the Core Rules via `cli.py rules`, not recalled. Do not re-derive these.

## Temporary and scoring

- **728.1.b** — Temporary is shorthand for *"At the start of this permanent's controller's Beginning Phase, before scoring, kill this."*
- **515.2.a / 515.2.b** — the Beginning Phase runs its start-of-phase triggers, then the **Scoring Step**. Temporary resolves first.
- **630.2 (Hold)** — you score by having control of a battlefield *during your Beginning Phase*.

> ### CORRECTION (v1/v2 were built on a false premise)
> v1 and v2 asserted **"Sprites can never Hold."** That is **wrong**, and `reference/riftbound_temporary_interactions.txt` (RiftJudge, rules-cited) says so directly: *"A Temporary unit CAN hold a battlefield and score. The keyword does not restrict holding or scoring. If it is present at the Scoring Step, it scores normally."*
>
> The mechanism I missed: **Temporary is a triggered ability that uses the chain, not silent auto-removal.** At the start of the Beginning Phase it goes on the chain and **can be responded to**. Two consequences:
>
> 1. **The check happens once per turn, at the start of the turn only.** A Temporary unit created *mid-turn* is past that turn's check and survives until your **next** Beginning Phase.
> 2. **You can respond to the trigger with a replacement.** While the trigger is still pending, the old token is *still alive*, so you still control the battlefield — and a card Hidden there is still valid. Flip **Hidden Sprite Call** (Reaction speed, {0 energy}, must go to the battlefield it was hidden at): the new Sprite enters, the trigger then resolves and kills only the *old* token, and the new one is present at the Scoring Step and **holds for a point**.
>
> **Rule of thumb: respond to the trigger; never let it resolve first.** If the old token dies before the replacement exists you drop to zero units there, lose control, and lose the Hidden card with it.
>
> **The speed gate:** only **Reaction**-speed things can answer the trigger. Sprite Call played *from hand* is **Action** speed and cannot — Hidden is what grants Reaction speed. So this line requires **pre-commitment on an earlier turn** (paying the {any rune} hide cost then). Ambush units also qualify. No amount of available energy lets an Action or Neutral card in.
>
> **What this changes about the deck:** the conquest loop still works and is still the fastest clock, but "Sprites are conquest-only, LeBlanc is the sole route to holding" was false. Hidden Sprite Call is itself a per-turn holding engine, which raises its value and lowers LeBlanc's uniqueness (she is still better — she converts *every* Sprite with no per-turn card cost). It also promotes **Dusk Rose Lab** from a 56 to a genuine engine battlefield (see below).
- **630.1 (Conquer)** — you score by *gaining* control of a battlefield you have not already scored this turn. This happens the moment control changes, during your Action Phase. **Sprites score fine this way.**
- Therefore: after a Sprite conquers and dies, the battlefield has no units and reverts to uncontrolled — **the same battlefield is conquerable again next turn.** This is the deck's income. It remains true; it is just no longer the *only* income.

## Dusk Rose Lab (battlefield) — verified engine, not a cute trick

`reference/riftbound_temporary_interactions.txt` §6, citing RiftJudge FAQ #9231 / ruling #9428.

*"At the start of your Beginning Phase, you may kill a unit you control here to draw 1. (This happens before scoring.)"*

- Both the Lab trigger and the Temporary trigger hit the chain at the start of your Beginning Phase. **You control both, so you choose the resolution order.**
- Resolve the **Lab first**: kill the doomed Temporary token as the ability's cost, draw 1. The Temporary trigger then finds its unit already gone and is **ignored**. Net: a token that was dying anyway becomes a card.
- **Full line** (Lab + Temporary + Hidden Sprite Call): flip the Hidden Sprite Call **first**, while the old token is still alive — never lose control, never lose the Hidden card. New Sprite enters. *Then* feed the old token to the Lab for a card. *Then* Temporary fizzles. At the Scoring Step the new token holds and scores.
- **Result every Beginning Phase: +1 card, battlefield kept, point scored.** An aristocrats engine off bodies that were doomed regardless.
- **Never** resolve the Lab and kill your only token before flipping the Hidden card.
- **178.2** — the token itself: *a domainless unit token with 3 Might, the Fae tag, and Temporary.* The Fae tag matters for nothing in this list but is worth knowing.

## Where units can go

- **139.4** — **units enter the board exhausted** unless an effect says otherwise (Accelerate, or a token printed "ready"). A "ready" Sprite is the entire point; an exhausted one cannot move.
- **559.2** — when you play a unit you *choose a location you control*. **You can never play a unit directly onto an enemy or uncontrolled battlefield.** Every conquest requires *moving* a ready body in.
- **140.2 / 140.4** — the standard move costs **exhausting the unit**, and only goes base→battlefield or battlefield→base. Battlefield→battlefield needs **Ganking** (140.4.c) or a card effect that moves the unit (Smoke and Mirrors, Forgotten Signpost, Resonating Strike, Emperor's Divide) — those are not standard moves and are not restricted.
- **140.4.a.1** — you cannot move into a battlefield that already has units from two *other* players. Irrelevant in 1v1.

## Combat

- **626.1.b–d** — sum the attackers' Might, sum the defenders' Might, each side distributes that much damage among the other's units. **Lethal damage must be assigned in full to one unit before moving to the next** (626.1.d.2). Tank units must be assigned lethal first (626.1.d.1).
- **627.3** — the battlefield is conquered only if **no defenders remain and at least one attacker does**. Trading evenly is not enough.
- **627.2** — if units remain on both sides, the attackers are **recalled** (sent to base). A failed attack costs you the tempo, not the units.
- Consequence for this deck: three 3-Might Sprites are 9 summed Might and absorb incoming damage in 3-point chunks. Soul Shepherd making them 4s takes that to 12 and makes each one cost the opponent a whole extra point of damage to kill. That is why Shepherd is a 3-of.

## 1v1 format

Numbers below were re-checked against RUP4 on 2026-08-05; the old 644.x cites
were pre-RUP4 and the battlefield one was also substantively wrong.

- **485.3 / 486.3** — Victory Score **8**.
- **485.4 / 486.4** — **2 battlefields in play**. Each player brings 3, only 1 is used per game.
- **Selection depends on the mode.** **Duel (Bo1, 485.5)** — one of your three at random, other two removed; all three must be independently strong and there is no battlefield "package." **Match (Bo3, 486.5)** — you **choose** which to present, and one used in a game someone won is removed for the rest of the match (a drawn game lets it be re-used, 486.5.a). In Match the three want distinct roles — go-first, go-second, and a neutral game-1 pick — because you commit before turn order is rolled (115).
- **485.7 / 486.7** — the player going second channels one extra rune on their first Channel Phase only.

## Rune economy for this list

- 2 runes channelled per turn, 12-rune deck, fully channelled turn 6. On the play: T1 2, T2 4, T3 6, T4 8, T5 10, T6 12.
- **156.1.a** — Energy has no domain; any rune pays it. **156.2.a** — Power does have a domain. v2 has **11 Mind pips and 3 Calm pips**; rune deck is 9 Mind / 3 Calm.
- **606.1 + 103.3.b** — channelling takes runes **from the top of the rune deck**, and the rune deck is **shuffled** at setup. You do **not** choose which domain you channel, so any split is a real consistency tax and must be priced. At 9/3 the tax is nil: with only 3 non-Mind runes in a 12-card deck it is arithmetically impossible to channel 4 runes without hitting Mind, so ≥1 Mind by turn 2 is 100% and ≥2 Mind by turn 2 is 98.2%. Calm arrives 74.5% by T2 and 90.9% by T3. Going to 8/4 drops ≥2 Mind by T2 to 93.3%, which is where it starts to hurt — Zilean plus Smoke Screen in one turn needs two Mind recycles.
- **157.2.b** — Power is paid by **Recycling** a rune, which removes it from play and sends it to the bottom of the Rune Deck. Energy (157.2.a, exhaust) is renewable; Power is not. A card with a Power cost genuinely shrinks your board of runes for a turn cycle.
- Ability costs are **not** counted in the printed Power cost and must be budgeted separately. This deck's ability costs: Fae Fawn's Accelerate is `{1 energy}{Mind rune}`; the Hidden cards (Sprite Call, Smoke and Mirrors, Back Off) each cost `{any rune}` to hide, then `{0 energy}` to flip.

## Hidden cards

- **523** — at a specific point in the turn, Hidden cards at a battlefield where you have **no unit** are trashed. This deck's units at battlefields are frequently Temporary and die every Beginning Phase, so **a hidden card left at a battlefield garrisoned only by Sprites is not safe.** This is the specific reason Mushroom Pouch is a trap here, and the reason to hide cards at battlefields where a non-Temporary body (Petal Pixie, LeBlanc, Zilean) is standing.

## Legend activation

- `{4 energy}, Exhaust: Play a ready 3 Might Sprite token with Temporary. Costs {1 energy} less for each friendly unit with Temporary.`
- The discount counts **friendly units with Temporary**, so Sprite Fountain (a *gear* with Temporary) does **not** discount it — the Sprites it makes do.
- 2 Sprites on board → activation costs {2}. 4 Sprites → **free**.
- Exhaust cost means once per turn, unless something readies the Legend: **Hall of Legends** (conquer here, pay {1}, ready your legend) or Royal Entourage.
