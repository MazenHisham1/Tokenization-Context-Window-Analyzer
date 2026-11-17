# Phase 3 Walkthrough: how the web app works

Read this once from top to bottom, then open the files in the order of section 3.

## 1. The big picture

```
 Browser (React, port 5173)                 Python server (FastAPI, port 8000)
 ┌──────────────────────────┐   HTTP/JSON   ┌───────────────────────────────────────┐
 │ textarea + dropdown      │ ────────────► │ api/main.py   validates the request   │
 │ waits 300 ms after typing│  POST         │      │                                │
 │ shows count + token table│  /api/tokenize│      ▼                                │
 │                          │ ◄──────────── │ TokenizerRegistry.get(name)  (Phase 2)│
 └──────────────────────────┘   tokens      │      │  loads the model only now      │
                                            │      ▼                                │
                                            │ adapter.encode(text) -> list[Token]   │
                                            └───────────────────────────────────────┘
```
The browser never runs a tokenizer and never sees your Hugging Face token. The Phase 2 engine
(adapters, registry, config) is reused unchanged. Phase 3 only adds a thin HTTP layer and a UI.

## 2. What happens when you type

1. You type. `useDebounce` waits until you stop for 300 ms (typing "hello" sends 1 request, not 5).
2. `App.tsx` calls `tokenize(text, tokenizer)` in `api.ts` with an `AbortController`.
3. Vite forwards `/api/...` to port 8000 (`vite.config.ts`), so the browser sees one address.
4. FastAPI validates the body (`schemas.py`): text at most 50,000 characters, tokenizer not empty.
5. `main.py` asks the registry for the tokenizer. The **first** time, the model loads (it can take seconds). Later calls reuse it.
6. The adapter returns `Token` objects; the API turns them into JSON with counts.
7. React shows the stats and the table. If you typed again meanwhile, the old request is cancelled.

## 3. File by file (read in this order)

| File | What to learn from it |
|---|---|
| `api/schemas.py` | The shape of every request and response. Pydantic checks them and FastAPI builds `/docs` from them. |
| `api/main.py` | `create_app(...)` receives its dependencies instead of creating them. That is **dependency injection**, and it is why the tests can pass a fake registry. |
| `api/server.py` | The real wiring: reads `config/models.json`, builds the lazy registry, adds your BPE trained at start-up. |
| `tests/test_api.py` | What the API promises: 404, 503, 422, empty text, no model loading when listing. |
| `frontend/src/types.ts` | The same shapes as `schemas.py`, in TypeScript. |
| `frontend/src/api.ts` | One `request()` function that turns every failure into a readable message. |
| `frontend/src/useDebounce.ts` | 8 lines; the cleanup function is the important part. |
| `frontend/src/App.tsx` | Two `useEffect`s: load the tokenizer list once; tokenize when the debounced text or the tokenizer changes. |
| `frontend/src/TokenTable.tsx`, `visible.ts` | Shows the first 1,000 tokens; makes spaces and newlines visible (`·`, `↵`). |

## 4. Design decisions, and the bugs that shaped them

| Decision | Why |
|---|---|
| `/api/tokenizers` reads metadata only | Listing must never download a model. A test proves it (a broken tokenizer is listed without error). |
| Endpoints are plain `def`, not `async def` | FastAPI runs them in worker threads, so a slow model load does not block other requests. |
| A lock inside `registry.get` | Two requests arriving together must not load the same model twice. |
| 503 for "cannot load", 404 for "unknown", 422 for "bad input" | The front end can show a precise message for each. |
| Limit of 50,000 characters, reported by `/api/limits` | Protects the server. The UI shows the same number, so the two can't disagree. |
| Table shows at most 1,000 rows | 50,000 rows would freeze the page. Phase 4 replaces the table with a smarter view. |
| Debounce + `AbortController` | Fewer requests, and an old slow answer can never overwrite a newer one. |

**Bug 1, found while testing:** FastAPI's default 422 reply sends your input back. For a lone
invalid character (`"\ud800"`) that reply could not be encoded and became a 500 error; for a
too-long text it would send back 50,000 characters. `api/main.py` now returns only *where* and
*what* the problem is. A test checks the reply never contains the text.

**Bug 2, found in the browser:** the counter under the text box said 69 characters while the
server said 68. JavaScript's `text.length` counts UTF-16 units, so one emoji counts as 2; Python
counts 1. The fix is `[...text].length`. This is the same lesson as byte vs character offsets in
Phase 2: **"length" depends on how you count**, and every layer must agree.

## 5. How to run

You need Python (your `dl_env`) and Node.js 22 LTS (nodejs.org).

```bash
# Terminal 1 (project root)
pip install -r requirements.txt
uvicorn api.server:app --reload          # API on http://127.0.0.1:8000, docs at /docs

# Terminal 2
cd frontend
npm install
npm run dev                              # open http://localhost:5173
```
Tests: `pytest` (74 tests) and, inside `frontend/`, `npm test` (7 tests) and `npm run build` (type check).

Try the API without the UI:
```bash
curl -X POST http://127.0.0.1:8000/api/tokenize -H "Content-Type: application/json" \
     -d '{"text": "Hello 😊", "tokenizer": "my-bpe"}'
```

## 6. Known limitations
- The token table is plain text. Colour-coded chips over the original text come in Phase 4.
- No comparison view yet (Phase 5) and no context-window simulation yet (Phase 6). `/api/models` already serves the context windows from the config.
- The first request to a model is slow because it loads the model. The UI shows "Tokenizing…".
- Gated models need your Hugging Face login on the machine that runs the server.
- Tested here in Chromium on desktop and phone width; not tested in Safari or Firefox.
- Nothing is deployed yet (Phase 8). Deploying needs `HF_TOKEN` as a server secret and `CORS_ORIGINS` if the front end is hosted elsewhere.

## 7. Check yourself (answer in your own words)
1. Why does `/api/tokenizers` not call the tokenizers, and which test proves it?
2. What would go wrong without the `AbortController` if you type quickly and the first request is slow?
3. Why does the server return 503 for a model that cannot load, but 404 for an unknown name?
4. Why is `create_app` a function that takes a registry instead of a global `app`?
5. Why can a text box say 69 characters when the server counts 68?

## 8. Your tasks to make it yours
1. Run it. Type English, Arabic and an emoji, and switch between all four tokenizers. Send a screenshot.
2. Add a "Copy token IDs" button (hint: `navigator.clipboard.writeText`).
3. Add one test to `tests/test_api.py` and one to `frontend/src/api.test.ts` for behaviour you add.
4. Put the project on GitHub (the `.gitignore` is ready) and send me the link.
