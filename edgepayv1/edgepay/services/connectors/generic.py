# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import flt
from edgepayv1.edgepay.services.connectors.base import BaseSourceConnector

class GenericSourceConnector(BaseSourceConnector):
	def validate_source_context(self, source_context):
		if not isinstance(source_context, dict):
			frappe.throw(_("Source context must be a dictionary"))

		required_fields = ["source_app", "source_doctype", "source_name", "amount", "currency"]
		for field in required_fields:
			if not source_context.get(field):
				frappe.throw(_("Missing required source context field: {0}").format(field))

		amount = flt(source_context.get("amount"))
		if amount <= 0:
			frappe.throw(_("Amount must be greater than zero"))

	def build_payment_request_payload(self, source_context):
		self.validate_source_context(source_context)
		
		# Return a dictionary of fields expected by create_payment_request
		# Safe fields: provider, amount, currency, customer_name, customer_email,
		# customer_phone, payment_purpose, source_app, source_doctype, source_name,
		# expires_on, metadata_json, idempotency_key
		return {
			"provider": source_context.get("provider"),
			"amount": flt(source_context.get("amount")),
			"currency": source_context.get("currency"),
			"customer_name": source_context.get("customer_name") or "Unknown",
			"customer_email": source_context.get("customer_email") or "unknown@customer.com",
			"customer_phone": source_context.get("customer_phone"),
			"payment_purpose": source_context.get("payment_purpose"),
			"source_app": source_context.get("source_app"),
			"source_doctype": source_context.get("source_doctype"),
			"source_name": source_context.get("source_name"),
			"expires_on": source_context.get("expires_on"),
			"metadata_json": source_context.get("metadata_json"),
			"idempotency_key": source_context.get("idempotency_key")
		}

	def handle_payment_status_update(self, payment_request, transaction=None):
		# Default generic connector is read-only / no-op.
		# Log only a safe operational message.
		from edgepayv1.edgepay.services.logging import log
		log(f"Status update received for {payment_request.name} (Source: {payment_request.source_app}/{payment_request.source_doctype}/{payment_request.source_name}). No-op handoff executed.", level="info")

	def get_safe_source_summary(self, source_context):
		# Returns a safe/sanitized summary (no secrets or document internals)
		from edgepayv1.edgepay.services.security import redact_secrets
		summary = {
			"source_app": source_context.get("source_app"),
			"source_doctype": source_context.get("source_doctype"),
			"source_name": source_context.get("source_name"),
			"amount": flt(source_context.get("amount")),
			"currency": source_context.get("currency")
		}
		return redact_secrets(summary)
