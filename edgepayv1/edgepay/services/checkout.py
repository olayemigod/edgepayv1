import frappe
from frappe import _
from frappe.utils import flt

from edgepayv1.edgepay.services.clients import get_client
from edgepayv1.edgepay.services.external_references import register_reference
from edgepayv1.edgepay.services.logging import log
from edgepayv1.edgepay.services.payment_state import create_attempt, transition_attempt, transition_request
from edgepayv1.edgepay.services.providers.registry import get_provider_instance


def check_and_mark_expired(pr, save=True):
	if pr.expires_on:
		from frappe.utils import get_datetime, now_datetime

		if now_datetime() > get_datetime(pr.expires_on):
			if pr.status not in ["Paid", "Cancelled", "Expired", "Refunded"]:
				if save:
					transition_request(pr, "Expired", "Payment Request Expired", "expiry")
					try:
						from edgepayv1.edgepay.services.connectors import notify_source_payment_status

						notify_source_payment_status(pr.name, event_source="expiry")
					except Exception as exc:
						log(f"Failed to dispatch expiry status handoff for {pr.name}: {exc}", level="error")
				else:
					pr.status = "Expired"
				return True
			if pr.status == "Expired":
				return True
	return False


def _get_reusable_attempt(pr):
	name = frappe.db.get_value(
		"EdgePay Payment Attempt",
		{
			"payment_request": pr.name,
			"status": ["in", ["Initiated", "Pending"]],
			"checkout_url": ["is", "set"],
		},
		"name",
		order_by="attempt_number desc",
	)
	return frappe.get_doc("EdgePay Payment Attempt", name) if name else None


def initialize_checkout(payment_request_name, payment_method=None):
	pr = frappe.get_doc("EdgePay Payment Request", payment_request_name)
	if check_and_mark_expired(pr):
		frappe.throw(_("Cannot initialize checkout for an expired Payment Request"))
	if pr.status in [
		"Paid",
		"Overpaid",
		"Refund Pending",
		"Partly Refunded",
		"Refunded",
		"Expired",
		"Cancelled",
		"Disputed",
		"Chargeback",
	]:
		frappe.throw(_("Cannot initialize checkout for a Payment Request with status: {0}").format(pr.status))
	if not pr.provider_account:
		frappe.throw(_("Payment Request has no Provider Account"))

	reusable = _get_reusable_attempt(pr)
	if reusable:
		return {
			"status": pr.status,
			"attempt": reusable.name,
			"checkout_url": reusable.checkout_url,
			"provider_reference": reusable.provider_payment_reference,
		}
	if not pr.amount or flt(pr.amount) <= 0:
		frappe.throw(_("Payment amount must be greater than zero to initialize checkout"))

	attempt = create_attempt(pr.name, payment_method=payment_method, expires_on=pr.expires_on)
	provider_instance = get_provider_instance(pr.provider, provider_account=pr.provider_account)
	provider_instance.validate_configuration()
	payload = provider_instance.build_checkout_payload(pr)
	provider_code = provider_instance.get_provider_code()
	client = get_client(provider_code, provider_instance.provider_doc, provider_instance.provider_account)
	base_url = provider_instance.get_base_url()
	log(
		f"Initializing checkout for {pr.name}, attempt {attempt.name}, via provider {provider_code}",
		level="info",
	)

	try:
		response = client.post(f"{base_url}/v1/merchant/transactions/init-transaction", payload)
		parsed_response = provider_instance.parse_checkout_response(response)
	except Exception as exc:
		attempt.failure_message = str(exc)
		attempt.save(ignore_permissions=True)
		transition_attempt(
			attempt, "Failed", "Checkout Initialisation Failed", "checkout", details={"error": str(exc)}
		)
		log(f"Checkout initialization failed for {pr.name}: {exc}", level="error")
		raise

	attempt.checkout_url = parsed_response.get("checkout_url")
	attempt.checkout_token = parsed_response.get("checkout_token")
	attempt.provider_payment_reference = parsed_response.get("provider_reference")
	attempt.expires_on = parsed_response.get("expires_on") or attempt.expires_on
	attempt.save(ignore_permissions=True)
	if attempt.provider_payment_reference:
		register_reference(
			"Provider Payment", attempt.provider_payment_reference, pr.name, payment_attempt=attempt.name
		)
	if parsed_response.get("checkout_session_reference"):
		register_reference(
			"Checkout Session",
			parsed_response.get("checkout_session_reference"),
			pr.name,
			payment_attempt=attempt.name,
		)
	transition_attempt(
		attempt,
		"Initiated",
		"Checkout Initiated",
		"checkout",
		details={"provider_status": parsed_response.get("status")},
	)

	pr.checkout_url = attempt.checkout_url
	pr.provider_reference = attempt.provider_payment_reference
	pr.save(ignore_permissions=True)
	if pr.status in {"Draft", "Failed", "Partly Paid"}:
		transition_request(pr, "Initiated", "Payment Request Initiated", "checkout", attempt=attempt)

	try:
		from edgepayv1.edgepay.services.connectors import notify_source_payment_status

		notify_source_payment_status(pr.name, event_source="checkout")
	except Exception as exc:
		log(f"Failed to dispatch checkout status handoff for {pr.name}: {exc}", level="error")

	return {
		"status": pr.status,
		"attempt": attempt.name,
		"checkout_url": attempt.checkout_url,
		"provider_reference": attempt.provider_payment_reference,
	}


@frappe.whitelist()
def initialize_payment_request_checkout(
	payment_request_name: str, payment_method: str | None = None
):
	if not frappe.has_permission("EdgePay Payment Request", "write", doc=payment_request_name):
		frappe.throw(
			_("Not permitted to initialize checkout for this Payment Request"), frappe.PermissionError
		)
	result = initialize_checkout(payment_request_name, payment_method=payment_method)
	return {
		"payment_request": payment_request_name,
		"payment_attempt": result.get("attempt"),
		"status": result.get("status"),
		"checkout_url": result.get("checkout_url"),
		"provider_reference": result.get("provider_reference"),
	}
