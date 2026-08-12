from __future__ import annotations

import frappe
from frappe import _

from edgepayv1.api.permission import has_app_permission
from edgepayv1.edgepay.services.merchant_context import get_default_merchant_context


def _edgepay_context() -> dict:
	if not has_app_permission():
		frappe.throw(_("You are not permitted to access EdgePay."), frappe.PermissionError)
	context = get_default_merchant_context()
	return {
		"merchant": context.get("merchant"),
		"merchant_account": context.get("merchant_account"),
		"merchant_branch": context.get("merchant_branch"),
		"has_context": bool(context.get("merchant")),
		"can_bootstrap": bool(context.get("can_bootstrap")),
	}


def _empty_context(context: dict, **collections) -> dict:
	return {
		"merchant": None,
		"context_state": {
			"has_context": False,
			"can_bootstrap": bool(context.get("can_bootstrap")),
			"message": _("No active EdgePay merchant context is assigned to this user."),
		},
		**collections,
	}


def _rows(
	doctype: str,
	merchant: str,
	fields: list[str],
	*,
	limit: int = 50,
	order_by: str = "modified desc",
) -> list[dict]:
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
	context = _edgepay_context()
	merchant = context.get("merchant")
	if not merchant:
		return _empty_context(context, requests=[], attempts=[], events=[])
	requests = _rows(
		"EdgePay Payment Request",
		merchant,
		[
			"name",
			"request_reference",
			"status",
			"amount",
			"paid_amount",
			"outstanding_amount",
			"currency",
			"customer_name",
			"source_app",
			"modified",
		],
	)
	attempts = _rows(
		"EdgePay Payment Attempt",
		merchant,
		[
			"name",
			"payment_request",
			"attempt_number",
			"status",
			"payment_method",
			"provider_payment_reference",
			"modified",
		],
		limit=30,
	)
	events = _rows(
		"EdgePay Payment Event",
		merchant,
		[
			"name",
			"payment_request",
			"payment_attempt",
			"event_type",
			"previous_status",
			"new_status",
			"event_source",
			"occurred_on",
		],
		limit=40,
		order_by="occurred_on desc",
	)
	return {
		"merchant": merchant,
		"context_state": {"has_context": True, "can_bootstrap": bool(context.get("can_bootstrap"))},
		"requests": requests,
		"attempts": attempts,
		"events": events,
	}


@frappe.whitelist()
def get_integrations_context() -> dict:
	context = _edgepay_context()
	merchant = context.get("merchant")
	if not merchant:
		return _empty_context(
			context,
			provider_accounts=[],
			api_clients=[],
			delivery_endpoints=[],
			deliveries=[],
		)
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
		"context_state": {"has_context": True, "can_bootstrap": bool(context.get("can_bootstrap"))},
		"provider_accounts": providers,
		"api_clients": clients,
		"delivery_endpoints": endpoints,
		"deliveries": deliveries,
	}


@frappe.whitelist()
def get_finance_context() -> dict:
	context = _edgepay_context()
	merchant = context.get("merchant")
	if not merchant:
		return _empty_context(context, refunds=[], settlements=[], disputes=[], chargebacks=[])
	return {
		"merchant": merchant,
		"context_state": {"has_context": True, "can_bootstrap": bool(context.get("can_bootstrap"))},
		"refunds": _rows(
			"EdgePay Refund Request",
			merchant,
			["name", "payment_request", "amount", "currency", "status", "modified"],
		),
		"settlements": _rows(
			"EdgePay Settlement Batch",
			merchant,
			["name", "provider_account", "status", "gross_amount", "net_amount", "currency", "modified"],
		),
		"disputes": _rows(
			"EdgePay Dispute",
			merchant,
			["name", "payment_request", "payment_transaction", "amount", "currency", "status", "modified"],
		),
		"chargebacks": _rows(
			"EdgePay Chargeback",
			merchant,
			["name", "payment_request", "payment_transaction", "amount", "currency", "status", "modified"],
		),
	}
