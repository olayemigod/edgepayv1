# -*- coding: utf-8 -*-
import frappe
from frappe import _

from edgepayv1.edgepay.services.authorization import require_payment_transaction_access
from edgepayv1.edgepay.services.payment_state import record_event, transition_request


def create_refund_request(payment_transaction, amount, reason):
	transaction = require_payment_transaction_access(payment_transaction, ptype="read")
	doc = frappe.new_doc("EdgePay Refund Request")
	doc.payment_transaction = transaction.name
	doc.amount = amount
	doc.reason = reason
	doc.status = "Requested"
	doc.insert(ignore_permissions=True)
	request = frappe.get_doc("EdgePay Payment Request", transaction.payment_request)
	if request.status in {"Paid", "Overpaid", "Partly Paid", "Partly Refunded"}:
		transition_request(
			request,
			"Refund Pending",
			"Refund Requested",
			event_source="refund",
			transaction=transaction,
			details={"refund_request": doc.name, "amount": doc.amount},
		)
	else:
		record_event(
			request,
			transaction=transaction,
			event_type="Refund Requested",
			event_source="refund",
			details={"refund_request": doc.name, "amount": doc.amount},
		)
	return doc


def approve_refund_request(refund_request):
	doc = frappe.get_doc("EdgePay Refund Request", refund_request)
	roles = set(frappe.get_roles(frappe.session.user))
	if frappe.session.user != "Administrator" and not roles.intersection({"EdgePay Admin", "EdgePay Manager", "System Manager"}):
		frappe.throw(_("Only authorised EdgePay reviewers may approve refunds"), frappe.PermissionError)
	if doc.status != "Requested":
		frappe.throw(_("Only requested refunds may be approved"))
	doc.status = "Approved"
	doc.save(ignore_permissions=True)
	return doc


@frappe.whitelist()
def request_refund(payment_transaction, amount, reason):
	doc = create_refund_request(payment_transaction, amount, reason)
	return {"refund_request": doc.name, "status": doc.status, "amount": doc.amount, "currency": doc.currency}


@frappe.whitelist()
def approve_refund(refund_request):
	doc = approve_refund_request(refund_request)
	return {"refund_request": doc.name, "status": doc.status}
