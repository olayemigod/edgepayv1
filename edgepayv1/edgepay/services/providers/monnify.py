import hashlib
import hmac

import frappe
from frappe import _

from edgepayv1.edgepay.services.providers.base import BaseProvider


class MonnifyProvider(BaseProvider):
	def _credentials(self):
		account = self.get_credentials_doc()
		if not account:
			frappe.throw(_("Merchant Provider Account is required for Monnify payment operations"))
		return account

	def validate_configuration(self):
		account = self._credentials()
		if not account.enabled or account.status != "Active":
			frappe.throw(_("The selected Monnify Provider Account is not active"))
		if not account.get_password("api_key"):
			frappe.throw(_("API Key / Public Key is missing in Monnify Provider Account"))
		if not account.get_password("secret_key"):
			frappe.throw(_("Secret Key is missing in Monnify Provider Account"))
		settings = frappe.get_doc("EdgePay Settings")
		if getattr(settings, "allow_external_http_calls", 0) and not account.contract_code:
			frappe.throw(_("Contract Code is required for Monnify external calls"))

	def get_base_url(self):
		settings = frappe.get_doc("EdgePay Settings")
		account = self.get_credentials_doc()
		sandbox_mode = bool(account and account.environment == "Sandbox") or self.provider_doc.sandbox_mode or settings.sandbox_mode
		base_url = self.provider_doc.base_url
		if not base_url:
			return "https://sandbox.monnify.com/api" if sandbox_mode else "https://api.monnify.com/api"
		base_url = base_url.rstrip("/")
		return f"{base_url}/api" if base_url.endswith("monnify.com") else base_url

	def build_checkout_payload(self, payment_request):
		account = self._credentials()
		unique_ref = f"{payment_request.name}-{frappe.generate_hash(length=8)}"
		return {
			"amount": payment_request.amount,
			"customerName": payment_request.customer_name,
			"customerEmail": payment_request.customer_email,
			"paymentReference": unique_ref,
			"paymentDescription": payment_request.payment_purpose or "Payment",
			"currencyCode": payment_request.currency,
			"contractCode": account.contract_code or "",
		}

	def parse_checkout_response(self, response):
		return {"checkout_url": response.get("checkoutUrl"), "provider_reference": response.get("transactionReference"), "status": "Initiated"}

	def build_verification_payload(self, reference):
		return {"transactionReference": reference}

	def parse_verification_response(self, response):
		return {"amount": response.get("amount"), "currency": response.get("currencyCode"), "status": self.normalize_transaction_status(response.get("paymentStatus")), "provider_reference": response.get("transactionReference"), "transaction_reference": response.get("transactionReference"), "paid_on": response.get("paidOn"), "settlement_status": response.get("settlementStatus") or "Unsettled"}

	def verify_webhook_signature(self, payload, headers):
		account = self._credentials()
		signature = headers.get("monnify-signature") or headers.get("Monnify-Signature")
		if not signature:
			return False
		secret_key = account.get_password("webhook_token") or account.get_password("secret_key")
		if not secret_key:
			return False
		msg = payload.encode() if isinstance(payload, str) else payload
		expected = hmac.new(secret_key.encode(), msg, hashlib.sha512).hexdigest()
		return hmac.compare_digest(expected, signature)

	def parse_webhook_payload(self, payload):
		event_data = payload.get("eventData") or {}
		return {"amount": event_data.get("amountPaid"), "currency": event_data.get("currency"), "status": self.normalize_transaction_status(event_data.get("paymentStatus")), "provider_reference": event_data.get("transactionReference"), "transaction_reference": event_data.get("transactionReference"), "paid_on": event_data.get("paidOn"), "settlement_status": event_data.get("settlementStatus") or "Unsettled", "event_type": payload.get("eventType")}

	def get_webhook_event_reference(self, payload):
		return payload.get("eventReference") or payload.get("eventData", {}).get("transactionReference")

	def get_webhook_payment_reference(self, payload):
		return payload.get("eventData", {}).get("paymentReference")

	def get_webhook_transaction_reference(self, payload):
		return payload.get("eventData", {}).get("transactionReference")

	def normalize_transaction_status(self, provider_status):
		return {"PAID": "Success", "OVERPAID": "Success", "PARTIALLY_PAID": "Success", "FAILED": "Failed", "PENDING": "Pending", "EXPIRED": "Failed"}.get(provider_status, "Pending")
