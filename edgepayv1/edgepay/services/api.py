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
