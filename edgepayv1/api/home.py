from __future__ import annotations

import frappe
from frappe import _

from edgepayv1.api.permission import has_app_permission

SAFE_REQUEST_FIELDS = [
	"name",
	"request_reference",
	"status",
	"amount",
	"currency",
	"customer_name",
	"source_app",
	"source_doctype",
	"source_name",
	"modified",
]
REQUEST_STATUSES = ("Draft", "Initiated", "Paid", "Failed", "Expired", "Cancelled")


def _can_read(doctype: str) -> bool:
	return bool(
		frappe.db.exists("DocType", doctype)
		and frappe.has_permission(doctype, "read")
	)


def _settings_summary() -> dict:
	if not _can_read("EdgePay Settings"):
		return {"visible": False}
	settings = frappe.get_single("EdgePay Settings")
	return {
		"visible": True,
		"enabled": bool(settings.enable_edgepay),
		"default_currency": settings.default_currency or "",
		"default_provider": settings.default_provider or "",
		"webhook_configured": bool(settings.webhook_base_url),
		"signature_validation": bool(settings.require_signature_validation),
		"sandbox_mode": bool(settings.sandbox_mode),
	}


def _registration_readiness(settings: dict) -> dict:
	if not settings.get("visible"):
		return {
			"status": "Restricted",
			"message": _("You do not have permission to view EdgePay setup readiness."),
			"checks": [],
		}
	checks = [
		{
			"key": "enabled",
			"label": _("EdgePay enabled"),
			"complete": bool(settings.get("enabled")),
		},
		{
			"key": "currency",
			"label": _("Default currency selected"),
			"complete": bool(settings.get("default_currency")),
		},
		{
			"key": "provider",
			"label": _("Default provider selected"),
			"complete": bool(settings.get("default_provider")),
		},
		{
			"key": "webhook",
			"label": _("Webhook address configured"),
			"complete": bool(settings.get("webhook_configured")),
		},
		{
			"key": "signature",
			"label": _("Webhook signature validation enabled"),
			"complete": bool(settings.get("signature_validation")),
		},
	]
	completed = sum(1 for check in checks if check["complete"])
	if completed == len(checks):
		status = "Ready"
		message = _("The tenant-level EdgePay setup checks are complete.")
	elif completed:
		status = "In Progress"
		message = _("Complete the remaining tenant-level EdgePay setup checks.")
	else:
		status = "Not Started"
		message = _("Start EdgePay setup before accepting payments.")
	return {
		"status": status,
		"message": message,
		"completed": completed,
		"total": len(checks),
		"checks": checks,
	}


@frappe.whitelist()
def get_home_context() -> dict:
	if not has_app_permission():
		frappe.throw(_("You are not permitted to access EdgePay."), frappe.PermissionError)

	can_read_requests = _can_read("EdgePay Payment Request")
	request_counts = {}
	recent_requests = []
	if can_read_requests:
		request_counts = {
			status: frappe.db.count("EdgePay Payment Request", {"status": status})
			for status in REQUEST_STATUSES
		}
		recent_requests = frappe.get_list(
			"EdgePay Payment Request",
			fields=SAFE_REQUEST_FIELDS,
			order_by="modified desc",
			limit_page_length=8,
		)

	settings = _settings_summary()
	return {
		"request_counts": request_counts,
		"recent_requests": recent_requests,
		"settings": settings,
		"registration": _registration_readiness(settings),
		"permissions": {
			"can_read_requests": can_read_requests,
			"can_read_settings": bool(settings.get("visible")),
			"can_manage_providers": _can_read("EdgePay Provider"),
		},
	}
