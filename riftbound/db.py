"""Local card database: load, look up, and cut the pool down to what is legal."""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path

from .model import Card, canonical_name, loose_key


class CardNotFound(Exception):
    def __init__(self, query: str, suggestions: list[str]):
        self.query = query
        self.suggestions = suggestions
        hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
        super().__init__(f"No card matches {query!r}.{hint}")


class AmbiguousCard(Exception):
    def __init__(self, query: str, matches: list[str]):
        self.query = query
        self.matches = matches
        super().__init__(
            f"{query!r} is ambiguous between: {', '.join(matches)}. "
            "Use the exact printed name."
        )


@dataclass
class LegalPool:
    legend: Card
    identity: set[str]
    champion_options: list[Card]
    main_deck: list[Card]
    battlefields: list[Card]
    runes: list[Card]

    @property
    def all_buildable(self) -> list[Card]:
        return self.main_deck + self.battlefields


class CardDB:
    def __init__(self, payload: dict):
        self.fetched_at = payload.get("fetched_at")
        self.sets = payload.get("sets", [])
        self.indexes = payload.get("indexes", {})
        self.cards = [Card.from_dict(c) for c in payload["cards"]]
        self._by_name = {}
        for c in self.cards:
            for n in [c.name, *c.aliases]:
                self._by_name[n.lower()] = c
        self._by_id = {c.id: c for c in self.cards}

    @classmethod
    def load(cls, data_dir: Path) -> "CardDB":
        path = data_dir / "cards.json"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found. Run `python cli.py sync` first."
            )
        return cls(json.loads(path.read_text()))

    # ---------- lookup ----------

    def get(self, name: str) -> Card:
        """Resolve a printed name. Raises rather than guessing.

        Deck imports are the fragile step of the whole pipeline: a silently
        mis-resolved card poisons every downstream conclusion, so near-misses
        surface as errors with suggestions instead of a best guess.
        """
        q = canonical_name(name).strip()
        exact = self._by_name.get(q.lower())
        if exact:
            return exact

        norm = loose_key(q)
        loose = [c for c in self.cards
                 if loose_key(c.name) == norm or any(loose_key(a) == norm for a in c.aliases)]
        if len(loose) == 1:
            return loose[0]
        if len(loose) > 1:
            raise AmbiguousCard(name, sorted(c.name for c in loose))

        prefix = [c for c in self.cards if loose_key(c.name).startswith(norm)]
        if len(prefix) == 1:
            return prefix[0]
        if len(prefix) > 1:
            raise AmbiguousCard(name, sorted(c.name for c in prefix)[:8])

        # Legend names get rendered with varying amounts of tag prefix
        # ("Heart of the Tempest" / "Kennen, Heart of the Tempest" /
        # "Yordle, Kennen - Heart of the Tempest"). Accept a suffix match, but
        # only when it is long enough to be meaningful and matches exactly one
        # card — this must not become a general fuzzy fallback.
        if len(norm) >= 8:
            suffix = [
                c for c in self.cards
                if loose_key(c.name).endswith(norm)
                or any(loose_key(a).endswith(norm) for a in c.aliases)
            ]
            if len(suffix) == 1:
                return suffix[0]
            if len(suffix) > 1:
                raise AmbiguousCard(name, sorted(c.name for c in suffix)[:8])

        close = difflib.get_close_matches(q, [c.name for c in self.cards], n=5, cutoff=0.7)
        raise CardNotFound(name, close)

    def find(self, **kw) -> list[Card]:
        def ok(c: Card) -> bool:
            for k, v in kw.items():
                got = getattr(c, k)
                if isinstance(v, (list, set, tuple)):
                    if got not in v:
                        return False
                elif got != v:
                    return False
            return True

        return [c for c in self.cards if ok(c)]

    @property
    def legends(self) -> list[Card]:
        return [c for c in self.cards if c.is_legend]

    def legend_named(self, name: str) -> Card:
        c = self.get(name)
        if not c.is_legend:
            raise ValueError(f"{c.name} is a {c.type}, not a Legend.")
        return c

    # ---------- the filter that makes this scale ----------

    def legal_pool(self, legend: Card) -> LegalPool:
        """Everything legal under a Legend's domain identity (rule 103.1.b)."""
        identity = legend.domain_set
        legend_tags = set(legend.tags)
        buildable = [
            c
            for c in self.cards
            if not c.is_legend
            and not c.is_token
            and not c.is_basic_rune
            and c.legal_under(identity)
            # 103.2.d.2: a signature card without the Legend's champion tag can
            # never be legal here, so it is filtered out rather than offered and
            # then rejected by the validator.
            and (not c.is_signature or legend_tags & set(c.tags))
        ]
        return LegalPool(
            legend=legend,
            identity=identity,
            champion_options=sorted(
                (c for c in buildable if c.is_champion_unit and legend_tags & set(c.tags)),
                key=lambda c: (c.energy or 0, c.name),
            ),
            main_deck=sorted(
                (c for c in buildable if any(c.is_a(t) for t in ("Unit", "Spell", "Gear"))),
                key=lambda c: (c.type, c.energy or 0, c.name),
            ),
            battlefields=sorted(
                (c for c in buildable if c.is_a("Battlefield")), key=lambda c: c.name
            ),
            runes=sorted(
                (
                    c
                    for c in self.cards
                    if c.is_basic_rune and c.domain_set <= identity
                ),
                key=lambda c: c.name,
            ),
        )

