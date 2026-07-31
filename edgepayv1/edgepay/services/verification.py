# -*- coding: utf-8 -*-
import json
import urllib.parse as urlparse

import frappe
from frappe import _
from frappe.utils import flt

from edgepayv1.edgepay.services.attempt_resolution import resolve_or_create_legacy_attempt
from edgepayv1.edgepay.services.clients import get_client
from edgepayv1.edgepay.services.logging import log
from edgepayv1.edgepay.services.payment_state import transition_attempt, transition_request
from edgepayv1.edgepay.services.providers.registry import get_provider_instance
from edgepayv1.edgepay.services.security import redact_secrets


def verify_transaction(payment_request_name):
	pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
	from edgepayv1.edgepay.services.checkout import check_and_mark_expired
	check_and_mark_expired(pr)
	if not pr.provider or not pr.provider_reference:
		frappe.throw(_("Payment Request has no provider reference generated"))

	attempt = resolve_or_create_legacy_attempt(pr.name)
	provider_reference = attempt.provider_payment_reference or pr.provider_reference
	provider_instance = get_provider_instance(pr.provider)
	provider_instance.validate_configuration()
	payload = provider_instance.build_verification_payload(provider_reference)
	client = get_client(provider_instance.get_provider_code(), provider_instance.provider_doc)
	url = f"{provider_instance.get_base_url()}/v1/merchant/transactions/query?{urlparse.urlencode(payload)}"
	response = client.get(url)
	parsed = provider_instance.parse_verification_response(response)
	if parsed.get("amount") is not None and flt(parsed.get("amount")) != flt(pr.amount):
		frappe.throw(_("Verification failed: Amount mismatch"))
	if parsed.get("currency") and parsed.get("currency").upper() != pr.currency.upper():
		frappe.throw(_("Verification failed: Currency mismatch"))

	txn_ref = parsed.get("transaction_reference") or parsed.get("provider_reference")
	prov_ref = parsed.get("provider_reference")
	txn_name = None
	if txn_ref:
		txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"transaction_reference": txn_ref}, "name")
	if not txn_name and prov_ref:
		txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"provider_reference": prov_ref}, "name")
	txn = frappe.get_doc("EdgePay Payment Transaction", txn_name) if txn_name else frappe.new_doc("EdgePay Payment Transaction")
	txn.payment_request = pr.name
	txn.payment_attempt = attempt.name
	txn.provider = pr.provider
	txn.transaction_reference = txn_ref
	txn.provider_reference = prov_ref
	txn.amount = pr.amount
	txn.currency = pr.currency
	txn.status = parsed.get("status")
	txn.paid_on = parsed.get("paid_on")
	txn.settlement_status = parsed.get("settlement_status") or txn.settlement_status
	txn.raw_response_json = json.dumps(redact_secrets(response), indent=2)
	txn.idempotency_key = f"{pr.idempotency_key or pr.name}:{attempt.name}:{txn_ref or prov_ref}"
	txn.save(ignore_permissions=True)

	attempt.provider_transaction_reference = txn_ref
	attempt.provider_payment_reference = prov_ref or attempt.provider_payment_reference
	attempt.save(ignore_permissions=True)
	if txn.status == "Success":
		transition_attempt(attempt, "Successful", "Verification Successful", "verification", txn)
		transition_request(pr, "Paid", "Payment Paid", "verification", attempt, txn)
	elif txn.status == "Failed":
		transition_attempt(attempt, "Failed", "Verification Failed", "verification", txn)
		transition_request(pr, "Failed", "Payment Failed", "verification", attempt, txn)
	else:
		if attempt.status == "Initiated":
			transition_attempt(attempt, "Pending", "Verification Pending", "verification", txn)

	from edgepayv1.edgepay.services.connectors import notify_source_payment_status
	notify_source_payment_status(pr.name, txn.name, event_source="verification")
	pr.reload()
	return {"payment_request": pr.name, "payment_attempt": attempt.name, "request_status": pr.status, "transaction": txn.name, "transaction_status": txn.status, "provider_reference": prov_ref, "amount": txn.amount, "currency": txn.currency, "paid_on": txn.paid_on}


@frappe.whitelist()
def verify_payment_request_transaction(payment_request_name):
	if not frappe.has_permission("EdgePay Payment Request", "write", doc=payment_request_name):
		frappe.throw(_("Not permitted to verify transaction for this Payment Request"), frappe.PermissionError)
	return verify_transaction(payment_request_name)
