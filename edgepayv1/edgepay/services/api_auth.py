# -*- coding: utf-8 -*-
import hashlib
import hmac
from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from edgepayv1.edgepay.services.api_usage import enforce_rate_limit, log_api_usage

MAX_CLOCK_SKEW_SECONDS = 300


def _normalise_scopes(value):
	return {item.strip() for item in (value or "").split(",") if item.strip()}


def _client_ip():
	request = getattr(frappe.local, "request", None)
	return request.remote_addr if request else None


def authenticate_api_request(required_scope=None, method=None, path=None, raw_body=b"", headers=None):
	headers = headers or getattr(getattr(frappe.local, "request", None), "headers", {}) or {}
	client_id = headers.get("X-EdgePay-Client-Id")
	timestamp = headers.get("X-EdgePay-Timestamp")
	nonce = headers.get("X-EdgePay-Nonce")
	signature = headers.get("X-EdgePay-Signature")
	if not all([client_id, timestamp, nonce, signature]):
		frappe.throw(_("Missing EdgePay API authentication headers"), frappe.AuthenticationError)

	client_name = frappe.db.get_value("EdgePay API Client", {"client_id": client_id, "enabled": 1}, "name")
	if not client_name:
		frappe.throw(_("Invalid API client"), frappe.AuthenticationError)
	client = frappe.get_doc("EdgePay API Client", client_name)
	if required_scope and required_scope not in _normalise_scopes(client.scopes):
		frappe.throw(_("API client does not have the required scope"), frappe.PermissionError)

	allowed_ips = {ip.strip() for ip in (client.allowed_ips or "").split(",") if ip.strip()}
	if allowed_ips and _client_ip() not in allowed_ips:
		frappe.throw(_("API client IP address is not allowed"), frappe.PermissionError)

	request_time = get_datetime(timestamp)
	if abs((now_datetime() - request_time).total_seconds()) > MAX_CLOCK_SKEW_SECONDS:
		frappe.throw(_("API request timestamp is outside the allowed window"), frappe.AuthenticationError)
	if frappe.db.exists("EdgePay API Request Nonce", {"nonce": nonce}):
		frappe.throw(_("API request nonce has already been used"), frappe.AuthenticationError)

	method = (method or getattr(getattr(frappe.local, "request", None), "method", "POST")).upper()
	path = path or getattr(getattr(frappe.local, "request", None), "path", "")
	enforce_rate_limit(client, request_path=path)
	body_bytes = raw_body if isinstance(raw_body, bytes) else str(raw_body or "").encode()
	body_hash = hashlib.sha256(body_bytes).hexdigest()
	canonical = "\n".join([method, path, str(timestamp), nonce, body_hash])
	secret = client.get_password("client_secret")
	expected = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
	if not hmac.compare_digest(expected, signature):
		frappe.throw(_("Invalid API request signature"), frappe.AuthenticationError)

	nonce_doc = frappe.new_doc("EdgePay API Request Nonce")
	nonce_doc.api_client = client.name
	nonce_doc.merchant = client.merchant
	nonce_doc.nonce = nonce
	nonce_doc.request_timestamp = request_time
	nonce_doc.expires_on = now_datetime() + timedelta(hours=24)
	nonce_doc.request_method = method
	nonce_doc.request_path = path
	nonce_doc.body_hash = body_hash
	nonce_doc.insert(ignore_permissions=True)
	client.db_set("last_used_on", now_datetime(), update_modified=False)
	log_api_usage(client, scope=required_scope, request_method=method, request_path=path, response_status=200)
	return client
