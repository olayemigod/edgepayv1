from pathlib import Path


def _root():
	return Path(__file__).resolve().parents[2]


def test_edgepay_home_uses_merchant_context_not_global_settings():
	text = (_root() / "api" / "home.py").read_text()
	assert "get_user_merchant_context" in text or "get_current_merchant_context" in text
	assert "EdgePay Settings" not in text
	assert "dead_letters" in text
	assert "settlements_open" in text


def test_edgesuite_surface_is_standalone_dependency():
	text = (_root() / "hooks.py").read_text()
	assert 'required_apps = ["edgesuite_ui"]' in text
	assert 'app_home = "/app/edgepay-home"' in text
	assert "CoreEdge is not required" in text


def test_payment_link_public_contract_exists():
	root = _root() / "edgepay"
	assert (root / "doctype" / "edgepay_payment_link" / "edgepay_payment_link.json").exists()
	service = (root / "services" / "payment_links.py").read_text()
	assert "get_payment_link" in service
	assert "start_payment_link" in service
	assert "get_payment_status" in service
	assert 'source_app="EdgePay Hosted Checkout"' in service


def test_hosted_checkout_does_not_claim_browser_success():
	text = (_root() / "www" / "pay.html").read_text()
	assert "authoritative verification" in text
	assert "get_payment_status" in text
	assert "sessionStorage" in text
	assert "Return to Merchant" in text
	assert "window.print" in text


def test_payment_link_is_merchant_scoped():
	permissions = (_root() / "edgepay" / "permissions.py").read_text()
	hooks = (_root() / "hooks.py").read_text()
	assert '"EdgePay Payment Link": "merchant"' in permissions
	assert '"EdgePay Payment Link": "edgepayv1.permissions.payment_link_query"' in hooks


def test_merchant_operation_pages_exist():
	page_root = _root() / "edgepay" / "page"
	for page in ("edgepay_payments", "edgepay_payment_links", "edgepay_integrations", "edgepay_finance"):
		assert (page_root / page / f"{page}.json").exists()
		assert (page_root / page / f"{page}.js").exists()


def test_payment_link_qr_is_server_generated_without_remote_runtime():
	service = (_root() / "edgepay" / "services" / "payment_link_qr.py").read_text()
	page = (_root() / "edgepay" / "page" / "edgepay_payment_links" / "edgepay_payment_links.js").read_text()
	pyproject = (_root().parent / "pyproject.toml").read_text()
	assert "segno" in service
	assert "require_merchant_access" in service
	assert "data:image/svg+xml;base64" in service
	assert "get_payment_link_qr" in page
	assert "segno>=1.6,<2" in pyproject
	assert "api.qrserver" not in page


def test_monnify_checkout_returns_to_edgepay_receipt_status():
	provider = (_root() / "edgepay" / "services" / "providers" / "monnify.py").read_text()
	assert '"redirectUrl": redirect_url' in provider
	assert 'get_url(f"/pay?ref=' in provider
	assert "request_reference" in provider
