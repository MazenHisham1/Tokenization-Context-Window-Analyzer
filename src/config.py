"""Load and validate config/models.json (tokenizers + model context windows)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .tokenizers import HeuristicAdapter, HuggingFaceAdapter, TiktokenAdapter, TokenizerRegistry


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ModelSpec:
    id: str
    display_name: str
    tokenizer: str
    context_window: int
    source_url: str
    last_verified: date
    max_output_tokens: int | None = None
    notes: str = ""


def load_config(path: str | Path) -> tuple[dict[str, dict], dict[str, ModelSpec]]:
    """Returns (tokenizer_specs, models_by_id). Raises ConfigError with a clear message."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    tokenizers = data.get("tokenizers") or {}
    models: dict[str, ModelSpec] = {}
    for raw in data.get("models", []):
        mid = raw.get("id", "<missing id>")
        for key in ("id", "display_name", "tokenizer", "context_window", "source_url", "last_verified"):
            if key not in raw:
                raise ConfigError(f"model {mid}: missing field {key!r}")
        if raw["tokenizer"] not in tokenizers:
            raise ConfigError(f"model {mid}: unknown tokenizer {raw['tokenizer']!r}")
        for key in ("context_window", "max_output_tokens"):
            v = raw.get(key)
            if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v <= 0):
                raise ConfigError(f"model {mid}: {key} must be a positive integer, got {v!r}")
        if not str(raw["source_url"]).startswith("http"):
            raise ConfigError(f"model {mid}: source_url must be a URL")
        try:
            verified = date.fromisoformat(raw["last_verified"])
        except ValueError as exc:
            raise ConfigError(f"model {mid}: last_verified must be YYYY-MM-DD") from exc
        if mid in models:
            raise ConfigError(f"duplicate model id {mid!r}")
        models[mid] = ModelSpec(
            id=mid, display_name=raw["display_name"], tokenizer=raw["tokenizer"],
            context_window=raw["context_window"], source_url=raw["source_url"],
            last_verified=verified, max_output_tokens=raw.get("max_output_tokens"),
            notes=raw.get("notes", ""))
    return tokenizers, models


def stale_models(models: dict[str, ModelSpec], today: date, max_age_days: int = 90) -> list[str]:
    """Ids of models whose numbers were last verified more than `max_age_days` ago."""
    return [m.id for m in models.values() if (today - m.last_verified).days > max_age_days]


def build_registry(tokenizer_specs: dict[str, dict]) -> TokenizerRegistry:
    """One lazy factory per tokenizer: nothing is downloaded until `registry.get(name)`."""
    registry = TokenizerRegistry()
    for name, spec in tokenizer_specs.items():
        adapter = spec.get("adapter")
        if adapter == "tiktoken":
            registry.register_factory(name, lambda n=name, s=spec: TiktokenAdapter(
                n, s["encoding"], family=s.get("family", "")))
        elif adapter == "huggingface":
            registry.register_factory(name, lambda n=name, s=spec: HuggingFaceAdapter(
                n, s["hf_id"], family=s.get("family", ""), algorithm=s.get("algorithm", "")))
        elif adapter == "heuristic":
            registry.register_factory(name, lambda n=name, s=spec: HeuristicAdapter(
                n, s.get("chars_per_token", 4.0), family=s.get("family", "estimate")))
        else:
            raise ConfigError(f"tokenizer {name}: unknown adapter {adapter!r}")
    return registry
