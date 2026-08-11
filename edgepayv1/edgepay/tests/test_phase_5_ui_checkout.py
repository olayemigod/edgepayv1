from pathlib import Path


def _root():
	return Path(__file__).resolve().parents[2]


def test_edgepay_home_uses_merchant_context_not_global_settings():
	text = (_root() / "api" / "home.py").read_text()
	assert "get_user_merchant_context" in text
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
	assert "source_app=\"EdgePay Hosted Checkout\"" in service
	assert "One Time" in service


def test_hosted_checkout_does_not_claim_browser_success():
	text = (_root() / "www" / "pay.html").read_text()
	assert "authoritative verification" in text
	assert "get_payment_status" in text
	assert "sessionStorage" in text
	assert "Print receipt" in text
	assert "Return to merchant" in text


def test_checkout_branding_is_merchant_owned_and_validated():
	merchant_json = (_root() / "edgepay" / "doctype" / "edgepay_merchant" / "edgepay_merchant.json").read_text()
	merchant_py = (_root() / "edgepay" / "doctype" / "edgepay_merchant" / "edgepay_merchant.py").read_text()
	assert "checkout_logo" in merchant_json
	assert "checkout_primary_colour" in merchant_json
	assert "HEX_COLOUR_RE" in merchant_py


def test_phase_5_operations_pages_exist():
	page_root = _root() / "edgepay" / "page"
	for page in ["edgepay_payments", "edgepay_payment_links", "edgepay_integrations", "edgepay_finance"]:
		assert (page_root / page).exists()
	merchant_views = (_root() / "api" / "merchant_views.py").read_text()
	assert "get_payments_view" in merchant_views
	assert "get_payment_links_view" in merchant_views
	assert "get_integrations_view" in merchant_views
	assert "get_finance_view" in merchant_views


def test_payment_links_page_supports_copy_and_share():
	text = (_root() / "edgepay" / "page" / "edgepay_payment_links" / "edgepay_payment_links.js").read_text()
	assert "navigator.clipboard" in text
	assert "navigator.share" in text
	assert "public_url" in text


def test_payment_link_is_merchant_scoped():
	permissions = (_root() / "edgepay" / "permissions.py").read_text()
	hooks = (_root() / "hooks.py").read_text()
	assert '"EdgePay Payment Link": "merchant"' in permissions
	assert '"EdgePay Payment Link": "edgepayv1.permissions.payment_link_query"' in hooks
