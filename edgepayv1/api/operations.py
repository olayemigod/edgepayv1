from __future__ import annotations

import frappe
from frappe import _

from edgepayv1.api.permission import has_app_permission
from edgepayv1.edgepay.services.merchant_context import get_default_merchant_context


def _require_edgepay() -> str:
	if not has_app_permission():
		frappe.throw(_("You are not permitted to access EdgePay."), frappe.PermissionError)
	merchant = get_default_merchant_context().get("merchant")
	if not merchant:
		frappe.throw(_("No active EdgePay merchant context is assigned to this user."), frappe.PermissionError)
	return merchant


def _rows(doctype: str, merchant: str, fields: list[str], *, limit: int = 50, order_by: str = "modified desc") -> list[dict]:
	if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
		return []
	return frappe.get_list(
		doctype,
		filters={"merchant": merchant},
		fields=fields,
		order_by=order_by,
		limit_page_length=limit,
	)


@frappe.whitelist()
def get_payments_context() -> dict:
	merchant = _require_edgepay()
	requests = _rows(
		"EdgePay Payment Request",
		merchant,
		["name", "request_reference", "status", "amount", "paid_amount", "outstanding_amount", "currency", "customer_name", "source_app", "modified"],
	)
	attempts = _rows(
		"EdgePay Payment Attempt",
		merchant,
		["name", "payment_request", "attempt_number", "status", "payment_method", "provider_payment_reference", "modified"],
		limit=30,
	)
	events = _rows(
		"EdgePay Payment Event",
		merchant,
		["name", "payment_request", "payment_attempt", "event_type", "previous_status", "new_status", "event_source", "occurred_on"],
		limit=40,
		order_by="occurred_on desc",
	)
	return {"merchant": merchant, "requests": requests, "attempts": attempts, "events": events}


@frappe.whitelist()
def get_integrations_context() -> dict:
	merchant = _require_edgepay()
	providers = _rows(
		"EdgePay Provider Account",
		merchant,
		["name", "provider", "account_label", "environment", "enabled", "status", "modified"],
		limit=30,
	)
	clients = _rows(
		"EdgePay API Client",
		merchant,
		["name", "client_name", "client_id", "enabled", "modified"],
		limit=30,
	)
	endpoints = _rows(
		"EdgePay Delivery Endpoint",
		merchant,
		["name", "endpoint_name", "endpoint_url", "enabled", "modified"],
		limit=30,
	)
	deliveries = _rows(
		"EdgePay Delivery",
		merchant,
		["name", "event_type", "status", "attempt_count", "next_attempt_on", "modified"],
		limit=30,
	)
	return {
		"merchant": merchant,
		"provider_accounts": providers,
		"api_clients": clients,
		"delivery_endpoints": endpoints,
		"deliveries": deliveries,
	}


@frappe.whitelist()
def get_finance_context() -> dict:
	merchant = _require_edgepay()
	return {
		"merchant": merchant,
		"refunds": _rows("EdgePay Refund Request", merchant, ["name", "payment_request", "amount", "currency", "status", "modified"]),
		"settlements": _rows("EdgePay Settlement Batch", merchant, ["name", "provider_account", "status", "gross_amount", "net_amount", "currency", "modified"]),
		"disputes": _rows("EdgePay Dispute", merchant, ["name", "payment_request", "payment_transaction", "amount", "currency", "status", "modified"]),
		"chargebacks": _rows("EdgePay Chargeback", merchant, ["name", "payment_request", "payment_transaction", "amount", "currency", "status", "modified"]),
	}
