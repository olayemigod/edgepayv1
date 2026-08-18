# -*- coding: utf-8 -*-
from pathlib import Path


def _root():
	return Path(__file__).resolve().parents[2]


def test_payment_attempt_doctype_exists():
	assert (_root() / "edgepay" / "doctype" / "edgepay_payment_attempt" / "edgepay_payment_attempt.json").exists()


def test_payment_event_doctype_exists():
	assert (_root() / "edgepay" / "doctype" / "edgepay_payment_event" / "edgepay_payment_event.json").exists()


def test_state_engine_declares_transition_maps():
	text = (_root() / "edgepay" / "services" / "payment_state.py").read_text()
	assert "ATTEMPT_TRANSITIONS" in text
	assert "REQUEST_TRANSITIONS" in text
	assert "create_attempt" in text
	assert "transition_attempt" in text
	assert "transition_request" in text


def test_checkout_creates_payment_attempt():
	text = (_root() / "edgepay" / "services" / "checkout.py").read_text()
	assert "create_attempt" in text
	assert "payment_attempt" in text


def test_transaction_links_attempt():
	text = (_root() / "edgepay" / "doctype" / "edgepay_payment_transaction" / "edgepay_payment_transaction.json").read_text()
	assert '"payment_attempt"' in text
