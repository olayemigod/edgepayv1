import json

import frappe
from frappe import _
from frappe.utils import flt

from edgepayv1.edgepay.services.attempt_resolution import resolve_attempt, resolve_or_create_legacy_attempt
from edgepayv1.edgepay.services.external_references import register_reference, resolve_reference
from edgepayv1.edgepay.services.logging import log
from edgepayv1.edgepay.services.payment_state import transition_attempt
from edgepayv1.edgepay.services.payment_totals import sync_payment_totals
from edgepayv1.edgepay.services.providers.registry import get_provider_instance
from edgepayv1.edgepay.services.request_security import require_post_request, validate_webhook_body
from edgepayv1.edgepay.services.security import redact_secrets

ALLOWED_TRANSACTION_STATUSES = {"Pending", "Success", "Failed", "Refunded"}


def _failure(event_doc, message):
	event_doc.processing_status = "Failed"
	event_doc.error_message = redact_secrets(message)
	event_doc.insert(ignore_permissions=True)
	log(redact_secrets(message), level="error")
	return {"status": "failed", "event": event_doc.name, "processing_status": "Failed", "duplicate": False}


def _resolve_webhook_payment_request(provider, payload):
	payment_ref = provider.get_webhook_payment_reference(payload)
	provider_ref = provider.get_webhook_transaction_reference(payload)
	from edgepayv1.edgepay.services.api import resolve_payment_request_by_ref

	pr_name = resolve_payment_request_by_ref(payment_ref) if payment_ref else None
	if not pr_name and provider_ref:
		row = resolve_reference(
			provider_ref,
			reference_types={"Provider Transaction", "Provider Payment"},
		)
		pr_name = row.payment_request if row else None
	if not pr_name and provider_ref:
		matches = frappe.get_all(
			"EdgePay Payment Request",
			filters={"provider_reference": provider_ref},
			pluck="name",
			limit=2,
		)
		if len(matches) > 1:
			frappe.throw(_("Webhook provider reference is ambiguous"))
		pr_name = matches[0] if matches else None
	return pr_name, payment_ref, provider_ref


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


