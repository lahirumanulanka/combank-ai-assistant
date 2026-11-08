from datetime import date

import pytest

from app.knowledge.catalog import CatalogView, Row, months_ago
from app.knowledge.sandbox import PlanRejected, batch, check_batches, run_plan


def row(doc_id: str, day: str, tags=("payments",), document_type="incident") -> Row:
    return Row(doc_id, f"Title {doc_id}", document_type, "payments", "payment-gateway", day, tags)


VIEW = CatalogView([
    row("INC-OLD", "2025-01-10"),
    row("INC-A", "2026-01-10"),
    row("INC-B", "2026-03-10"),
    row("INC-C", "2026-05-10", tags=("identity",)),
    row("POL-X", "2026-02-01", document_type="policy"),
])


def test_valid_plan_returns_batches_sorted_by_date():
    plan = 'rows = catalog.filter(document_type="incident", tag="payments", since="2025-11-07")\n' \
           "batches = batch(rows, size=1)"

    assert run_plan(plan, VIEW) == [["INC-A"], ["INC-B"]]


def test_plan_can_combine_results_without_duplicates():
    plan = 'a = catalog.filter(tag="payments")\nb = catalog.search("INC-A")\nbatches = batch(unique(a + b), size=10)'

    assert run_plan(plan, VIEW) == [["INC-OLD", "INC-A", "POL-X", "INC-B"]]


def test_months_ago_counts_back_whole_months():
    assert months_ago(12, today=date(2026, 11, 7)) == "2025-11-07"
    assert months_ago(3, today=date(2026, 1, 31)) == "2025-10-28"


def test_batch_size_is_capped():
    rows = [row(f"INC-{i}", "2026-01-01") for i in range(20)]

    assert max(len(group) for group in batch(rows, size=99)) == 6


@pytest.mark.parametrize(
    "plan",
    [
        "import os\nbatches = []",
        "x = __import__('os')\nbatches = []",
        "f = open('/etc/passwd')\nbatches = []",
        "x = catalog.__class__\nbatches = []",
        "x = catalog._rows\nbatches = []",
        "catalog.filter = 1\nbatches = []",
        "x = [r for r in catalog.filter()]\nbatches = []",
        "x = catalog.filter()[0]\nbatches = []",
        "f = lambda: 1\nbatches = []",
        "while True:\n    pass",
        "x = eval('1')\nbatches = []",
        "x = getattr(catalog, 'filter')\nbatches = []",
    ],
)
def test_dangerous_plans_are_rejected_before_running(plan):
    with pytest.raises(PlanRejected):
        run_plan(plan, VIEW)


def test_plan_without_batches_is_rejected():
    with pytest.raises(PlanRejected, match="batches"):
        run_plan('rows = catalog.filter(tag="payments")', VIEW)


def test_plan_cannot_write_document_ids_by_hand():
    with pytest.raises(PlanRejected, match="List is not allowed"):
        run_plan('batches = [["HR-COMP-001"]]', VIEW)


def test_batches_outside_the_users_catalog_are_rejected():
    with pytest.raises(PlanRejected, match="catalog"):
        check_batches([["HR-COMP-001"]], VIEW.ids())


def test_plan_with_unknown_variable_is_rejected():
    with pytest.raises(PlanRejected, match="NameError"):
        run_plan("batches = batch(secret_rows)", VIEW)


def test_search_can_be_limited_by_date():
    plan = 'rows = catalog.search("title", since="2026-01-01")\nbatches = batch(rows, size=10)'

    assert run_plan(plan, VIEW) == [["INC-A", "POL-X", "INC-B", "INC-C"]]
