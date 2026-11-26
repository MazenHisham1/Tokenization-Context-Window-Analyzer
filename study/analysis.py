"""The numbers of the multilingual study. Pure functions: no tokenizers, no files, no network."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Premium:
    ratio: float   # tokens in this language / tokens in the baseline language, for the same sentences
    low: float     # lower end of the confidence interval
    high: float    # upper end


def paired_ratio(lang_counts: Sequence[int], base_counts: Sequence[int], *, n_boot: int = 2000,
                 confidence: float = 0.95, seed: int = 0) -> Premium:
    """How many times as many tokens does a language need as the baseline, for the SAME sentences?

    `lang_counts[i]` and `base_counts[i]` are the token counts of the same sentence in two languages
    (a parallel corpus). The ratio is the total tokens of one over the total of the other, so long sentences
    count for more, as they do on a bill. The interval comes from the bootstrap: draw the sentence numbers
    with replacement many times, recompute the ratio each time, and take the middle `confidence` share.
    Drawing the SAME sentence numbers for both languages keeps the pairing, which is what makes the
    interval honest: some sentences are simply longer in every language.
    """
    if len(lang_counts) != len(base_counts):
        raise ValueError("the two languages need the same number of sentences (a parallel corpus)")
    if len(lang_counts) == 0:
        raise ValueError("no sentences")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    lang = np.asarray(lang_counts, dtype=float)
    base = np.asarray(base_counts, dtype=float)
    if base.sum() <= 0:
        raise ValueError("the baseline has no tokens")

    ratio = lang.sum() / base.sum()
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(lang), size=(n_boot, len(lang)))
    base_totals = base[picks].sum(axis=1)
    ratios = lang[picks].sum(axis=1) / np.where(base_totals > 0, base_totals, np.nan)
    tail = (1 - confidence) / 2 * 100
    low, high = np.nanpercentile(ratios, [tail, 100 - tail])
    return Premium(float(ratio), float(low), float(high))


@dataclass(frozen=True)
class Row:
    language: str
    tokenizer: str
    sentences: int
    mean_tokens: float
    chars_per_token: float
    bytes_per_token: float
    premium: Premium


def summarize(texts: dict[str, list[str]], counts: dict[str, list[int]], tokenizer: str, baseline: str,
              **boot) -> list[Row]:
    """One Row per language for one tokenizer. `texts[lang][i]` and `counts[lang][i]` describe sentence i."""
    if baseline not in counts:
        raise ValueError(f"baseline language {baseline!r} is not in the data")
    rows = []
    for lang, tokens in counts.items():
        chars = sum(len(t) for t in texts[lang])
        bytes_ = sum(len(t.encode("utf-8")) for t in texts[lang])
        total = sum(tokens)
        rows.append(Row(
            language=lang, tokenizer=tokenizer, sentences=len(tokens), mean_tokens=total / len(tokens),
            chars_per_token=chars / total if total else float("nan"),
            bytes_per_token=bytes_ / total if total else float("nan"),
            premium=paired_ratio(tokens, counts[baseline], **boot)))
    return rows
