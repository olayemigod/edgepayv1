# -*- coding: utf-8 -*-
import frappe
from frappe import _
import json
from edgepayv1.edgepay.services.providers.registry import get_provider_instance

@frappe.whitelist()
def validate_provider_configuration(provider_name):
	"""
	Validates local provider configuration without making external calls.
	"""
	try:
		provider = get_provider_instance(provider_name)
		provider.validate_configuration()
		return {"status": "success", "message": "Configuration is valid"}
	except Exception as e:
		return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_provider_health(provider_name):
	"""
	Validates local provider health/readiness.
	"""
	try:
		provider = get_provider_instance(provider_name)
		provider.validate_configuration()
		return {"status": "healthy", "provider": provider.get_provider_code()}
	except Exception as e:
		return {"status": "unhealthy", "error": str(e)}

@frappe.whitelist()
def validate_live_provider_readiness(provider_name):
	"""
	Returns a safe diagnostics report about provider readiness for live calls.
	Never returns actual keys/tokens.
	"""
	try:
		if not frappe.db.exists("EdgePay Provider", provider_name):
			frappe.throw(_("Provider {0} not found").format(provider_name))

		provider_doc = frappe.get_doc("EdgePay Provider", provider_name)
		settings = frappe.get_doc("EdgePay Settings")

		# Safe check of attributes without returning actual passwords
		api_key_present = False
		if provider_doc.api_key:
			try:
				api_key_present = bool(provider_doc.get_password("api_key"))
			except Exception:
				pass

		secret_key_present = False
		if provider_doc.secret_key:
			try:
				secret_key_present = bool(provider_doc.get_password("secret_key"))
			except Exception:
				pass

		return {
			"provider_name": provider_name,
			"provider_enabled": bool(provider_doc.enabled),
			"sandbox_mode": bool(provider_doc.sandbox_mode or settings.sandbox_mode),
			"contract_code_present": bool(getattr(provider_doc, "contract_code", None)),
			"api_key_present": api_key_present,
			"secret_key_present": secret_key_present,
			"external_calls_enabled": bool(getattr(settings, "allow_external_http_calls", 0)),
			"edgepay_enabled": bool(settings.enable_edgepay)
		}
	except Exception as e:
		return {"status": "error", "message": str(e)}

@frappe.whitelist()
def create_payment_request(
	provider, amount, currency, customer_name, customer_email,
	customer_phone=None, payment_purpose=None, source_app=None,
	source_doctype=None, source_name=None, expires_on=None,
	metadata_json=None, idempotency_key=None
):
	"""
	Whitelisted API to safely create a new Payment Request.
	Requires authenticated access. Enforces safe return fields and idempotency.
	"""
	try:
		if frappe.session.user == "Guest":
			frappe.throw(_("Authentication required to access this API"), frappe.PermissionError)
		from edgepayv1.edgepay.services.security import redact_secrets
		from edgepayv1.edgepay.services.checkout import check_and_mark_expired
		from frappe.utils import flt

		# 1. Validate required attributes
		if not amount or flt(amount) <= 0:
			frappe.throw(_("Amount must be greater than zero"))
		if not currency:
			frappe.throw(_("Currency is required"))
		if not provider:
			frappe.throw(_("Provider is required"))

		# Check if provider exists and is enabled
		if not frappe.db.exists("EdgePay Provider", provider):
			frappe.throw(_("Provider {0} not found").format(provider))
		
		provider_doc = frappe.get_doc("EdgePay Provider", provider)
		if not provider_doc.enabled:
			frappe.throw(_("Provider {0} is disabled").format(provider))

		# 2. Respect idempotency key
		if idempotency_key:
			existing_req = frappe.db.get_value(
				"EdgePay Payment Request",
				{
					"idempotency_key": idempotency_key,
					"status": ["not in", ["Paid", "Failed", "Expired", "Cancelled"]]
				},
				"name"
			)
			if existing_req:
				pr = frappe.get_doc("EdgePay Payment Request", existing_req)
				# Double check if it has expired since last query
				if not check_and_mark_expired(pr):
					data = {
						"payment_request": pr.name,
						"request_reference": pr.request_reference,
						"status": pr.status,
						"amount": pr.amount,
						"currency": pr.currency,
						"provider": pr.provider,
						"expires_on": pr.expires_on
					}
					return {
						"ok": True,
						"status": "success",
						"message": "Existing active Payment Request retrieved successfully (idempotent)",
						"data": redact_secrets(data)
					}

		# 3. Create request document
		pr = frappe.new_doc("EdgePay Payment Request")
		pr.provider = provider
		pr.amount = flt(amount)
		pr.currency = currency
		pr.customer_name = customer_name
		pr.customer_email = customer_email
		pr.customer_phone = customer_phone
		pr.payment_purpose = payment_purpose
		pr.source_app = source_app
		pr.source_doctype = source_doctype
		pr.source_name = source_name
		pr.expires_on = expires_on
		pr.idempotency_key = idempotency_key
		
		# Sanitize and validate metadata_json
		if metadata_json:
			try:
				if isinstance(metadata_json, str):
					parsed = json.loads(metadata_json)
				else:
					parsed = metadata_json
				# Clean/redact any accidental credentials inside metadata
				pr.metadata_json = json.dumps(redact_secrets(parsed))
			except Exception:
				frappe.throw(_("Invalid metadata_json payload"))

		# Generate a unique request_reference if not provided
		pr.request_reference = f"REQ-{frappe.generate_hash(length=12)}"
		
		pr.insert(ignore_permissions=True)
		if not frappe.flags.in_test:
			frappe.db.commit()

		data = {
			"payment_request": pr.name,
			"request_reference": pr.request_reference,
			"status": pr.status,
			"amount": pr.amount,
			"currency": pr.currency,
			"provider": pr.provider,
			"expires_on": pr.expires_on
		}

		return {
			"ok": True,
			"status": "success",
			"message": "Payment request created successfully",
			"data": redact_secrets(data)
		}
	except Exception as e:
		from edgepayv1.edgepay.services.security import redact_secrets
		redacted_msg = redact_secrets(str(e))
		return {
			"ok": False,
			"status": "error",
			"message": redacted_msg,
			"data": None
		}

