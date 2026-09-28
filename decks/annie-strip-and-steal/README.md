# Annie - Dark Child — Strip and Steal (Chaos + Fury)

**Current version: `v1.txt`** · Legend **Annie - Dark Child** · Chosen Champion
**Annie - Fiery** · created 2026-08-20 · `cli.py check` → LEGAL

## The plan, in one sentence

Strip their hand and take their units while cheap Fury removal keeps their
bodies off battlefields, then score 8 by holding with Vex - Apathetic and
Draven - Audacious — funded by Annie readying 2 runes every end of turn so a
Reaction is live on *their* turn, every turn.

## Why this deck exists — and the honest framing

This started as a request for a **mill deck**. Mill as a kill does not exist in
Riftbound and the deck should never be played as though it does:

- **Burn Out is not a loss.** Rule 431.2: the player recycles their trash into
  their Main Deck, then **chooses an opponent to gain 1 point** (431.2.c).
  Milling them pays you 1 point of the 8 and hands their trash back as a deck.
- The instant-win version (431.3, repeated Burn Outs when their trash is also
  empty) needs their trash emptied. The whole 929-card pool has **one** card
  that touches an opponent's trash (Gust Monk, one card at a time).
- **Two cards in the pool mill an opponent at all:** Blade Twirler (Burn 1 on
  move) and Kharox (Burn 3, once — Empowered is binary, 441.1.b). Blind Fury
  banishes their top card, which is the only permanent library reduction in the
  identity because banish survives a Burn Out.

So the deck attacks their **cards** rather than their **library**, and the two
mill cards are in it for what they steal, not what they deplete. **Kharox is the
card that makes deck-attack worth doing** — it Burns 3 and then plays a unit out
of their trash for free.

## Why Annie over the other four Fury+Chaos legends

| Legend | Ability | Verdict |
|---|---|---|
| **Annie - Dark Child** | End of turn, ready 2 runes | **Chosen.** Unconditional, no board cost, always relevant. 315.1.b means a rune spent on your turn is dead through theirs; Annie repeals that for 2 runes permanently. This deck has 5 copies at 6 runes and 9 Reaction/Hidden cards — it cannot function without slack. |
| Pyke - Bloodharbor Ripper | Bounce a friendly unit at a BF, make a Gold token | Rebuys "when you play me" strip triggers and ramps — but bouncing a body off a battlefield loses control (190.4.c), so the engine fights the scoring plan. Best Signature of the five (Death from Below). |
| Draven - Glorious Executioner | Draw on winning combat | Wants a combat deck. Draven - Audacious is a real wincon and is in this list *as a main-deck card* instead. |
| Jinx - Loose Cannon | Draw if hand ≤1 | Anti-synergy — this deck holds cards for Reactions. Its champions are a self-discard shell. |
| Zed - Master of Shadows | Empower on banishing your own cards | Self-mill. Blind Fury banishes *their* card, so it does not even trigger. |

**The price of Annie:** 103.2.d.2 requires every Signature card to carry the
Legend's Champion tag, so **Tibbers is the only legal Signature**. Death from
Below (Pyke), Death Mark (Zed), Super Mega Death Rocket! (Jinx) and Spinning Axe
(Draven) are all Chaos+Fury and all *illegal here*. Losing Death from Below —
4 runes, kill a unit, replay it from the trash for one rune — is a genuine cost
and the main argument for revisiting the Legend after testing.

## The named failure point

**The deck cannot hold a battlefield.** Its cards are disruption, and disruption
does not stand on ground. Cards addressing it: Vex - Apathetic ×3, Scorchclaw
×3, Kharox ×3, Miss Fortune - Buccaneer ×2, Draven - Audacious ×2, Tibbers ×1,
Insightful Investigator ×3, Evelynn - Entrancing ×3 = **20 of 39**, plus the
Champion. If the deck loses, this is why, and the first revision should add
bodies, not disruption.

