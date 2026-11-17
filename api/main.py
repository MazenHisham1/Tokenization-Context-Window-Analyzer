"""The web API. `create_app` receives its dependencies, so tests can pass a fake registry."""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import ModelSpec
from src.tokenizers import TokenizerLoadError, TokenizerRegistry

from .schemas import (MAX_TEXT_CHARS, Limits, ModelInfo, TokenizeRequest, TokenizeResponse,
                      TokenizerInfo, TokenOut)

log = logging.getLogger("tokenizer-api")


def create_app(registry: TokenizerRegistry, infos: list[TokenizerInfo],
               models: dict[str, ModelSpec], cors_origins: list[str] | None = None) -> FastAPI:
    app = FastAPI(title="Tokenization & Context Window Analyzer", version="0.3.0")

    if cors_origins:   # only needed when the front end is served from another address
        app.add_middleware(CORSMiddleware, allow_origins=cors_origins,
                           allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        # FastAPI's default reply echoes the input back. Here that could be 50,000
        # characters of user text, or an invalid string that cannot even be encoded
        # (a 500 error). We return only where the problem is and what it is.
        detail = [{"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": detail})

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/limits", response_model=Limits)
    def limits():
        return Limits(max_text_chars=MAX_TEXT_CHARS)

    @app.get("/api/tokenizers", response_model=list[TokenizerInfo])
    def list_tokenizers():
        # Built from metadata only: listing must never trigger a model download.
        return infos

    @app.get("/api/models", response_model=list[ModelInfo])
    def list_models():
        return [ModelInfo(id=m.id, display_name=m.display_name, tokenizer=m.tokenizer,
                          context_window=m.context_window, max_output_tokens=m.max_output_tokens,
                          source_url=m.source_url, last_verified=m.last_verified)
                for m in models.values()]

    # A plain `def` (not async): FastAPI runs it in a worker thread, so a slow first
    # model load does not freeze the other requests.
    @app.post("/api/tokenize", response_model=TokenizeResponse)
    def tokenize(req: TokenizeRequest):
        if req.tokenizer not in registry:
            raise HTTPException(404, f"Unknown tokenizer {req.tokenizer!r}")
        try:
            tokens = registry.get(req.tokenizer).encode(req.text)
            n_bytes = len(req.text.encode("utf-8"))
        except TokenizerLoadError as exc:
            log.warning("load failed: %s", exc)
            raise HTTPException(503, str(exc)[:300]) from exc
        n = len(tokens)
        return TokenizeResponse(
            tokenizer=req.tokenizer, count=n, chars=len(req.text), bytes=n_bytes,
            chars_per_token=round(len(req.text) / n, 3) if n else None,
            tokens=[TokenOut(id=t.id, text=t.text, piece=t.piece, start=t.start, end=t.end)
                    for t in tokens])

    return app
