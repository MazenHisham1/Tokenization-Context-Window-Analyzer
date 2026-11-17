"""Registry: find a tokenizer by name. Tokenizers load lazily, on first `get`."""
from __future__ import annotations

import threading
from typing import Callable

from .base import Tokenizer


class TokenizerRegistry:
    def __init__(self):
        self._factories: dict[str, Callable[[], Tokenizer]] = {}
        self._instances: dict[str, Tokenizer] = {}
        self._lock = threading.Lock()   # the web server calls get() from several threads

    def register(self, tokenizer: Tokenizer, *, replace: bool = False) -> None:
        """Register a ready tokenizer instance."""
        self.register_factory(tokenizer.name, lambda: tokenizer, replace=replace)

    def register_factory(self, name: str, factory: Callable[[], Tokenizer], *,
                         replace: bool = False) -> None:
        """Register a function that builds the tokenizer when first needed
        (so starting the app does not download every model)."""
        if name in self._factories and not replace:
            raise ValueError(f"tokenizer {name!r} is already registered (use replace=True)")
        self._factories[name] = factory
        self._instances.pop(name, None)

    def get(self, name: str) -> Tokenizer:
        if name not in self._factories:
            raise KeyError(f"unknown tokenizer {name!r}; available: {sorted(self._factories)}")
        with self._lock:                      # two requests must not load the same model twice
            if name not in self._instances:
                self._instances[name] = self._factories[name]()
            return self._instances[name]

    def names(self) -> list[str]:
        return list(self._factories)

    list_tokenizers = names   # name used in the first draft

    def __contains__(self, name: str) -> bool:
        return name in self._factories

    def __len__(self) -> int:
        return len(self._factories)