def process_webhook_event(provider_code, headers, raw_body):
	provider_name = frappe.db.get_value("EdgePay Provider", {"provider_code": provider_code}, "name")
	if not provider_name:
		frappe.throw(_("Unsupported provider code"))
	provider_doc = frappe.get_doc("EdgePay Provider", provider_name)
	if not provider_doc.enabled:
		frappe.throw(_("Provider is disabled"))

	provider_parser = get_provider_instance(provider_doc)
	try:
		payload = json.loads(raw_body.decode("utf-8") if isinstance(raw_body, bytes) else raw_body)
	except Exception:
		frappe.throw(_("Invalid JSON payload in webhook body"))
	if not isinstance(payload, dict):
		frappe.throw(_("Webhook payload must be a JSON object"))

	event_ref = provider_parser.get_webhook_event_reference(payload)
	if not event_ref:
		frappe.throw(_("Webhook event has no unique event identifier"))

	event_doc = frappe.new_doc("EdgePay Webhook Event")
	event_doc.provider = provider_doc.name
	event_doc.event_type = payload.get("eventType") or "unknown"
	event_doc.event_reference = event_ref
	event_doc.received_on = frappe.utils.now_datetime()
	event_doc.payload_json = json.dumps(redact_secrets(payload), indent=2)

	pr_name, payment_ref, provider_ref = _resolve_webhook_payment_request(provider_parser, payload)
	if not pr_name:
		return _failure(event_doc, "Payment Request not resolved")
	pr = frappe.get_doc("EdgePay Payment Request", pr_name)
	if pr.provider != provider_doc.name:
		return _failure(event_doc, "Webhook Provider does not match Payment Request Provider")
	if not pr.provider_account:
		return _failure(event_doc, "Payment Request has no Provider Account")

	existing = frappe.db.get_value(
		"EdgePay Webhook Event",
		{
			"provider": provider_doc.name,
			"provider_account": pr.provider_account,
			"event_reference": event_ref,
		},
		["name", "processing_status"],
		as_dict=True,
	)
	if existing:
		return {
			"status": "success",
			"event": existing.name,
			"processing_status": existing.processing_status,
			"duplicate": True,
		}

	event_doc.merchant = pr.merchant
	event_doc.provider_account = pr.provider_account
	event_doc.linked_payment_request = pr.name
	provider = get_provider_instance(provider_doc, provider_account=pr.provider_account)
	event_doc.signature_valid = 1 if provider.verify_webhook_signature(raw_body, headers) else 0
	if not event_doc.signature_valid:
		return _failure(event_doc, "Webhook signature validation failed")

	parsed = provider.parse_webhook_payload(payload)
	incoming_status = parsed.get("status") if isinstance(parsed, dict) else None
	if incoming_status not in ALLOWED_TRANSACTION_STATUSES:
		return _failure(event_doc, "Unsupported normalized payment status")
	parsed_amount = flt(parsed.get("amount") or pr.amount)
	if parsed_amount <= 0 or parsed_amount > flt(pr.amount):
		return _failure(event_doc, "Amount mismatch: payment exceeds Payment Request amount")
	if parsed.get("currency") and parsed.get("currency").upper() != pr.currency.upper():
		return _failure(event_doc, "Currency mismatch")

	txn_ref = parsed.get("transaction_reference") or parsed.get("provider_reference")
	prov_ref = parsed.get("provider_reference")
	attempt = resolve_attempt(
		pr.name,
		provider_payment_reference=prov_ref or payment_ref,
		provider_transaction_reference=txn_ref or provider_ref,
	)
	if not attempt:
		attempt = resolve_or_create_legacy_attempt(pr.name)

	txn_name = _find_transaction_name(pr.name, txn_ref, prov_ref)
	txn = (
		frappe.get_doc("EdgePay Payment Transaction", txn_name)
		if txn_name
		else frappe.new_doc("EdgePay Payment Transaction")
	)
	preserve_success = bool(txn_name and txn.status == "Success" and incoming_status in {"Pending", "Failed"})
	if not preserve_success:
		txn.payment_request = pr.name
		txn.payment_attempt = attempt.name
		txn.provider = pr.provider
		txn.transaction_reference = txn_ref
		txn.provider_reference = prov_ref
		txn.amount = parsed_amount
		txn.currency = pr.currency
		txn.status = incoming_status
		txn.paid_on = parsed.get("paid_on") or txn.paid_on
		txn.settlement_status = parsed.get("settlement_status") or txn.settlement_status
		txn.raw_response_json = json.dumps(redact_secrets(payload), indent=2)
		txn.idempotency_key = f"webhook:{pr.merchant}:{event_ref}"
		txn.save(ignore_permissions=True)
	status = txn.status

	attempt.provider_transaction_reference = txn_ref or attempt.provider_transaction_reference
	attempt.provider_payment_reference = prov_ref or attempt.provider_payment_reference
	attempt.save(ignore_permissions=True)
	register_reference(
		"Webhook Event", event_ref, pr.name, payment_attempt=attempt.name, payment_transaction=txn.name
	)
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

	if status == "Success" and attempt.status != "Successful":
		transition_attempt(
			attempt,
			"Successful",
			"Webhook Payment Successful",
			"webhook",
			txn,
			{"event_reference": event_ref},
		)
	elif status == "Failed" and attempt.status not in {"Successful", "Failed"}:
		transition_attempt(
			attempt, "Failed", "Webhook Payment Failed", "webhook", txn, {"event_reference": event_ref}
		)
	elif status == "Pending" and attempt.status in {"Created", "Initiated"}:
		transition_attempt(
			attempt, "Pending", "Webhook Payment Pending", "webhook", txn, {"event_reference": event_ref}
		)
	elif status == "Refunded":
		refund_name = frappe.db.get_value(
			"EdgePay Refund Request",
			{"payment_transaction": txn.name, "status": ["in", ["Approved", "Submitted", "Processing"]]},
			"name",
		)
		if refund_name:
			from edgepayv1.edgepay.services.refund_processing import complete_refund

			complete_refund(refund_name, provider_reference=prov_ref or txn_ref)

	totals = sync_payment_totals(pr.name)
	from edgepayv1.edgepay.services.connectors import notify_source_payment_status

	notify_source_payment_status(pr.name, txn.name, event_source="webhook")
	event_doc.linked_payment_transaction = txn.name
	event_doc.processing_status = "Processed"
	event_doc.insert(ignore_permissions=True)
	return {
		"status": "success",
		"event": event_doc.name,
		"processing_status": "Processed",
		"duplicate": False,
		"totals": totals,
	}


# Provider webhooks must be publicly reachable; POST/body validation and merchant-scoped HMAC verification are mandatory.
@frappe.whitelist(allow_guest=True)  # nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
def process_provider_webhook(provider_code: str):
	try:
		require_post_request()
		request = getattr(frappe.local, "request", None)
		raw_body = request.get_data() if request is not None else b""
		headers = request.headers if request is not None else {}
		validate_webhook_body(raw_body)
		result = process_webhook_event(provider_code, headers, raw_body)
		return {
			"status": result.get("status"),
			"event": result.get("event"),
			"processing_status": result.get("processing_status"),
			"duplicate": result.get("duplicate", False),
		}
	except Exception as exc:
		frappe.log_error(
			f"EdgePay Webhook Exception: {redact_secrets(str(exc))}",
			"EdgePay Webhook Error",
		)
		if not frappe.local.response.get("http_status_code"):
			frappe.local.response["http_status_code"] = 400
		return {"status": "failed", "message": "An error occurred during webhook processing"}