@frappe.whitelist()
def initialize_payment_request_checkout(payment_request_name):
	"""
	Whitelisted API to safely initialize checkout.
	Requires authenticated access. Enforces safe return fields.
	"""
	try:
		if frappe.session.user == "Guest":
			frappe.throw(_("Authentication required to access this API"), frappe.PermissionError)
		from edgepayv1.edgepay.services.checkout import initialize_checkout
		from edgepayv1.edgepay.services.security import redact_secrets

		# Run initialize_checkout service
		result = initialize_checkout(payment_request_name)
		
		pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)

		data = {
			"payment_request": pr.name,
			"status": result.get("status"),
			"checkout_url": result.get("checkout_url"),
			"provider_reference": result.get("provider_reference"),
			"expires_on": pr.expires_on
		}

		return {
			"ok": True,
			"status": "success",
			"message": "Checkout initialized successfully",
			"data": redact_secrets(data)
		}
	except Exception as e:
		from edgepayv1.edgepay.services.security import redact_secrets
		redacted_msg = redact_secrets(str(e))
		return {
			"ok": False,
			"status": "error",
			"message": redacted_msg,
			"data": None
		}

@frappe.whitelist()
def verify_payment_request_transaction(payment_request_name):
	"""
	Whitelisted API to safely verify a payment request transaction.
	Requires authenticated access. Enforces safe return fields.
	"""
	try:
		if frappe.session.user == "Guest":
			frappe.throw(_("Authentication required to access this API"), frappe.PermissionError)
		from edgepayv1.edgepay.services.verification import verify_transaction
		from edgepayv1.edgepay.services.security import redact_secrets

		# Run verify_transaction service
		result = verify_transaction(payment_request_name)

		data = {
			"payment_request": result.get("payment_request"),
			"request_status": result.get("request_status"),
			"transaction": result.get("transaction"),
			"transaction_status": result.get("transaction_status"),
			"provider_reference": result.get("provider_reference"),
			"amount": result.get("amount"),
			"currency": result.get("currency"),
			"paid_on": result.get("paid_on")
		}

		return {
			"ok": True,
			"status": "success",
			"message": "Transaction verified successfully",
			"data": redact_secrets(data)
		}
	except Exception as e:
		from edgepayv1.edgepay.services.security import redact_secrets
		redacted_msg = redact_secrets(str(e))
		return {
			"ok": False,
			"status": "error",
			"message": redacted_msg,
			"data": None
		}

