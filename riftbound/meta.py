"""The meta layer — the one part of the pipeline card data cannot supply.

Card data says what a card does. It has no idea what people are playing. Every
matchup claim therefore has to come from this hand-maintained file, and when it
is switched off the prompts forbid matchup claims outright rather than letting
the model invent a field.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

FIELDS = (
    "legend",
    "identity",
    "speed",
    "prevalence",
    "plan",
    "key_cards",
    "strong_vs",
    "weak_to",
    "tech_against",
    "updated",
)


@dataclass
class Archetype:
    name: str
    fields: dict[str, str] = field(default_factory=dict)

    def get(self, k: str, default: str = "") -> str:
        return self.fields.get(k, default)

    def render(self) -> str:
        lines = [f"### {self.name}"]
        for k in FIELDS:
            v = self.fields.get(k)
            if v:
                lines.append(f"- {k}: {v}")
        for k, v in self.fields.items():
            if k not in FIELDS and v:
                lines.append(f"- {k}: {v}")
        return "\n".join(lines)


@dataclass
class MetaContext:
    enabled: bool
    archetypes: list[Archetype] = field(default_factory=list)
    source_path: Path | None = None
    as_of: str | None = None

    @property
    def usable(self) -> bool:
        return self.enabled and bool(self.archetypes)

    def block(self) -> str:
        """The prompt fragment. Explicit in both directions."""
        if not self.enabled:
            return (
                "## Meta context: DISABLED\n"
                "You have no information about what decks are currently popular.\n"
                "HARD CONSTRAINT: do not make any claim about matchups, tier "
                "placement, what this deck 'beats' or 'loses to', or what is "
                "prevalent in the field. Do not include tech or hate cards chosen "
                "to answer a specific opposing deck. Evaluate the deck only on "
                "what is provable from card text, costs, counts, and curve. If "
                "the user asks a matchup question, say the meta layer is off."
            )
        if not self.archetypes:
            return (
                "## Meta context: REQUESTED BUT EMPTY\n"
                "The meta file has no archetypes in it. Treat this exactly as if "
                "meta context were disabled: make no matchup or prevalence claims."
            )
        head = [
            "## Meta context: ENABLED",
            f"The following is the ONLY meta information you have"
            + (f" (as of {self.as_of})" if self.as_of else "")
            + ". It is hand-maintained and may be incomplete or out of date.",
            "",
            "Rules for using it:",
            "- Every matchup claim must name the archetype below that it is about.",
            "- If a relevant archetype is absent, say so rather than inventing one.",
            "- Tech/hate cards must be justified against a listed archetype, and "
            "you must state the maindeck cost of including them.",
            "- Prevalence values are the user's estimate, not measured data.",
            "",
        ]
        return "\n".join(head + [a.render() + "\n" for a in self.archetypes])

    def names(self) -> list[str]:
        return [a.name for a in self.archetypes]


_H2 = re.compile(r"^##\s+(?!#)(.+?)\s*$")
_KV = re.compile(r"^\s*[-*]?\s*([a-z_]+)\s*:\s*(.+?)\s*$", re.I)
_ASOF = re.compile(r"^\s*as[_ ]of\s*:\s*(.+?)\s*$", re.I)


def load(path: Path, enabled: bool) -> MetaContext:
    if not enabled:
        return MetaContext(enabled=False, source_path=path)
    if not path.exists():
        return MetaContext(enabled=True, archetypes=[], source_path=path)

    archetypes: list[Archetype] = []
    as_of = None
    current: Archetype | None = None
    last_key: str | None = None
    in_prose = False

    for line in path.read_text().splitlines():
        if line.startswith("#") and not line.startswith("##"):
            in_prose = True
            continue
        m = _H2.match(line)
        if m:
            current = Archetype(name=m.group(1))
            archetypes.append(current)
            last_key = None
            in_prose = False
            continue
        if current is None:
            a = _ASOF.match(line)
            if a and in_prose:
                as_of = a.group(1)
            continue
        kv = _KV.match(line)
        if kv:
            last_key = kv.group(1).lower()
            current.fields[last_key] = kv.group(2)
        elif last_key and line.strip() and line[:1].isspace():
            # Indented continuation of the previous value. Without this, every
            # multi-line entry silently loses everything after its first line.
            current.fields[last_key] += " " + line.strip()

    return MetaContext(
        enabled=True,
        archetypes=[a for a in archetypes if a.fields],
        source_path=path,
        as_of=as_of,
    )


def staleness_warning(ctx: MetaContext, newest_set: str, newest_date: str) -> str | None:
    if not ctx.usable:
        return None
    if ctx.as_of and newest_date and ctx.as_of[:10] < newest_date[:10]:
        return (
            f"Meta file is dated {ctx.as_of} but the newest set ({newest_set}) "
            f"released {newest_date[:10]}. Matchup claims may be pre-rotation."
        )
    return None
