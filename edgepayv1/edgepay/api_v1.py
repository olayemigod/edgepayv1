# -*- coding: utf-8 -*-
import json

import frappe
from frappe import _

from edgepayv1.edgepay.services.api_auth import authenticate_api_request
from edgepayv1.edgepay.services.payment_requests import create_payment_request_record
from edgepayv1.edgepay.services.security import redact_secrets


def _request_body():
	request = getattr(frappe.local, "request", None)
	raw = request.get_data(cache=True) if request else b"{}"
	try:
		data = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw or "{}")
	except Exception:
		frappe.throw(_("Invalid JSON request body"))
	if not isinstance(data, dict):
		frappe.throw(_("Request body must be a JSON object"))
	return raw, data


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_payment_request_v1():
	raw, data = _request_body()
	client = authenticate_api_request("payments:create", raw_body=raw)
	result = create_payment_request_record(
		merchant=client.merchant,
		provider=data.get("provider"),
		provider_account=data.get("provider_account"),
		amount=data.get("amount"),
		currency=data.get("currency"),
		customer_name=data.get("customer_name"),
		customer_email=data.get("customer_email"),
		customer_phone=data.get("customer_phone"),
		payment_purpose=data.get("payment_purpose"),
		source_app=data.get("source_app"),
		source_doctype=data.get("source_doctype"),
		source_name=data.get("source_name"),
		external_tenant_reference=data.get("external_tenant_reference"),
		external_company_reference=data.get("external_company_reference"),
		external_branch_reference=data.get("external_branch_reference"),
		expires_on=data.get("expires_on"),
		metadata_json=data.get("metadata") or {},
		idempotency_key=frappe.get_request_header("Idempotency-Key") or data.get("idempotency_key"),
	)
	return redact_secrets({"api_version": "v1", **result})


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_payment_request_v1(payment_reference):
	client = authenticate_api_request("payments:read", method="GET", raw_body=b"")
	name = frappe.db.get_value(
		"EdgePay Payment Request",
		{"merchant": client.merchant, "request_reference": payment_reference},
		"name",
	) or (payment_reference if frappe.db.exists("EdgePay Payment Request", {"name": payment_reference, "merchant": client.merchant}) else None)
	if not name:
		frappe.throw(_("Payment Request not found"))
	from edgepayv1.edgepay.services.payment_timeline import get_payment_timeline
	return {"api_version": "v1", "data": redact_secrets(get_payment_timeline(name))}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def initialize_payment_request_v1(payment_reference):
	raw, data = _request_body()
	client = authenticate_api_request("payments:create", raw_body=raw)
	name = frappe.db.get_value("EdgePay Payment Request", {"merchant": client.merchant, "request_reference": payment_reference}, "name")
	if not name:
		frappe.throw(_("Payment Request not found"))
	from edgepayv1.edgepay.services.checkout import initialize_checkout
	return {"api_version": "v1", "data": redact_secrets(initialize_checkout(name, payment_method=data.get("payment_method")))}
