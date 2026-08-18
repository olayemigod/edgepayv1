from __future__ import annotations

import frappe
from frappe import _

from edgepayv1.api.permission import has_app_permission
from edgepayv1.edgepay.services.merchant_context import get_default_merchant_context

REQUEST_STATUSES = (
	"Draft",
	"Initiated",
	"Partly Paid",
	"Paid",
	"Overpaid",
	"Failed",
	"Expired",
	"Cancelled",
	"Refund Pending",
	"Partly Refunded",
	"Refunded",
	"Disputed",
	"Chargeback",
)
ATTEMPT_STATUSES = ("Created", "Initiated", "Pending", "Successful", "Failed", "Expired", "Cancelled")
SAFE_REQUEST_FIELDS = [
	"name",
	"request_reference",
	"status",
	"amount",
	"paid_amount",
	"outstanding_amount",
	"currency",
	"customer_name",
	"source_app",
	"source_doctype",
	"source_name",
	"modified",
]


def _can_read(doctype: str) -> bool:
	return bool(frappe.db.exists("DocType", doctype) and frappe.has_permission(doctype, "read"))


def _count(doctype: str, filters: dict) -> int | None:
	if not _can_read(doctype):
		return None
	return int(frappe.db.count(doctype, filters=filters) or 0)


def _merchant_summary(merchant: str | None) -> dict:
	if not merchant or not _can_read("EdgePay Merchant"):
		return {"visible": False, "name": merchant or ""}
	row = frappe.db.get_value(
		"EdgePay Merchant",
		merchant,
		[
			"name",
			"merchant_name",
			"public_id",
			"status",
			"onboarding_status",
			"verification_status",
			"live_payments_allowed",
			"default_currency",
		],
		as_dict=True,
	)
	if not row:
		return {"visible": False, "name": merchant}
	return {
		"visible": True,
		"name": row.name,
		"merchant_name": row.merchant_name or row.name,
		"public_id": row.public_id or "",
		"status": row.status or "",
		"onboarding_status": row.onboarding_status or "",
		"verification_status": row.verification_status or "",
		"live_payments_allowed": bool(row.live_payments_allowed),
		"default_currency": row.default_currency or "",
	}


def _readiness(merchant: dict, operational: dict) -> dict:
	if not merchant.get("visible"):
		return {
			"status": "No Merchant Context",
			"message": _("No active EdgePay merchant context is assigned to this user."),
			"checks": [],
		}

	checks = [
		{
			"key": "merchant_active",
			"label": _("Merchant account active"),
			"visible": True,
			"complete": merchant.get("status") == "Active",
		},
		{
			"key": "onboarding",
			"label": _("Merchant onboarding completed"),
			"visible": True,
			"complete": merchant.get("onboarding_status") == "Completed",
		},
		{
			"key": "verification",
			"label": _("Merchant verification approved"),
			"visible": True,
			"complete": merchant.get("verification_status") == "Verified",
		},
		{
			"key": "provider_account",
			"label": _("Active provider account available"),
			"visible": operational.get("active_provider_accounts") is not None,
			"complete": bool(operational.get("active_provider_accounts")),
		},
		{
			"key": "api_client",
			"label": _("Enabled API client available"),
			"visible": operational.get("enabled_api_clients") is not None,
			"complete": bool(operational.get("enabled_api_clients")),
		},
		{
			"key": "delivery_endpoint",
			"label": _("Enabled signed delivery endpoint available"),
			"visible": operational.get("enabled_delivery_endpoints") is not None,
			"complete": bool(operational.get("enabled_delivery_endpoints")),
		},
		{
			"key": "live_approval",
			"label": _("Live payments approved"),
			"visible": True,
			"complete": bool(merchant.get("live_payments_allowed")),
		},
	]
	visible_checks = [check for check in checks if check["visible"]]
	completed = sum(1 for check in visible_checks if check["complete"])
	hidden = len(checks) - len(visible_checks)
	if visible_checks and completed == len(visible_checks) and not hidden:
		status = "Ready"
		message = _("The current merchant is operationally ready for its approved payment mode.")
	elif hidden:
		status = "Limited View"
		message = _("Some readiness controls are restricted for your current role.")
	elif completed:
		status = "In Progress"
		message = _("Complete the remaining merchant activation and integration controls.")
	else:
		status = "Action Required"
		message = _("Merchant onboarding and payment integration controls require attention.")
	return {
		"status": status,
		"message": message,
		"completed": completed,
		"total": len(visible_checks),
		"checks": checks,
	}


@frappe.whitelist()
def get_home_context() -> dict:
	if not has_app_permission():
		frappe.throw(_("You are not permitted to access EdgePay."), frappe.PermissionError)

	context = get_default_merchant_context()
	merchant_name = context.get("merchant")
	merchant = _merchant_summary(merchant_name)

	request_counts = {status: 0 for status in REQUEST_STATUSES}
	attempt_counts = {status: 0 for status in ATTEMPT_STATUSES}
	recent_requests = []
	operational = {
		"active_provider_accounts": None,
		"enabled_api_clients": None,
		"enabled_delivery_endpoints": None,
	}

	if merchant_name:
		merchant_filter = {"merchant": merchant_name}
		if _can_read("EdgePay Payment Request"):
			request_counts = {
				status: int(
					frappe.db.count("EdgePay Payment Request", {**merchant_filter, "status": status}) or 0
				)
				for status in REQUEST_STATUSES
			}
			recent_requests = frappe.get_list(
				"EdgePay Payment Request",
				filters=merchant_filter,
				fields=SAFE_REQUEST_FIELDS,
				order_by="modified desc",
				limit_page_length=8,
			)
		if _can_read("EdgePay Payment Attempt"):
			attempt_counts = {
				status: int(
					frappe.db.count("EdgePay Payment Attempt", {**merchant_filter, "status": status}) or 0
				)
				for status in ATTEMPT_STATUSES
			}
		operational = {
			"active_provider_accounts": _count(
				"EdgePay Provider Account",
				{**merchant_filter, "status": "Active", "enabled": 1},
			),
			"enabled_api_clients": _count("EdgePay API Client", {**merchant_filter, "enabled": 1}),
			"enabled_delivery_endpoints": _count(
				"EdgePay Delivery Endpoint",
				{**merchant_filter, "enabled": 1},
			),
		}

	return {
		"merchant_context": {
			"merchant": merchant_name or "",
			"merchant_account": context.get("merchant_account") or "",
			"merchant_branch": context.get("merchant_branch") or "",
			"can_bootstrap": bool(context.get("can_bootstrap")),
		},
		"merchant": merchant,
		"request_counts": request_counts,
		"attempt_counts": attempt_counts,
		"recent_requests": recent_requests,
		"operational": operational,
		"readiness": _readiness(merchant, operational),
		"permissions": {
			"can_read_requests": _can_read("EdgePay Payment Request"),
			"can_read_attempts": _can_read("EdgePay Payment Attempt"),
			"can_read_provider_accounts": _can_read("EdgePay Provider Account"),
			"can_read_api_clients": _can_read("EdgePay API Client"),
			"can_read_delivery_endpoints": _can_read("EdgePay Delivery Endpoint"),
		},
	}
