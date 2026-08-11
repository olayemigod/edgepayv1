import frappe
from frappe import _

from edgepayv1.edgepay.services.providers.monnify import MonnifyProvider

_PROVIDER_MAP = {"monnify": MonnifyProvider}


def get_provider_instance(provider_name, provider_account=None):
	"""Return a provider runtime bound to an optional merchant Provider Account."""
	provider_doc = (
		frappe.get_doc("EdgePay Provider", provider_name)
		if isinstance(provider_name, str)
		else provider_name
	)
	if not provider_doc:
		frappe.throw(_("Provider Configuration not found"))

	provider_code = provider_doc.provider_code.lower() if provider_doc.provider_code else ""
	if provider_code not in _PROVIDER_MAP:
		frappe.throw(_("Unsupported provider code: {0}").format(provider_code))
	if not provider_doc.enabled:
		frappe.throw(_("Provider {0} is disabled").format(provider_doc.provider_name))

	account_doc = None
	if provider_account:
		account_doc = (
			frappe.get_doc("EdgePay Provider Account", provider_account)
			if isinstance(provider_account, str)
			else provider_account
		)
		if account_doc.provider != provider_doc.name:
			frappe.throw(_("Provider Account does not match the selected Provider"))

	return _PROVIDER_MAP[provider_code](provider_doc, provider_account=account_doc)
