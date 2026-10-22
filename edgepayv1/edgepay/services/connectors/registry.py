# -*- coding: utf-8 -*-
import json

import frappe
from frappe import _

# Registry mapping from app name to connector class or instance
_CONNECTORS = {}


def register_connector(app_name, connector_instance):
	"""Register a custom source connector for a product app."""
	_CONNECTORS[app_name] = connector_instance


def get_connector(app_name):
	"""Return the registered connector or the generic connector."""
	if app_name in _CONNECTORS:
		return _CONNECTORS[app_name]

	from edgepayv1.edgepay.services.connectors.generic import GenericSourceConnector
	return GenericSourceConnector()


def create_payment_request_from_source(source_context):
	"""Create a Payment Request from a validated generic source context."""
	if isinstance(source_context, str):
		source_context = json.loads(source_context)

	source_app = source_context.get("source_app")
	if not source_app:
		frappe.throw(_("Missing required source context field: source_app"))

	connector = get_connector(source_app)
	connector.validate_source_context(source_context)
	payload = connector.build_payment_request_payload(source_context)

	# Call the non-whitelisted domain service. Authentication and source-document
	# authorization are enforced by the public wrapper before this function runs.
	from edgepayv1.edgepay.services.payment_requests import create_payment_request_record

	res = create_payment_request_record(
		provider=payload.get("provider"),
		amount=payload.get("amount"),
		currency=payload.get("currency"),
		customer_name=payload.get("customer_name"),
		customer_email=payload.get("customer_email"),
		customer_phone=payload.get("customer_phone"),
		payment_purpose=payload.get("payment_purpose"),
		source_app=payload.get("source_app"),
		source_doctype=payload.get("source_doctype"),
		source_name=payload.get("source_name"),
		expires_on=payload.get("expires_on"),
		metadata_json=payload.get("metadata_json"),
		idempotency_key=payload.get("idempotency_key"),
	)

	from edgepayv1.edgepay.services.security import redact_secrets
	return redact_secrets(res)


def notify_source_payment_status(payment_request_name, transaction_name=None, event_source="verification"):
	"""Dispatch a normalized payment status update to the source connector."""
	try:
		pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
		txn = frappe.get_doc("EdgePay Payment Transaction", transaction_name) if transaction_name else None

		if not pr.source_app:
			return

		connector = get_connector(pr.source_app)
		handoff_payload = {
			"source_app": pr.source_app,
			"source_doctype": pr.source_doctype,
			"source_name": pr.source_name,
			"payment_request": pr.name,
			"request_status": pr.status,
			"transaction_status": txn.status if txn else None,
			"amount": pr.amount,
			"currency": pr.currency,
			"provider_reference": pr.provider_reference,
			"paid_on": txn.paid_on if txn else None,
			"event_source": event_source,
		}

		from edgepayv1.edgepay.services.security import redact_secrets
		connector.handle_payment_status_update(pr, txn, redact_secrets(handoff_payload))

		from edgepayv1.edgepay.services.handoff import emit_status_handoff
		emit_status_handoff(pr.name, txn.name if txn else None, event_source=event_source)
	except Exception as exc:
		from edgepayv1.edgepay.services.logging import log
		log(
			f"Failed to notify source payment status for {payment_request_name}: {str(exc)}",
			level="error",
		)
