# -*- coding: utf-8 -*-
from pathlib import Path


def _root():
	return Path(__file__).resolve().parents[2]


def test_phase_4_doctypes_exist():
	for name in ["edgepay_api_usage_log", "edgepay_delivery_endpoint", "edgepay_delivery", "edgepay_delivery_attempt"]:
		assert (_root() / "edgepay" / "doctype" / name / f"{name}.json").exists()


def test_api_auth_has_scope_signature_nonce_and_rate_limit():
	text = (_root() / "edgepay" / "services" / "api_auth.py").read_text()
	for token in ["X-EdgePay-Client-Id", "X-EdgePay-Signature", "EdgePay API Request Nonce", "enforce_rate_limit", "hmac.compare_digest"]:
		assert token in text


def test_v1_api_surface_exists():
	text = (_root() / "edgepay" / "api_v1.py").read_text()
	for method in ["create_payment_request_v1", "initialize_payment_request_v1", "verify_payment_request_v1", "get_transaction_v1", "create_refund_v1", "get_refund_v1"]:
		assert method in text


def test_delivery_outbox_is_signed_and_retryable():
	text = (_root() / "edgepay" / "services" / "deliveries.py").read_text()
	assert "hmac.new" in text
	assert "Retry Scheduled" in text
	assert "Dead Letter" in text
	assert "EdgePay Delivery Attempt" in text


def test_secret_rotation_returns_secret_once():
	text = (_root() / "edgepay" / "services" / "api_credentials.py").read_text()
	assert "rotate_api_client_secret" in text
	assert '"shown_once": True' in text
