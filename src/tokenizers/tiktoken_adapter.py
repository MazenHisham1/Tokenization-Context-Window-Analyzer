"""Adapter for OpenAI's `tiktoken` (cl100k_base, o200k_base, ...)."""
from __future__ import annotations

from .base import Token, Tokenizer, TokenizerLoadError


class TiktokenAdapter(Tokenizer):
    """`name` is the display name; `encoding_name` defaults to it.

    Pass `encoding=` to inject a ready `tiktoken.Encoding` (used by the tests, so they
    need no internet). Otherwise the encoding is loaded lazily on first use, so
    creating the adapter never touches the network.
    """

    def __init__(self, name: str, encoding_name: str | None = None, *, encoding=None,
                 family: str = "OpenAI"):
        super().__init__(name, family=family, algorithm="byte-level BPE")
        self.encoding_name = encoding_name or name
        self._encoding = encoding

    @property
    def encoding(self):
        if self._encoding is None:
            try:
                import tiktoken
                self._encoding = tiktoken.get_encoding(self.encoding_name)
            except Exception as exc:  # unknown name, offline, missing package
                raise TokenizerLoadError(
                    f"{self.name}: cannot load tiktoken encoding {self.encoding_name!r}: {exc}"
                ) from exc
        return self._encoding

    def _ids(self, text: str) -> list[int]:
        # disallowed_special=() -> '<|endoftext|>' in user text is treated as plain text
        return self.encoding.encode(text, disallowed_special=())

    def encode(self, text: str) -> list[Token]:
        if not text:
            return []
        tokens, pos = [], 0
        for token_id in self._ids(text):
            raw = self.encoding.decode_single_token_bytes(token_id)
            tokens.append(Token(
                id=token_id,
                text=raw.decode("utf-8", errors="replace"),
                start=pos,
                end=pos + len(raw),
                piece=raw.decode("utf-8", errors="backslashreplace"),
            ))
            pos += len(raw)
        return tokens

    def count(self, text: str) -> int:
        return len(self._ids(text)) if text else 0
