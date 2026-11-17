"""Compare token counts for 5 sentences.
Run from this folder:  python run_compare.py
Prints the table AND saves it next to this script as results.csv and results.md
"""
import csv
import sys
from pathlib import Path

from src.bpe import BPETokenizer
from src.config import build_registry, load_config
from src.tokenizers import CustomBPEAdapter, compare_counts

sys.stdout.reconfigure(encoding="utf-8", errors="replace")   # safe in Windows cmd
HERE = Path(__file__).parent

specs, models = load_config(HERE / "config" / "models.json")
registry = build_registry(specs)

# Your own tokenizer from Phase 0. Replace README.md with any bigger text you like.
my_bpe = BPETokenizer().train((HERE / "README.md").read_text(encoding="utf-8"), vocab_size=300)
registry.register(CustomBPEAdapter(my_bpe))

sentences = {
    "English": "Tokenization turns text into tokens.",
    "Arabic":  "التقسيم إلى رموز يحول النص إلى أرقام.",
    "Emoji":   "Hello 😊🎉 great job 👍",
    "Code":    "def add(a, b):\n    return a + b",
    "Numbers": "The price is 1234567.89 on 2026-11-14.",
}

rows = []   # (sentence, characters, tokenizer, tokens, chars_per_token, error)
for label, text in sentences.items():
    for r in compare_counts(registry, text):
        rows.append((label, len(text), r.name, r.tokens, r.chars_per_token, r.error or ""))

print(f"{'sentence':<9} {'tokenizer':<11} {'tokens':>6} {'chars/token':>12}")
for label, nchars, name, tokens, cpt, err in rows:
    if err:
        print(f"{label:<9} {name:<11} {'ERROR':>6}   {err[:70]}")
    else:
        print(f"{label:<9} {name:<11} {tokens:>6} {cpt:>12}")

with open(HERE / "results.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["sentence", "characters", "tokenizer", "tokens", "chars_per_token", "error"])
    w.writerows(rows)

with open(HERE / "results.md", "w", encoding="utf-8") as f:
    f.write("| sentence | characters | tokenizer | tokens | chars/token | error |\n|---|---|---|---|---|---|\n")
    for label, nchars, name, tokens, cpt, err in rows:
        f.write(f"| {label} | {nchars} | {name} | {tokens if tokens is not None else ''} | "
                f"{cpt if cpt is not None else ''} | {err.replace('|', '/')[:120]} |\n")

print(f"\nSaved: {HERE / 'results.csv'}\n       {HERE / 'results.md'}")
