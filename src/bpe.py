"""Minimal byte-level BPE tokenizer (GPT-2 style, simplified).

Pipeline:  text -> pre-tokens (regex) -> UTF-8 bytes -> apply learned merges -> ids
Because the base vocabulary is all 256 byte values, ANY text (Arabic, emoji,
code, odd whitespace) can be encoded, and decode(encode(text)) == text.
"""
import re
from collections import Counter

# Pre-tokenizer: a word (with its leading space), punctuation/emoji run, or whitespace.
PRETOKEN = re.compile(r" ?\w+| ?[^\w\s]+|\s+(?!\S)|\s+")


class BPETokenizer:
    def __init__(self, special_tokens=("<|endoftext|>",)):
        self.merges = {}            # (id_a, id_b) -> new_id, in learning order
        self.vocab = {i: bytes([i]) for i in range(256)}   # id -> bytes
        self.special = {}           # special token string -> id
        self._special_tokens = tuple(special_tokens)
        self._cache = {}

    # ---------- training ----------
    @staticmethod
    def _pair_counts(words):
        counts = Counter()
        for word, freq in words.items():
            for pair in zip(word, word[1:], strict=False):
                counts[pair] += freq
        return counts

    @staticmethod
    def _merge(word, pair, new_id):
        out, i = [], 0
        while i < len(word):
            if i < len(word) - 1 and (word[i], word[i + 1]) == pair:
                out.append(new_id)
                i += 2
            else:
                out.append(word[i])
                i += 1
        return tuple(out)

    def train(self, text, vocab_size, verbose=False):
        """Learn (vocab_size - 256) merges from `text`."""
        if vocab_size < 256:
            raise ValueError("vocab_size must be >= 256 (the byte alphabet)")
        pieces = Counter(PRETOKEN.findall(text))
        words = {tuple(p.encode("utf-8")): f for p, f in pieces.items()}
        for _ in range(vocab_size - 256):
            counts = self._pair_counts(words)
            if not counts:
                break
            # most frequent pair; ties -> smallest pair (deterministic)
            best = min(counts, key=lambda p: (-counts[p], p))
            new_id = 256 + len(self.merges)
            self.merges[best] = new_id
            self.vocab[new_id] = self.vocab[best[0]] + self.vocab[best[1]]
            words = {self._merge(w, best, new_id): f for w, f in words.items()}
            if verbose:
                print(f"merge {new_id - 255:>3}: {self.vocab[best[0]]!r} + "
                      f"{self.vocab[best[1]]!r} -> {self.vocab[new_id]!r}  (x{counts[best]})")
        for tok in self._special_tokens:          # special tokens get ids AFTER merges
            self.special[tok] = len(self.vocab)
            self.vocab[self.special[tok]] = tok.encode("utf-8")
        self._cache.clear()
        return self

    # ---------- encoding ----------
    def _encode_piece(self, piece):
        if piece in self._cache:
            return self._cache[piece]
        ids = list(piece.encode("utf-8"))
        while len(ids) >= 2:
            pairs = set(zip(ids, ids[1:], strict=False))
            # apply the merge that was learned EARLIEST (lowest new id)
            best = min(pairs, key=lambda p: self.merges.get(p, float("inf")))
            if best not in self.merges:
                break
            ids = list(self._merge(tuple(ids), best, self.merges[best]))
        self._cache[piece] = ids
        return ids

    def encode(self, text):
        if self.special:
            pattern = "(" + "|".join(re.escape(t) for t in self.special) + ")"
            parts = re.split(pattern, text)
        else:
            parts = [text]
        ids = []
        for part in parts:
            if part in self.special:
                ids.append(self.special[part])
            else:
                for piece in PRETOKEN.findall(part):
                    ids.extend(self._encode_piece(piece))
        return ids

    def decode(self, ids):
        raw = b"".join(self.vocab[i] for i in ids)
        return raw.decode("utf-8", errors="replace")

    def tokens(self, text):
        """Human-readable pieces. Partial UTF-8 bytes are shown as escapes."""
        return [self.vocab[i].decode("utf-8", errors="backslashreplace")
                for i in self.encode(text)]

    @property
    def vocab_size(self):
        return len(self.vocab)
