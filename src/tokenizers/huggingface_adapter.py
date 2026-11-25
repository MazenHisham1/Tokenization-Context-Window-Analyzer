"""Adapter for any *fast* Hugging Face tokenizer (BERT, GPT-2, T5, Llama, Gemma...)."""
from __future__ import annotations

from .base import Token, Tokenizer, TokenizerLoadError, char_to_byte_offsets


class HuggingFaceAdapter(Tokenizer):
    """Load by `model_name` (lazily, on first use) or inject a ready tokenizer with
    `tokenizer=`. Gated models (Llama, Gemma) need `huggingface-cli login` or the
    `HF_TOKEN` environment variable.

    Character offsets from the library are converted to byte offsets once per call
    (O(n)), not once per token. Tokens that split one character (byte fallback) share
    that character's span, so spans can repeat; see docs/DESIGN.md.
    """

    def __init__(self, name: str, model_name: str | None = None, *, tokenizer=None,
                 family: str = "", algorithm: str = "", exact: bool = True,
                 **from_pretrained_kwargs):
        if tokenizer is None and not model_name:
            raise ValueError("give either model_name or tokenizer")
        super().__init__(name, family=family, algorithm=algorithm, exact=exact)
        self.model_name = model_name
        self._tokenizer = tokenizer
        self._kwargs = from_pretrained_kwargs
        if tokenizer is not None:
            self._check_fast(tokenizer)

    def _check_fast(self, tok) -> None:
        if not getattr(tok, "is_fast", False):
            raise ValueError(f"{self.name}: a fast tokenizer is required to get offsets "
                             "(this one is a slow, Python-only tokenizer)")

    @property
    def tokenizer(self):
        if self._tokenizer is None:
            try:
                from transformers import AutoTokenizer
                tok = AutoTokenizer.from_pretrained(self.model_name, use_fast=True, **self._kwargs)
            except Exception as exc:  # offline, gated, unknown id...
                raise TokenizerLoadError(
                    f"{self.name}: cannot load {self.model_name!r}: {exc}. "
                    "For gated models run `huggingface-cli login` or set HF_TOKEN."
                ) from exc
            self._check_fast(tok)
            self._tokenizer = tok
        return self._tokenizer

    def encode(self, text: str) -> list[Token]:
        if not text:
            return []
        tok = self.tokenizer
        result = tok(text, add_special_tokens=False, return_offsets_mapping=True,
                     truncation=False, verbose=False)   # verbose=False: no length warning
        ids, spans = result["input_ids"], result["offset_mapping"]
        pieces = tok.convert_ids_to_tokens(ids)
        byte_at = char_to_byte_offsets(text)
        return [
            Token(id=i, text=text[s:e], start=byte_at[s], end=byte_at[e], piece=str(p))
            for i, (s, e), p in zip(ids, spans, pieces, strict=True)
        ]
