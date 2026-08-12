import json
import urllib.parse as urlparse

import frappe
from frappe import _
from frappe.utils import flt

from edgepayv1.edgepay.services.attempt_resolution import resolve_or_create_legacy_attempt
from edgepayv1.edgepay.services.clients import get_client
from edgepayv1.edgepay.services.external_references import register_reference
from edgepayv1.edgepay.services.payment_state import transition_attempt, transition_request
from edgepayv1.edgepay.services.payment_totals import sync_payment_totals
from edgepayv1.edgepay.services.providers.registry import get_provider_instance
from edgepayv1.edgepay.services.security import redact_secrets

NON_VERIFIABLE_REQUEST_STATUSES = {
	"Expired",
	"Cancelled",
	"Refund Pending",
	"Partly Refunded",
	"Refunded",
	"Disputed",
	"Chargeback",
}


def _find_transaction_name(payment_request, transaction_reference=None, provider_reference=None):
	if transaction_reference:
		name = frappe.db.get_value(
			"EdgePay Payment Transaction",
			{
				"payment_request": payment_request,
				"transaction_reference": transaction_reference,
			},
			"name",
		)
		if name:
			return name
	if provider_reference:
		return frappe.db.get_value(
			"EdgePay Payment Transaction",
			{
				"payment_request": payment_request,
				"provider_reference": provider_reference,
			},
			"name",
		)
	return None


def verify_transaction(payment_request_name):
	pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
	from edgepayv1.edgepay.services.checkout import check_and_mark_expired

	check_and_mark_expired(pr)
	pr.reload()
	if pr.status in NON_VERIFIABLE_REQUEST_STATUSES:
		frappe.throw(
			_("Cannot verify transaction for a Payment Request with final status: {0}").format(pr.status)
		)
	if not pr.provider or not pr.provider_reference:
		frappe.throw(_("Payment Request has no provider reference generated"))
	if not pr.provider_account:
		frappe.throw(_("Payment Request has no Provider Account"))

	attempt = resolve_or_create_legacy_attempt(pr.name)
	provider_reference = attempt.provider_payment_reference or pr.provider_reference
	provider_instance = get_provider_instance(pr.provider, provider_account=pr.provider_account)
	provider_instance.validate_configuration()
	payload = provider_instance.build_verification_payload(provider_reference)
	client = get_client(
		provider_instance.get_provider_code(),
		provider_instance.provider_doc,
		provider_instance.provider_account,
	)
	url = f"{provider_instance.get_base_url()}/v1/merchant/transactions/query?{urlparse.urlencode(payload)}"
	response = client.get(url)
	parsed = provider_instance.parse_verification_response(response)
	if parsed.get("amount") is not None and flt(parsed.get("amount")) > flt(pr.amount):
		frappe.throw(_("Verification failed: Amount mismatch; payment exceeds Payment Request amount"))
	if parsed.get("currency") and parsed.get("currency").upper() != pr.currency.upper():
		frappe.throw(_("Verification failed: Currency mismatch"))

	txn_ref = parsed.get("transaction_reference") or parsed.get("provider_reference")
	prov_ref = parsed.get("provider_reference")
	txn_name = _find_transaction_name(pr.name, txn_ref, prov_ref)
	txn = (
		frappe.get_doc("EdgePay Payment Transaction", txn_name)
		if txn_name
		else frappe.new_doc("EdgePay Payment Transaction")
	)
	txn.payment_request = pr.name
	txn.payment_attempt = attempt.name
	txn.provider = pr.provider
	txn.transaction_reference = txn_ref
	txn.provider_reference = prov_ref
	txn.amount = flt(parsed.get("amount") or pr.amount)
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
	if prov_ref:
		register_reference(
			"Provider Payment", prov_ref, pr.name, payment_attempt=attempt.name, payment_transaction=txn.name
		)
	if txn_ref:
		register_reference(
			"Provider Transaction",
			txn_ref,
			pr.name,
			payment_attempt=attempt.name,
			payment_transaction=txn.name,
		)

	if txn.status == "Success" and attempt.status != "Successful":
		transition_attempt(attempt, "Successful", "Verification Successful", "verification", txn)
	elif txn.status == "Failed" and attempt.status not in {"Successful", "Failed"}:
		transition_attempt(attempt, "Failed", "Verification Failed", "verification", txn)
	elif txn.status == "Pending" and attempt.status in {"Created", "Initiated"}:
		transition_attempt(attempt, "Pending", "Verification Pending", "verification", txn)

	totals = sync_payment_totals(pr.name)
	pr.reload()
	if txn.status == "Failed" and totals["net_paid_amount"] <= 0 and pr.status == "Initiated":
		transition_request(
			pr,
			"Failed",
			"Payment Verification Failed",
			"verification",
			attempt=attempt,
			transaction=txn,
		)

	from edgepayv1.edgepay.services.connectors import notify_source_payment_status

	notify_source_payment_status(pr.name, txn.name, event_source="verification")
	pr.reload()
	return {
		"payment_request": pr.name,
		"payment_attempt": attempt.name,
		"request_status": pr.status,
		"transaction": txn.name,
		"transaction_status": txn.status,
		"provider_reference": prov_ref,
		"amount": txn.amount,
		"currency": txn.currency,
		"paid_on": txn.paid_on,
		"totals": totals,
	}


@frappe.whitelist()
def verify_payment_request_transaction(payment_request_name):
	if not frappe.has_permission("EdgePay Payment Request", "write", doc=payment_request_name):
		frappe.throw(
			_("Not permitted to verify transaction for this Payment Request"), frappe.PermissionError
		)
	return verify_transaction(payment_request_name)
