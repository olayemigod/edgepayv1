# -*- coding: utf-8 -*-
import frappe
from frappe import _
from edgepayv1.edgepay.services.connectors import create_payment_request_from_source
from edgepayv1.edgepay.services.checkout import initialize_checkout
from edgepayv1.edgepay.services.verification import verify_transaction
from edgepayv1.edgepay.services.security import redact_secrets

def create_source_payment_request(source_context):
	"""
	Wraps create_payment_request_from_source.
	Returns safe normalized dictionary only.
	"""
	try:
		res = create_payment_request_from_source(source_context)
		return redact_secrets(res)
	except Exception as e:
		redacted_msg = redact_secrets(str(e))
		return {
			"ok": False,
			"status": "error",
			"message": redacted_msg,
			"data": None
		}

def initialize_source_checkout(payment_request_name):
	"""
	Wraps initialize_checkout.
	Returns safe normalized dictionary with only safe checkout fields.
	"""
	try:
		result = initialize_checkout(payment_request_name)
		pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
		data = {
			"payment_request": pr.name,
			"status": result.get("status"),
			"checkout_url": result.get("checkout_url"),
			"provider_reference": result.get("provider_reference"),
			"expires_on": pr.expires_on
		}
		return {
			"ok": True,
			"status": "success",
			"message": "Checkout initialized successfully",
			"data": redact_secrets(data)
		}
	except Exception as e:
		redacted_msg = redact_secrets(str(e))
		return {
			"ok": False,
			"status": "error",
			"message": redacted_msg,
			"data": None
		}

def verify_source_payment(payment_request_name):
	"""
	Wraps verify_transaction.
	Returns safe normalized status fields only.
	"""
	try:
		result = verify_transaction(payment_request_name)
		data = {
			"payment_request": result.get("payment_request"),
			"request_status": result.get("request_status"),
			"transaction": result.get("transaction"),
			"transaction_status": result.get("transaction_status"),
			"provider_reference": result.get("provider_reference"),
			"amount": result.get("amount"),
			"currency": result.get("currency"),
			"paid_on": result.get("paid_on")
		}
		return {
			"ok": True,
			"status": "success",
			"message": "Transaction verified successfully",
			"data": redact_secrets(data)
		}
	except Exception as e:
		redacted_msg = redact_secrets(str(e))
		return {
			"ok": False,
			"status": "error",
			"message": redacted_msg,
			"data": None
		}

def get_pending_payment_handoffs(source_app=None, limit=50):
	"""
	Safe wrapper to fetch pending status handoff events.
	Returns safe normalized list of event dicts.
	"""
	try:
		if frappe.session.user == "Guest":
			frappe.throw(_("Authentication required to access this API"), frappe.PermissionError)
		
		from edgepayv1.edgepay.services.handoff import get_pending_handoff_events
		events = get_pending_handoff_events(source_app=source_app, limit=limit)
		return {
			"ok": True,
			"status": "success",
			"message": "Pending handoffs retrieved successfully",
			"data": redact_secrets(events)
		}
	except Exception as e:
		redacted_msg = redact_secrets(str(e))
		return {
			"ok": False,
			"status": "error",
			"message": redacted_msg,
			"data": None
		}

def mark_payment_handoff_delivered(event_name):
	"""
	Safe wrapper to mark handoff event as delivered.
	"""
	try:
		if frappe.session.user == "Guest":
			frappe.throw(_("Authentication required to access this API"), frappe.PermissionError)
		
		from edgepayv1.edgepay.services.handoff import mark_handoff_event_delivered
		mark_handoff_event_delivered(event_name)
		return {
			"ok": True,
			"status": "success",
			"message": f"Handoff event {event_name} marked as delivered",
			"data": None
		}
	except Exception as e:
		redacted_msg = redact_secrets(str(e))
		return {
			"ok": False,
			"status": "error",
			"message": redacted_msg,
			"data": None
		}

def mark_payment_handoff_failed(event_name, error_message=None):
	"""
	Safe wrapper to mark handoff event as failed.
	"""
	try:
		if frappe.session.user == "Guest":
			frappe.throw(_("Authentication required to access this API"), frappe.PermissionError)
		
		from edgepayv1.edgepay.services.handoff import mark_handoff_event_failed
		mark_handoff_event_failed(event_name, error_message=error_message)
		return {
			"ok": True,
			"status": "success",
			"message": f"Handoff event {event_name} marked as failed",
			"data": None
		}
	except Exception as e:
		redacted_msg = redact_secrets(str(e))
		return {
			"ok": False,
			"status": "error",
			"message": redacted_msg,
			"data": None
		}
