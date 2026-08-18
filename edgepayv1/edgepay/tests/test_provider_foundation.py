import frappe
from frappe.tests.utils import FrappeTestCase

from edgepayv1.edgepay.services.providers.registry import get_provider_instance
from edgepayv1.edgepay.services.security import redact_secrets
from edgepayv1.edgepay.tests.utils import (
	DatabaseStateBackup,
	cleanup_test_merchant_provider_account,
	create_test_merchant_provider_account,
)


class TestProviderFoundation(FrappeTestCase):
	def setUp(self):
		self.db_backup = DatabaseStateBackup()
		self.db_backup.backup()
		super().setUp()
		frappe.db.delete("EdgePay Provider", {"provider_code": "monnify"})
		self.provider = frappe.get_doc(
			{
				"doctype": "EdgePay Provider",
				"provider_name": "Test Monnify",
				"provider_code": "monnify",
				"enabled": 1,
				"sandbox_mode": 1,
				"base_url": "https://sandbox.monnify.com/api",
				"api_key": "global_api_key_not_runtime",
				"secret_key": "global_secret_not_runtime",
				"provider_type": "Monnify",
				"status": "Active",
			}
		).insert()
		self.merchant, self.provider_account = create_test_merchant_provider_account(
			self.provider.name,
			"Test Provider Foundation Merchant",
			api_key="test_api_key",
			secret_key="test_secret_key",
			contract_code="test_contract_code",
		)

	def tearDown(self):
		cleanup_test_merchant_provider_account(self.merchant, self.provider.name)
		frappe.db.delete("EdgePay Provider", self.provider.name)
		super().tearDown()
		self.db_backup.restore()

	def test_registry_loads_monnify(self):
		instance = get_provider_instance(self.provider.name)
		self.assertEqual(instance.get_provider_code(), "monnify")

	def test_disabled_provider_rejected(self):
		self.provider.enabled = 0
		self.provider.save()
		with self.assertRaises(frappe.ValidationError) as context:
			get_provider_instance(self.provider.name)
		self.assertIn("disabled", str(context.exception).lower())

	def test_unknown_provider_rejected(self):
		doc = frappe.get_doc(
			{
				"doctype": "EdgePay Provider",
				"provider_name": "Unknown Pay",
				"provider_code": "paystack",
				"enabled": 1,
				"provider_type": "Other",
				"status": "Active",
			}
		)
		with self.assertRaises(frappe.ValidationError) as context:
			get_provider_instance(doc)
		self.assertIn("unsupported provider code", str(context.exception).lower())

	def test_sandbox_url_resolution(self):
		instance = get_provider_instance(self.provider.name)
		self.assertEqual(instance.get_base_url(), "https://sandbox.monnify.com/api")
		self.provider.base_url = ""
		self.provider.sandbox_mode = 1
		self.provider.save()
		self.assertEqual(
			get_provider_instance(self.provider.name).get_base_url(), "https://sandbox.monnify.com/api"
		)

	def test_missing_scoped_config_caught(self):
		self.provider_account.api_key = ""
		self.provider_account.save()
		instance = get_provider_instance(self.provider.name, self.provider_account.name)
		with self.assertRaises(frappe.ValidationError) as context:
			instance.validate_configuration()
		self.assertIn("api key", str(context.exception).lower())

	def test_global_provider_credentials_are_not_runtime_credentials(self):
		instance = get_provider_instance(self.provider.name, self.provider_account.name)
		self.assertEqual(instance.get_credentials_doc().name, self.provider_account.name)
		payload = instance.build_checkout_payload(
			frappe._dict(
				name="TEST-PR",
				amount=100,
				customer_name="Customer",
				customer_email="customer@example.com",
				payment_purpose="Test",
				currency="NGN",
			)
		)
		self.assertEqual(payload["contractCode"], "test_contract_code")

	def test_secret_redaction(self):
		payload = {
			"api_key": "super_secret_api_key",
			"normal_field": "public_data",
			"headers": {"Authorization": "Bearer some_bearer_token_12345", "Custom": "Hello"},
			"list_field": [{"secret_key": "some_secret_key"}, "plain_string"],
		}
		redacted = redact_secrets(payload)
		self.assertEqual(redacted["api_key"], "[REDACTED]")
		self.assertEqual(redacted["normal_field"], "public_data")
		self.assertEqual(redacted["headers"]["Authorization"], "[REDACTED]")
		self.assertEqual(redacted["headers"]["Custom"], "Hello")
		self.assertEqual(redacted["list_field"][0]["secret_key"], "[REDACTED]")
		self.assertEqual(redacted["list_field"][1], "plain_string")
