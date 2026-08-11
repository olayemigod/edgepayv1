# -*- coding: utf-8 -*-
import frappe
from frappe import _


def resolve_attempt(payment_request_name, provider_payment_reference=None, provider_transaction_reference=None):
	filters = {"payment_request": payment_request_name}
	candidates = []
	if provider_transaction_reference:
		candidates = frappe.get_all("EdgePay Payment Attempt", filters={**filters, "provider_transaction_reference": provider_transaction_reference}, pluck="name")
	if not candidates and provider_payment_reference:
		candidates = frappe.get_all("EdgePay Payment Attempt", filters={**filters, "provider_payment_reference": provider_payment_reference}, pluck="name")
	if not candidates:
		candidates = frappe.get_all("EdgePay Payment Attempt", filters={**filters, "status": ["in", ["Created", "Initiated", "Pending"]]}, pluck="name", order_by="attempt_number desc", limit=2)
	if len(candidates) > 1:
		frappe.throw(_("Payment Attempt resolution is ambiguous for Payment Request {0}").format(payment_request_name))
	return frappe.get_doc("EdgePay Payment Attempt", candidates[0]) if candidates else None


def resolve_or_create_legacy_attempt(payment_request_name):
	attempt = resolve_attempt(payment_request_name)
	if attempt:
		return attempt
	from edgepayv1.edgepay.services.payment_state import create_attempt
	return create_attempt(payment_request_name)
