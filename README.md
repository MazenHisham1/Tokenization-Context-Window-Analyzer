# Tokenization & Context Window Analyzer

See how different tokenizers (OpenAI, Llama, Gemma, and my own BPE) split the same text.

**Status:** Phase 3, a working local MVP (API + web UI). Not deployed yet.

```
config/models.json   tokenizers and models (context windows with source + last_verified date)
src/                 Phase 0-2 engine: from-scratch BPE, adapters, registry, config loader
api/                 FastAPI server wrapping the engine
frontend/            React + TypeScript (Vite) UI
tests/               pytest (74 tests, offline)
docs/                DESIGN.md (engine design), PHASE3_WALKTHROUGH.md (how the web app works)
```

## Run it
```bash
pip install -r requirements.txt
uvicorn api.server:app --reload            # terminal 1: http://127.0.0.1:8000/docs
cd frontend && npm install && npm run dev  # terminal 2: http://localhost:5173
```
Llama and Gemma are gated: accept their licenses on huggingface.co and run `hf auth login`
(or set `HF_TOKEN`) on the machine that runs the server. The token never reaches the browser.

## Test it
```bash
pytest                                     # backend, no internet needed
cd frontend && npm test && npm run build   # unit tests + type check
```

## API
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/tokenizers` | Names and metadata (never loads a model) |
| POST | `/api/tokenize` | `{text, tokenizer}` -> count and tokens (id, text, piece, byte span) |
| GET | `/api/models` | Context windows from the config, with source and verification date |
| GET | `/api/limits`, `/api/health` | Limits and health check |

Errors: 404 unknown tokenizer, 503 tokenizer cannot load, 422 invalid input.
See `docs/PHASE3_WALKTHROUGH.md` for how it works and `docs/DESIGN.md` for the engine design.
