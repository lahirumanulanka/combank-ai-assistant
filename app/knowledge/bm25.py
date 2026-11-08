import json
import math
import re
import zlib
from collections import Counter
from pathlib import Path
from typing import TypedDict

TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:[-_.][a-z0-9]+)*")

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "in", "is", "it", "of", "on",
    "or", "that", "the", "this", "to", "was", "were", "what", "when", "which", "who", "with", "our", "we",
}


class SparseVector(TypedDict):
    indices: list[int]
    values: list[float]


SUFFIXES = ("ions", "ion", "ing", "ed", "es", "s", "e")


def stem(token: str) -> str:
    for suffix in SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    return [stem(token) for token in TOKEN_PATTERN.findall(text.lower()) if token not in STOP_WORDS]


def token_id(token: str) -> int:
    return zlib.crc32(token.encode())


def to_sparse(weights: dict[int, float]) -> SparseVector:
    indices = sorted(weights)
    return {"indices": indices, "values": [round(weights[i], 6) for i in indices]}


class BM25Encoder:
    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_count = 0
        self.avg_doc_length = 0.0
        self.doc_freq: dict[str, int] = {}

    def fit(self, texts: list[str]) -> "BM25Encoder":
        token_lists = [tokenize(text) for text in texts]
        self.doc_count = len(token_lists)
        self.avg_doc_length = sum(len(tokens) for tokens in token_lists) / max(self.doc_count, 1)
        self.doc_freq = dict(Counter(token for tokens in token_lists for token in set(tokens)))
        return self

    def encode_document(self, text: str) -> SparseVector:
        counts = Counter(tokenize(text))
        length = sum(counts.values())
        weights: dict[int, float] = {}
        for token, count in counts.items():
            length_norm = 1 - self.b + self.b * length / self.avg_doc_length
            score = count / (count + self.k1 * length_norm)
            weights[token_id(token)] = weights.get(token_id(token), 0.0) + score
        return to_sparse(weights)

    def encode_query(self, text: str) -> SparseVector:
        idf_by_id = {token_id(token): self.idf(token) for token in set(tokenize(text)) if token in self.doc_freq}
        total = sum(idf_by_id.values())
        return to_sparse({index: value / total for index, value in idf_by_id.items()})

    def idf(self, token: str) -> float:
        n = self.doc_freq.get(token, 0)
        return math.log(1 + (self.doc_count - n + 0.5) / (n + 0.5))

    def save(self, path: Path) -> None:
        data = {
            "k1": self.k1,
            "b": self.b,
            "doc_count": self.doc_count,
            "avg_doc_length": self.avg_doc_length,
            "doc_freq": self.doc_freq,
        }
        path.write_text(json.dumps(data))

    @classmethod
    def load(cls, path: Path) -> "BM25Encoder":
        data = json.loads(path.read_text())
        encoder = cls(k1=data["k1"], b=data["b"])
        encoder.doc_count = data["doc_count"]
        encoder.avg_doc_length = data["avg_doc_length"]
        encoder.doc_freq = data["doc_freq"]
        return encoder
