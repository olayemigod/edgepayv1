# -*- coding: utf-8 -*-
import frappe
from frappe import _
import json
from frappe.utils import now_datetime, flt
from edgepayv1.edgepay.services.security import redact_secrets
from edgepayv1.edgepay.services.logging import log

def build_status_handoff_payload(pr, txn=None, event_source=None, event_type=None):
	"""
	Assembles a standardized, redacted safe payload for payment status handoffs.
	"""
	payload = {
		"source_app": pr.source_app,
		"source_doctype": pr.source_doctype,
		"source_name": pr.source_name,
		"source_reference": getattr(pr, "source_reference", None) or pr.source_name,
		"payment_request": pr.name,
		"payment_transaction": txn.name if txn else None,
		"request_status": pr.status,
		"transaction_status": txn.status if txn else None,
		"amount": flt(pr.amount),
		"currency": pr.currency,
		"provider": pr.provider,
		"provider_reference": pr.provider_reference,
		"transaction_reference": txn.transaction_reference if txn else None,
		"paid_on": str(txn.paid_on) if (txn and txn.paid_on) else None,
		"event_source": event_source,
		"event_type": event_type
	}
	return redact_secrets(payload)

def emit_status_handoff(payment_request_name, transaction_name=None, event_source=None, event_type=None):
	"""
	Emits a Status Handoff Event if the state transitions meaningfully, avoiding duplicate entries.
	"""
	try:
		if not frappe.db.exists("EdgePay Payment Request", payment_request_name):
			return None

		pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
		txn = frappe.get_doc("EdgePay Payment Transaction", transaction_name) if transaction_name else None

		# Normalize event source to capitalized format (e.g. "checkout" -> "Checkout")
		if event_source:
			event_source = str(event_source).strip().capitalize()
		else:
			event_source = "Manual"

		# Auto-resolve event type if not provided
		if not event_type:
			if pr.status == "Paid":
				event_type = "Payment Paid"
			elif pr.status == "Failed":
				event_type = "Payment Failed"
			elif pr.status == "Expired":
				event_type = "Payment Expired"
			elif pr.status == "Cancelled":
				event_type = "Payment Cancelled"
			elif pr.status == "Initiated":
				event_type = "Payment Initiated"
			else:
				event_type = "Payment Pending"

		# Generate a deterministic idempotency key
		txn_part = f"-{transaction_name}" if transaction_name else ""
		idempotency_key = f"{payment_request_name}{txn_part}-{event_source}-{event_type}"

		# De-duplication check
		existing_event = frappe.db.get_value(
			"EdgePay Status Handoff Event",
			{"idempotency_key": idempotency_key},
			"name"
		)
		if existing_event:
			log(f"Status Handoff Event already exists for key {idempotency_key}. Skipping duplicate emission.", level="info")
			return existing_event

		safe_payload = build_status_handoff_payload(pr, txn, event_source, event_type)

		# Build and insert Event doc
		event = frappe.new_doc("EdgePay Status Handoff Event")
		event.payment_request = pr.name
		event.payment_transaction = txn.name if txn else None
		event.source_app = pr.source_app
		event.source_doctype = pr.source_doctype
		event.source_name = pr.source_name
		event.source_reference = getattr(pr, "source_reference", None) or pr.source_name
		event.event_source = event_source or "Manual"
		event.event_type = event_type
		event.request_status = pr.status
		event.transaction_status = txn.status if txn else None
		event.provider = pr.provider
		event.provider_reference = pr.provider_reference
		event.transaction_reference = txn.transaction_reference if txn else None
		event.amount = pr.amount
		event.currency = pr.currency
		event.paid_on = txn.paid_on if txn else None
		event.processing_status = "Pending"
		event.delivery_attempts = 0
		event.payload_json = json.dumps(safe_payload, indent=2)
		event.idempotency_key = idempotency_key

		event.insert(ignore_permissions=True)
		if not frappe.flags.in_test:
			frappe.db.commit()

		log(f"Status Handoff Event {event.name} emitted for Payment Request {pr.name} (Source: {event_source}/{event_type})", level="info")
		return event.name

	except Exception as e:
		# Important: Handoff emission failure must not crash or silently corrupt core payments processing
		log(f"Failed to emit status handoff event for {payment_request_name}: {str(e)}", level="error")
		return None

def get_pending_handoff_events(source_app=None, limit=50):
	"""
	Returns a list of pending status handoff event dictionaries with sanitized payloads.
	"""
	filters = {"processing_status": "Pending"}
	if source_app:
		filters["source_app"] = source_app

	events = frappe.get_all(
		"EdgePay Status Handoff Event",
		filters=filters,
		fields=[
			"name", "payment_request", "payment_transaction", "source_app",
			"source_doctype", "source_name", "source_reference", "event_source",
			"event_type", "request_status", "transaction_status", "provider",
			"provider_reference", "transaction_reference", "amount", "currency",
			"paid_on", "processing_status", "delivery_attempts", "payload_json"
		],
		limit=flt(limit) or 50,
		order_by="creation asc"
	)

	for ev in events:
		if ev.get("payload_json"):
			try:
				ev["payload"] = redact_secrets(json.loads(ev["payload_json"]))
			except Exception:
				ev["payload"] = {}
		else:
			ev["payload"] = {}
	return events

def mark_handoff_event_delivered(event_name):
	"""
	Marks the specified handoff event as Delivered.
	"""
	if not frappe.db.exists("EdgePay Status Handoff Event", event_name):
		frappe.throw(_("Status Handoff Event {0} not found").format(event_name))

	ev = frappe.get_doc("EdgePay Status Handoff Event", event_name)
	ev.processing_status = "Delivered"
	ev.delivery_attempts = (ev.delivery_attempts or 0) + 1
	ev.last_delivery_on = now_datetime()
	ev.save(ignore_permissions=True)
	if not frappe.flags.in_test:
		frappe.db.commit()

def mark_handoff_event_failed(event_name, error_message=None):
	"""
	Marks the specified handoff event as Failed with redacted error logging.
	"""
	if not frappe.db.exists("EdgePay Status Handoff Event", event_name):
		frappe.throw(_("Status Handoff Event {0} not found").format(event_name))

	ev = frappe.get_doc("EdgePay Status Handoff Event", event_name)
	ev.processing_status = "Failed"
	ev.delivery_attempts = (ev.delivery_attempts or 0) + 1
	ev.last_delivery_on = now_datetime()
	if error_message:
		ev.error_message = redact_secrets(str(error_message))
	ev.save(ignore_permissions=True)
	if not frappe.flags.in_test:
		frappe.db.commit()
