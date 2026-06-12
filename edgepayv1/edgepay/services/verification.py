# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import flt
from edgepayv1.edgepay.services.providers.registry import get_provider_instance
from edgepayv1.edgepay.services.clients import get_client
from edgepayv1.edgepay.services.logging import log
from edgepayv1.edgepay.services.security import redact_secrets
import json
import urllib.parse as urlparse

def verify_transaction(payment_request_name):
	"""
	Verifies the transaction status for an EdgePay Payment Request and records
	the result in an EdgePay Payment Transaction document.
	"""
	pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
	
	from edgepayv1.edgepay.services.checkout import check_and_mark_expired
	check_and_mark_expired(pr)

	if not pr.provider:
		frappe.throw(_("Payment Request has no provider specified"))
		
	if not pr.provider_reference:
		frappe.throw(_("Payment Request has no provider reference generated"))

	# Enforce status eligibility
	# Final statuses are Paid, Failed, Expired, Cancelled.
	if pr.status in ["Paid", "Failed", "Expired", "Cancelled"]:
		# Idempotent lookup check: return existing transaction details if they exist
		existing_txn = frappe.db.get_value(
			"EdgePay Payment Transaction",
			{"payment_request": pr.name},
			["name", "status", "amount", "currency", "provider_reference", "paid_on"],
			as_dict=True
		)
		if existing_txn:
			log(f"Payment Request {pr.name} already in final status ({pr.status}). Returning cached transaction.", level="info")
			return {
				"payment_request": pr.name,
				"request_status": pr.status,
				"transaction": existing_txn.name,
				"transaction_status": existing_txn.status,
				"provider_reference": existing_txn.provider_reference,
				"amount": existing_txn.amount,
				"currency": existing_txn.currency,
				"paid_on": existing_txn.paid_on
			}
		else:
			frappe.throw(_("Cannot verify transaction for a Payment Request with final status: {0}").format(pr.status))

	# Verifiable status check (verifiable status is "Initiated")
	if pr.status != "Initiated":
		frappe.throw(_("Payment Request must be in 'Initiated' status to verify, current status is: {0}").format(pr.status))

	# Resolve provider via registry (checks if enabled)
	provider_instance = get_provider_instance(pr.provider)
	provider_instance.validate_configuration()
	
	# Build payload
	payload = provider_instance.build_verification_payload(pr.provider_reference)
	
	# Retrieve injectable client
	provider_code = provider_instance.get_provider_code()
	client = get_client(provider_code, provider_instance.provider_doc)
	
	base_url = provider_instance.get_base_url()
	query_str = urlparse.urlencode(payload)
	url = f"{base_url}/v1/merchant/transactions/query?{query_str}"
	
	log(f"Verifying transaction for {pr.name} via provider {provider_code} GET at {url}", level="info")
	
	try:
		response = client.get(url)
	except Exception as e:
		log(f"Transaction verification call failed for {pr.name}: {str(e)}", level="error")
		raise e
		
	# Redact secrets in logs/raw response
	redacted_response = redact_secrets(response)
	
	# Parse response
	parsed_response = provider_instance.parse_verification_response(response)
	
	# Validate consistency
	parsed_amount = parsed_response.get("amount")
	parsed_currency = parsed_response.get("currency")
	
	if parsed_amount is not None:
		if flt(parsed_amount) != flt(pr.amount):
			frappe.throw(_("Verification failed: Amount mismatch. Expected {0}, got {1}").format(pr.amount, parsed_amount))
			
	if parsed_currency and pr.currency:
		if parsed_currency.upper() != pr.currency.upper():
			frappe.throw(_("Verification failed: Currency mismatch. Expected {0}, got {1}").format(pr.currency, parsed_currency))
			
	# Update or Create transaction record linked to the Payment Request
	# Lookup using payment_request, provider_reference, or transaction_reference
	txn_ref = parsed_response.get("transaction_reference") or parsed_response.get("provider_reference")
	prov_ref = parsed_response.get("provider_reference")
	
	existing_txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"payment_request": pr.name}, "name")
	if not existing_txn_name and prov_ref:
		existing_txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"provider_reference": prov_ref}, "name")
	if not existing_txn_name and txn_ref:
		existing_txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"transaction_reference": txn_ref}, "name")
		
	if existing_txn_name:
		txn = frappe.get_doc("EdgePay Payment Transaction", existing_txn_name)
		log(f"Updating existing transaction record {txn.name} for {pr.name}", level="info")
	else:
		txn = frappe.new_doc("EdgePay Payment Transaction")
		log(f"Creating new transaction record for {pr.name}", level="info")
		
	txn.payment_request = pr.name
	txn.provider = pr.provider
	txn.transaction_reference = txn_ref
	txn.provider_reference = prov_ref
	txn.amount = pr.amount
	txn.currency = pr.currency
	txn.status = parsed_response.get("status") # Success, Failed, Pending, Refunded
	
	if parsed_response.get("paid_on"):
		txn.paid_on = parsed_response.get("paid_on")
	if parsed_response.get("settlement_status"):
		txn.settlement_status = parsed_response.get("settlement_status")
		
	txn.raw_response_json = json.dumps(redacted_response, indent=2)
	txn.idempotency_key = pr.idempotency_key
	
	txn.save(ignore_permissions=True)
	
	# Update Payment Request status based on transaction outcome
	if txn.status == "Success":
		pr.status = "Paid"
	elif txn.status == "Failed":
		pr.status = "Failed"
	# If txn.status is "Pending", request status remains "Initiated"
	
	pr.save(ignore_permissions=True)
	
	log(f"Transaction verification completed for {pr.name}. Request Status: {pr.status}, Transaction Status: {txn.status}", level="info")
	
	return {
		"payment_request": pr.name,
		"request_status": pr.status,
		"transaction": txn.name,
		"transaction_status": txn.status,
		"provider_reference": prov_ref,
		"amount": txn.amount,
		"currency": txn.currency,
		"paid_on": txn.paid_on
	}

@frappe.whitelist()
def verify_payment_request_transaction(payment_request_name):
	"""
	Whitelisted API to verify transaction status. Enforces write permissions and returns safe fields.
	"""
	if not frappe.has_permission("EdgePay Payment Request", "write", doc=payment_request_name):
		frappe.throw(_("Not permitted to verify transaction for this Payment Request"), frappe.PermissionError)
		
	result = verify_transaction(payment_request_name)
	
	return {
		"payment_request": payment_request_name,
		"request_status": result.get("request_status"),
		"transaction": result.get("transaction"),
		"transaction_status": result.get("transaction_status"),
		"provider_reference": result.get("provider_reference"),
		"amount": result.get("amount"),
		"currency": result.get("currency"),
		"paid_on": result.get("paid_on")
	}
