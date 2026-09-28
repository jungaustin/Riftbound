# Playstyle — Empower/Chaos, all three builds

## Universal: what you are actually doing

You are a **midrange deck with a value engine**, not a combo deck. The Empower engine
produces roughly one cheated cost per turn; it does not win on the spot. You win by
holding battlefields with persistent bodies while the engine buries the opponent in
free triggers.

**The mulligan question is the same in all three:** do I have a two-drop and a way to
start the engine? Keep any hand with a cheap body plus either Tornado Warrior (to hide
turn 1-2) or, in Calm, a Sanction. Ship hands whose only Empower payoff costs 6+.

**Rune slack.** All three run Reaction-speed cards (Gust everywhere; Sanction and Block
in Calm; Retreat and Consult the Past in Mind). Per rules-fact 1b a rune you exhaust on
your turn stays exhausted through the opponent's whole turn. **Leave 1-3 runes live** —
in Calm specifically, always leave 3 for Sanction, because Sanction during your own
Beginning Phase is the deck's best turn.

**Never tap out the turn you hide.** A facedown card you cannot protect is a card the
opponent takes by taking the battlefield (811.1.b).

---

## Which battlefield to present

**Game 1 (blind to turn order): Risen Altar, in all three builds.** It cannot be turned
against you — most decks in the field run zero Empower costs — and it patches the
archetype's actual weakness, which is paying hard for an Empower when the free ones
don't show up.

**On the play, games 2-3: Seat of Power** in all three — except Mind/Chaos, where
**Minefield** is better if you have already seen Tail-Cloaked Matriarch, and Body/Chaos,
where **Sunken Temple** is better if you are on the Dame the Despoiler draw.

**On the draw, games 2-3:** Calm/Chaos presents **Reckoner's Arena** — it is the pick
that is good from behind, because holding is what you do when you cannot push. The
other two builds have no true go-second battlefield yet; that is an open gap, noted in
the README.

*(This assumes the loser-chooses-turn-order convention applies at your event. It is
**not** in RUP4 — 115 says fair random method and 486 adds no exception. You have said
it holds in Bo3; if an event says otherwise, present Risen Altar every game.)*

### Per battlefield, concretely

- **Risen Altar** — the discount applies to your **units here**, so put the unit you
  intend to hard-Empower *at the Altar*, not at the other battlefield. It turns
  Kharox's `{6}{Chaos}{Chaos}` into `{5}{Chaos}` — still expensive, but reachable at 12
  runes without the engine. The mistake: leaving the Empower target in base.
- **Seat of Power** — conquer the *other* battlefield first, then this one on the same
  turn; that is what makes "draw 1 for each other battlefield you control" pay more
  than one card. Do not conquer here first.
- **Reckoner's Arena** (Calm) — see `patterns.md` for the exact chain. The mistake:
  letting the hold trigger resolve before you Sanction. Respond to it, don't follow it.
- **Minefield** (Mind) — conquering here mills **you** 2. That is upside only while
  Tail-Cloaked Matriarch is live or in hand. If she is not in the deck any more, this
  slot is actively bad.
- **Sunken Temple** (Body) — check the 5-Might line (708) before paying the `{1}`;
  Legion Marauder and Brutal Hunter do not qualify unbuffed.

---

## Build 1 — Calm/Chaos: cheat the biggest costs

**How you win:** grind two points a turn off Reckoner's Arena + Nasus, or ride
Deflect bodies to a hold-lock and let Kharox strip their trash.

- **T1-2** Steel Paws `{1}` or Scuttle Crab `{2}` down; hide Tornado Warrior.
- **T3-4** Flip Tornado Warrior. Empower **Kharox** if he is out (Burn 3 + steal a unit
  from their trash) — that is the biggest single swing the deck has. Otherwise Empower
  Steel Paws and attack with a **7-Might Deflect body for one turn**.
- **T5+** Nasus lands at `{8}`. From here the game is: hold, Sanction in your Beginning
  Phase, take two points a turn.

**Steel Paws is a trick, not a threat.** `[Empowered][>] I have +7 Might` is stripped at
end of turn, so he is a **0-Might blank on defence**. Empower him on the turn you swing
and never rely on him to hold.

**Irelia's Legend** — "when you choose a friendly unit, you may exhaust me and pay
`{any rune}` to ready it." Sanction *chooses a friendly unit*, so every Sanction can
also ready that unit. Use it to re-Move a body that already attacked.

## Build 2 — Mind/Chaos: the flicker loop

**How you win:** banish their board one unit per turn with Mel, Defiant Soul while
drawing ahead, then take uncontested battlefields.

- **T1-2** Teemo - Strategist or Blastcone Fae; hide Tornado Warrior or Temporal Breach.
- **T3-4** Mel, Defiant Soul from the Champion Zone at `{5}`, or Apprentice Mage. Empower
  Mel by **discarding a spell** — cheap, and it is the printed cost, so no engine needed.
  Banish an enemy unit ≤3 Might.
- **T5+** Each turn: free-Empower Mel again (Tornado Warrior) → banish another. The
  Legend empowers herself alongside → Disempower her, Exhaust → **−2 Might** on the next
  target, dragging a 5-Might unit into banish range. With **Mel, Newly Awakened**
  Empowered, that is **−3** and 6-Might units die.

**Temporal Breach** does two jobs — it clears an Empowered status so you can re-Empower,
and it replays the body **ignoring its cost**. On Kharox that is 6 runes saved.

Highest attrition build (18). Watch the rune count; do not cast Portal Rescue and
Temporal Breach in the same turn unless you are closing.

## Build 3 — Body/Chaos: Empowered beatdown

**How you win:** biggest bodies on the board, Ganking for the double conquer.

- **T1-2** Legion Marauder `{2}`. Its Empower is `{1}` **or** `{Body rune}` — the
  cheapest in the format, and the point is not the +1 Might.
- **T3-5** **Profiteer** is the engine: play him, **disempower Legion Marauder, empower
  Kharox.** You have just converted a `{1}` Empower into a `{6}{Chaos}{Chaos}` one.
  That line is the whole reason this build exists — Profiteer is a *transfer*, so you
  must have something cheap Empowered first.
- **T6+** Renekton, Brute is the only card in any of the three builds whose Empower
  **permanently sticks** — pump him to 10 Might with Guttural Roar and his own `{1}`,
  and he self-empowers into Deflect + Ganking with no disempower attached.

**The 8th point:** Miss Fortune's Legend grants **Ganking** for the turn, which is the
only way a unit already at a battlefield can reach the second one (144.4). At 7 points,
Gank one body across and conquer both battlefields the same turn (471.1.b.1).

Clunkiest curve — 13 cards at 4 runes. Do not keep a hand with no play before turn 3.
