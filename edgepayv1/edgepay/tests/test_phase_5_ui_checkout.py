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


def test_hosted_checkout_does_not_claim_browser_success():
	text = (_root() / "www" / "pay.html").read_text()
	assert "authoritative verification" in text
	assert "get_payment_status" in text
	assert "sessionStorage" in text


def test_payment_link_is_merchant_scoped():
	permissions = (_root() / "edgepay" / "permissions.py").read_text()
	hooks = (_root() / "hooks.py").read_text()
	assert '"EdgePay Payment Link": "merchant"' in permissions
	assert '"EdgePay Payment Link": "edgepayv1.permissions.payment_link_query"' in hooks
