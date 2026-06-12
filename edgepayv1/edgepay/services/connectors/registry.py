# -*- coding: utf-8 -*-
import frappe
from frappe import _
import json

# Registry mapping from app name to connector class or instance
_CONNECTORS = {}

def register_connector(app_name, connector_instance):
	"""
	Registers a custom source connector for a specific product app.
	"""
	_CONNECTORS[app_name] = connector_instance

def get_connector(app_name):
	"""
	Retrieves the source connector for the specified app name.
	Defaults to GenericSourceConnector if not explicitly registered.
	"""
	if app_name in _CONNECTORS:
		return _CONNECTORS[app_name]
		
	# Fall back to GenericSourceConnector dynamically to avoid circular/hard imports
	from edgepayv1.edgepay.services.connectors.generic import GenericSourceConnector
	return GenericSourceConnector()

def create_payment_request_from_source(source_context):
	"""
	Service function to create a Payment Request from a generic source context dictionary.
	"""
	if isinstance(source_context, str):
		source_context = json.loads(source_context)

	# 1. Resolve connector by source_app
	source_app = source_context.get("source_app")
	if not source_app:
		frappe.throw(_("Missing required source context field: source_app"))

	connector = get_connector(source_app)

	# 2. Validate source context
	connector.validate_source_context(source_context)

	# 3. Build payload for create_payment_request
	payload = connector.build_payment_request_payload(source_context)

	# 4. Invoke create_payment_request service
	# We import locally to avoid circular dependency
	from edgepayv1.edgepay.services.api import create_payment_request
	
	res = create_payment_request(
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
		ignore_auth=True
	)
	
	from edgepayv1.edgepay.services.security import redact_secrets
	return redact_secrets(res)

def notify_source_payment_status(payment_request_name, transaction_name=None, event_source="verification"):
	"""
	Internal event dispatcher invoked when status updates occur.
	"""
	try:
		pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
		txn = frappe.get_doc("EdgePay Payment Transaction", transaction_name) if transaction_name else None

		if not pr.source_app:
			return

		connector = get_connector(pr.source_app)
		
		# Build status handoff payload
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
			"event_source": event_source
		}
		
		from edgepayv1.edgepay.services.security import redact_secrets
		safe_payload = redact_secrets(handoff_payload)
		
		connector.handle_payment_status_update(pr, txn, safe_payload)
	except Exception as e:
		from edgepayv1.edgepay.services.logging import log
		log(f"Failed to notify source payment status for {payment_request_name}: {str(e)}", level="error")
