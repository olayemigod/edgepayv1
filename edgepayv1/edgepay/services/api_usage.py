# -*- coding: utf-8 -*-
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import now_datetime


def enforce_rate_limit(client, request_path=None):
	limit = int(getattr(client, "rate_limit_per_minute", None) or 60)
	count = frappe.db.count("EdgePay API Usage Log", {"api_client": client.name, "occurred_on": [">=", now_datetime() - timedelta(minutes=1)]})
	if count >= limit:
		frappe.throw(_("API rate limit exceeded"), frappe.RateLimitExceededError)


def log_api_usage(client, scope=None, request_method=None, request_path=None, response_status=200, duration_ms=None):
	doc = frappe.new_doc("EdgePay API Usage Log")
	doc.merchant = client.merchant
	doc.api_client = client.name
	doc.request_method = request_method
	doc.request_path = request_path
	doc.scope = scope
	doc.response_status = response_status
	doc.duration_ms = duration_ms
	request = getattr(frappe.local, "request", None)
	doc.client_ip = request.remote_addr if request else None
	doc.occurred_on = now_datetime()
	doc.insert(ignore_permissions=True)
	return doc.name
