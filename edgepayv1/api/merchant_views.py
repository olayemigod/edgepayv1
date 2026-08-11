from __future__ import annotations

import frappe
from frappe import _

from edgepayv1.api.permission import has_app_permission
from edgepayv1.edgepay.services.merchant_context import get_current_merchant_context
from edgepayv1.edgepay.services.payment_timeline import get_payment_timeline


def _require_app_access():
	if not has_app_permission():
		frappe.throw(_("You are not permitted to access EdgePay."), frappe.PermissionError)


def _merchant():
	context = get_current_merchant_context()
	merchant = context.get("merchant") if isinstance(context, dict) else None
	if not merchant:
		frappe.throw(_("No active Merchant context is available for this user."), frappe.PermissionError)
	return merchant


@frappe.whitelist()
def get_payments_view(status=None, limit=50):
	_require_app_access()
	merchant = _merchant()
	filters = {"merchant": merchant}
	if status:
		filters["status"] = status
	rows = frappe.get_list(
		"EdgePay Payment Request",
		filters=filters,
		fields=["name", "request_reference", "customer_name", "amount", "paid_amount", "outstanding_amount", "refunded_amount", "currency", "status", "source_app", "source_doctype", "source_name", "modified"],
		order_by="modified desc",
		limit_page_length=min(int(limit or 50), 200),
	)
	return {"merchant": merchant, "rows": rows}


@frappe.whitelist()
def get_payment_detail(payment_request):
	_require_app_access()
	return get_payment_timeline(payment_request)


@frappe.whitelist()
def get_integrations_view():
	_require_app_access()
	merchant = _merchant()
	return {
		"merchant": merchant,
		"provider_accounts": frappe.get_list("EdgePay Provider Account", filters={"merchant": merchant}, fields=["name", "provider", "environment", "status", "enabled"], order_by="modified desc"),
		"api_clients": frappe.get_list("EdgePay API Client", filters={"merchant": merchant}, fields=["name", "client_name", "client_id", "environment", "enabled", "last_used_on"], order_by="modified desc"),
		"delivery_endpoints": frappe.get_list("EdgePay Delivery Endpoint", filters={"merchant": merchant}, fields=["name", "endpoint_name", "environment", "endpoint_url", "enabled", "event_types"], order_by="modified desc"),
		"dead_letters": frappe.db.count("EdgePay Delivery", {"merchant": merchant, "status": "Dead Letter"}),
	}


@frappe.whitelist()
def get_finance_view():
	_require_app_access()
	merchant = _merchant()
	return {
		"merchant": merchant,
		"settlements": frappe.get_list("EdgePay Settlement Batch", filters={"merchant": merchant}, fields=["name", "provider_account", "currency", "status", "gross_amount", "provider_fee", "edgepay_fee", "tax_amount", "net_amount", "expected_settlement_date", "actual_settlement_date"], order_by="modified desc", limit_page_length=50),
		"refunds": frappe.get_list("EdgePay Refund Request", filters={"merchant": merchant}, fields=["name", "payment_request", "payment_transaction", "amount", "currency", "status", "modified"], order_by="modified desc", limit_page_length=50),
		"disputes": frappe.get_list("EdgePay Dispute", filters={"merchant": merchant}, fields=["name", "payment_request", "payment_transaction", "amount", "currency", "status", "response_deadline"], order_by="modified desc", limit_page_length=50),
		"chargebacks": frappe.get_list("EdgePay Chargeback", filters={"merchant": merchant}, fields=["name", "payment_request", "payment_transaction", "amount", "currency", "status", "evidence_deadline"], order_by="modified desc", limit_page_length=50),
	}
