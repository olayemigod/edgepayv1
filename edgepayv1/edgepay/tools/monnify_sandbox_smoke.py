import json
import os

import frappe

from edgepayv1.edgepay.services.checkout import initialize_checkout
from edgepayv1.edgepay.services.security import redact_secrets
from edgepayv1.edgepay.services.verification import verify_transaction


def run_monnify_sandbox_smoke():
	"""Run an explicitly enabled, isolated Monnify sandbox connectivity smoke test."""
	if os.environ.get("EDGEPAY_RUN_MONNIFY_SANDBOX_SMOKE") != "1":
		print(
			"EDGEPAY_RUN_MONNIFY_SANDBOX_SMOKE environment variable is not set to '1'. "
			"Smoke test execution aborted."
		)
		return False

	api_key = os.environ.get("EDGEPAY_MONNIFY_SANDBOX_API_KEY")
	secret_key = os.environ.get("EDGEPAY_MONNIFY_SANDBOX_SECRET_KEY")
	contract_code = os.environ.get("EDGEPAY_MONNIFY_SANDBOX_CONTRACT_CODE")
	if not api_key or not secret_key or not contract_code:
		print(
			"Missing required environment variables: EDGEPAY_MONNIFY_SANDBOX_API_KEY, "
			"EDGEPAY_MONNIFY_SANDBOX_SECRET_KEY, and EDGEPAY_MONNIFY_SANDBOX_CONTRACT_CODE "
			"must be populated."
		)
		return False

	settings_name = "EdgePay Settings"
	settings_exist = frappe.db.exists("EdgePay Settings", settings_name)
	if settings_exist:
		settings = frappe.get_doc("EdgePay Settings", settings_name)
		prev_enable_edgepay = settings.enable_edgepay
		prev_allow_external_http_calls = getattr(settings, "allow_external_http_calls", 0)
		prev_sandbox_mode = settings.sandbox_mode
	else:
		settings = frappe.new_doc("EdgePay Settings")
		prev_enable_edgepay = 0
		prev_allow_external_http_calls = 0
		prev_sandbox_mode = 0

	provider_name = "Monnify Sandbox Smoke Test"
	merchant_name = "EdgePay Monnify Sandbox Smoke Merchant"
	provider_existed = frappe.db.exists("EdgePay Provider", provider_name)
	merchant_existed = frappe.db.exists("EdgePay Merchant", merchant_name)
	payment_request_name = None
	transaction_name = None
	provider_account_name = None

	try:
		if provider_existed:
			provider_doc = frappe.get_doc("EdgePay Provider", provider_name)
		else:
			provider_doc = frappe.new_doc("EdgePay Provider")
			provider_doc.provider_name = provider_name
			provider_doc.provider_code = "monnify"
			provider_doc.provider_type = "Monnify"
			provider_doc.status = "Active"

		provider_doc.enabled = 1
		provider_doc.sandbox_mode = 1
		provider_doc.base_url = "https://sandbox.monnify.com/api"
		provider_doc.api_key = api_key
		provider_doc.secret_key = secret_key
		provider_doc.contract_code = contract_code
		provider_doc.save(ignore_permissions=True)

		if merchant_existed:
			merchant = frappe.get_doc("EdgePay Merchant", merchant_name)
		else:
			merchant = frappe.get_doc(
				{
					"doctype": "EdgePay Merchant",
					"merchant_name": merchant_name,
					"status": "Draft",
					"legal_name": merchant_name,
					"email": "smoke_test@edgepay.com",
					"country": "Nigeria",
					"default_currency": "NGN",
				}
			).insert(ignore_permissions=True)

		frappe.db.delete(
			"EdgePay Provider Account",
			{"merchant": merchant.name, "provider": provider_name, "environment": "Sandbox"},
		)
		provider_account = frappe.get_doc(
			{
				"doctype": "EdgePay Provider Account",
				"merchant": merchant.name,
				"provider": provider_name,
				"account_label": "Sandbox Smoke",
				"environment": "Sandbox",
				"enabled": 1,
				"status": "Active",
				"api_key": api_key,
				"secret_key": secret_key,
				"contract_code": contract_code,
			}
		).insert(ignore_permissions=True)
		provider_account_name = provider_account.name

		settings.enable_edgepay = 1
		settings.allow_external_http_calls = 1
		settings.sandbox_mode = 1
		settings.save(ignore_permissions=True)

		pr = frappe.new_doc("EdgePay Payment Request")
		pr.merchant = merchant.name
		pr.provider_account = provider_account.name
		pr.provider = provider_name
		pr.amount = 10.00
		pr.currency = "NGN"
		pr.customer_name = "Sandbox Smoke Test Customer"
		pr.customer_email = "smoke_test@edgepay.com"
		pr.payment_purpose = "Sandbox Smoke Test Verification"
		pr.status = "Draft"
		pr.request_reference = f"SMOKE-PR-{frappe.generate_hash(length=8)}"
		pr.source_app = "EdgePay Developer Utility"
		pr.metadata_json = json.dumps({"smoke_test": True})
		pr.insert(ignore_permissions=True)
		payment_request_name = pr.name

		print(f"Temporary Payment Request created: {payment_request_name}")
		print("Initializing checkout...")
		checkout_res = initialize_checkout(payment_request_name)
		checkout_url = checkout_res.get("checkout_url")
		provider_ref = checkout_res.get("provider_reference")
		print(f"Checkout URL: {redact_secrets(checkout_url) if checkout_url else None}")
		print(f"Provider Reference: {redact_secrets(provider_ref) if provider_ref else None}")
		if not checkout_url or not provider_ref:
			raise Exception(
				"Checkout initialization did not return a valid checkout URL or provider reference."
			)

		print("Running transaction verification...")
		verify_res = verify_transaction(payment_request_name)
		verification_status = verify_res.get("transaction_status")
		transaction_name = verify_res.get("transaction")
		print(f"Verification Status: {verification_status}")
		print(f"Transaction Record: {transaction_name}")
		print("Smoke test successfully executed!")
		return True

	except Exception as exc:
		redacted_err = redact_secrets(str(exc))
		print(f"Error during smoke test execution: {redacted_err}")
		raise
	finally:
		if transaction_name and frappe.db.exists("EdgePay Payment Transaction", transaction_name):
			frappe.db.delete("EdgePay Payment Transaction", transaction_name)
		if payment_request_name and frappe.db.exists("EdgePay Payment Request", payment_request_name):
			frappe.db.delete("EdgePay Payment Request", payment_request_name)
		if provider_account_name and frappe.db.exists("EdgePay Provider Account", provider_account_name):
			frappe.db.delete("EdgePay Provider Account", provider_account_name)
		if not merchant_existed and frappe.db.exists("EdgePay Merchant", merchant_name):
			frappe.db.delete("EdgePay Merchant", merchant_name)
		if not provider_existed and frappe.db.exists("EdgePay Provider", provider_name):
			frappe.db.delete("EdgePay Provider", provider_name)

		if settings_exist:
			settings.enable_edgepay = prev_enable_edgepay
			settings.allow_external_http_calls = prev_allow_external_http_calls
			settings.sandbox_mode = prev_sandbox_mode
			settings.save(ignore_permissions=True)
		else:
			frappe.db.delete("EdgePay Settings", settings_name)
		print("Settings and temporary smoke-test records successfully restored.")
