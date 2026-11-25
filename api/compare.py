"""Run several tokenizers on one text. A failing tokenizer becomes an error row; it never
stops the others."""
import logging
from concurrent.futures import ThreadPoolExecutor

from src.tokenizers import TokenizerLoadError, TokenizerRegistry

from .schemas import CompareResult, TokenizerInfo, TokenOut

log = logging.getLogger("tokenizer-api")


def run_compare(registry: TokenizerRegistry, infos: dict[str, TokenizerInfo], text: str,
                names: list[str], max_tokens: int) -> list[CompareResult]:
    def one(name: str) -> CompareResult:
        info = infos.get(name)
        meta = dict(name=name, family=info.family if info else "", algorithm=info.algorithm if info else "",
                    exact=info.exact if info else True, has_tokens=info.has_tokens if info else True)
        try:
            tok = registry.get(name)
            meta.update(family=tok.family, algorithm=tok.algorithm, exact=tok.exact,
                        has_tokens=tok.provides_tokens)
            if tok.provides_tokens:
                tokens = tok.encode(text)
                count = len(tokens)
            else:                       # count-only source: there is no token list
                tokens, count = [], tok.count(text)
        except TokenizerLoadError as exc:
            log.warning("load failed: %s", exc)
            return CompareResult(**meta, count=None, chars_per_token=None, tokens=[], truncated=False,
                                 error=str(exc)[:300])
        except Exception:               # a bug in one adapter must not break the whole comparison
            log.exception("tokenizer %s failed", name)
            return CompareResult(**meta, count=None, chars_per_token=None, tokens=[], truncated=False,
                                 error="Unexpected error while tokenizing (see the server log)")
        return CompareResult(
            **meta, count=count, chars_per_token=round(len(text) / count, 3) if count else None,
            tokens=[TokenOut(id=t.id, text=t.text, piece=t.piece, start=t.start, end=t.end)
                    for t in tokens[:max_tokens]],
            truncated=count > len(tokens[:max_tokens]) and meta["has_tokens"], error=None)

    # Threads: the first request may have to load several models, and they can load in parallel.
    with ThreadPoolExecutor(max_workers=max(1, min(len(names), 8))) as pool:
        return list(pool.map(one, names))   # map keeps the order of `names`
