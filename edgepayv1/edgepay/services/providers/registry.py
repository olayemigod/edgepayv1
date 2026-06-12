# -*- coding: utf-8 -*-
import frappe
from frappe import _
from edgepayv1.edgepay.services.providers.monnify import MonnifyProvider

_PROVIDER_MAP = {
	"monnify": MonnifyProvider
}

def get_provider_instance(provider_name):
	"""
	Returns a configured provider instance for the given provider_name.
	Accepts either the DocType name of the Provider or a Provider document object.
	"""
	if isinstance(provider_name, str):
		provider_doc = frappe.get_doc("EdgePay Provider", provider_name)
	else:
		provider_doc = provider_name

	if not provider_doc:
		frappe.throw(_("Provider Configuration not found"))

	provider_code = provider_doc.provider_code.lower() if provider_doc.provider_code else ""
	
	if provider_code not in _PROVIDER_MAP:
		frappe.throw(_("Unsupported provider code: {0}").format(provider_code))

	if not provider_doc.enabled:
		frappe.throw(_("Provider {0} is disabled").format(provider_doc.provider_name))

	provider_class = _PROVIDER_MAP[provider_code]
	
	return provider_class(provider_doc)
