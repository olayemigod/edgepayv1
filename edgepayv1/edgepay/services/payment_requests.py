# -*- coding: utf-8 -*-
"""Internal Payment Request domain services."""

import json

import frappe
from frappe import _
from frappe.utils import flt

from edgepayv1.edgepay.services.authorization import require_merchant_access
from edgepayv1.edgepay.services.security import redact_secrets

LEGACY_MERCHANT = "ProcessEdge Legacy Merchant"


def resolve_provider_account(provider, merchant=None, provider_account=None):
	if provider_account:
		account = frappe.get_doc("EdgePay Provider Account", provider_account)
		if merchant and account.merchant != merchant:
			frappe.throw(_("Provider Account does not belong to the selected Merchant"))
		if provider and account.provider != provider:
			frappe.throw(_("Provider Account does not match the selected Provider"))
		return account

	filters = {"provider": provider, "enabled": 1}
	if merchant:
		filters["merchant"] = merchant
	name = frappe.db.get_value("EdgePay Provider Account", filters, "name", order_by="modified desc")
	if not name:
		frappe.throw(_("No enabled Provider Account is available for the selected Merchant and Provider"))
	return frappe.get_doc("EdgePay Provider Account", name)


def create_payment_request_record(
	provider,
	amount,
	currency,
	customer_name,
	customer_email,
	merchant=None,
	provider_account=None,
	customer_phone=None,
	payment_purpose=None,
	source_app=None,
	source_doctype=None,
	source_name=None,
	external_tenant_reference=None,
	external_company_reference=None,
	external_branch_reference=None,
	expires_on=None,
	metadata_json=None,
	idempotency_key=None,
):
	from edgepayv1.edgepay.services.checkout import check_and_mark_expired

	if not amount or flt(amount) <= 0:
		frappe.throw(_("Amount must be greater than zero"))
	if not currency or not provider:
		frappe.throw(_("Currency and Provider are required"))
	if not customer_name or not customer_email:
		frappe.throw(_("Customer name and email are required"))

	account = resolve_provider_account(provider, merchant=merchant, provider_account=provider_account)
	merchant = account.merchant
	require_merchant_access(merchant)

	provider_doc = frappe.get_doc("EdgePay Provider", provider)
	if not provider_doc.enabled or not account.enabled or account.status != "Active":
		frappe.throw(_("The selected provider account is not active"))

	if idempotency_key:
		existing_name = frappe.db.get_value(
			"EdgePay Payment Request",
			{
				"merchant": merchant,
				"idempotency_key": idempotency_key,
				"status": ["not in", ["Paid", "Failed", "Expired", "Cancelled"]],
			},
			"name",
		)
		if existing_name:
			request = frappe.get_doc("EdgePay Payment Request", existing_name)
			if not check_and_mark_expired(request):
				return _success_response(request, "Existing active Payment Request retrieved successfully (idempotent)")

	request = frappe.new_doc("EdgePay Payment Request")
	request.merchant = merchant
	request.provider_account = account.name
	request.provider = provider
	request.amount = flt(amount)
	request.currency = currency
	request.customer_name = customer_name
	request.customer_email = customer_email
	request.customer_phone = customer_phone
	request.payment_purpose = payment_purpose
	request.source_app = source_app
	request.source_doctype = source_doctype
	request.source_name = source_name
	request.external_tenant_reference = external_tenant_reference
	request.external_company_reference = external_company_reference
	request.external_branch_reference = external_branch_reference
	request.expires_on = expires_on
	request.idempotency_key = idempotency_key

	if metadata_json:
		try:
			parsed_metadata = json.loads(metadata_json) if isinstance(metadata_json, str) else metadata_json
			if not isinstance(parsed_metadata, dict):
				frappe.throw(_("metadata_json must contain a JSON object"))
			request.metadata_json = json.dumps(redact_secrets(parsed_metadata))
		except (TypeError, ValueError):
			frappe.throw(_("Invalid metadata_json payload"))

	request.request_reference = f"REQ-{frappe.generate_hash(length=12)}"
	request.insert()
	return _success_response(request, "Payment request created successfully")


def _success_response(request, message):
	return {
		"ok": True,
		"status": "success",
		"message": message,
		"data": redact_secrets({
			"payment_request": request.name,
			"request_reference": request.request_reference,
			"merchant": request.merchant,
			"provider_account": request.provider_account,
			"status": request.status,
			"amount": request.amount,
			"currency": request.currency,
			"provider": request.provider,
			"expires_on": request.expires_on,
		}),
	}
