# -*- coding: utf-8 -*-
import frappe
from frappe import _
import requests
import base64
import json
from edgepayv1.edgepay.services.security import redact_secrets

def get_monnify_token(provider_doc):
	"""
	Fetches a cached bearer token for Monnify, or generates a new one if expired or not found.
	Strictly respects live-call gating.
	"""
	from edgepayv1.edgepay.services.clients import is_live_call_allowed
	if not is_live_call_allowed(provider_doc):
		frappe.throw(_("Live external calls are disabled. Cannot fetch authentication token."))

	provider_name = provider_doc.name
	api_key = None
	secret_key = None
	if provider_doc.api_key:
		try:
			api_key = provider_doc.get_password("api_key")
		except Exception:
			pass
	if provider_doc.secret_key:
		try:
			secret_key = provider_doc.get_password("secret_key")
		except Exception:
			pass
	
	if not api_key or not secret_key:
		frappe.throw(_("API Key or Secret Key is missing in Monnify provider configuration"))

	import hashlib
	creds_hash = hashlib.sha256(f"{api_key}:{secret_key}".encode('utf-8')).hexdigest()
	cache_key = f"edgepay:monnify_token:{provider_name}:{creds_hash}"

	# Try getting token from cache
	token = frappe.cache().get_value(cache_key)
	if token:
		return token

	# If not in cache, request a new token
	settings = frappe.get_doc("EdgePay Settings")
	sandbox_mode = provider_doc.sandbox_mode or settings.sandbox_mode
	base_url = provider_doc.base_url
	if not base_url:
		if sandbox_mode:
			base_url = "https://sandbox.monnify.com/api"
		else:
			base_url = "https://api.monnify.com/api"

	url = f"{base_url}/v1/auth/login"

	# Build base64 credentials for Basic Auth
	raw_creds = f"{api_key}:{secret_key}"
	encoded_creds = base64.b64encode(raw_creds.encode('utf-8')).decode('utf-8')

	headers = {
		"Authorization": f"Basic {encoded_creds}",
		"Content-Type": "application/json"
	}

	try:
		# Use timeout=10 for login endpoint
		response = requests.post(url, headers=headers, timeout=10)
		response.raise_for_status()
		resp_json = response.json()
	except Exception as e:
		redacted_err = redact_secrets(str(e))
		frappe.throw(_("Monnify Authentication request failed: {0}").format(redacted_err))

	if not resp_json.get("requestSuccessful"):
		frappe.throw(_("Monnify Authentication failed: {0}").format(resp_json.get("responseMessage")))

	body = resp_json.get("responseBody") or {}
	access_token = body.get("accessToken")
	expires_in = body.get("expiresIn") or 86400

	if not access_token:
		frappe.throw(_("Monnify Authentication response did not return an accessToken"))

	# Cache token with a safety buffer of 300 seconds (5 minutes)
	cache_expiry = int(expires_in) - 300
	if cache_expiry <= 0:
		cache_expiry = int(expires_in)

	frappe.cache().set_value(cache_key, access_token, expires_in_sec=cache_expiry)

	return access_token
