from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
	return (ROOT / relative).read_text(encoding="utf-8")


def test_operational_search_is_merchant_scoped_and_bounded():
	source = _read("api/operational_search.py")
	assert 'filters={"merchant": merchant}' in source
	assert "CANDIDATE_LIMIT = 100" in source
	assert "MAX_RESULTS = 50" in source
	assert "limit_page_length=CANDIDATE_LIMIT" in source


def test_operational_search_prefers_financial_identifiers():
	source = _read("api/operational_search.py")
	assert 'exact_fields=("value", "reference", "provider_reference", "transaction_reference")' in source
	assert 'kind="Payment Request"' in source
	assert 'kind="Payment Attempt"' in source
	assert 'kind="Payment Transaction"' in source
	assert 'kind="Refund"' in source
	assert 'kind="Settlement"' in source
	assert 'kind="Dispute"' in source
	assert 'kind="Chargeback"' in source


def test_operational_search_uses_edgesuite_ranker_with_safe_fallback():
	source = _read("api/operational_search.py")
	assert "from edgesuite_ui.search_ranking import rank_search_records" in source
	assert "except (ImportError, ModuleNotFoundError)" in source
	assert "_fallback_rank" in source


def test_operational_search_is_discovery_only():
	source = _read("api/operational_search.py")
	assert "Search merchant-scoped EdgePay operational records for discovery only." in source
	for mutation_token in (
		".insert(",
		".save(",
		".submit(",
		"frappe.db.set_value",
		"frappe.delete_doc",
	):
		assert mutation_token not in source
