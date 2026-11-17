"""The common interface every tokenizer adapter implements.

Design rules (see docs/DESIGN.md):
* Offsets are **byte offsets into the UTF-8 encoding** of the input. Byte-level tokenizers
  (GPT, Llama 3...) can split one character, e.g. an emoji, across several tokens, so
  character offsets cannot describe them. Use `char_spans()` when you need character offsets.
* `Token.text` is the readable text of the token. A token that holds only part of a
  character is shown with U+FFFD. `Token.piece` is the vocabulary's own spelling.
* Adapters never mutate input and return `[]` for empty text.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from bisect import bisect_left, bisect_right
from dataclasses import dataclass


class TokenizerLoadError(RuntimeError):
    """A tokenizer could not be loaded (offline, gated model, wrong name...)."""


@dataclass(frozen=True, slots=True)
class Token:
    id: int
    text: str
    start: int            # byte offset in the UTF-8 input, inclusive
    end: int              # byte offset in the UTF-8 input, exclusive
    piece: str = ""       # vocabulary spelling, e.g. 'Ġthe', '##ing', '\\xf0'

    def __post_init__(self):
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid span ({self.start}, {self.end})")


class Tokenizer(ABC):
    """Base class. Subclasses implement `encode`."""

    def __init__(self, name: str, *, family: str = "", algorithm: str = "", exact: bool = True):
        if not name:
            raise ValueError("a tokenizer needs a non-empty name")
        self.name = name
        self.family = family          # e.g. "OpenAI", "Meta"
        self.algorithm = algorithm    # e.g. "byte-level BPE"
        self.exact = exact            # False for estimates (closed tokenizers)

    @abstractmethod
    def encode(self, text: str) -> list[Token]:
        """Tokenize `text`. Must return [] for empty text."""

    def count(self, text: str) -> int:
        """Number of tokens. Adapters may override with a faster path."""
        return len(self.encode(text))

    def __repr__(self) -> str:
        return f"{type(self).__name__}(name={self.name!r}, family={self.family!r})"


def char_to_byte_offsets(text: str) -> list[int]:
    """offsets[i] = UTF-8 byte offset where character i starts (last item = total bytes)."""
    offsets = [0]
    for ch in text:
        offsets.append(offsets[-1] + len(ch.encode("utf-8", "surrogatepass")))
    return offsets


def char_spans(text: str, tokens: list[Token]) -> list[tuple[int, int]]:
    """Convert tokens' byte spans to (start, end) character spans in `text`.

    A token holding part of a character gets the span of the whole character, so several
    tokens of one emoji share one character span.
    """
    offsets = char_to_byte_offsets(text)
    return [(bisect_right(offsets, t.start) - 1, bisect_left(offsets, t.end)) for t in tokens]