**The 8th point is *not* a problem for this deck, unusually.** 471.1.b.1 only
restricts points gained through a **Conquer**; 471.1.a.1 exempts every other
source. This deck holds rather than conquers, and Hold scoring is exempt — so
the standard "score 7 and stall" failure mode does not apply. Power Nexus is a
second exempt route (a paid ability, not a Conquer).

## The XP question, answered explicitly

`critique` flags Conscription as a conditional payoff. XP has **no default
source** in Riftbound (rules 728-733) — it comes only from cards.

- **Demand:** Insightful Investigator ×3 at 2 XP = 6 XP mandatory.
  Conscription ×2 at 5 XP = 10 XP optional (the card functions without it,
  capped at 3-Might targets).
- **Supply:** Scorchclaw ×3, `[Hunt 2]` = *"when I conquer **or hold**, gain 2
  XP"* (823.1.c.1). This deck holds, so it is 2 XP per Scorchclaw per turn held.
  One Scorchclaw holding three turns covers the mandatory demand alone.
- Scorchclaw went from 2 copies to 3 specifically so the XP supply is not a
  36%-of-games proposition when three Investigators depend on it.

## Battlefield selection

This deck **persists** — 4-6 Might Deflect bodies that take ground and stand on
it — so hold triggers (471.2.b) fire far more often than conquer triggers
(471.2.a). Every pick below follows from that.

| Role | Battlefield | Why, and question 2: *what if they have it?* |
|---|---|---|
| **Go-first / proactive** | **Power Nexus** | *"When you hold here, you may pay 4 Power to score 1 point."* On the play you land a body first and hold; Annie's rune slack then converts directly into points, exempt from the final-point rule (471.1.a.1). Deliberately bad from behind — you cannot hold, and 4 Power is unaffordable. **If they hold it:** any deck can use it, but paying 4 recycled runes is ruinous for a deck that spends its whole pool and trivial for the one whose Legend hands 2 back a turn. That gap is the pick. |
| **Go-second / reactive** | **Ravenbloom Conservatory** | *"When you defend here, reveal the top card of your Main Deck. If it's a spell, put it in your hand."* Triggers on **defending** — the seat you are in when behind — and this deck is 19/39 spells, so it hits about half the time. Free cards precisely under pressure, and it pairs with the extra rune the second player channels (485.7/486.7) to cast what you just revealed. **If they defend on it:** a creature deck reveals spells far less often than this one does. |
| **Neutral — game 1** | **Void Gate** | *"Spells and abilities affecting units here each deal 1 Bonus Damage."* Stacks with Annie - Fiery: Hextech Ray becomes **5 damage for one rune** here. Turn-order neutral, and it is question 3 in its strongest form — near-blank against a combat-midrange deck, free value for the removal-dense one. **If they control it:** genuinely dangerous against a burn deck; that is the matchup to board it out for. |

**Bench, in preference order, with the promotion condition:**
1. **Grove of the God-Willow** (draw 1 on hold) — promote over Void Gate if the
   deck floods on removal and starves on cards. Highest-rated battlefield in the
   pool for this deck (82); benched only because it is fully symmetric and
   answers question 2 worst of the candidates.
2. **Altar to Unity** (free Recruit token in base on hold) — promote over Power
   Nexus if the body count is what is losing games. The token enters in **base**
   and is therefore able to move out and conquer later (rules-fact 3).
3. **Frozen Fortress** (1 damage to each unit here, each player's Beginning
   Phase) — promote against swarm; it also kills our own 2-Might Evelynns.
4. **Gardens of Becoming** (units here: Exhaust for 1 XP) — promote if Scorchclaw
   keeps dying and the XP engine stalls.
5. **Forgotten Monument** (nobody scores here until their third turn) — promote
   against aggro; a pure clock-slower is a gift to the slower deck.
6. **Amateur Recital** (hold → move any unit at a battlefield to base) — rated
   78, benched on question 2 alone: in their hands it bounces our holder off,
   which is our own plan aimed at us.

