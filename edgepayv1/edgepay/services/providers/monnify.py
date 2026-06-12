# -*- coding: utf-8 -*-
import frappe
from edgepayv1.edgepay.services.providers.base import BaseProvider
from frappe import _

class MonnifyProvider(BaseProvider):
	def validate_configuration(self):
		if not self.provider_doc.base_url:
			# Fallback url resolution checks are handled in get_base_url,
			# but require api/secret keys to be populated.
			pass
		if not self.provider_doc.api_key:
			frappe.throw(_("API Key / Public Key is missing in Monnify configuration"))
		if not self.provider_doc.secret_key:
			frappe.throw(_("Secret Key is missing in Monnify configuration"))

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
			"contractCode": "", 
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
			"status": self.normalize_transaction_status(response.get("paymentStatus")),
			"provider_reference": response.get("transactionReference")
		}

	def verify_webhook_signature(self, payload, headers):
		return True

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
