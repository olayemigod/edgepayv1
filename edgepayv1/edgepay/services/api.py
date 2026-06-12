# -*- coding: utf-8 -*-
import frappe
from edgepayv1.edgepay.services.providers.registry import get_provider_instance

@frappe.whitelist()
def validate_provider_configuration(provider_name):
	"""
	Validates local provider configuration without making external calls.
	"""
	try:
		provider = get_provider_instance(provider_name)
		provider.validate_configuration()
		return {"status": "success", "message": "Configuration is valid"}
	except Exception as e:
		return {"status": "error", "message": str(e)}

@frappe.whitelist()
def get_provider_health(provider_name):
	"""
	Validates local provider health/readiness.
	"""
	try:
		provider = get_provider_instance(provider_name)
		provider.validate_configuration()
		return {"status": "healthy", "provider": provider.get_provider_code()}
	except Exception as e:
		return {"status": "unhealthy", "error": str(e)}

@frappe.whitelist()
def validate_live_provider_readiness(provider_name):
	"""
	Returns a safe diagnostics report about provider readiness for live calls.
	Never returns actual keys/tokens.
	"""
	try:
		if not frappe.db.exists("EdgePay Provider", provider_name):
			frappe.throw(_("Provider {0} not found").format(provider_name))

		provider_doc = frappe.get_doc("EdgePay Provider", provider_name)
		settings = frappe.get_doc("EdgePay Settings")

		# Safe check of attributes without returning actual passwords
		api_key_present = False
		if provider_doc.api_key:
			try:
				api_key_present = bool(provider_doc.get_password("api_key"))
			except Exception:
				pass

		secret_key_present = False
		if provider_doc.secret_key:
			try:
				secret_key_present = bool(provider_doc.get_password("secret_key"))
			except Exception:
				pass

		return {
			"provider_name": provider_name,
			"provider_enabled": bool(provider_doc.enabled),
			"sandbox_mode": bool(provider_doc.sandbox_mode or settings.sandbox_mode),
			"contract_code_present": bool(getattr(provider_doc, "contract_code", None)),
			"api_key_present": api_key_present,
			"secret_key_present": secret_key_present,
			"external_calls_enabled": bool(getattr(settings, "allow_external_http_calls", 0)),
			"edgepay_enabled": bool(settings.enable_edgepay)
		}
	except Exception as e:
		return {"status": "error", "message": str(e)}
