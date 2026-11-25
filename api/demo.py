"""OFFLINE DEMO: no downloads, no Hugging Face login.

Three byte-level BPE tokenizers trained by this project, with different vocabulary sizes,
plus the characters ÷ 4 estimate. Handy for trying the Compare view anywhere, and it shows
the effect of vocabulary size directly.

Run from the project root:   uvicorn api.demo:app --reload
"""
from datetime import date
from pathlib import Path

from src.bpe import BPETokenizer
from src.config import ModelSpec
from src.tokenizers import CustomBPEAdapter, HeuristicAdapter, TokenizerRegistry

from .main import create_app
from .schemas import TokenizerInfo

ROOT = Path(__file__).resolve().parent.parent
VOCAB_SIZES = (280, 300, 360)


def build_demo_app():
    text = (ROOT / "data" / "bpe_training_text.txt").read_text(encoding="utf-8")
    registry, infos = TokenizerRegistry(), []
    for size in VOCAB_SIZES:
        tok = CustomBPEAdapter(BPETokenizer().train(text, vocab_size=size), name=f"bpe-{size}")
        registry.register(tok)
        infos.append(TokenizerInfo(name=tok.name, family="custom", exact=True,
                                   algorithm=f"byte-level BPE, vocabulary {size}"))
    est = HeuristicAdapter("rule-of-thumb-4", 4)
    registry.register(est)
    infos.append(TokenizerInfo(name=est.name, family=est.family, algorithm=est.algorithm,
                               exact=False, has_tokens=False))
    # Tiny windows on purpose: a 128,000-token window is hard to overflow by typing.
    models = {m.id: m for m in (
        ModelSpec("demo-small", "Demo (tiny window)", "bpe-300", 200, "local demo", date(2026, 11, 18)),
        ModelSpec("demo-medium", "Demo (medium window)", "bpe-360", 600, "local demo", date(2026, 11, 18)),
    )}
    return create_app(registry, infos, models=models)


app = build_demo_app()
