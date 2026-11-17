# Design: Tokenizer Core (Phase 2)

## Goal
One interface for many tokenizer families, so the app (comparison view, context simulator) never
needs to know whether a token list came from tiktoken, Hugging Face, or my own BPE.

## Folder structure
```
config/models.json            tokenizers + models: context window, source URL, last_verified
src/bpe.py                    from-scratch byte-level BPE (Phase 0)
src/config.py                 load + validate models.json, stale check, build lazy registry
src/tokenizers/base.py        Token, Tokenizer (ABC), char_spans helper, TokenizerLoadError
src/tokenizers/tiktoken_adapter.py
src/tokenizers/huggingface_adapter.py
src/tokenizers/custom_bpe_adapter.py
src/tokenizers/registry.py    name -> tokenizer, lazy factories
src/tokenizers/compare.py     compare_counts(): one row per tokenizer, errors kept per row
tests/                        contract tests (all adapters), registry, config
```

## Data model
`Token(id, text, start, end, piece)` is frozen. `start`/`end` are **byte offsets** into the UTF-8
input.

## Decisions and why
| Decision | Reason |
|---|---|
| Byte offsets, not character offsets | Byte-level tokenizers split one emoji into several tokens; a character offset cannot describe half a character. `char_spans()` converts when the UI needs characters. |
| Tokens that split a character show U+FFFD as `text` | Honest: that token alone is not valid text. `piece` keeps the raw spelling (`\xf0`). |
| Adapters load lazily; the registry stores factories | Starting the app must not download Llama and Gemma. A gated or offline model fails only when used. |
| `exact` flag on every tokenizer | Some vendors do not publish tokenizers. A future adapter can return estimates and the UI can label them. |
| Dependency injection (`encoding=`, `tokenizer=`) | Tests run offline with tiny tokenizers built locally. |
| `compare_counts` returns an error per row | One broken tokenizer must not hide the others. |
| Context windows live in JSON with `source_url` + `last_verified` | They change often. `stale_models()` flags entries older than 90 days. |

## Known limitations
- HF tokens that split one character (byte fallback) share that character's span, so spans can repeat. tiktoken and custom-BPE spans never overlap.
- HF offsets come from the library; their exact handling of leading spaces differs by tokenizer (SentencePiece vs byte-level). Check each real model in Phase 5.
- Python offsets are not JavaScript (UTF-16) offsets. The web app must compute its own spans.
- Gated models (Llama, Gemma) need a Hugging Face login or `HF_TOKEN`.
- No decode, no special-token insertion, no chat templates yet.

## Extension points
- `AnthropicEstimateAdapter` (exact=False) for closed tokenizers.
- A JSON export of `list[Token]` for the web front end (Phase 3).
