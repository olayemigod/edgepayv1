import json

import frappe
from frappe import _

from edgepayv1.edgepay.services.authorization import (
	require_authenticated_user,
	require_doctype_permission,
	require_payment_request_access,
	require_payment_transaction_access,
	require_platform_configuration_access,
	require_platform_operations_access,
	require_provider_access,
	require_provider_account_access,
)
from edgepayv1.edgepay.services.providers.registry import get_provider_instance
from edgepayv1.edgepay.services.security import redact_secrets


def _error_response(exc):
	return {"ok": False, "status": "error", "message": redact_secrets(str(exc)), "data": None}


def resolve_payment_request_by_ref(ref):
	if not ref:
		return None
	if frappe.db.exists("EdgePay Payment Request", ref):
		return ref
	if "-" in ref:
		possible_pr = ref.rsplit("-", 1)[0]
		if frappe.db.exists("EdgePay Payment Request", possible_pr):
			return possible_pr
	pr_name = frappe.db.get_value("EdgePay Payment Request", {"request_reference": ref}, "name")
	if pr_name:
		return pr_name
	if "-" in ref:
		possible_req = ref.rsplit("-", 1)[0]
		return frappe.db.get_value("EdgePay Payment Request", {"request_reference": possible_req}, "name")
	return None


@frappe.whitelist()
def validate_provider_configuration(provider_name, provider_account=None):
	try:
		require_platform_configuration_access()
		provider_doc = require_provider_access(provider_name, ptype="read")
		account = None
		if provider_account:
			account = require_provider_account_access(provider_account, ptype="read")
			if account.provider != provider_doc.name:
				frappe.throw(_("Provider Account does not match the selected Provider"))
		provider = get_provider_instance(provider_doc, provider_account=account)
		provider.validate_configuration()
		return {"status": "success", "message": "Configuration is valid"}
	except Exception as exc:
		return {"status": "error", "message": redact_secrets(str(exc))}


@frappe.whitelist()
def get_provider_health(provider_name):
	try:
		require_platform_configuration_access()
		require_provider_access(provider_name, ptype="read")
		provider = get_provider_instance(provider_name)
		provider.validate_configuration()
		return {"status": "healthy", "provider": provider.get_provider_code()}
	except Exception as exc:
		return {"status": "unhealthy", "error": redact_secrets(str(exc))}


@frappe.whitelist()
def validate_live_provider_readiness(provider_name, provider_account=None):
	try:
		require_platform_configuration_access()
		provider_doc = require_provider_access(provider_name, ptype="read")
		if not provider_account:
			frappe.throw(_("Provider Account is required for merchant credential readiness"))
		account = require_provider_account_access(provider_account, ptype="read")
		if account.provider != provider_doc.name:
			frappe.throw(_("Provider Account does not match the selected Provider"))
		settings = frappe.get_doc("EdgePay Settings")
		api_key_present = bool(account.get_password("api_key", raise_exception=False))
		secret_key_present = bool(account.get_password("secret_key", raise_exception=False))
		return {
			"provider_name": provider_name,
			"provider_account": account.name,
			"provider_enabled": bool(provider_doc.enabled),
			"provider_account_enabled": bool(account.enabled),
			"provider_account_status": account.status,
			"environment": account.environment,
			"sandbox_mode": account.environment == "Sandbox",
			"contract_code_present": bool(account.contract_code),
			"api_key_present": api_key_present,
			"secret_key_present": secret_key_present,
			"external_calls_enabled": bool(getattr(settings, "allow_external_http_calls", 0)),
			"edgepay_enabled": bool(settings.enable_edgepay),
		}
	except Exception as exc:
		return {"status": "error", "message": redact_secrets(str(exc))}


