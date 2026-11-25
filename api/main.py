"""The web API. `create_app` receives its dependencies, so tests can pass a fake registry."""
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import ModelSpec
from src.context import Size, plan_context
from src.tokenizers import TokenizationNotSupported, TokenizerLoadError, TokenizerRegistry
from src.tokenizers.base import char_spans

from .compare import run_compare
from .schemas import (
    COMPARE_MAX_TOKENS,
    MAX_TEXT_CHARS,
    TOKENIZE_MAX_TOKENS,
    CompareRequest,
    CompareResponse,
    Limits,
    ModelInfo,
    SimMessageResult,
    SimulateRequest,
    SimulateResponse,
    TokenizeRequest,
    TokenizeResponse,
    TokenizerInfo,
    TokenOut,
)

log = logging.getLogger("tokenizer-api")


def create_app(registry: TokenizerRegistry, infos: list[TokenizerInfo],
               models: dict[str, ModelSpec], cors_origins: list[str] | None = None) -> FastAPI:
    app = FastAPI(title="Tokenization & Context Window Analyzer", version="0.6.0")
    infos_by_name = {i.name: i for i in infos}

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
        except TokenizationNotSupported as exc:   # an estimate: it has a count but no tokens
            raise HTTPException(400, str(exc)) from exc
        n = len(tokens)
        return TokenizeResponse(
            tokenizer=req.tokenizer, count=n, chars=len(req.text), bytes=n_bytes,
            chars_per_token=round(len(req.text) / n, 3) if n else None,
            tokens=[TokenOut(id=t.id, text=t.text, piece=t.piece, start=t.start, end=t.end)
                    for t in tokens[:TOKENIZE_MAX_TOKENS]],   # 50,000 characters can be 44,000 tokens = 2.7 MB of JSON
            truncated=n > TOKENIZE_MAX_TOKENS)

    @app.post("/api/compare", response_model=CompareResponse)
    def compare(req: CompareRequest):
        names = list(dict.fromkeys(req.tokenizers)) if req.tokenizers else registry.names()  # no duplicates
        unknown = [n for n in names if n not in registry]
        if unknown:
            raise HTTPException(404, f"Unknown tokenizer(s): {unknown}")
        return CompareResponse(
            chars=len(req.text), bytes=len(req.text.encode("utf-8")),
            results=run_compare(registry, infos_by_name, req.text, names, COMPARE_MAX_TOKENS))

    @app.post("/api/simulate", response_model=SimulateResponse)
    def simulate(req: SimulateRequest):
        """What stays in the context window, and what is dropped or cut, for a conversation."""
        spec = models.get(req.model)
        if spec is None:
            raise HTTPException(404, f"Unknown model {req.model!r}")
        if spec.tokenizer not in registry:
            raise HTTPException(503, f"Tokenizer {spec.tokenizer!r} of this model is not available")
        window = req.context_window or spec.context_window
        if req.reserve_output >= window:
            raise HTTPException(
                400, f"reserve_output ({req.reserve_output}) must be smaller than the context window ({window})")
        try:
            tok = registry.get(spec.tokenizer)
            if req.strategy in ("truncate_start", "truncate_end") and not tok.provides_tokens:
                raise HTTPException(400, f"{spec.tokenizer} only estimates counts, so it cannot cut text at a token")
            counts = [tok.count(m.text) for m in req.messages]
            plan = plan_context([Size(m.role, c) for m, c in zip(req.messages, counts, strict=True)],
                                window - req.reserve_output, req.strategy, req.per_message_overhead)
            out: list[SimMessageResult] = []
            for i, (m, c, d) in enumerate(zip(req.messages, counts, plan.decisions, strict=True)):
                kept_chars = None
                if d.status == "partial":
                    spans = char_spans(m.text, tok.encode(m.text))   # one (start, end) per token
                    n = len(spans)
                    if d.keeps == "start":
                        kept_chars = (0, spans[d.kept_tokens - 1][1])
                    else:
                        kept_chars = (spans[n - d.kept_tokens][0], len(m.text))
                out.append(SimMessageResult(index=i, role=m.role, chars=len(m.text), tokens=c, status=d.status,
                                            kept_tokens=d.kept_tokens, kept_chars=kept_chars))
        except TokenizerLoadError as exc:
            log.warning("load failed: %s", exc)
            raise HTTPException(503, str(exc)[:300]) from exc
        return SimulateResponse(
            model=spec.id, tokenizer=spec.tokenizer, exact=tok.exact, strategy=req.strategy, context_window=window,
            reserve_output=req.reserve_output, budget=plan.budget, per_message_overhead=req.per_message_overhead,
            total_tokens=plan.total, used_tokens=plan.used, overflow_tokens=max(0, plan.total - plan.budget),
            fits=plan.fits, cannot_fit=plan.cannot_fit, nothing_fits=plan.nothing_fits, messages=out)

    return app
