"""Riftbound deckbuilding toolkit.

Layering, deliberately: every module below is pure Python with no LLM in it.
`prompt.py` emits text. Whether that text goes to a Claude Code session or the
Anthropic API is a decision made outside this package.
"""

from pathlib import Path

__version__ = "0.1.0"

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
