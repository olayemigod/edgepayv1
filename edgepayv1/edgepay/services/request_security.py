# -*- coding: utf-8 -*-
"""Security guards for public EdgePay HTTP endpoints."""

import frappe
from frappe import _


DEFAULT_MAX_WEBHOOK_BYTES = 256 * 1024


def get_request_method():
	request = getattr(frappe.local, "request", None)
	return (getattr(request, "method", None) or "").upper()


def require_post_request():
	"""Reject browser GET requests against mutation-style public endpoints."""
	method = get_request_method()
	if method and method != "POST":
		_set_http_status(405)
		frappe.throw(_("This endpoint accepts POST requests only"))


def get_max_webhook_bytes():
	"""Resolve the webhook body limit from site configuration with a safe default."""
	configured = frappe.conf.get("edgepay_max_webhook_bytes")
	try:
		value = int(configured) if configured is not None else DEFAULT_MAX_WEBHOOK_BYTES
	except (TypeError, ValueError):
		value = DEFAULT_MAX_WEBHOOK_BYTES
	return max(1024, min(value, 2 * 1024 * 1024))


def validate_webhook_body(raw_body):
	"""Require a non-empty webhook body within the configured size limit."""
	if raw_body is None:
		raw_body = b""
	if isinstance(raw_body, str):
		body_size = len(raw_body.encode("utf-8"))
	else:
		body_size = len(raw_body)

	if body_size <= 0:
		_set_http_status(400)
		frappe.throw(_("Webhook request body is required"))

	max_bytes = get_max_webhook_bytes()
	if body_size > max_bytes:
		_set_http_status(413)
		frappe.throw(_("Webhook request body exceeds the allowed size"))
	return raw_body


def _set_http_status(status_code):
	if hasattr(frappe, "local") and hasattr(frappe.local, "response"):
		frappe.local.response["http_status_code"] = status_code
