import base64
import hashlib

import frappe
import requests
from frappe import _

from edgepayv1.edgepay.services.security import redact_secrets


def get_monnify_token(provider_doc, provider_account):
	"""Fetch/cache a Monnify token for one merchant Provider Account."""
	from edgepayv1.edgepay.services.clients import is_live_call_allowed

	if not is_live_call_allowed(provider_doc, provider_account):
		frappe.throw(_("Live external calls are disabled or the selected Provider Account is not ready"))

	api_key = provider_account.get_password("api_key")
	secret_key = provider_account.get_password("secret_key")
	if not api_key or not secret_key:
		frappe.throw(_("API Key or Secret Key is missing in Monnify Provider Account"))

	creds_hash = hashlib.sha256(f"{api_key}:{secret_key}".encode()).hexdigest()
	cache_key = f"edgepay:monnify_token:{provider_account.name}:{creds_hash}"
	token = frappe.cache().get_value(cache_key)
	if token:
		return token

	settings = frappe.get_doc("EdgePay Settings")
	sandbox_mode = provider_account.environment == "Sandbox" or provider_doc.sandbox_mode or settings.sandbox_mode
	base_url = provider_doc.base_url
	if not base_url:
		base_url = "https://sandbox.monnify.com/api" if sandbox_mode else "https://api.monnify.com/api"
	else:
		base_url = base_url.rstrip("/")
		if base_url.endswith("monnify.com"):
			base_url = f"{base_url}/api"

	raw_creds = f"{api_key}:{secret_key}"
	encoded_creds = base64.b64encode(raw_creds.encode()).decode()
	headers = {"Authorization": f"Basic {encoded_creds}", "Content-Type": "application/json"}
	try:
		response = requests.post(f"{base_url}/v1/auth/login", headers=headers, timeout=10)
		response.raise_for_status()
		resp_json = response.json()
	except Exception as exc:
		frappe.throw(_("Monnify Authentication request failed: {0}").format(redact_secrets(str(exc))))

	if not resp_json.get("requestSuccessful"):
		frappe.throw(_("Monnify Authentication failed: {0}").format(resp_json.get("responseMessage")))
	body = resp_json.get("responseBody") or {}
	access_token = body.get("accessToken")
	expires_in = body.get("expiresIn") or 86400
	if not access_token:
		frappe.throw(_("Monnify Authentication response did not return an accessToken"))
	cache_expiry = max(int(expires_in) - 300, 1)
	frappe.cache().set_value(cache_key, access_token, expires_in_sec=cache_expiry)
	return access_token
