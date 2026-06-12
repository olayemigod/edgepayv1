# -*- coding: utf-8 -*-
import frappe
from frappe import _

class BaseHTTPClient(object):
	def post(self, url, payload, headers=None):
		raise NotImplementedError
	def get(self, url, headers=None):
		raise NotImplementedError

class MonnifyClient(BaseHTTPClient):
	def __init__(self, provider_doc):
		self.provider_doc = provider_doc

	def post(self, url, payload, headers=None):
		# Prevent any live external HTTP calls in this phase
		raise NotImplementedError("Live HTTP calls are not implemented in this phase.")

	def get(self, url, headers=None):
		# Prevent any live external HTTP calls in this phase
		raise NotImplementedError("Live HTTP calls are not implemented in this phase.")

class SimulatedMonnifyClient(BaseHTTPClient):
	def __init__(self, provider_doc=None):
		self.provider_doc = provider_doc
		self.mock_status = "PAID"
		self.mock_amount = 1500.50
		self.mock_paid_on = "2026-06-12 18:00:00"

	def post(self, url, payload, headers=None):
		payment_reference = payload.get("paymentReference", "EP-MOCK-REF")
		return {
			"checkoutUrl": f"https://sandbox.monnify.com/checkout/{payment_reference}",
			"transactionReference": f"MON-{payment_reference}-TX",
			"status": "PAID"
		}

	def get(self, url, headers=None):
		import urllib.parse as urlparse
		parsed = urlparse.urlparse(url)
		params = urlparse.parse_qs(parsed.query)
		ref = params.get("transactionReference", ["MON-MOCK-TX"])[0]
		return {
			"amount": self.mock_amount,
			"paymentStatus": self.mock_status,
			"transactionReference": ref,
			"paidOn": self.mock_paid_on,
			"paymentDescription": "Test Payment",
			"currencyCode": "NGN"
		}

_CLIENT_OVERRIDES = {}

def get_client(provider_code, provider_doc):
	if provider_code in _CLIENT_OVERRIDES:
		return _CLIENT_OVERRIDES[provider_code]
	
	if provider_code == "monnify":
		return MonnifyClient(provider_doc)
		
	raise frappe.ValidationError(_("No client found for provider code: {0}").format(provider_code))

def set_client_override(provider_code, client_instance):
	_CLIENT_OVERRIDES[provider_code] = client_instance

def clear_client_overrides():
	_CLIENT_OVERRIDES.clear()
