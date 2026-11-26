"""Parallel corpora: the same sentences in several languages. Sentence i of every language says the same thing."""
from __future__ import annotations

from pathlib import Path

DEFAULT_LANGUAGES = [   # FLORES+ codes: ISO 639-3 language + script
    "eng_Latn", "fra_Latn", "spa_Latn", "deu_Latn", "tur_Latn", "vie_Latn", "swh_Latn",
    "rus_Cyrl", "ell_Grek", "arb_Arab", "heb_Hebr", "hin_Deva", "ben_Beng", "tam_Taml",
    "tha_Thai", "amh_Ethi", "kor_Hang", "jpn_Jpan", "cmn_Hans",
]


def load_dir(path: Path) -> dict[str, list[str]]:
    """Your own corpus: one file `<language>.txt` per language, one sentence per line, the same lines in every file."""
    corpus = {}
    for file in sorted(Path(path).glob("*.txt")):
        corpus[file.stem] = [line.rstrip("\n") for line in file.read_text(encoding="utf-8").splitlines()]
    if not corpus:
        raise ValueError(f"no .txt files in {path}")
    check_parallel({k: list(range(len(v))) for k, v in corpus.items()})
    return corpus


def load_flores(languages: list[str], split: str = "devtest") -> dict[str, list[str]]:
    """FLORES+ (gated: accept its terms on huggingface.co/datasets/openlanguagedata/flores_plus, then log in).

    Its terms ask that the text is not re-published where web crawlers can collect it, so this function only
    reads it into memory. Nothing in this project writes the sentences to disk.
    """
    from datasets import load_dataset  # imported here so the rest of the project does not need the package

    texts, ids = {}, {}
    for lang in languages:
        try:
            rows = load_dataset("openlanguagedata/flores_plus", lang, split=split)
        except Exception as exc:
            raise RuntimeError(
                f"could not load FLORES+ language {lang!r}: {str(exc)[:200]}\n"
                "Did you accept the dataset terms and run `hf auth login`? Is the language code spelled as on the "
                "dataset page (for example fra_Latn)?") from exc
        ordered = sorted(zip(rows["id"], rows["text"], strict=True))
        ids[lang] = [i for i, _ in ordered]
        texts[lang] = [t for _, t in ordered]
    check_parallel(ids)
    return texts


def check_parallel(ids: dict[str, list]) -> None:
    """Every language must have exactly the same sentence ids, otherwise the comparison is meaningless."""
    first_lang = next(iter(ids))
    for lang, these in ids.items():
        if these != ids[first_lang]:
            raise ValueError(f"{lang} is not parallel to {first_lang}: "
                             f"{len(these)} vs {len(ids[first_lang])} sentences, or different ids")
