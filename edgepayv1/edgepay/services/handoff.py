# -*- coding: utf-8 -*-
import json

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from edgepayv1.edgepay.services.logging import log
from edgepayv1.edgepay.services.security import redact_secrets


def build_status_handoff_payload(pr, txn=None, event_source=None, event_type=None):
	return redact_secrets({
		"merchant": pr.merchant,
		"merchant_account": getattr(pr, "merchant_account", None),
		"merchant_branch": getattr(pr, "merchant_branch", None),
		"provider_account": pr.provider_account,
		"source_app": pr.source_app,
		"source_doctype": pr.source_doctype,
		"source_name": pr.source_name,
		"source_reference": getattr(pr, "source_reference", None) or pr.source_name,
		"payment_request": pr.name,
		"payment_transaction": txn.name if txn else None,
		"request_status": pr.status,
		"transaction_status": txn.status if txn else None,
		"amount": flt(pr.amount),
		"paid_amount": flt(getattr(pr, "paid_amount", 0)),
		"outstanding_amount": flt(getattr(pr, "outstanding_amount", pr.amount)),
		"currency": pr.currency,
		"provider": pr.provider,
		"provider_reference": pr.provider_reference,
		"transaction_reference": txn.transaction_reference if txn else None,
		"paid_on": str(txn.paid_on) if txn and txn.paid_on else None,
		"event_source": event_source,
		"event_type": event_type,
	})


def emit_status_handoff(payment_request_name, transaction_name=None, event_source=None, event_type=None):
	try:
		if not frappe.db.exists("EdgePay Payment Request", payment_request_name):
			return None
		pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
		txn = frappe.get_doc("EdgePay Payment Transaction", transaction_name) if transaction_name else None
		event_source = str(event_source or "Manual").strip().capitalize()
		if not event_type:
			event_type = {
				"Paid": "Payment Paid", "Partly Paid": "Payment Partly Paid", "Overpaid": "Payment Overpaid",
				"Failed": "Payment Failed", "Expired": "Payment Expired", "Cancelled": "Payment Cancelled",
				"Initiated": "Payment Initiated", "Refunded": "Payment Refunded",
			}.get(pr.status, "Payment Pending")
		idempotency_key = f"{pr.merchant}:{payment_request_name}:{transaction_name or ''}:{event_source}:{event_type}"
		existing = frappe.db.get_value("EdgePay Status Handoff Event", {"idempotency_key": idempotency_key}, "name")
		if existing:
			return existing
		payload = build_status_handoff_payload(pr, txn, event_source, event_type)
		event = frappe.new_doc("EdgePay Status Handoff Event")
		event.update({
			"merchant": pr.merchant, "merchant_account": getattr(pr, "merchant_account", None),
			"merchant_branch": getattr(pr, "merchant_branch", None), "provider_account": pr.provider_account,
			"payment_request": pr.name, "payment_transaction": txn.name if txn else None,
			"source_app": pr.source_app, "source_doctype": pr.source_doctype, "source_name": pr.source_name,
			"source_reference": getattr(pr, "source_reference", None) or pr.source_name,
			"event_source": event_source, "event_type": event_type, "request_status": pr.status,
			"transaction_status": txn.status if txn else None, "provider": pr.provider,
			"provider_reference": pr.provider_reference, "transaction_reference": txn.transaction_reference if txn else None,
			"amount": pr.amount, "currency": pr.currency, "paid_on": txn.paid_on if txn else None,
			"processing_status": "Pending", "delivery_attempts": 0,
			"payload_json": json.dumps(payload, indent=2), "idempotency_key": idempotency_key,
		})
		event.insert(ignore_permissions=True)
		try:
			from edgepayv1.edgepay.services.deliveries import create_delivery
			create_delivery(
				pr.merchant,
				"handoff." + str(event_type).strip().lower().replace(" ", "."),
				{"handoff_event": event.name, **payload},
				payment_request=pr.name,
				payment_transaction=txn.name if txn else None,
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"EdgePay handoff delivery enqueue failed: {event.name}")
		return event.name
	except Exception as exc:
		log(f"Failed to emit status handoff event for {payment_request_name}: {redact_secrets(str(exc))}", level="error")
		return None


def get_pending_handoff_events(source_app=None, merchant=None, limit=50):
	filters = {"processing_status": "Pending"}
	if source_app:
		filters["source_app"] = source_app
	if merchant:
		filters["merchant"] = merchant
	events = frappe.get_all("EdgePay Status Handoff Event", filters=filters,
		fields=["name", "merchant", "merchant_account", "merchant_branch", "provider_account", "payment_request", "payment_transaction", "source_app", "source_doctype", "source_name", "source_reference", "event_source", "event_type", "request_status", "transaction_status", "provider", "provider_reference", "transaction_reference", "amount", "currency", "paid_on", "processing_status", "delivery_attempts", "payload_json"],
		limit=int(limit or 50), order_by="creation asc")
	for event in events:
		try:
			event["payload"] = redact_secrets(json.loads(event.get("payload_json") or "{}"))
		except Exception:
			event["payload"] = {}
	return events


def _update_delivery(event_name, status, error_message=None):
	if not frappe.db.exists("EdgePay Status Handoff Event", event_name):
		frappe.throw(_("Status Handoff Event {0} not found").format(event_name))
	event = frappe.get_doc("EdgePay Status Handoff Event", event_name)
	event.processing_status = status
	event.delivery_attempts = (event.delivery_attempts or 0) + 1
	event.last_delivery_on = now_datetime()
	if error_message:
		event.error_message = redact_secrets(str(error_message))
	event.save(ignore_permissions=True)


def mark_handoff_event_delivered(event_name):
	_update_delivery(event_name, "Delivered")


def mark_handoff_event_failed(event_name, error_message=None):
	_update_delivery(event_name, "Failed", error_message=error_message)
