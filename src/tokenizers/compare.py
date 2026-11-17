"""Compare token counts across tokenizers. One failing tokenizer never stops the rest."""
from __future__ import annotations

from dataclasses import dataclass

from .registry import TokenizerRegistry


@dataclass(frozen=True)
class CountRow:
    name: str
    family: str
    exact: bool
    tokens: int | None
    chars_per_token: float | None
    error: str | None = None


def compare_counts(registry: TokenizerRegistry, text: str,
                   names: list[str] | None = None) -> list[CountRow]:
    rows = []
    for name in names or registry.names():
        try:
            tok = registry.get(name)
            n = tok.count(text)
            rows.append(CountRow(name, tok.family, tok.exact, n,
                                 round(len(text) / n, 3) if n else None))
        except Exception as exc:   # report it in the row, keep going
            rows.append(CountRow(name, "", True, None, None, error=str(exc)))
    return rows
