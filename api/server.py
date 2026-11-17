"""Production wiring: reads config/models.json and builds the real app.

Run from the project root:   uvicorn api.server:app --reload
"""
import os
from pathlib import Path

from src.bpe import BPETokenizer
from src.config import build_registry, load_config
from src.tokenizers import CustomBPEAdapter

from .main import create_app
from .schemas import TokenizerInfo

ROOT = Path(__file__).resolve().parent.parent


def build_default_app():
    specs, models = load_config(ROOT / "config" / "models.json")
    registry = build_registry(specs)   # lazy: nothing is downloaded yet
    infos = [TokenizerInfo(name=n, family=s.get("family", ""), algorithm=s.get("algorithm", ""),
                           exact=True) for n, s in specs.items()]

    # Your own tokenizer from Phase 0, trained at start-up on a small bundled text (fast).
    text = (ROOT / "data" / "bpe_training_text.txt").read_text(encoding="utf-8")
    mine = CustomBPEAdapter(BPETokenizer().train(text, vocab_size=300))
    registry.register(mine)
    infos.append(TokenizerInfo(name=mine.name, family=mine.family, algorithm=mine.algorithm, exact=True))

    origins = [o for o in os.getenv("CORS_ORIGINS", "").split(",") if o]
    return create_app(registry, infos, models, cors_origins=origins)


app = build_default_app()
