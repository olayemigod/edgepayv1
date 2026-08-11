import frappe
from frappe import _


class BaseHTTPClient:
	def post(self, url, payload, headers=None):
		raise NotImplementedError

	def get(self, url, headers=None):
		raise NotImplementedError


class MonnifyClient(BaseHTTPClient):
	def __init__(self, provider_doc, provider_account=None):
		self.provider_doc = provider_doc
		self.provider_account = provider_account
		self.timeout = 30

	def post(self, url, payload, headers=None):
		if not is_live_call_allowed(self.provider_doc, self.provider_account):
			frappe.throw(_("External HTTP calls are disabled or the selected Provider Account is not ready"))
		from edgepayv1.edgepay.services.providers.monnify_auth import get_monnify_token

		token = get_monnify_token(self.provider_doc, self.provider_account)
		headers = headers or {}
		headers["Authorization"] = f"Bearer {token}"
		headers["Content-Type"] = "application/json"
		import requests

		from edgepayv1.edgepay.services.security import redact_secrets

		try:
			response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
			response.raise_for_status()
			return response.json()
		except Exception as exc:
			frappe.throw(_("Monnify API POST call failed: {0}").format(redact_secrets(str(exc))))

	def get(self, url, headers=None):
		if not is_live_call_allowed(self.provider_doc, self.provider_account):
			frappe.throw(_("External HTTP calls are disabled or the selected Provider Account is not ready"))
		from edgepayv1.edgepay.services.providers.monnify_auth import get_monnify_token

		token = get_monnify_token(self.provider_doc, self.provider_account)
		headers = headers or {}
		headers["Authorization"] = f"Bearer {token}"
		import requests

		from edgepayv1.edgepay.services.security import redact_secrets

		try:
			response = requests.get(url, headers=headers, timeout=self.timeout)
			response.raise_for_status()
			return response.json()
		except Exception as exc:
			frappe.throw(_("Monnify API GET call failed: {0}").format(redact_secrets(str(exc))))


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
			"status": "PAID",
		}

	def get(self, url, headers=None):
		import urllib.parse as urlparse

		params = urlparse.parse_qs(urlparse.urlparse(url).query)
		ref = params.get("transactionReference", ["MON-MOCK-TX"])[0]
		return {
			"amount": self.mock_amount,
			"paymentStatus": self.mock_status,
			"transactionReference": ref,
			"paidOn": self.mock_paid_on,
			"paymentDescription": "Test Payment",
			"currencyCode": "NGN",
		}


_CLIENT_OVERRIDES = {}


def get_client(provider_code, provider_doc, provider_account=None):
	if provider_code in _CLIENT_OVERRIDES:
		return _CLIENT_OVERRIDES[provider_code]
	if provider_code == "monnify":
		return MonnifyClient(provider_doc, provider_account=provider_account)
	raise frappe.ValidationError(_("No client found for provider code: {0}").format(provider_code))


def set_client_override(provider_code, client_instance):
	_CLIENT_OVERRIDES[provider_code] = client_instance


def clear_client_overrides():
	_CLIENT_OVERRIDES.clear()


def is_live_call_allowed(provider_doc, provider_account=None):
	if not frappe.db.exists("EdgePay Settings", "EdgePay Settings"):
		return False
	settings = frappe.get_doc("EdgePay Settings")
	if not settings.enable_edgepay or not getattr(settings, "allow_external_http_calls", 0):
		return False
	if not provider_doc.enabled or not provider_account:
		return False
	if not provider_account.enabled or provider_account.status != "Active":
		return False
	api_key = provider_account.get_password("api_key", raise_exception=False)
	secret_key = provider_account.get_password("secret_key", raise_exception=False)
	return bool(api_key and secret_key)
