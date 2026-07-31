# -*- coding: utf-8 -*-
from pathlib import Path


def _root():
	return Path(__file__).resolve().parents[2]


def test_external_reference_registry_exists():
	assert (_root() / "edgepay" / "doctype" / "edgepay_external_reference" / "edgepay_external_reference.json").exists()
	text = (_root() / "edgepay" / "services" / "external_references.py").read_text()
	assert "register_reference" in text
	assert "resolve_reference" in text


def test_refund_request_foundation_exists():
	assert (_root() / "edgepay" / "doctype" / "edgepay_refund_request" / "edgepay_refund_request.json").exists()
	text = (_root() / "edgepay" / "services" / "refunds.py").read_text()
	assert "create_refund_request" in text
	assert "approve_refund_request" in text


def test_payment_totals_support_partial_and_refunds():
	text = (_root() / "edgepay" / "services" / "payment_totals.py").read_text()
	assert "Partly Paid" in text
	assert "refunded_amount" in text
	request_json = (_root() / "edgepay" / "doctype" / "edgepay_payment_request" / "edgepay_payment_request.json").read_text()
	assert '"paid_amount"' in request_json
	assert '"outstanding_amount"' in request_json
	assert '"refunded_amount"' in request_json


def test_state_engine_declares_refund_states():
	text = (_root() / "edgepay" / "services" / "payment_state.py").read_text()
	assert "Refund Pending" in text
	assert "Partly Refunded" in text
	assert "Refunded" in text
