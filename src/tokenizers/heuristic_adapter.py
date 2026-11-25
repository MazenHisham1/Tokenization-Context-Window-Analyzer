"""An ESTIMATE, not a tokenizer: characters divided by a fixed number.

Some vendors (for example Anthropic) do not publish a tokenizer you can run. All you can get
is a count from their API, and even that is described as an estimate. This adapter shows how
the app handles "count only" sources: it is marked `exact=False` and has no token list.
It is also a useful baseline, because a fixed rule hides how much languages differ.
"""
from __future__ import annotations

import math

from .base import TokenizationNotSupported, Tokenizer


class HeuristicAdapter(Tokenizer):
    def __init__(self, name: str, chars_per_token: float = 4.0, *, family: str = "estimate"):
        if chars_per_token <= 0:
            raise ValueError("chars_per_token must be positive")
        super().__init__(name, family=family, exact=False, provides_tokens=False,
                         algorithm=f"rule of thumb: characters ÷ {chars_per_token:g}")
        self.chars_per_token = chars_per_token

    def encode(self, text):
        raise TokenizationNotSupported(
            f"{self.name} only estimates a count; it has no tokens to show")

    def count(self, text: str) -> int:
        return math.ceil(len(text) / self.chars_per_token) if text else 0
