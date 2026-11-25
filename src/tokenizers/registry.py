"""Registry: find a tokenizer by name. Tokenizers load lazily, on first `get`."""
from __future__ import annotations

import threading
from collections.abc import Callable

from .base import Tokenizer


class TokenizerRegistry:
    def __init__(self):
        self._factories: dict[str, Callable[[], Tokenizer]] = {}
        self._instances: dict[str, Tokenizer] = {}
        self._guard = threading.Lock()                 # protects the dict of locks below
        self._locks: dict[str, threading.Lock] = {}    # one lock per tokenizer name

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
        tokenizer = self._instances.get(name)
        if tokenizer is not None:
            return tokenizer
        # The web server calls get() from several threads. One lock PER NAME means two
        # requests for the same model load it once, while different models load in parallel
        # (the comparison endpoint relies on that).
        with self._guard:
            lock = self._locks.setdefault(name, threading.Lock())
        with lock:
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
