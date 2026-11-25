"""Request and response shapes of the API. FastAPI validates them and builds the docs from them."""
import os
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# One limit, used by the API validation and reported to the front end.
MAX_TEXT_CHARS = int(os.getenv("MAX_TEXT_CHARS", "50000"))


class TokenizeRequest(BaseModel):
    text: str = Field(max_length=MAX_TEXT_CHARS)
    tokenizer: str = Field(min_length=1, max_length=100)


class TokenOut(BaseModel):
    id: int
    text: str
    piece: str
    start: int   # UTF-8 byte offset, inclusive
    end: int     # UTF-8 byte offset, exclusive


TOKENIZE_MAX_TOKENS = 2000   # tokens sent back by /api/tokenize; the page colours at most this many


class TokenizeResponse(BaseModel):
    tokenizer: str
    count: int                 # always the full number of tokens
    chars: int
    bytes: int
    chars_per_token: float | None
    tokens: list[TokenOut]     # at most TOKENIZE_MAX_TOKENS
    truncated: bool = False    # True when `count` is larger than len(tokens)


class TokenizerInfo(BaseModel):
    name: str
    family: str
    algorithm: str
    exact: bool                # False = an estimate, not a real tokenizer
    has_tokens: bool = True    # False = only a count is available, no token list


class ModelInfo(BaseModel):
    id: str
    display_name: str
    tokenizer: str
    context_window: int
    max_output_tokens: int | None
    source_url: str
    last_verified: date


class Limits(BaseModel):
    max_text_chars: int


# ---- /api/compare -------------------------------------------------------------------------
MAX_COMPARE = 8              # tokenizers per request
COMPARE_MAX_TOKENS = 1000    # tokens sent back per tokenizer (the count is always complete)


class CompareRequest(BaseModel):
    text: str = Field(max_length=MAX_TEXT_CHARS)
    tokenizers: list[str] | None = Field(default=None, min_length=1, max_length=MAX_COMPARE)  # None = all


class CompareResult(BaseModel):
    """One row of the comparison. A tokenizer that fails gets error=... and the others still work."""
    name: str
    family: str
    algorithm: str
    exact: bool
    has_tokens: bool
    count: int | None
    chars_per_token: float | None
    tokens: list[TokenOut]       # at most COMPARE_MAX_TOKENS
    truncated: bool              # True when count is larger than len(tokens)
    error: str | None


class CompareResponse(BaseModel):
    chars: int
    bytes: int
    results: list[CompareResult]


# ---- /api/simulate ------------------------------------------------------------------------
MAX_MESSAGES = 50
MAX_WINDOW = 10_000_000


class SimMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    text: str = Field(max_length=MAX_TEXT_CHARS)


class SimulateRequest(BaseModel):
    model: str                                     # chooses the tokenizer (and the default window)
    messages: list[SimMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    strategy: Literal["error", "drop_oldest", "truncate_start", "truncate_end"] = "drop_oldest"
    context_window: int | None = Field(default=None, ge=1, le=MAX_WINDOW)   # None = the model's own
    reserve_output: int = Field(default=1024, ge=0, le=MAX_WINDOW)          # room kept for the answer
    per_message_overhead: int = Field(default=4, ge=0, le=100)              # chat-format tokens per message

    @model_validator(mode="after")
    def _total_size(self):
        if sum(len(m.text) for m in self.messages) > MAX_TEXT_CHARS:
            raise ValueError(f"all messages together may have at most {MAX_TEXT_CHARS} characters")
        return self


class SimMessageResult(BaseModel):
    index: int
    role: str
    chars: int
    tokens: int                                    # the message's own tokens (without overhead)
    status: Literal["kept", "partial", "dropped"]
    kept_tokens: int
    kept_chars: tuple[int, int] | None = None      # [start, end) in characters, only for "partial"


class SimulateResponse(BaseModel):
    model: str
    tokenizer: str
    exact: bool
    strategy: str
    context_window: int
    reserve_output: int
    budget: int                                    # window minus reserve_output
    per_message_overhead: int
    total_tokens: int                              # the whole conversation, overhead included
    used_tokens: int                               # what remains after the strategy was applied
    overflow_tokens: int                           # how far the whole conversation is over the budget
    fits: bool
    cannot_fit: bool                               # the system messages alone are over the budget
    nothing_fits: bool
    messages: list[SimMessageResult]
