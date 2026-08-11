from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from edgepayv1.api.permission import has_app_permission
from edgepayv1.edgepay.services.merchant_context import get_user_merchant_context
from edgepayv1.edgepay.services.merchant_onboarding import get_onboarding_readiness


def _count(doctype, filters):
	return frappe.db.count(doctype, filters) if frappe.db.exists("DocType", doctype) else 0


@frappe.whitelist()
def get_home_context() -> dict:
	if not has_app_permission():
		frappe.throw(_("You are not permitted to access EdgePay."), frappe.PermissionError)

	context = get_user_merchant_context()
	merchant = context.get("merchant")
	if not merchant:
		return {"merchant_context": context, "registration": {"status": "Not Started", "message": _("No active Merchant is assigned to this user.")}, "summary": {}, "recent_requests": [], "operations": {}}

	merchant_doc = frappe.get_doc("EdgePay Merchant", merchant)
	registration = get_onboarding_readiness(merchant)
	statuses = ["Draft", "Initiated", "Partly Paid", "Paid", "Overpaid", "Failed", "Expired", "Refund Pending", "Partly Refunded", "Refunded", "Disputed", "Chargeback"]
	counts = {status: _count("EdgePay Payment Request", {"merchant": merchant, "status": status}) for status in statuses}

	requests = frappe.get_list(
		"EdgePay Payment Request",
		filters={"merchant": merchant},
		fields=["name", "request_reference", "status", "amount", "currency", "paid_amount", "outstanding_amount", "customer_name", "source_app", "modified"],
		order_by="modified desc",
		limit_page_length=10,
	)

	paid_value = sum(flt(row.get("paid_amount")) for row in frappe.get_all("EdgePay Payment Request", filters={"merchant": merchant}, fields=["paid_amount"]))
	return {
		"merchant_context": context,
		"merchant": {"name": merchant_doc.name, "legal_name": merchant_doc.legal_name, "trading_name": merchant_doc.trading_name, "status": merchant_doc.status, "verification_status": merchant_doc.verification_status, "live_payments_allowed": bool(merchant_doc.live_payments_allowed)},
		"registration": registration,
		"summary": {"counts": counts, "paid_value": paid_value, "currency": merchant_doc.default_currency or "NGN"},
		"recent_requests": requests,
		"operations": {
			"provider_accounts": _count("EdgePay Provider Account", {"merchant": merchant, "enabled": 1}),
			"api_clients": _count("EdgePay API Client", {"merchant": merchant, "enabled": 1}),
			"delivery_endpoints": _count("EdgePay Delivery Endpoint", {"merchant": merchant, "enabled": 1}),
			"refunds_open": _count("EdgePay Refund Request", {"merchant": merchant, "status": ["not in", ["Completed", "Cancelled", "Failed"]]}),
			"settlements_open": _count("EdgePay Settlement Batch", {"merchant": merchant, "status": ["not in", ["Settled", "Reversed"]]}),
			"dead_letters": _count("EdgePay Delivery", {"merchant": merchant, "status": "Dead Letter"}),
		},
	}
