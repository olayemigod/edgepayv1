# -*- coding: utf-8 -*-
import json

import frappe
from frappe import _
from frappe.utils import now_datetime

from edgepayv1.edgepay.services.provider_financial_adapters import get_financial_adapter
from edgepayv1.edgepay.services.security import redact_secrets
from edgepayv1.edgepay.services.external_references import register_reference
from edgepayv1.edgepay.services.payment_totals import sync_payment_totals
from edgepayv1.edgepay.services.payment_state import record_event


def submit_refund(refund_request_name):
	refund = frappe.get_doc("EdgePay Refund Request", refund_request_name)
	if refund.status != "Approved":
		frappe.throw(_("Refund Request must be Approved before provider submission"))
	latest = frappe.db.get_value("EdgePay Refund Processing Attempt", {"refund_request": refund.name}, "attempt_number", order_by="attempt_number desc") or 0
	attempt = frappe.new_doc("EdgePay Refund Processing Attempt")
	attempt.merchant = refund.merchant
	attempt.refund_request = refund.name
	attempt.provider_account = refund.provider_account
	attempt.attempt_number = int(latest) + 1
	attempt.started_on = now_datetime()
	attempt.request_json = json.dumps({"refund_request": refund.name, "amount": refund.amount, "currency": refund.currency})
	attempt.insert(ignore_permissions=True)
	adapter = get_financial_adapter(refund.provider_account)
	try:
		result = adapter.submit_refund(refund) or {}
		attempt.status = result.get("status") or "Submitted"
		attempt.provider_reference = result.get("provider_refund_reference")
		attempt.response_json = json.dumps(redact_secrets(result), indent=2)
		refund.status = "Processing" if attempt.status in {"Submitted", "Processing"} else attempt.status
		refund.provider_refund_reference = attempt.provider_reference
		if refund.provider_refund_reference:
			register_reference("Refund", refund.provider_refund_reference, refund.payment_request, payment_transaction=refund.payment_transaction)
		attempt.save(ignore_permissions=True)
		refund.save(ignore_permissions=True)
		request = frappe.get_doc("EdgePay Payment Request", refund.payment_request)
		record_event(request, transaction=frappe.get_doc("EdgePay Payment Transaction", refund.payment_transaction), event_type="Refund Submitted", event_source="refund", details={"refund_request": refund.name, "status": refund.status})
		return refund
	except Exception as exc:
		attempt.status = "Failed"
		attempt.error_message = str(exc)
		attempt.completed_on = now_datetime()
		attempt.save(ignore_permissions=True)
		refund.status = "Failed"
		refund.failure_reason = str(exc)
		refund.save(ignore_permissions=True)
		raise


def complete_refund(refund_request_name, provider_reference=None):
	refund = frappe.get_doc("EdgePay Refund Request", refund_request_name)
	if refund.status not in {"Submitted", "Processing", "Approved"}:
		frappe.throw(_("Refund Request is not awaiting completion"))
	refund.status = "Completed"
	refund.completed_on = now_datetime()
	if provider_reference:
		refund.provider_refund_reference = provider_reference
	refund.save(ignore_permissions=True)
	for name in frappe.get_all("EdgePay Refund Processing Attempt", filters={"refund_request": refund.name, "status": ["in", ["Created", "Submitted", "Processing"]]}, pluck="name"):
		attempt = frappe.get_doc("EdgePay Refund Processing Attempt", name)
		attempt.status = "Completed"
		attempt.completed_on = now_datetime()
		attempt.save(ignore_permissions=True)
	if refund.provider_refund_reference:
		register_reference("Refund", refund.provider_refund_reference, refund.payment_request, payment_transaction=refund.payment_transaction)
	sync_payment_totals(refund.payment_request)
	request = frappe.get_doc("EdgePay Payment Request", refund.payment_request)
	record_event(request, transaction=frappe.get_doc("EdgePay Payment Transaction", refund.payment_transaction), event_type="Refund Completed", event_source="refund", details={"refund_request": refund.name, "amount": refund.amount})
	return refund
