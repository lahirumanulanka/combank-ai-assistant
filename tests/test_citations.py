from app.guards.citations import check_citations, find_citations

RETRIEVED = ["POL-SEC-001#4", "INC-2026-03-14#3"]


def test_finds_citation_ids_in_order_without_duplicates():
    text = "Rotate every 90 days [POL-SEC-001#4]. MFA too [POL-SEC-001#4]. Pool full [INC-2026-03-14#3]."

    assert find_citations(text) == ["POL-SEC-001#4", "INC-2026-03-14#3"]


def test_ignores_brackets_that_are_not_citation_ids():
    assert find_citations("See note [1] and [optional] and [POL-SEC-001]") == []


def test_all_known_citations_pass():
    result = check_citations("90 days [POL-SEC-001#4].", RETRIEVED)

    assert result.ok
    assert result.cited == ["POL-SEC-001#4"]


def test_made_up_citation_fails_and_is_named():
    result = check_citations("90 days [POL-SEC-001#4]. Also [INC-1999-01-01#9].", RETRIEVED)

    assert not result.ok
    assert result.unknown == ["INC-1999-01-01#9"]
    assert "INC-1999-01-01#9" in result.reason


def test_answer_without_any_citation_fails():
    result = check_citations("Passwords rotate every 90 days.", RETRIEVED)

    assert not result.ok
    assert result.reason == "The answer has no citations."
