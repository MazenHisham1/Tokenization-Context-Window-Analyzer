"""Tiny tokenizers built locally, so the whole suite runs offline."""
import pytest
import tiktoken
from tokenizers import Tokenizer as HFT, decoders, models, normalizers, pre_tokenizers, trainers
from transformers import PreTrainedTokenizerFast

from src.bpe import PRETOKEN, BPETokenizer

CORPUS = ("low lower lowest newest widest tokenization tokenizer tokens " * 30 +
          "the quick brown fox jumps over the lazy dog. Hello world! " * 30)


@pytest.fixture(scope="session")
def my_bpe():
    return BPETokenizer().train(CORPUS, vocab_size=320)


@pytest.fixture(scope="session")
def tiktoken_encoding(my_bpe):
    """A real tiktoken.Encoding whose ranks come from my own BPE."""
    n_base = len(my_bpe.vocab) - len(my_bpe.special)
    ranks = {}
    for i in range(n_base):
        ranks.setdefault(my_bpe.vocab[i], i)
    return tiktoken.Encoding("test-enc", pat_str=PRETOKEN.pattern, mergeable_ranks=ranks,
                             special_tokens=dict(my_bpe.special))


@pytest.fixture(scope="session")
def hf_bytelevel():
    tok = HFT(models.BPE())
    tok.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tok.decoder = decoders.ByteLevel()
    trainer = trainers.BpeTrainer(vocab_size=320, special_tokens=["<|endoftext|>"],
                                  initial_alphabet=pre_tokenizers.ByteLevel.alphabet())
    tok.train_from_iterator([CORPUS], trainer)
    return PreTrainedTokenizerFast(tokenizer_object=tok)


@pytest.fixture(scope="session")
def hf_wordpiece():
    tok = HFT(models.WordPiece(unk_token="[UNK]"))
    tok.normalizer = normalizers.BertNormalizer(lowercase=True)
    tok.pre_tokenizer = pre_tokenizers.BertPreTokenizer()
    trainer = trainers.WordPieceTrainer(vocab_size=150, special_tokens=["[UNK]"])
    tok.train_from_iterator([CORPUS], trainer)
    return PreTrainedTokenizerFast(tokenizer_object=tok, unk_token="[UNK]")
