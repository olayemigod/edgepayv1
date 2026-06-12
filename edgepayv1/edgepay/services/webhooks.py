# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import flt
from edgepayv1.edgepay.services.providers.registry import get_provider_instance
from edgepayv1.edgepay.services.logging import log
from edgepayv1.edgepay.services.security import redact_secrets
import json

def process_webhook_event(provider_code, headers, raw_body):
	"""
	Logs and processes a webhook event from a specific provider.
	Enforces signature verification, deduplication, amount/currency validation,
	and idempotent status updates.
	"""
	# Resolve provider document using provider_code (rejects if unknown or disabled)
	# Find provider doc by provider_code
	provider_name = frappe.db.get_value("EdgePay Provider", {"provider_code": provider_code}, "name")
	if not provider_name:
		frappe.throw(_("Unsupported provider code: {0}").format(provider_code))
		
	provider_doc = frappe.get_doc("EdgePay Provider", provider_name)
	if not provider_doc.enabled:
		frappe.throw(_("Provider {0} is disabled").format(provider_doc.provider_name))
		
	provider_instance = get_provider_instance(provider_doc)
	
	# Parse raw body safely
	try:
		if isinstance(raw_body, bytes):
			body_str = raw_body.decode('utf-8')
		else:
			body_str = raw_body
		payload = json.loads(body_str)
	except Exception as e:
		frappe.throw(_("Invalid JSON payload in webhook body: {0}").format(str(e)))
		
	# Redact secrets before logs or DB insertions
	redacted_payload = redact_secrets(payload)
	
	# Retrieve event reference
	event_ref = provider_instance.get_webhook_event_reference(payload)
	if not event_ref:
		frappe.throw(_("Webhook event has no unique event identifier"))
		
	# Check for duplicate webhook events
	existing_event = frappe.db.get_value(
		"EdgePay Webhook Event",
		{"provider": provider_doc.name, "event_reference": event_ref},
		["name", "processing_status"],
		as_dict=True
	)
	if existing_event:
		log(f"Duplicate webhook event {event_ref} ignored.", level="info")
		return {
			"status": "success",
			"event": existing_event.name,
			"processing_status": existing_event.processing_status,
			"duplicate": True
		}
		
	# Log new webhook event
	event_doc = frappe.new_doc("EdgePay Webhook Event")
	event_doc.provider = provider_doc.name
	event_doc.event_type = payload.get("eventType") or "unknown"
	event_doc.event_reference = event_ref
	event_doc.received_on = frappe.utils.now_datetime()
	event_doc.payload_json = json.dumps(redacted_payload, indent=2)
	
	# Verify signature
	signature_valid = provider_instance.verify_webhook_signature(raw_body, headers)
	event_doc.signature_valid = 1 if signature_valid else 0
	
	if not signature_valid:
		event_doc.processing_status = "Failed"
		event_doc.error_message = "Invalid webhook signature"
		event_doc.insert(ignore_permissions=True)
		log(f"Webhook signature validation failed for event {event_ref}", level="error")
		return {
			"status": "failed",
			"event": event_doc.name,
			"processing_status": "Failed",
			"duplicate": False
		}
		
	# Parse payload
	parsed = provider_instance.parse_webhook_payload(payload)
	payment_ref = provider_instance.get_webhook_payment_reference(payload)
	provider_ref = provider_instance.get_webhook_transaction_reference(payload)
	
	# Resolve Payment Request
	pr_name = None
	if payment_ref:
		pr_name = frappe.db.get_value("EdgePay Payment Request", {"request_reference": payment_ref}, "name")
	if not pr_name and provider_ref:
		pr_name = frappe.db.get_value("EdgePay Payment Request", {"provider_reference": provider_ref}, "name")
		
	if not pr_name:
		event_doc.processing_status = "Failed"
		event_doc.error_message = f"Payment Request not resolved for ref={payment_ref}, provider_ref={provider_ref}"
		event_doc.insert(ignore_permissions=True)
		log(event_doc.error_message, level="error")
		return {
			"status": "failed",
			"event": event_doc.name,
			"processing_status": "Failed",
			"duplicate": False
		}
		
	pr = frappe.get_doc("EdgePay Payment Request", pr_name)
	
	# Validate amount consistency
	parsed_amount = parsed.get("amount")
	if parsed_amount is not None and flt(parsed_amount) != flt(pr.amount):
		event_doc.processing_status = "Failed"
		event_doc.error_message = f"Amount mismatch: expected {pr.amount}, got {parsed_amount}"
		event_doc.insert(ignore_permissions=True)
		log(event_doc.error_message, level="error")
		return {
			"status": "failed",
			"event": event_doc.name,
			"processing_status": "Failed",
			"duplicate": False
		}
		
	# Validate currency consistency
	parsed_currency = parsed.get("currency")
	if parsed_currency and pr.currency and parsed_currency.upper() != pr.currency.upper():
		event_doc.processing_status = "Failed"
		event_doc.error_message = f"Currency mismatch: expected {pr.currency}, got {parsed_currency}"
		event_doc.insert(ignore_permissions=True)
		log(event_doc.error_message, level="error")
		return {
			"status": "failed",
			"event": event_doc.name,
			"processing_status": "Failed",
			"duplicate": False
		}

	# Resolve or Create Transaction record
	txn_ref = parsed.get("transaction_reference") or parsed.get("provider_reference")
	prov_ref = parsed.get("provider_reference")
	
	existing_txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"payment_request": pr.name}, "name")
	if not existing_txn_name and prov_ref:
		existing_txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"provider_reference": prov_ref}, "name")
	if not existing_txn_name and txn_ref:
		existing_txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"transaction_reference": txn_ref}, "name")
		
	if existing_txn_name:
		txn = frappe.get_doc("EdgePay Payment Transaction", existing_txn_name)
	else:
		txn = frappe.new_doc("EdgePay Payment Transaction")
		
	# Update transaction fields
	txn.payment_request = pr.name
	txn.provider = pr.provider
	txn.transaction_reference = txn_ref
	txn.provider_reference = prov_ref
	txn.amount = pr.amount
	txn.currency = pr.currency
	
	if parsed.get("paid_on"):
		txn.paid_on = parsed.get("paid_on")
	if parsed.get("settlement_status"):
		txn.settlement_status = parsed.get("settlement_status")
	txn.raw_response_json = json.dumps(redacted_payload, indent=2)
	txn.idempotency_key = pr.idempotency_key

	# Enforce transition status safety:
	# Do not allow downgrading request or transaction from success/paid status.
	new_status = parsed.get("status") # Pending, Success, Failed, Refunded
	
	if pr.status == "Paid" and new_status != "Success":
		log(f"Payment Request {pr.name} is already Paid. Webhook status {new_status} skipped.", level="info")
	else:
		if new_status == "Success":
			pr.status = "Paid"
		elif new_status == "Failed":
			pr.status = "Failed"
			
	if txn.status == "Success" and new_status != "Success":
		log(f"Payment Transaction {txn.name} is already Success. Webhook status {new_status} skipped.", level="info")
	else:
		txn.status = new_status
		
	txn.save(ignore_permissions=True)
	pr.save(ignore_permissions=True)
	
	from edgepayv1.edgepay.services.connectors import notify_source_payment_status
	notify_source_payment_status(pr.name, txn.name)
	
	# Complete Webhook Event Doc
	event_doc.linked_payment_request = pr.name
	event_doc.linked_payment_transaction = txn.name
	event_doc.processing_status = "Processed"
	event_doc.insert(ignore_permissions=True)
	
	return {
		"status": "success",
		"event": event_doc.name,
		"processing_status": "Processed",
		"duplicate": False
	}

@frappe.whitelist(allow_guest=True)
def process_provider_webhook(provider_code):
	"""
	Whitelisted guest endpoint for receiving webhooks.
	Reads raw body and headers securely, runs signature verification, and maps response.
	"""
	try:
		# Get raw body from request context
		if hasattr(frappe.local, "request"):
			raw_body = frappe.local.request.get_data()
			headers = frappe.local.request.headers
		else:
			# Fallback for tests / console runs
			raw_body = frappe.request.data if hasattr(frappe, "request") else ""
			headers = frappe.request.headers if hasattr(frappe, "request") else {}
			
		result = process_webhook_event(provider_code, headers, raw_body)
		
		return {
			"status": result.get("status"),
			"event": result.get("event"),
			"processing_status": result.get("processing_status"),
			"duplicate": result.get("duplicate", False)
		}
	except Exception as e:
		frappe.log_error(f"EdgePay Webhook Exception: {str(e)}", "EdgePay Webhook Error")
		if hasattr(frappe, "local") and hasattr(frappe.local, "response"):
			frappe.local.response["http_status_code"] = 400
		return {
			"status": "failed",
			"message": "An error occurred during webhook processing"
		}
