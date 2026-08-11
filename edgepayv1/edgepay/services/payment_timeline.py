# -*- coding: utf-8 -*-
import frappe
from frappe import _

from edgepayv1.edgepay.services.authorization import require_payment_request_access


@frappe.whitelist()
def get_payment_timeline(payment_request_name):
	request = require_payment_request_access(payment_request_name, ptype="read")
	attempts = frappe.get_all("EdgePay Payment Attempt", filters={"payment_request": request.name}, fields=["name", "attempt_number", "status", "payment_method", "provider_payment_reference", "provider_transaction_reference", "started_on", "completed_on"], order_by="attempt_number asc")
	transactions = frappe.get_all("EdgePay Payment Transaction", filters={"payment_request": request.name}, fields=["name", "payment_attempt", "status", "transaction_reference", "provider_reference", "amount", "currency", "paid_on", "settlement_status"], order_by="creation asc")
	events = frappe.get_all("EdgePay Payment Event", filters={"payment_request": request.name}, fields=["name", "payment_attempt", "payment_transaction", "event_type", "previous_status", "new_status", "event_source", "provider_reference", "occurred_on", "actor"], order_by="occurred_on asc")
	return {"payment_request": request.name, "status": request.status, "amount": request.amount, "currency": request.currency, "attempts": attempts, "transactions": transactions, "events": events}
