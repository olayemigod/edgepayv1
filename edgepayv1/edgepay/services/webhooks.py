# -*- coding: utf-8 -*-
import json

import frappe
from frappe import _
from frappe.utils import flt

from edgepayv1.edgepay.services.logging import log
from edgepayv1.edgepay.services.providers.registry import get_provider_instance
from edgepayv1.edgepay.services.request_security import (
	require_post_request,
	validate_webhook_body,
)
from edgepayv1.edgepay.services.security import redact_secrets


ALLOWED_TRANSACTION_STATUSES = {"Pending", "Success", "Failed", "Refunded"}


def _failure(event_doc, message):
	event_doc.processing_status = "Failed"
	event_doc.error_message = message
	event_doc.insert(ignore_permissions=True)
	log(message, level="error")
	return {
		"status": "failed",
		"event": event_doc.name,
		"processing_status": "Failed",
		"duplicate": False,
	}


def process_webhook_event(provider_code, headers, raw_body):
	"""Validate and process one signed provider webhook event.

	This is an internal privileged service. The public wrapper is responsible for
	HTTP-method and request-size validation before invoking it.
	"""
	provider_name = frappe.db.get_value(
		"EdgePay Provider", {"provider_code": provider_code}, "name"
	)
	if not provider_name:
		frappe.throw(_("Unsupported provider code: {0}").format(provider_code))

	provider_doc = frappe.get_doc("EdgePay Provider", provider_name)
	if not provider_doc.enabled:
		frappe.throw(_("Provider {0} is disabled").format(provider_doc.provider_name))

	provider_instance = get_provider_instance(provider_doc)
	try:
		body_str = raw_body.decode("utf-8") if isinstance(raw_body, bytes) else raw_body
		payload = json.loads(body_str)
	except (UnicodeDecodeError, TypeError, ValueError):
		frappe.throw(_("Invalid JSON payload in webhook body"))
	if not isinstance(payload, dict):
		frappe.throw(_("Webhook payload must be a JSON object"))

	redacted_payload = redact_secrets(payload)
	event_ref = provider_instance.get_webhook_event_reference(payload)
	if not event_ref:
		frappe.throw(_("Webhook event has no unique event identifier"))

	existing_event = frappe.db.get_value(
		"EdgePay Webhook Event",
		{"provider": provider_doc.name, "event_reference": event_ref},
		["name", "processing_status"],
		as_dict=True,
	)
	if existing_event:
		log(f"Duplicate webhook event {event_ref} ignored.", level="info")
		return {
			"status": "success",
			"event": existing_event.name,
			"processing_status": existing_event.processing_status,
			"duplicate": True,
		}

	event_doc = frappe.new_doc("EdgePay Webhook Event")
	event_doc.provider = provider_doc.name
	event_doc.event_type = payload.get("eventType") or "unknown"
	event_doc.event_reference = event_ref
	event_doc.received_on = frappe.utils.now_datetime()
	event_doc.payload_json = json.dumps(redacted_payload, indent=2)

	signature_valid = provider_instance.verify_webhook_signature(raw_body, headers)
	event_doc.signature_valid = 1 if signature_valid else 0
	if not signature_valid:
		return _failure(
			event_doc,
			f"Webhook signature validation failed for event {event_ref}",
		)

	parsed = provider_instance.parse_webhook_payload(payload)
	if not isinstance(parsed, dict):
		return _failure(event_doc, f"Provider returned an invalid normalized event for {event_ref}")

	new_status = parsed.get("status")
	if new_status not in ALLOWED_TRANSACTION_STATUSES:
		return _failure(event_doc, f"Unsupported normalized payment status for event {event_ref}")

	payment_ref = provider_instance.get_webhook_payment_reference(payload)
	provider_ref = provider_instance.get_webhook_transaction_reference(payload)
	pr_name = None
	if payment_ref:
		from edgepayv1.edgepay.services.api import resolve_payment_request_by_ref

		pr_name = resolve_payment_request_by_ref(payment_ref)
	if not pr_name and provider_ref:
		pr_name = frappe.db.get_value(
			"EdgePay Payment Request", {"provider_reference": provider_ref}, "name"
		)
	if not pr_name:
		return _failure(
			event_doc,
			f"Payment Request not resolved for event {event_ref}",
		)

	pr = frappe.get_doc("EdgePay Payment Request", pr_name)
	parsed_amount = parsed.get("amount")
	if parsed_amount is not None and flt(parsed_amount) != flt(pr.amount):
		return _failure(event_doc, f"Amount mismatch for event {event_ref}")

	parsed_currency = parsed.get("currency")
	if parsed_currency and pr.currency and parsed_currency.upper() != pr.currency.upper():
		return _failure(event_doc, f"Currency mismatch for event {event_ref}")

	txn_ref = parsed.get("transaction_reference") or parsed.get("provider_reference")
	provider_transaction_ref = parsed.get("provider_reference")
	existing_txn_name = frappe.db.get_value(
		"EdgePay Payment Transaction", {"payment_request": pr.name}, "name"
	)
	if not existing_txn_name and provider_transaction_ref:
		existing_txn_name = frappe.db.get_value(
			"EdgePay Payment Transaction",
			{"provider_reference": provider_transaction_ref},
			"name",
		)
	if not existing_txn_name and txn_ref:
		existing_txn_name = frappe.db.get_value(
			"EdgePay Payment Transaction",
			{"transaction_reference": txn_ref},
			"name",
		)

	txn = (
		frappe.get_doc("EdgePay Payment Transaction", existing_txn_name)
		if existing_txn_name
		else frappe.new_doc("EdgePay Payment Transaction")
	)
	txn.payment_request = pr.name
	txn.provider = pr.provider
	txn.transaction_reference = txn_ref
	txn.provider_reference = provider_transaction_ref
	txn.amount = pr.amount
	txn.currency = pr.currency
	if parsed.get("paid_on"):
		txn.paid_on = parsed.get("paid_on")
	if parsed.get("settlement_status"):
		txn.settlement_status = parsed.get("settlement_status")
	txn.raw_response_json = json.dumps(redacted_payload, indent=2)
	txn.idempotency_key = pr.idempotency_key

	if pr.status == "Paid" and new_status != "Success":
		log(
			f"Payment Request {pr.name} is already Paid; webhook status downgrade skipped.",
			level="info",
		)
	elif new_status == "Success":
		pr.status = "Paid"
	elif new_status == "Failed":
		pr.status = "Failed"

	if txn.status == "Success" and new_status != "Success":
		log(
			f"Payment Transaction {txn.name} is already Success; status downgrade skipped.",
			level="info",
		)
	else:
		txn.status = new_status

	# These writes are deliberately privileged because the caller is a verified
	# provider webhook, not a Desk user. Merchant scoping will extend this seam.
	txn.save(ignore_permissions=True)
	pr.save(ignore_permissions=True)

	from edgepayv1.edgepay.services.connectors import notify_source_payment_status

	notify_source_payment_status(pr.name, txn.name, event_source="webhook")
	event_doc.linked_payment_request = pr.name
	event_doc.linked_payment_transaction = txn.name
	event_doc.processing_status = "Processed"
	event_doc.insert(ignore_permissions=True)
	return {
		"status": "success",
		"event": event_doc.name,
		"processing_status": "Processed",
		"duplicate": False,
	}


@frappe.whitelist(allow_guest=True)
def process_provider_webhook(provider_code):
	"""Receive a bounded POST webhook and return a minimal provider response."""
	try:
		require_post_request()
		request = getattr(frappe.local, "request", None)
		raw_body = request.get_data(cache=True) if request is not None else b""
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
		return {
			"status": "failed",
			"message": "An error occurred during webhook processing",
		}
