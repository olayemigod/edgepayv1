# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import flt
from edgepayv1.edgepay.services.providers.registry import get_provider_instance
from edgepayv1.edgepay.services.clients import get_client
from edgepayv1.edgepay.services.logging import log

def check_and_mark_expired(pr, save=True):
	"""
	Checks if a Payment Request is past its expires_on time, updates its status to 'Expired'
	if needed, and saves it. Returns True if expired.
	"""
	if pr.expires_on:
		from frappe.utils import now_datetime, get_datetime
		if now_datetime() > get_datetime(pr.expires_on):
			if pr.status not in ["Paid", "Failed", "Cancelled", "Expired"]:
				pr.status = "Expired"
				if save:
					pr.save(ignore_permissions=True)
					if not frappe.flags.in_test:
						frappe.db.commit()
				return True
			elif pr.status == "Expired":
				return True
	return False

def initialize_checkout(payment_request_name):
	"""
	Loads an EdgePay Payment Request and initializes checkout using the provider registry.
	Ensures repeat-call safety, eligibility validation, and secret redaction.
	"""
	pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
	
	# Block expired payment requests
	if check_and_mark_expired(pr):
		frappe.throw(_("Cannot initialize checkout for an expired Payment Request"))

	# Block paid, cancelled, failed, expired requests
	# Valid status options: Draft, Initiated, Paid, Failed, Expired, Cancelled
	if pr.status in ["Paid", "Failed", "Expired", "Cancelled"]:
		frappe.throw(_("Cannot initialize checkout for a Payment Request with status: {0}").format(pr.status))
		
	# Repeat-call / Idempotency check:
	# If already Initiated and has checkout details, return them safely
	if pr.status == "Initiated" and pr.checkout_url and pr.provider_reference:
		log(f"Payment Request {pr.name} is already initiated. Returning existing checkout details.", level="info")
		return {
			"status": pr.status,
			"checkout_url": pr.checkout_url,
			"provider_reference": pr.provider_reference
		}
		
	# Validate amount
	if not pr.amount or flt(pr.amount) <= 0:
		frappe.throw(_("Payment amount must be greater than zero to initialize checkout"))
		
	# Load provider via registry (automatically blocks disabled providers)
	provider_instance = get_provider_instance(pr.provider)
	
	# Validate provider configuration (e.g. checks key fields)
	provider_instance.validate_configuration()
	
	# Build payload
	payload = provider_instance.build_checkout_payload(pr)
	
	# Retrieve client (returns stub client or mock/simulated client)
	provider_code = provider_instance.get_provider_code()
	client = get_client(provider_code, provider_instance.provider_doc)
	
	base_url = provider_instance.get_base_url()
	log(f"Initializing checkout for {pr.name} via provider {provider_code} at {base_url}", level="info")
	
	try:
		response = client.post(f"{base_url}/v1/merchant/transactions/init-transaction", payload)
	except Exception as e:
		log(f"Checkout initialization failed for {pr.name}: {str(e)}", level="error")
		raise e
		
	# Parse response
	parsed_response = provider_instance.parse_checkout_response(response)
	
	# Update Payment Request fields
	pr.checkout_url = parsed_response.get("checkout_url")
	pr.provider_reference = parsed_response.get("provider_reference")
	pr.status = parsed_response.get("status", "Initiated")
	
	pr.save(ignore_permissions=True)

	try:
		from edgepayv1.edgepay.services.connectors import notify_source_payment_status
		notify_source_payment_status(pr.name, event_source="checkout")
	except Exception as e:
		log(f"Failed to dispatch checkout status handoff for {pr.name}: {str(e)}", level="error")
	
	log(f"Checkout initialized successfully for {pr.name}. Ref: {pr.provider_reference}", level="info")
	
	return {
		"status": pr.status,
		"checkout_url": pr.checkout_url,
		"provider_reference": pr.provider_reference
	}

@frappe.whitelist()
def initialize_payment_request_checkout(payment_request_name):
	"""
	Whitelisted API wrapper. Verifies appropriate write permission, initiates checkout,
	and returns only safe fields.
	"""
	# Verify write permission on the Payment Request document
	if not frappe.has_permission("EdgePay Payment Request", "write", doc=payment_request_name):
		frappe.throw(_("Not permitted to initialize checkout for this Payment Request"), frappe.PermissionError)
		
	result = initialize_checkout(payment_request_name)
	
	return {
		"payment_request": payment_request_name,
		"status": result.get("status"),
		"checkout_url": result.get("checkout_url"),
		"provider_reference": result.get("provider_reference")
	}
