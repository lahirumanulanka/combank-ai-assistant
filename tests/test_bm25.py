import pytest

from app.knowledge.bm25 import BM25Encoder, token_id, tokenize

CORPUS = [
    "Passwords rotate every 90 days and MFA is mandatory.",
    "The adapter logged ERR_CONN_POOL_EXHAUSTED when the pool was full.",
    "Certificates expired and SSL handshake failed for payments.",
    "Payments failed during the salary day peak for payments users.",
]


def dot(query, document) -> float:
    doc = dict(zip(document["indices"], document["values"], strict=True))
    return sum(value * doc.get(index, 0.0) for index, value in zip(query["indices"], query["values"], strict=True))


def best_match(encoder: BM25Encoder, query: str) -> int:
    query_vector = encoder.encode_query(query)
    scores = [dot(query_vector, encoder.encode_document(text)) for text in CORPUS]
    return scores.index(max(scores))


def test_tokenize_lowercases_drops_stop_words_and_keeps_codes():
    tokens = tokenize("The adapter logged ERR_CONN_POOL_EXHAUSTED for INC-2026-03-14")

    assert tokens == ["adapter", "logged", "err_conn_pool_exhausted", "inc-2026-03-14"]


def test_token_id_is_the_same_every_run():
    assert token_id("payments") == token_id("payments") == 1708301106


def test_rare_words_are_worth_more_than_common_words():
    encoder = BM25Encoder().fit(CORPUS)

    assert encoder.idf("mfa") > encoder.idf("payments")


def test_exact_error_code_finds_the_right_chunk():
    encoder = BM25Encoder().fit(CORPUS)

    assert best_match(encoder, "ERR_CONN_POOL_EXHAUSTED") == 1


def test_query_finds_password_chunk():
    encoder = BM25Encoder().fit(CORPUS)

    assert best_match(encoder, "how often do passwords rotate?") == 0


def test_unknown_query_words_give_an_empty_vector():
    encoder = BM25Encoder().fit(CORPUS)

    assert encoder.encode_query("zebra giraffe") == {"indices": [], "values": []}


def test_save_and_load_give_identical_vectors(tmp_path):
    encoder = BM25Encoder().fit(CORPUS)
    path = tmp_path / "bm25.json"
    encoder.save(path)

    loaded = BM25Encoder.load(path)

    assert loaded.encode_document(CORPUS[2]) == encoder.encode_document(CORPUS[2])
    assert loaded.encode_query("ssl payments") == encoder.encode_query("ssl payments")


def test_scores_stay_on_a_zero_to_one_scale_like_dense_scores():
    encoder = BM25Encoder().fit(CORPUS)

    query = encoder.encode_query("payments ssl certificates")
    document = encoder.encode_document(CORPUS[2])

    assert sum(query["values"]) == pytest.approx(1.0, abs=1e-4)
    assert all(0 < value < 1 for value in document["values"])
    assert 0 < dot(query, document) < 1
