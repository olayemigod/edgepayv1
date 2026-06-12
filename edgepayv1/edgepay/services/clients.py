# -*- coding: utf-8 -*-
import frappe
from frappe import _

class BaseHTTPClient(object):
	def post(self, url, payload, headers=None):
		raise NotImplementedError

class MonnifyClient(BaseHTTPClient):
	def __init__(self, provider_doc):
		self.provider_doc = provider_doc

	def post(self, url, payload, headers=None):
		# Prevent any live external HTTP calls in this phase
		raise NotImplementedError("Live HTTP calls are not implemented in this phase.")

class SimulatedMonnifyClient(BaseHTTPClient):
	def __init__(self, provider_doc=None):
		self.provider_doc = provider_doc

	def post(self, url, payload, headers=None):
		payment_reference = payload.get("paymentReference", "EP-MOCK-REF")
		return {
			"checkoutUrl": f"https://sandbox.monnify.com/checkout/{payment_reference}",
			"transactionReference": f"MON-{payment_reference}-TX",
			"status": "PAID"
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
