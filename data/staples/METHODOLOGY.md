# Methodology

## 1. Domain identity

Six Domains: Fury (red), Calm (green), Mind (blue), Body (orange), Chaos (purple), Order (yellow).

A deck's Domain Identity is the two Domains of its Champion Legend. A card may be included if
at least one of its Domains matches the Legend's identity; a dual-Domain card requires **both**
of its Domains to be in the identity. Battlefields and Tokens have no Domain and go in any deck.

Consequence: "decks of Domain D" = decks whose Legend identity contains D. A given deck counts
toward exactly two Domains.

## 2. The metric

riftdecks per-Legend `/stats` pages give, per card:

- **Presence %** — share of that Legend's decks running ≥1 copy. Their wording: "80% means 4 out
  of every 5 decks run it."
- **×N** — average copies among decks that run it.
- **Top-cut performance (Xx)** — top-25% finish rate relative to the Legend average. Not needed
  for this analysis but captured anyway.
- The page header states the deck count backing the stats.

The site also buckets cards as Core (>60%) / Flex / Fringe / Gem / Trap. These are descriptive
only — don't use them as the threshold; use the raw percentage.

## 3. Aggregation

For Domain D:

```
inclusion(card, D) = Σ_L (n_L × presence[card, L]) / Σ_L n_L
```

L = every Legend whose identity includes D. n_L = that Legend's deck count.
Cards absent from a Legend's table contribute presence 0 for that Legend (not missing —
absence means no deck of that Legend ran it).

**Do not average per-Legend percentages.** A 2,565-deck Legend and a 253-deck Legend must not
carry equal weight.

Average copies per Domain, if wanted, is a presence-weighted mean:
`Σ (n_L × presence × copies) / Σ (n_L × presence)`.

## 4. Format / sample-size decision

Two candidate bases:

- **Vendetta (Set 4)** — the current format. As of early Aug 2026 riftdecks showed roughly 310
  tournament decks total across ~7 events, top Legend ~29 decks. A 20% threshold on a 29-deck
  sample moves by one deck per 3.4 percentage points. Not usable.
- **Unleashed (Set 3)** — thousands of decks per top Legend. Statistically sound but describes a
  format that has been superseded, and a July 2026 errata/ban wave plus Set 4's new Legends will
  have shifted the Chaos and Mind spell cores in particular.

The prior report used Unleashed and labeled it. **Re-check current Vendetta counts before
committing** — if major Legends are now at 150+ decks each, switch, or report both side by side.
Whatever you pick, label every table with the format and the date the data was read.

## 5. Type filter

Include type = **Spell** only. Exclude Unit, Gear, Rune, Battlefield, Legend.

Verify against `https://riftdecks.com/cards/details-{slug}`, which exposes explicit `types` and
`domains` fields. Confirmed by direct fetch during the original session:

- `Defy` — types: spell, domains: calm, cost 1C, Reaction counter. (This one is verified.)

Everything else in `data/card_types.csv` is a guess pending confirmation.

Cards that look like spells in the presence tables but are not:
Scuttle Crab, Stellacorn Herder, Lonely Poro, Fizz Trickster, Vex Apathetic, Adaptatron,
Tasty Faefolk, Baron Nashor, Sneaky Deckhand (Units); Boots of Swiftness, Zhonya's Hourglass,
Hidden Blade, Edge of Night, The Syren (Gear — several of these need confirming).

## 6. Domain attribution of each spell

A spell is listed under the Domain(s) printed on the card, not under every Domain whose decks
happen to run it. `Punch First` appearing at 88% in Master Yi (Body/Calm) decks does not make it
a Calm spell — check its printed Domain and file it there.

Dual-Domain spells belong on both lists; flag them explicitly rather than silently duplicating.

Colorless cards have no Domain and are excluded from all six lists. State this in the output.

## 7. Output shape

Six sections, one per Domain. Each: sample size (total decks of that Domain, and which Legends
contributed), then a table of spells at ≥20% sorted descending — card name, inclusion %,
avg copies. Note any Domain where the contributing Legend set is thin enough that the number is
directional rather than reliable.
