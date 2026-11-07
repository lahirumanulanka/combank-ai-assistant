from collections import Counter

from app.knowledge.documents import load_documents
from scripts.generate_incidents import INCIDENTS, ROOT_CAUSE_TEXT, main

ONE_YEAR_BEFORE_TODAY = "2025-11-07"


def payment_incidents_last_year():
    return [i for i in INCIDENTS if i.payment_related and i.date >= ONE_YEAR_BEFORE_TODAY]


def test_there_are_16_incidents_with_unique_ids():
    ids = [incident.doc_id for incident in INCIDENTS]

    assert len(ids) == 16
    assert len(set(ids)) == 16


def test_12_payment_incidents_in_the_last_year():
    assert len(payment_incidents_last_year()) == 12


def test_one_payment_incident_is_older_than_a_year():
    older = [i for i in INCIDENTS if i.payment_related and i.date < ONE_YEAR_BEFORE_TODAY]

    assert [i.doc_id for i in older] == ["INC-2025-09-30"]


def test_recurring_root_causes_match_the_demo_answer():
    counts = Counter(i.root_cause for i in payment_incidents_last_year())

    assert counts == {
        "connection_pool_exhaustion": 4,
        "expired_tls_certificate": 3,
        "idempotency_cache_eviction": 3,
        "config_drift_deployment": 2,
    }


def test_generated_files_load_as_valid_documents(tmp_path):
    main(tmp_path)

    documents = load_documents(tmp_path / "docs")

    assert len(documents) == 16
    assert (tmp_path / "ground_truth.json").exists()


def test_root_cause_key_never_appears_in_the_document_text(tmp_path):
    main(tmp_path)

    for doc in load_documents(tmp_path / "docs"):
        for key in ROOT_CAUSE_TEXT:
            assert key not in doc.body
