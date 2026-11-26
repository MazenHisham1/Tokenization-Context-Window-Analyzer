"""The chart of the study: how many times as many tokens as English, per language, per tokenizer."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")   # draw to a file, no window
import matplotlib.pyplot as plt  # noqa: E402

from .analysis import Row  # noqa: E402

OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9"]   # distinguishable with colour-vision deficiency


def draw(rows: list[Row], baseline: str, path: Path) -> None:
    tokenizers = list(dict.fromkeys(r.tokenizer for r in rows))
    languages = [lang for lang in dict.fromkeys(r.language for r in rows) if lang != baseline]
    mean_by_lang = {lang: sum(r.premium.ratio for r in rows if r.language == lang) / len(tokenizers)
                    for lang in languages}
    languages.sort(key=lambda lang: mean_by_lang[lang])          # cheapest at the top

    height = 0.8 / len(tokenizers)
    fig, ax = plt.subplots(figsize=(9, 0.55 * len(languages) + 1.8))
    for t_index, tokenizer in enumerate(tokenizers):
        by_lang = {r.language: r for r in rows if r.tokenizer == tokenizer}
        ys = [i + (t_index - (len(tokenizers) - 1) / 2) * height for i in range(len(languages))]
        ratios = [by_lang[lang].premium.ratio for lang in languages]
        err = [[r - by_lang[lang].premium.low for r, lang in zip(ratios, languages, strict=True)],
               [by_lang[lang].premium.high - r for r, lang in zip(ratios, languages, strict=True)]]
        ax.barh(ys, ratios, height=height * 0.9, xerr=err, label=tokenizer, color=OKABE_ITO[t_index % 5],
                error_kw={"elinewidth": 1, "capsize": 2})
        # the number itself, so the chart never relies on bar length alone
        for y, lang in zip(ys, languages, strict=True):
            p = by_lang[lang].premium
            ax.text(p.high + 0.04, y, f"{p.ratio:.1f}x", va="center", fontsize=7)
    ax.axvline(1, color="#444", linewidth=1, linestyle="--")
    ax.set_yticks(range(len(languages)), languages)
    ax.invert_yaxis()
    ax.set_xlabel(f"tokens needed, as a multiple of {baseline} (same sentences; bars show the 95% interval)")
    ax.margins(x=0.08)
    ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=len(tokenizers))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=160)
    plt.close(fig)
