# -*- coding: utf-8 -*-
from pathlib import Path


def _root():
	return Path(__file__).resolve().parents[2]


def test_phase_3_financial_doctypes_exist():
	base = _root() / "edgepay" / "doctype"
	for name in (
		"edgepay_refund_processing_attempt",
		"edgepay_dispute",
		"edgepay_chargeback",
		"edgepay_fee_record",
		"edgepay_settlement_batch",
		"edgepay_settlement_item",
	):
		assert (base / name / f"{name}.json").exists()


def test_provider_financial_adapter_contract_exists():
	text = (_root() / "edgepay" / "services" / "provider_financial_adapters.py").read_text()
	assert "submit_refund" in text
	assert "query_refund" in text
	assert "fetch_settlement" in text
	assert "SandboxProviderFinancialAdapter" in text


def test_outcome_paths_register_references_and_sync_totals():
	for filename in ("checkout.py", "verification.py", "webhooks.py"):
		text = (_root() / "edgepay" / "services" / filename).read_text()
		assert "register_reference" in text
	for filename in ("verification.py", "webhooks.py"):
		text = (_root() / "edgepay" / "services" / filename).read_text()
		assert "sync_payment_totals" in text


def test_refund_processing_uses_attempt_history():
	text = (_root() / "edgepay" / "services" / "refund_processing.py").read_text()
	assert "EdgePay Refund Processing Attempt" in text
	assert "complete_refund" in text


def test_financial_operations_are_merchant_scoped():
	hooks = (_root() / "hooks.py").read_text()
	permissions = (_root() / "edgepay" / "permissions.py").read_text()
	for doctype in (
		"EdgePay Refund Processing Attempt",
		"EdgePay Dispute",
		"EdgePay Chargeback",
		"EdgePay Fee Record",
		"EdgePay Settlement Batch",
		"EdgePay Settlement Item",
	):
		assert doctype in hooks
		assert doctype in permissions
