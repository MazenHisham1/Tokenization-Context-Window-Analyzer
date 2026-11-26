"""Production wiring: reads config/models.json and builds the real app.

Run from the project root:   uvicorn api.server:app --reload
"""
import os
from pathlib import Path

from src.bpe import BPETokenizer
from src.config import build_registry, load_config
from src.tokenizers import CustomBPEAdapter

from .hardening import add_rate_limit, warm_up
from .main import create_app
from .schemas import TokenizerInfo

ROOT = Path(__file__).resolve().parent.parent


def build_default_app():
    specs, models = load_config(ROOT / "config" / "models.json")
    registry = build_registry(specs)   # lazy: nothing is downloaded yet
    infos = [TokenizerInfo(name=n, family=s.get("family", ""), algorithm=s.get("algorithm", ""),
                           exact=s.get("exact", True), has_tokens=s.get("adapter") != "heuristic")
             for n, s in specs.items()]

    # Your own tokenizer from Phase 0, trained at start-up on a small bundled text (fast).
    text = (ROOT / "data" / "bpe_training_text.txt").read_text(encoding="utf-8")
    mine = CustomBPEAdapter(BPETokenizer().train(text, vocab_size=300))
    registry.register(mine)
    infos.append(TokenizerInfo(name=mine.name, family=mine.family, algorithm=mine.algorithm, exact=True))

    origins = [o for o in os.getenv("CORS_ORIGINS", "").split(",") if o]
    dist = Path(os.getenv("FRONTEND_DIST", ROOT / "frontend" / "dist"))
    app = create_app(registry, infos, models, cors_origins=origins, static_dir=dist)

    # Public-site settings, all off by default so a local run behaves as before.
    if int(os.getenv("RATE_LIMIT_PER_MIN", "0")) > 0:
        add_rate_limit(app, int(os.getenv("RATE_LIMIT_PER_MIN", "0")), int(os.getenv("TRUST_PROXY_HOPS", "0")))
    if os.getenv("WARMUP") == "1":
        warm_up(registry, [n for n, s in specs.items() if s.get("adapter") != "heuristic"])
    return app


app = build_default_app()
