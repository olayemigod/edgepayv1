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


def _payment_name(merchant, payment_reference):
	name = frappe.db.get_value("EdgePay Payment Request", {"merchant": merchant, "request_reference": payment_reference}, "name")
	if not name and frappe.db.exists("EdgePay Payment Request", {"name": payment_reference, "merchant": merchant}):
		name = payment_reference
	if not name:
		frappe.throw(_("Payment Request not found"))
	return name


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
	name = _payment_name(client.merchant, payment_reference)
	from edgepayv1.edgepay.services.payment_timeline import get_payment_timeline
	return {"api_version": "v1", "data": redact_secrets(get_payment_timeline(name))}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def initialize_payment_request_v1(payment_reference):
	raw, data = _request_body()
	client = authenticate_api_request("payments:create", raw_body=raw)
	name = _payment_name(client.merchant, payment_reference)
	from edgepayv1.edgepay.services.checkout import initialize_checkout
	return {"api_version": "v1", "data": redact_secrets(initialize_checkout(name, payment_method=data.get("payment_method")))}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def verify_payment_request_v1(payment_reference):
	raw, _data = _request_body()
	client = authenticate_api_request("payments:verify", raw_body=raw)
	name = _payment_name(client.merchant, payment_reference)
	from edgepayv1.edgepay.services.verification import verify_transaction
	return {"api_version": "v1", "data": redact_secrets(verify_transaction(name))}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_transaction_v1(transaction_reference):
	client = authenticate_api_request("transactions:read", method="GET", raw_body=b"")
	name = frappe.db.get_value("EdgePay Payment Transaction", {"merchant": client.merchant, "transaction_reference": transaction_reference}, "name")
	if not name:
		name = frappe.db.get_value("EdgePay Payment Transaction", {"merchant": client.merchant, "provider_reference": transaction_reference}, "name")
	if not name:
		frappe.throw(_("Transaction not found"))
	txn = frappe.get_doc("EdgePay Payment Transaction", name)
	return {"api_version": "v1", "data": redact_secrets({"transaction": txn.name, "payment_request": txn.payment_request, "payment_attempt": txn.payment_attempt, "status": txn.status, "amount": txn.amount, "currency": txn.currency, "provider_reference": txn.provider_reference, "transaction_reference": txn.transaction_reference, "paid_on": txn.paid_on, "settlement_status": txn.settlement_status})}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_refund_v1():
	raw, data = _request_body()
	client = authenticate_api_request("refunds:create", raw_body=raw)
	txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"merchant": client.merchant, "transaction_reference": data.get("transaction_reference")}, "name")
	if not txn_name:
		frappe.throw(_("Transaction not found"))
	from edgepayv1.edgepay.services.refunds import create_refund_request
	refund = create_refund_request(txn_name, data.get("amount"), data.get("reason"))
	return {"api_version": "v1", "data": {"refund_reference": refund.name, "status": refund.status, "amount": refund.amount, "currency": refund.currency}}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_refund_v1(refund_reference):
	client = authenticate_api_request("refunds:create", method="GET", raw_body=b"")
	name = frappe.db.get_value("EdgePay Refund Request", {"merchant": client.merchant, "name": refund_reference}, "name")
	if not name:
		frappe.throw(_("Refund Request not found"))
	refund = frappe.get_doc("EdgePay Refund Request", name)
	return {"api_version": "v1", "data": redact_secrets({"refund_reference": refund.name, "payment_request": refund.payment_request, "payment_transaction": refund.payment_transaction, "status": refund.status, "amount": refund.amount, "currency": refund.currency, "provider_refund_reference": refund.provider_refund_reference, "completed_on": refund.completed_on})}
