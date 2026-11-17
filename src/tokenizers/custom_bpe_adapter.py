"""Adapter for the from-scratch byte-level BPE (src/bpe.py)."""
from __future__ import annotations

from .base import Token, Tokenizer


class CustomBPEAdapter(Tokenizer):
    """Wraps any object with `encode(text) -> ids` and `vocab: {id: bytes}`."""

    def __init__(self, bpe, name: str = "my-bpe"):
        super().__init__(name, family="custom", algorithm="byte-level BPE (from scratch)")
        self.bpe = bpe

    def encode(self, text: str) -> list[Token]:
        if not text:
            return []
        tokens, pos = [], 0
        for token_id in self.bpe.encode(text):
            raw = self.bpe.vocab[token_id]
            tokens.append(Token(
                id=token_id,
                text=raw.decode("utf-8", errors="replace"),
                start=pos,
                end=pos + len(raw),
                piece=raw.decode("utf-8", errors="backslashreplace"),
            ))
            pos += len(raw)
        return tokens
