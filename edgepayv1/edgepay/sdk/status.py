# -*- coding: utf-8 -*-
import frappe
from frappe import _
from edgepayv1.edgepay.services.checkout import check_and_mark_expired
from edgepayv1.edgepay.services.security import redact_secrets

def get_source_payment_status(payment_request_name):
	"""
	Wraps status check without mutating database records.
	"""
	try:
		if not frappe.db.exists("EdgePay Payment Request", payment_request_name):
			frappe.throw(_("Payment Request {0} not found").format(payment_request_name))

		pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
		
		# Check and update expiry in memory only (no mutation)
		check_and_mark_expired(pr, save=False)

		data = {
			"payment_request": pr.name,
			"request_reference": pr.request_reference,
			"status": pr.status,
			"amount": pr.amount,
			"currency": pr.currency,
			"provider": pr.provider,
			"expires_on": pr.expires_on
		}
		return {
			"ok": True,
			"status": "success",
			"message": "Payment request status retrieved successfully",
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

def get_source_transaction_status(payment_request_name=None, provider_reference=None, transaction_reference=None):
	"""
	Retrieves transaction status safely without mutating database records.
	"""
	try:
		filters = {}
		if payment_request_name:
			filters["payment_request"] = payment_request_name
		if provider_reference:
			filters["provider_reference"] = provider_reference
		if transaction_reference:
			filters["transaction_reference"] = transaction_reference

		if not filters:
			frappe.throw(_("At least one reference parameter is required"))

		txn_name = frappe.db.get_value("EdgePay Payment Transaction", filters, "name")
		if not txn_name:
			frappe.throw(_("Transaction not found for the given references"))

		txn = frappe.get_doc("EdgePay Payment Transaction", txn_name)

		data = {
			"transaction": txn.name,
			"payment_request": txn.payment_request,
			"status": txn.status,
			"amount": txn.amount,
			"currency": txn.currency,
			"provider_reference": txn.provider_reference,
			"transaction_reference": txn.transaction_reference,
			"paid_on": txn.paid_on,
			"settlement_status": txn.settlement_status
		}
		return {
			"ok": True,
			"status": "success",
			"message": "Payment transaction status retrieved successfully",
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