@frappe.whitelist()
def get_payment_request_status(payment_request_name):
	"""
	Whitelisted API to safely check Payment Request status.
	Requires authenticated access. Never mutates database besides checking expiry.
	"""
	try:
		if frappe.session.user == "Guest":
			frappe.throw(_("Authentication required to access this API"), frappe.PermissionError)

		from edgepayv1.edgepay.services.checkout import check_and_mark_expired
		from edgepayv1.edgepay.services.security import redact_secrets

		if not frappe.db.exists("EdgePay Payment Request", payment_request_name):
			frappe.throw(_("Payment Request {0} not found").format(payment_request_name))

		pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
		
		# Check and update expiry in memory only (no mutation)
		check_and_mark_expired(pr, save=False)

		data = {
			"payment_request": pr.name,
			"request_reference": pr.request_reference,
			"status": pr.status,
			"amount": pr.amount,
			"currency": pr.currency,
			"provider": pr.provider,
			"expires_on": pr.expires_on
		}

		return {
			"ok": True,
			"status": "success",
			"message": "Payment request status retrieved successfully",
			"data": redact_secrets(data)
		}
	except Exception as e:
		from edgepayv1.edgepay.services.security import redact_secrets
		redacted_msg = redact_secrets(str(e))
		return {
			"ok": False,
			"status": "error",
			"message": redacted_msg,
			"data": None
		}

@frappe.whitelist()
def get_payment_transaction_status(payment_request_name=None, provider_reference=None, transaction_reference=None):
	"""
	Whitelisted API to safely retrieve transaction status.
	Requires authenticated access. Never mutates database records.
	"""
	try:
		if frappe.session.user == "Guest":
			frappe.throw(_("Authentication required to access this API"), frappe.PermissionError)
		from edgepayv1.edgepay.services.security import redact_secrets

		filters = {}
		if payment_request_name:
			filters["payment_request"] = payment_request_name
		if provider_reference:
			filters["provider_reference"] = provider_reference
		if transaction_reference:
			filters["transaction_reference"] = transaction_reference

		if not filters:
			frappe.throw(_("At least one reference parameter is required"))

		txn_name = frappe.db.get_value("EdgePay Payment Transaction", filters, "name")
		if not txn_name:
			frappe.throw(_("Transaction not found for the given references"))

		txn = frappe.get_doc("EdgePay Payment Transaction", txn_name)

		data = {
			"transaction": txn.name,
			"payment_request": txn.payment_request,
			"status": txn.status,
			"amount": txn.amount,
			"currency": txn.currency,
			"provider_reference": txn.provider_reference,
			"transaction_reference": txn.transaction_reference,
			"paid_on": txn.paid_on,
			"settlement_status": txn.settlement_status
		}

		return {
			"ok": True,
			"status": "success",
			"message": "Payment transaction status retrieved successfully",
			"data": redact_secrets(data)
		}
	except Exception as e:
		from edgepayv1.edgepay.services.security import redact_secrets
		redacted_msg = redact_secrets(str(e))
		return {
			"ok": False,
			"status": "error",
			"message": redacted_msg,
			"data": None
		}

@frappe.whitelist(allow_guest=True)
def handle_checkout_callback(payment_request=None, provider_reference=None, transaction_reference=None, status=None):
	"""
	Whitelisted guest endpoint for handling checkout redirect/callbacks.
	Treats query parameters as untrusted hints, runs server-side validation,
	and returns minimal safe output for frontend presentation.
	"""
	try:
		from edgepayv1.edgepay.services.verification import verify_transaction
		from edgepayv1.edgepay.services.security import redact_secrets

		# Resolve payment request name from hints
		pr_name = payment_request
		if not pr_name and provider_reference:
			pr_name = frappe.db.get_value("EdgePay Payment Request", {"provider_reference": provider_reference}, "name")
		if not pr_name and transaction_reference:
			# Look up by request_reference or transaction_reference
			pr_name = frappe.db.get_value("EdgePay Payment Request", {"request_reference": transaction_reference}, "name")

		if not pr_name:
			frappe.throw(_("Payment request could not be resolved from callback parameters"))

		# Run server-side verification before drawing conclusions
		result = verify_transaction(pr_name)

		data = {
			"payment_request": pr_name,
			"status": result.get("request_status"),
			"message": "Payment verified successfully" if result.get("request_status") == "Paid" else "Payment verification completed"
		}

		return {
			"ok": True,
			"status": "success",
			"message": "Callback processed successfully",
			"data": redact_secrets(data)
		}
	except Exception as e:
		frappe.log_error(f"EdgePay Callback Error: {str(e)}", "EdgePay API Callback")
		return {
			"ok": False,
			"status": "error",
			"message": "An error occurred during verification",
			"data": None
		}
