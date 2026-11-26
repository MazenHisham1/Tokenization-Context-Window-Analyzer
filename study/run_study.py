"""Run the multilingual token-cost study.

    pip install -r requirements-study.txt
    hf auth login                                     (FLORES+ and Llama/Gemma are gated)
    python -m study.run_study                         # FLORES+ devtest, o200k_base + llama-3 + gemma-3
    python -m study.run_study --data-dir my_corpus    # your own parallel corpus: one <language>.txt per language
    python -m study.run_study --languages eng_Latn fra_Latn arb_Arab --tokenizers o200k_base

Writes results/multilingual.csv, results/multilingual.md and docs/multilingual_chart.png.
Only token COUNTS are written, never the sentences.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from src.config import build_registry, load_config

from .analysis import Row, summarize
from .corpus import DEFAULT_LANGUAGES, load_dir, load_flores

ROOT = Path(__file__).resolve().parent.parent


def count_all(texts: dict[str, list[str]], tokenizer) -> dict[str, list[int]]:
    return {lang: [tokenizer.count(s) for s in sentences] for lang, sentences in texts.items()}


def write_csv(rows: list[Row], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["language", "tokenizer", "sentences", "mean_tokens", "chars_per_token", "bytes_per_token",
                    "ratio_vs_baseline", "ci_low", "ci_high"])
        for r in rows:
            w.writerow([r.language, r.tokenizer, r.sentences, f"{r.mean_tokens:.2f}", f"{r.chars_per_token:.3f}",
                        f"{r.bytes_per_token:.3f}", f"{r.premium.ratio:.3f}", f"{r.premium.low:.3f}",
                        f"{r.premium.high:.3f}"])


def markdown_table(rows: list[Row], baseline: str) -> str:
    tokenizers = list(dict.fromkeys(r.tokenizer for r in rows))
    languages = list(dict.fromkeys(r.language for r in rows))
    cell = {(r.language, r.tokenizer): r for r in rows}
    lines = [f"Tokens needed as a multiple of {baseline} for the same sentences (95% interval in brackets).", "",
             "| Language | " + " | ".join(tokenizers) + " |", "|---|" + "---:|" * len(tokenizers)]
    for lang in languages:
        cells = []
        for t in tokenizers:
            p = cell[(lang, t)].premium
            cells.append(f"{p.ratio:.2f} ({p.low:.2f} to {p.high:.2f})")
        lines.append(f"| {lang} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--languages", nargs="+", default=DEFAULT_LANGUAGES)
    ap.add_argument("--tokenizers", nargs="+", default=["o200k_base", "llama-3", "gemma-3"])
    ap.add_argument("--baseline", default="eng_Latn")
    ap.add_argument("--split", default="devtest", choices=["dev", "devtest"])
    ap.add_argument("--data-dir", type=Path, help="use your own parallel corpus instead of FLORES+")
    ap.add_argument("--out", type=Path, default=ROOT / "results")
    ap.add_argument("--chart", type=Path, default=ROOT / "docs" / "multilingual_chart.png")
    args = ap.parse_args(argv)

    texts = load_dir(args.data_dir) if args.data_dir else load_flores(args.languages, args.split)
    print(f"{len(texts)} languages, {len(next(iter(texts.values())))} sentences each")

    specs, _ = load_config(ROOT / "config" / "models.json")
    registry = build_registry(specs)
    rows: list[Row] = []
    for name in args.tokenizers:
        print(f"counting with {name} ...")
        rows += summarize(texts, count_all(texts, registry.get(name)), name, args.baseline)

    write_csv(rows, args.out / "multilingual.csv")
    table = markdown_table(rows, args.baseline)
    (args.out / "multilingual.md").write_text(table, encoding="utf-8")
    from .chart import draw
    draw(rows, args.baseline, args.chart)
    print(table)
    print(f"written: {args.out / 'multilingual.csv'}, {args.out / 'multilingual.md'}, {args.chart}")


if __name__ == "__main__":
    main()