**Never-pick for this deck:**
- **Heisho, Shell of the World** — players ignore Deflect when paying for spells
  here. Our three most important bodies are Deflect (Vex - Apathetic, Vex -
  Cheerless, Draven - Audacious). It switches off our own keyword.
- **Mystic Vortex** — Reaction cards cost {any rune} more here. It taxes Annie's
  ability directly.
- **Shadow Temple / Minefield** — both Burn *your own* deck, moving you toward a
  Burn Out that hands the **opponent** a point (431.2.c).

## Copy counts that depart from the audit, and why

`critique` asks for 3 copies of four cards. Three are deliberately left lower:

- **Draven - Audacious at 2**, not 3. It scores a point per turn on winning
  combat *and* **gives them a point when it dies in combat**. Drawing two is
  fine; drawing three in a deck this slow means casting one into a bigger body.
- **Blind Fury at 2**, not 3. Four runes and 2 Power of ongoing attrition for a
  **random** card off their deck. Excellent when it hits, unusable when it turns
  up a card whose runes you cannot pay.
- **Tibbers at 1.** Section 4 says default a Signature to 3; that advice does
  not survive an 8-rune card in a deck with five 6-drops. It is the closer.
- **Kharox went to 3** as the audit asked — it is the card the whole plan is
  named for and a 36%-by-turn-5 engine piece is not an engine.

## Known `critique` false positives — do not "fix" these

The auditor is a text matcher and cannot see:
- **The XP engine.** Scorchclaw's "gain 2 XP" and Insightful Investigator's "pay
  2 XP" / Conscription's "spend 5 XP" are the same resource. It reports all
  three as orphans.
- **Miss Fortune - Buccaneer** granting *"friendly units may be played to open
  battlefields"* to the **whole deck** — that is a permanent rules exemption
  from 806.3, not a synergy with any one card.
- **Vex - Apathetic + every removal spell.** Stun is not removal (423.1.b-c);
  Vex is a lock only because the deck has 10 damage spells to finish the stunned
  body. No shared text, so no detected interaction.
- **Annie - Fiery** applying +1 Bonus Damage to all 10 damage spells at once.

## Open questions for testing — do not resolve these on paper

1. **Annie - Fiery vs Annie - Stubborn.** Fiery was chosen for a continuous +1
   damage across a removal-dense deck. But 5 runes for a 4-Might body with no
   enter-the-board impact is exactly the profile rules-fact 1b says to rate
   *below* its stat line. If the Champion keeps feeling like a bad turn, switch.
2. **Is Kharox worth 12 runes across two turns?** 6 to cast, then
   `{6}{Chaos}{Chaos}` to Empower, for Burn 3 and one unit out of their trash.
   If their trash is empty when it fires, it was a 5-Might body for 6 runes.
3. **Does the hand attack actually matter?** Stripping is strongest against a
   deck holding answers and near-worthless against one that empties its hand by
   turn 4. This is the assumption most likely to be wrong.
4. **Is 19 spells too many?** Every source says cut a spell and add a unit when
   in doubt. The deck is at 21 units / 19 spells and the failure point above is
   body count.
5. **Card draw is thin** — Void Seeker ×3 and Ravenbloom Conservatory. Both
   domains are named weak at draw. Grove of the God-Willow is the bench answer.

## Version history

- **v1** (2026-08-20) — first build. Full 252-card pool rating in `ratings.md`.
  Post-audit changes before shipping: Kharox 2→3, Scorchclaw 2→3, cut
  Mindsplitter (1) and Shakedown (1). Mindsplitter's targeted strip is covered
  by Bone Skewer ×3 and Insightful Investigator ×3 at a third of the runes;
  **what that cost:** the deck's only 7-Might body, so the top end is now Tibbers
  alone. Shakedown was a singleton Reaction — cut for consistency, and **what
  that cost** is the deck's cheapest punisher for Annie's held-up runes.
