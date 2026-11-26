"""The multilingual study's code, tested on small invented data (never on real FLORES text)."""
import csv
import sys
import types

import numpy as np
import pytest

from study.analysis import paired_ratio, summarize
from study.corpus import check_parallel, load_dir, load_flores
from study.run_study import main


# ---- paired_ratio ----
def test_ratio_is_total_over_total():
    p = paired_ratio([2, 4, 6], [1, 2, 3])
    assert p.ratio == pytest.approx(2.0)


def test_identical_counts_give_one_and_an_interval_around_one():
    p = paired_ratio([5, 9, 3, 12, 7], [5, 9, 3, 12, 7])
    assert p.ratio == 1.0 and p.low == p.high == 1.0


def test_exactly_proportional_sentences_have_no_uncertainty():
    """Pairing is the point: if every sentence needs exactly 3x, the ratio is 3 however the sentences are drawn."""
    base = [4, 11, 2, 30, 8, 5]
    p = paired_ratio([3 * b for b in base], base)
    assert p.low == pytest.approx(3.0) and p.high == pytest.approx(3.0)


def test_more_sentences_give_a_narrower_interval():
    rng = np.random.default_rng(1)

    def width(n):
        base = rng.integers(5, 40, size=n)
        lang = base * 2 + rng.integers(-3, 4, size=n)          # about 2x with noise
        p = paired_ratio(lang.tolist(), base.tolist())
        return p.high - p.low

    assert width(1000) < width(30)


def test_interval_contains_the_estimate_and_is_reproducible():
    a = paired_ratio([3, 8, 5, 9], [2, 4, 3, 5], seed=7)
    b = paired_ratio([3, 8, 5, 9], [2, 4, 3, 5], seed=7)
    assert a == b and a.low <= a.ratio <= a.high


@pytest.mark.parametrize("lang,base,kw", [
    ([1, 2], [1], {}),                   # different number of sentences
    ([], [], {}),                        # no sentences
    ([1], [0], {}),                      # the baseline has no tokens
    ([1], [1], {"confidence": 1.5}),     # not a probability
])
def test_bad_input(lang, base, kw):
    with pytest.raises(ValueError):
        paired_ratio(lang, base, **kw)


# ---- summarize ----
def test_summarize_computes_characters_and_bytes_per_token():
    texts = {"en": ["abcd", "efgh"], "xx": ["é€", "éé"]}      # 2 chars = 5 bytes ... é is 2 bytes, € is 3
    counts = {"en": [2, 2], "xx": [4, 2]}
    rows = {r.language: r for r in summarize(texts, counts, "tok", "en", n_boot=50)}
    assert rows["en"].chars_per_token == 2.0 and rows["en"].premium.ratio == 1.0
    assert rows["xx"].mean_tokens == 3.0 and rows["xx"].premium.ratio == pytest.approx(1.5)
    assert rows["xx"].chars_per_token == pytest.approx(4 / 6)
    assert rows["xx"].bytes_per_token == pytest.approx((5 + 4) / 6)


def test_summarize_needs_the_baseline_language():
    with pytest.raises(ValueError, match="baseline"):
        summarize({"xx": ["a"]}, {"xx": [1]}, "tok", "en")


# ---- corpus ----
def test_load_dir_reads_one_file_per_language(tmp_path):
    (tmp_path / "en.txt").write_text("one\ntwo\n", encoding="utf-8")
    (tmp_path / "ar.txt").write_text("واحد\nاثنان\n", encoding="utf-8")
    assert load_dir(tmp_path) == {"ar": ["واحد", "اثنان"], "en": ["one", "two"]}


def test_load_dir_refuses_files_that_are_not_parallel(tmp_path):
    (tmp_path / "en.txt").write_text("one\ntwo\n", encoding="utf-8")
    (tmp_path / "ar.txt").write_text("واحد\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not parallel"):
        load_dir(tmp_path)


def test_load_dir_with_no_files(tmp_path):
    with pytest.raises(ValueError, match="no .txt"):
        load_dir(tmp_path)


def test_check_parallel_compares_ids():
    check_parallel({"a": [1, 2], "b": [1, 2]})
    with pytest.raises(ValueError):
        check_parallel({"a": [1, 2], "b": [1, 3]})


def fake_datasets(monkeypatch, data, fail=()):
    def load_dataset(name, lang, split):
        assert name == "openlanguagedata/flores_plus"
        if lang in fail:
            raise RuntimeError("gated")
        return data[lang]
    monkeypatch.setitem(sys.modules, "datasets", types.SimpleNamespace(load_dataset=load_dataset))


def test_flores_rows_are_sorted_by_id_so_sentences_line_up(monkeypatch):
    fake_datasets(monkeypatch, {"eng_Latn": {"id": [2, 1], "text": ["second", "first"]},
                                "fra_Latn": {"id": [1, 2], "text": ["premier", "deuxieme"]}})
    out = load_flores(["eng_Latn", "fra_Latn"])
    assert out == {"eng_Latn": ["first", "second"], "fra_Latn": ["premier", "deuxieme"]}


def test_flores_with_different_ids_is_rejected(monkeypatch):
    fake_datasets(monkeypatch, {"eng_Latn": {"id": [1, 2], "text": ["a", "b"]},
                                "fra_Latn": {"id": [1, 3], "text": ["a", "b"]}})
    with pytest.raises(ValueError, match="not parallel"):
        load_flores(["eng_Latn", "fra_Latn"])


def test_a_flores_failure_explains_what_to_check(monkeypatch):
    fake_datasets(monkeypatch, {"eng_Latn": {"id": [1], "text": ["a"]}}, fail=("xxx_Latn",))
    with pytest.raises(RuntimeError, match="accept the dataset terms"):
        load_flores(["xxx_Latn"])


# ---- the whole run ----
def test_a_full_run_writes_counts_and_a_chart_but_no_sentences(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    secret = "UNIQUE-SENTENCE-TEXT"
    (corpus / "eng_Latn.txt").write_text(f"{secret} one\nhello there friend\n", encoding="utf-8")
    (corpus / "xxx_Latn.txt").write_text("a much longer made-up sentence here\nsecond made-up line of text\n",
                                         encoding="utf-8")
    out = tmp_path / "out"
    main(["--data-dir", str(corpus), "--tokenizers", "rule-of-thumb-4", "--out", str(out),
          "--chart", str(tmp_path / "chart.png")])

    rows = list(csv.DictReader((out / "multilingual.csv").open(encoding="utf-8")))
    assert {r["language"] for r in rows} == {"eng_Latn", "xxx_Latn"}
    assert float(next(r for r in rows if r["language"] == "eng_Latn")["ratio_vs_baseline"]) == 1.0
    assert (tmp_path / "chart.png").stat().st_size > 1000
    written = "".join((out / name).read_text(encoding="utf-8") for name in ("multilingual.csv", "multilingual.md"))
    assert secret not in written                                  # only counts leave the program
