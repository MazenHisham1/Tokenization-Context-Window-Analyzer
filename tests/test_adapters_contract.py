"""Contract tests: every adapter must obey the same rules."""
import pytest

from src.tokenizers import CustomBPEAdapter, HuggingFaceAdapter, TiktokenAdapter, Token, char_spans

TEXTS = ["", "hello world", "  leading and  double  spaces ", "مرحبا بالعالم", "Hello 😊",
         "a\nb\tc", "low lowest newest!", "x" * 5000, "<|endoftext|>x"]


@pytest.fixture(params=["tiktoken", "custom", "hf-bytelevel", "hf-wordpiece"])
def adapter(request, my_bpe, tiktoken_encoding, hf_bytelevel, hf_wordpiece):
    return {
        "tiktoken": lambda: TiktokenAdapter("t", encoding=tiktoken_encoding),
        "custom": lambda: CustomBPEAdapter(my_bpe),
        "hf-bytelevel": lambda: HuggingFaceAdapter("h1", tokenizer=hf_bytelevel),
        "hf-wordpiece": lambda: HuggingFaceAdapter("h2", tokenizer=hf_wordpiece),
    }[request.param]()


@pytest.mark.parametrize("text", TEXTS)
def test_contract(adapter, text):
    tokens = adapter.encode(text)
    assert all(isinstance(t, Token) for t in tokens)
    assert adapter.count(text) == len(tokens)
    if not text:
        assert tokens == []
        return
    n_bytes = len(text.encode("utf-8"))
    starts = [t.start for t in tokens]
    assert starts == sorted(starts)                                   # in order
    assert all(0 <= t.start <= t.end <= n_bytes for t in tokens)      # inside the input
    spans = char_spans(text, tokens)
    assert all(0 <= s <= e <= len(text) for s, e in spans)


@pytest.mark.parametrize("text", [t for t in TEXTS if t])
def test_byte_exact_adapters_cover_input_exactly(my_bpe, tiktoken_encoding, text):
    for ad in (TiktokenAdapter("t", encoding=tiktoken_encoding), CustomBPEAdapter(my_bpe)):
        tokens = ad.encode(text)
        assert tokens[0].start == 0 and tokens[-1].end == len(text.encode("utf-8"))
        assert all(a.end == b.start for a, b in zip(tokens, tokens[1:], strict=False))   # no gaps/overlaps
        raw = text.encode("utf-8")
        assert b"".join(raw[t.start:t.end] for t in tokens) == raw


def test_emoji_is_split_into_byte_tokens_sharing_one_char_span(tiktoken_encoding):
    ad = TiktokenAdapter("t", encoding=tiktoken_encoding)
    tokens = ad.encode("a😊")
    emoji = [t for t in tokens if t.start >= 1]
    assert len(emoji) == 4                                   # 4 UTF-8 bytes, no merge learned
    assert all(t.text == "�" for t in emoji)            # partial characters
    assert set(char_spans("a😊", emoji)) == {(1, 2)}         # all map to the same character


def test_wordpiece_unknown_word_maps_back_to_original_text(hf_wordpiece):
    ad = HuggingFaceAdapter("h", tokenizer=hf_wordpiece)
    text = "hello مرحبا"
    tokens = ad.encode(text)
    unk = [t for t in tokens if t.piece == "[UNK]"]
    assert unk and unk[0].text == "مرحبا"
    assert text.encode()[unk[0].start:unk[0].end].decode() == "مرحبا"


def test_hf_adapter_rejects_slow_tokenizers():
    """Older transformers versions still have slow (Python-only) tokenizers without offsets."""
    class SlowTokenizer:
        is_fast = False
    with pytest.raises(ValueError, match="fast"):
        HuggingFaceAdapter("slow", tokenizer=SlowTokenizer())


def test_hf_adapter_requires_model_name_or_tokenizer():
    with pytest.raises(ValueError):
        HuggingFaceAdapter("x")


def test_long_text_offsets_are_fast(hf_bytelevel):
    import time
    text = "héllo wörld 😊 " * 20000          # 300k characters
    t0 = time.perf_counter()
    tokens = HuggingFaceAdapter("h", tokenizer=hf_bytelevel).encode(text)
    assert time.perf_counter() - t0 < 10        # the first draft's per-token re-encoding was quadratic
    assert tokens[-1].end <= len(text.encode())


def test_my_bpe_matches_tiktoken_algorithm(my_bpe, tiktoken_encoding):
    """Same merges + same regex => tiktoken and my from-scratch BPE give identical ids."""
    for text in ["low lowest newest", "tokenization of the quick fox!", "Hello 😊", "مرحبا"]:
        assert my_bpe.encode(text) == tiktoken_encoding.encode(text, disallowed_special=())
