# -*- coding: utf-8 -*-
import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from edgepayv1.edgepay.services.security import redact_secrets

ATTEMPT_TRANSITIONS = {
	"Created": {"Initiated", "Cancelled", "Expired"},
	"Initiated": {"Pending", "Successful", "Failed", "Cancelled", "Expired"},
	"Pending": {"Successful", "Failed", "Cancelled", "Expired"},
	"Successful": set(),
	"Failed": set(),
	"Expired": set(),
	"Cancelled": set(),
}
REQUEST_TRANSITIONS = {
	"Draft": {"Initiated", "Cancelled", "Expired"},
	"Initiated": {"Partly Paid", "Paid", "Overpaid", "Failed", "Cancelled", "Expired"},
	"Partly Paid": {"Initiated", "Paid", "Overpaid", "Refund Pending", "Partly Refunded", "Refunded", "Disputed", "Chargeback", "Cancelled"},
	"Paid": {"Refund Pending", "Partly Refunded", "Refunded", "Disputed", "Chargeback"},
	"Overpaid": {"Refund Pending", "Partly Refunded", "Refunded", "Disputed", "Chargeback"},
	"Refund Pending": {"Partly Refunded", "Refunded", "Paid", "Failed"},
	"Partly Refunded": {"Refund Pending", "Refunded", "Paid", "Disputed", "Chargeback"},
	"Refunded": {"Disputed", "Chargeback"},
	"Disputed": {"Paid", "Partly Refunded", "Refunded", "Chargeback"},
	"Chargeback": set(),
	"Failed": {"Initiated", "Partly Paid", "Paid", "Overpaid", "Cancelled", "Expired"},
	"Expired": set(),
	"Cancelled": set(),
}


def create_attempt(payment_request_name, payment_method=None, expires_on=None):
	request = frappe.get_doc("EdgePay Payment Request", payment_request_name)
	latest = frappe.db.get_value("EdgePay Payment Attempt", {"payment_request": request.name}, "attempt_number", order_by="attempt_number desc") or 0
	attempt = frappe.new_doc("EdgePay Payment Attempt")
	attempt.payment_request = request.name
	attempt.attempt_number = int(latest) + 1
	attempt.payment_method = payment_method
	attempt.expires_on = expires_on or request.expires_on
	attempt.status = "Created"
	attempt.insert(ignore_permissions=True)
	record_event(request, attempt=attempt, event_type="Attempt Created", new_status="Created", event_source="checkout")
	return attempt


def transition_attempt(attempt, new_status, event_type, event_source=None, transaction=None, details=None):
	if isinstance(attempt, str):
		attempt = frappe.get_doc("EdgePay Payment Attempt", attempt)
	previous = attempt.status
	if new_status != previous and new_status not in ATTEMPT_TRANSITIONS.get(previous, set()):
		frappe.throw(_("Invalid Payment Attempt transition from {0} to {1}").format(previous, new_status))
	attempt.status = new_status
	if new_status == "Initiated" and not attempt.started_on:
		attempt.started_on = now_datetime()
	if new_status in {"Successful", "Failed", "Expired", "Cancelled"}:
		attempt.completed_on = now_datetime()
	attempt.save(ignore_permissions=True)
	request = frappe.get_doc("EdgePay Payment Request", attempt.payment_request)
	record_event(request, attempt, transaction, event_type, previous, new_status, event_source, details)
	return attempt


def transition_request(request, new_status, event_type, event_source=None, attempt=None, transaction=None, details=None):
	if isinstance(request, str):
		request = frappe.get_doc("EdgePay Payment Request", request)
	previous = request.status
	if new_status != previous and new_status not in REQUEST_TRANSITIONS.get(previous, set()):
		frappe.throw(_("Invalid Payment Request transition from {0} to {1}").format(previous, new_status))
	request.status = new_status
	request.save(ignore_permissions=True)
	record_event(request, attempt, transaction, event_type, previous, new_status, event_source, details)
	return request


def _event_key(event_type):
	return str(event_type or "payment.updated").strip().lower().replace(" ", ".").replace("_", ".")


def record_event(request, attempt=None, transaction=None, event_type=None, previous_status=None, new_status=None, event_source=None, details=None):
	event = frappe.new_doc("EdgePay Payment Event")
	event.merchant = request.merchant
	event.payment_request = request.name
	event.payment_attempt = attempt.name if attempt else None
	event.payment_transaction = transaction.name if transaction else None
	event.event_type = event_type or "Payment Updated"
	event.previous_status = previous_status
	event.new_status = new_status
	event.event_source = event_source
	event.provider_reference = (getattr(transaction, "provider_reference", None) if transaction else None) or (getattr(attempt, "provider_payment_reference", None) if attempt else None)
	event.occurred_on = now_datetime()
	event.actor = frappe.session.user or "System"
	event.details_json = json.dumps(redact_secrets(details or {}), indent=2)
	event.insert(ignore_permissions=True)
	try:
		from edgepayv1.edgepay.services.deliveries import create_delivery
		create_delivery(
			request.merchant,
			_event_key(event.event_type),
			{
				"payment_event": event.name,
				"payment_request": request.name,
				"request_reference": request.request_reference,
				"payment_attempt": event.payment_attempt,
				"payment_transaction": event.payment_transaction,
				"previous_status": previous_status,
				"new_status": new_status,
				"event_source": event_source,
				"amount": request.amount,
				"paid_amount": getattr(request, "paid_amount", None),
				"outstanding_amount": getattr(request, "outstanding_amount", None),
				"currency": request.currency,
			},
			payment_request=request.name,
			payment_transaction=event.payment_transaction,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"EdgePay delivery enqueue failed for event {event.name}")
	return event
