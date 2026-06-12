# -*- coding: utf-8 -*-
import frappe
from edgepayv1.edgepay.services.providers.base import BaseProvider
from frappe import _

class MonnifyProvider(BaseProvider):
	def validate_configuration(self):
		if not self.provider_doc.api_key:
			frappe.throw(_("API Key / Public Key is missing in Monnify configuration"))
		if not self.provider_doc.secret_key:
			frappe.throw(_("Secret Key is missing in Monnify configuration"))
		settings = frappe.get_doc("EdgePay Settings")
		if getattr(settings, "allow_external_http_calls", 0):
			if not getattr(self.provider_doc, "contract_code", None):
				frappe.throw(_("Contract Code is required for Monnify external calls"))

	def get_base_url(self):
		# Fallback resolution: check provider doc sandbox_mode and global settings sandbox_mode
		settings = frappe.get_doc("EdgePay Settings")
		sandbox_mode = self.provider_doc.sandbox_mode or settings.sandbox_mode
		
		base_url = self.provider_doc.base_url
		if not base_url:
			if sandbox_mode:
				base_url = "https://sandbox.monnify.com/api"
			else:
				base_url = "https://api.monnify.com/api"
		return base_url

	def build_checkout_payload(self, payment_request):
		return {
			"amount": payment_request.amount,
			"customerName": payment_request.customer_name,
			"customerEmail": payment_request.customer_email,
			"paymentReference": payment_request.request_reference,
			"paymentDescription": payment_request.payment_purpose or "Payment",
			"currencyCode": payment_request.currency,
			"contractCode": getattr(self.provider_doc, "contract_code", None) or "", 
		}

	def parse_checkout_response(self, response):
		return {
			"checkout_url": response.get("checkoutUrl"),
			"provider_reference": response.get("transactionReference"),
			"status": "Initiated"
		}

	def build_verification_payload(self, reference):
		return {
			"transactionReference": reference
		}

	def parse_verification_response(self, response):
		return {
			"amount": response.get("amount"),
			"currency": response.get("currencyCode"),
			"status": self.normalize_transaction_status(response.get("paymentStatus")),
			"provider_reference": response.get("transactionReference"),
			"transaction_reference": response.get("transactionReference"),
			"paid_on": response.get("paidOn"),
			"settlement_status": response.get("settlementStatus") or "Unsettled"
		}

	def verify_webhook_signature(self, payload, headers):
		signature = headers.get("monnify-signature") or headers.get("Monnify-Signature")
		if not signature:
			return False
		secret_key = self.provider_doc.get_password("secret_key")
		if not secret_key:
			return False
		import hmac
		import hashlib
		key = secret_key.encode('utf-8')
		if isinstance(payload, str):
			msg = payload.encode('utf-8')
		else:
			msg = payload
		expected = hmac.new(key, msg, hashlib.sha512).hexdigest()
		return hmac.compare_digest(expected, signature)

	def parse_webhook_payload(self, payload):
		event_data = payload.get("eventData") or {}
		return {
			"amount": event_data.get("amountPaid"),
			"currency": event_data.get("currency"),
			"status": self.normalize_transaction_status(event_data.get("paymentStatus")),
			"provider_reference": event_data.get("transactionReference"),
			"transaction_reference": event_data.get("transactionReference"),
			"paid_on": event_data.get("paidOn"),
			"settlement_status": event_data.get("settlementStatus") or "Unsettled",
			"event_type": payload.get("eventType")
		}

	def get_webhook_event_reference(self, payload):
		return payload.get("eventReference") or payload.get("eventData", {}).get("transactionReference")

	def get_webhook_payment_reference(self, payload):
		return payload.get("eventData", {}).get("paymentReference")

	def get_webhook_transaction_reference(self, payload):
		return payload.get("eventData", {}).get("transactionReference")

	def normalize_transaction_status(self, provider_status):
		status_map = {
			"PAID": "Success",
			"OVERPAID": "Success",
			"PARTIALLY_PAID": "Success",
			"FAILED": "Failed",
			"PENDING": "Pending",
			"EXPIRED": "Failed"
		}
		return status_map.get(provider_status, "Pending")
