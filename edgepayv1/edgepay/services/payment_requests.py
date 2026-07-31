# -*- coding: utf-8 -*-
"""Internal Payment Request domain services.

These functions are deliberately not whitelisted. Public APIs must authenticate
and authorize the caller before invoking them.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt

from edgepayv1.edgepay.services.security import redact_secrets


def create_payment_request_record(
	provider,
	amount,
	currency,
	customer_name,
	customer_email,
	customer_phone=None,
	payment_purpose=None,
	source_app=None,
	source_doctype=None,
	source_name=None,
	expires_on=None,
	metadata_json=None,
	idempotency_key=None,
):
	"""Create or return an idempotent active Payment Request."""
	from edgepayv1.edgepay.services.checkout import check_and_mark_expired

	if not amount or flt(amount) <= 0:
		frappe.throw(_("Amount must be greater than zero"))
	if not currency:
		frappe.throw(_("Currency is required"))
	if not provider:
		frappe.throw(_("Provider is required"))
	if not customer_name:
		frappe.throw(_("Customer name is required"))
	if not customer_email:
		frappe.throw(_("Customer email is required"))

	if not frappe.db.exists("EdgePay Provider", provider):
		frappe.throw(_("Provider {0} not found").format(provider))

	provider_doc = frappe.get_doc("EdgePay Provider", provider)
	if not provider_doc.enabled:
		frappe.throw(_("Provider {0} is disabled").format(provider))

	if idempotency_key:
		existing_name = frappe.db.get_value(
			"EdgePay Payment Request",
			{
				"idempotency_key": idempotency_key,
				"status": ["not in", ["Paid", "Failed", "Expired", "Cancelled"]],
			},
			"name",
		)
		if existing_name:
			request = frappe.get_doc("EdgePay Payment Request", existing_name)
			if not check_and_mark_expired(request):
				return _success_response(
					request,
					"Existing active Payment Request retrieved successfully (idempotent)",
				)

	request = frappe.new_doc("EdgePay Payment Request")
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
		"data": redact_secrets(
			{
				"payment_request": request.name,
				"request_reference": request.request_reference,
				"status": request.status,
				"amount": request.amount,
				"currency": request.currency,
				"provider": request.provider,
				"expires_on": request.expires_on,
			}
		),
	}
