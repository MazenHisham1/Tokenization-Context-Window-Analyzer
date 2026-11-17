"""Request and response shapes of the API. FastAPI validates them and builds the docs from them."""
import os
from datetime import date

from pydantic import BaseModel, Field

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


class TokenizeResponse(BaseModel):
    tokenizer: str
    count: int
    chars: int
    bytes: int
    chars_per_token: float | None
    tokens: list[TokenOut]


class TokenizerInfo(BaseModel):
    name: str
    family: str
    algorithm: str
    exact: bool


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
