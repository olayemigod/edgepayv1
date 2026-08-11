import frappe


class DatabaseStateBackup:
	def __init__(self):
		self.saved_providers = []
		self.saved_settings = None
		self.saved_settings_provider = None

	def backup(self):
		# 1. Backup any existing monnify providers
		providers = frappe.get_all("EdgePay Provider", filters={"provider_code": "monnify"}, fields=["name"])
		for p in providers:
			try:
				doc = frappe.get_doc("EdgePay Provider", p.name)
				doc_dict = doc.as_dict()
				doc_dict["api_key"] = doc.get_password("api_key")
				doc_dict["secret_key"] = doc.get_password("secret_key")
				self.saved_providers.append(doc_dict)
			except Exception:
				pass

		# 2. Backup settings and temporarily clear default_provider to avoid link validation issues
		if frappe.db.exists("EdgePay Settings", "EdgePay Settings"):
			try:
				settings = frappe.get_doc("EdgePay Settings", "EdgePay Settings")
				self.saved_settings = settings.as_dict()
				if settings.default_provider:
					self.saved_settings_provider = settings.default_provider
					settings.default_provider = None
					settings.save(ignore_permissions=True)
					frappe.db.commit()
			except Exception:
				pass

	def restore(self):
		# 1. Restore settings
		if self.saved_settings:
			try:
				settings = frappe.get_doc("EdgePay Settings", "EdgePay Settings")
				for k, v in self.saved_settings.items():
					if k not in ["modified", "modified_by", "creation", "owner"]:
						settings.set(k, v)
				# Ensure we also restore default_provider field properly if it was cleared
				if self.saved_settings_provider:
					settings.default_provider = self.saved_settings_provider
				settings.save(ignore_permissions=True)
				frappe.db.commit()
			except Exception:
				pass

		# 2. Restore providers
		for p_dict in self.saved_providers:
			try:
				name = p_dict.get("name")
				if not frappe.db.exists("EdgePay Provider", name):
					# Delete any provider occupying the same provider_code before restoring
					frappe.db.delete("EdgePay Provider", {"provider_code": p_dict.get("provider_code")})
					doc = frappe.get_doc(p_dict)
					doc.insert(ignore_permissions=True)
					frappe.db.commit()
			except Exception:
				pass


def create_test_merchant_provider_account(
	provider,
	merchant_name,
	api_key="test_api_key",
	secret_key="test_secret_key",
	contract_code="test_contract_code",
	webhook_token=None,
):
	"""Create an isolated sandbox Merchant and active Provider Account for legacy payment tests."""
	if frappe.db.exists("EdgePay Merchant", merchant_name):
		merchant = frappe.get_doc("EdgePay Merchant", merchant_name)
	else:
		merchant = frappe.get_doc(
			{
				"doctype": "EdgePay Merchant",
				"merchant_name": merchant_name,
				"status": "Draft",
				"legal_name": merchant_name,
				"email": "edgepay-tests@example.com",
				"country": "Nigeria",
				"default_currency": "NGN",
			}
		).insert(ignore_permissions=True)

	frappe.db.delete(
		"EdgePay Provider Account",
		{"merchant": merchant.name, "provider": provider, "environment": "Sandbox"},
	)
	account = frappe.get_doc(
		{
			"doctype": "EdgePay Provider Account",
			"merchant": merchant.name,
			"provider": provider,
			"account_label": "Test Primary",
			"environment": "Sandbox",
			"enabled": 1,
			"status": "Active",
			"api_key": api_key,
			"secret_key": secret_key,
			"contract_code": contract_code,
			"webhook_token": webhook_token,
		}
	).insert(ignore_permissions=True)
	return merchant, account


def cleanup_test_merchant_provider_account(merchant, provider):
	"""Remove only the isolated merchant/provider-account fixtures created by tests."""
	if merchant:
		merchant_name = merchant.name if hasattr(merchant, "name") else merchant
		frappe.db.delete("EdgePay Provider Account", {"merchant": merchant_name, "provider": provider})
		frappe.db.delete("EdgePay Merchant User", {"merchant": merchant_name})
		frappe.db.delete("EdgePay Merchant", merchant_name)
