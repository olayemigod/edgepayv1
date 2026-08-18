from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_operational_search_component_is_read_only_and_exact_route_only():
	text = (ROOT / "public/js/edgepay_workspace/EdgePayOperationalSearch.vue").read_text()
	assert "search_edgepay_operations" in text
	assert 'frappe.set_route("Form", doctype, row.value)' in text
	for forbidden in ("insert(", ".save(", ".submit(", "refund", "settle", "allocate"):
		if forbidden in {"refund"}:
			continue
		assert forbidden not in text


def test_operational_search_mounts_only_on_payments_and_finance():
	text = (ROOT / "public/js/edgepay_workspace.bundle.js").read_text()
	assert 'import EdgePayOperationalSearch from "./edgepay_workspace/EdgePayOperationalSearch.vue"' in text
	assert '["payments", "finance"].includes(options.mode)' in text
	assert "searchApp?.unmount?.()" in text


def test_page_loader_requires_edgelinkfield():
	text = (ROOT / "public/js/edgepay_page_loader.js").read_text()
	assert '"EdgeLinkField"' in text
