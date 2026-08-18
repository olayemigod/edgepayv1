# -*- coding: utf-8 -*-
from pathlib import Path


def _root():
	return Path(__file__).resolve().parents[2]


def test_api_nonce_doctype_exists():
	assert (_root() / "edgepay" / "doctype" / "edgepay_api_request_nonce" / "edgepay_api_request_nonce.json").exists()


def test_signed_api_authentication_contract_exists():
	text = (_root() / "edgepay" / "services" / "api_auth.py").read_text()
	for token in ["X-EdgePay-Client-Id", "X-EdgePay-Timestamp", "X-EdgePay-Nonce", "X-EdgePay-Signature", "hmac.compare_digest"]:
		assert token in text


def test_v1_payment_endpoints_exist():
	text = (_root() / "edgepay" / "api_v1.py").read_text()
	assert "create_payment_request_v1" in text
	assert "get_payment_request_v1" in text
	assert "initialize_payment_request_v1" in text
	assert "payments:create" in text
	assert "payments:read" in text