@frappe.whitelist()
def create_payment_request(
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
	"""Authenticated public wrapper for Payment Request creation."""
	try:
		require_authenticated_user()
		require_doctype_permission("EdgePay Payment Request", ptype="create")
		require_provider_access(provider, ptype="read")
		from edgepayv1.edgepay.services.payment_requests import create_payment_request_record

		return create_payment_request_record(
			provider=provider,
			amount=amount,
			currency=currency,
			customer_name=customer_name,
			customer_email=customer_email,
			customer_phone=customer_phone,
			payment_purpose=payment_purpose,
			source_app=source_app,
			source_doctype=source_doctype,
			source_name=source_name,
			expires_on=expires_on,
			metadata_json=metadata_json,
			idempotency_key=idempotency_key,
		)
	except Exception as exc:
		return _error_response(exc)


@frappe.whitelist()
def initialize_payment_request_checkout(payment_request_name):
	try:
		require_payment_request_access(payment_request_name, ptype="write")
		from edgepayv1.edgepay.services.checkout import initialize_checkout

		result = initialize_checkout(payment_request_name)
		pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
		return {
			"ok": True,
			"status": "success",
			"message": "Checkout initialized successfully",
			"data": redact_secrets(
				{
					"payment_request": pr.name,
					"status": result.get("status"),
					"checkout_url": result.get("checkout_url"),
					"provider_reference": result.get("provider_reference"),
					"expires_on": pr.expires_on,
				}
			),
		}
	except Exception as exc:
		return _error_response(exc)


@frappe.whitelist()
def verify_payment_request_transaction(payment_request_name):
	try:
		require_payment_request_access(payment_request_name, ptype="write")
		from edgepayv1.edgepay.services.verification import verify_transaction

		result = verify_transaction(payment_request_name)
		return {
			"ok": True,
			"status": "success",
			"message": "Transaction verified successfully",
			"data": redact_secrets(
				{
					"payment_request": result.get("payment_request"),
					"request_status": result.get("request_status"),
					"transaction": result.get("transaction"),
					"transaction_status": result.get("transaction_status"),
					"provider_reference": result.get("provider_reference"),
					"amount": result.get("amount"),
					"currency": result.get("currency"),
					"paid_on": result.get("paid_on"),
				}
			),
		}
	except Exception as exc:
		return _error_response(exc)


@frappe.whitelist()
def get_payment_request_status(payment_request_name):
	try:
		pr = require_payment_request_access(payment_request_name, ptype="read")
		from edgepayv1.edgepay.services.checkout import check_and_mark_expired

		check_and_mark_expired(pr, save=False)
		return {
			"ok": True,
			"status": "success",
			"message": "Payment request status retrieved successfully",
			"data": redact_secrets(
				{
					"payment_request": pr.name,
					"request_reference": pr.request_reference,
					"status": pr.status,
					"amount": pr.amount,
					"currency": pr.currency,
					"provider": pr.provider,
					"expires_on": pr.expires_on,
				}
			),
		}
	except Exception as exc:
		return _error_response(exc)


@frappe.whitelist()
def get_payment_transaction_status(
	payment_request_name=None, provider_reference=None, transaction_reference=None
):
	try:
		require_authenticated_user()
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
		txn = require_payment_transaction_access(txn_name, ptype="read")
		return {
			"ok": True,
			"status": "success",
			"message": "Payment transaction status retrieved successfully",
			"data": redact_secrets(
				{
					"transaction": txn.name,
					"payment_request": txn.payment_request,
					"status": txn.status,
					"amount": txn.amount,
					"currency": txn.currency,
					"provider_reference": txn.provider_reference,
					"transaction_reference": txn.transaction_reference,
					"paid_on": txn.paid_on,
					"settlement_status": txn.settlement_status,
				}
			),
		}
	except Exception as exc:
		return _error_response(exc)


@frappe.whitelist(allow_guest=True)
def handle_checkout_callback(
	payment_request=None, provider_reference=None, transaction_reference=None, status=None
):
	"""Treat redirect parameters as hints and verify payment server-side."""
	try:
		from edgepayv1.edgepay.services.verification import verify_transaction

		pr_name = payment_request or frappe.form_dict.get("paymentReference")
		if pr_name:
			pr_name = resolve_payment_request_by_ref(pr_name)
		provider_ref = provider_reference or frappe.form_dict.get("transactionReference")
		if not pr_name and provider_ref:
			pr_name = frappe.db.get_value(
				"EdgePay Payment Request", {"provider_reference": provider_ref}, "name"
			)
		tx_ref = transaction_reference or frappe.form_dict.get("paymentReference")
		if not pr_name and tx_ref:
			pr_name = resolve_payment_request_by_ref(tx_ref)
		if not pr_name:
			frappe.throw(_("Payment request could not be resolved from callback parameters"))
		result = verify_transaction(pr_name)
		return {
			"ok": True,
			"status": "success",
			"message": "Callback processed successfully",
			"data": redact_secrets(
				{
					"payment_request": pr_name,
					"status": result.get("request_status"),
					"message": (
						"Payment verified successfully"
						if result.get("request_status") == "Paid"
						else "Payment verification completed"
					),
				}
			),
		}
	except Exception as exc:
		frappe.log_error(f"EdgePay Callback Error: {redact_secrets(str(exc))}", "EdgePay API Callback")
		return {
			"ok": False,
			"status": "error",
			"message": "An error occurred during verification",
			"data": None,
		}


@frappe.whitelist()
def create_payment_request_from_source(source_context):
	try:
		require_authenticated_user()
		require_doctype_permission("EdgePay Payment Request", ptype="create")
		if isinstance(source_context, str):
			source_context = json.loads(source_context)
		provider = source_context.get("provider") if isinstance(source_context, dict) else None
		if provider:
			require_provider_access(provider, ptype="read")
		from edgepayv1.edgepay.services.connectors.registry import (
			create_payment_request_from_source as create_from_source,
		)

		return create_from_source(source_context)
	except Exception as exc:
		return _error_response(exc)


@frappe.whitelist()
def get_pending_payment_handoffs(source_app=None, limit=50):
	try:
		require_platform_operations_access()
		from edgepayv1.edgepay.services.handoff import get_pending_handoff_events

		return {
			"ok": True,
			"status": "success",
			"message": "Pending handoffs retrieved successfully",
			"data": get_pending_handoff_events(source_app=source_app, limit=limit),
		}
	except Exception as exc:
		return _error_response(exc)


@frappe.whitelist()
def mark_payment_handoff_delivered(event_name):
	try:
		require_platform_operations_access()
		from edgepayv1.edgepay.services.handoff import mark_handoff_event_delivered

		mark_handoff_event_delivered(event_name)
		return {
			"ok": True,
			"status": "success",
			"message": f"Handoff event {event_name} marked as delivered",
			"data": None,
		}
	except Exception as exc:
		return _error_response(exc)


@frappe.whitelist()
def mark_payment_handoff_failed(event_name, error_message=None):
	try:
		require_platform_operations_access()
		from edgepayv1.edgepay.services.handoff import mark_handoff_event_failed

		mark_handoff_event_failed(event_name, error_message=error_message)
		return {
			"ok": True,
			"status": "success",
			"message": f"Handoff event {event_name} marked as failed",
			"data": None,
		}
	except Exception as exc:
		return _error_response(exc)
