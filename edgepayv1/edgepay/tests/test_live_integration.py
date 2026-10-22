import base64
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from edgepayv1.edgepay.services.api import validate_live_provider_readiness
from edgepayv1.edgepay.services.clients import MonnifyClient, is_live_call_allowed
from edgepayv1.edgepay.services.providers.monnify_auth import get_monnify_token
from edgepayv1.edgepay.services.providers.registry import get_provider_instance
from edgepayv1.edgepay.tests.utils import (
	DatabaseStateBackup,
	cleanup_test_merchant_provider_account,
	create_test_merchant_provider_account,
)


class TestLiveIntegration(FrappeTestCase):
	def setUp(self):
		self.db_backup = DatabaseStateBackup()
		self.db_backup.backup()
		super().setUp()

		self.settings = frappe.get_doc("EdgePay Settings")
		self.settings.enable_edgepay = 1
		self.settings.allow_external_http_calls = 0
		self.settings.sandbox_mode = 1
		self.settings.save()

		self.provider_name = "Test Monnify Live Integration Provider"
		frappe.db.delete("EdgePay Provider", {"provider_code": "monnify"})
		self.provider = frappe.get_doc(
			{
				"doctype": "EdgePay Provider",
				"provider_name": self.provider_name,
				"provider_code": "monnify",
				"enabled": 1,
				"sandbox_mode": 1,
				"provider_type": "Monnify",
				"status": "Active",
				"base_url": "https://sandbox.monnify.com/api",
				"api_key": "global_api_key_must_not_be_used",
				"secret_key": "global_secret_must_not_be_used",
				"contract_code": "GLOBAL-CONTRACT",
			}
		).insert()
		self.merchant, self.provider_account = create_test_merchant_provider_account(
			self.provider_name,
			"Test Live Integration Merchant",
			api_key="live_test_api_key",
			secret_key="live_test_secret_key",
			contract_code="live_test_contract_code",
		)
		frappe.cache().delete_keys("edgepay:monnify_token:*")

	def tearDown(self):
		frappe.cache().delete_keys("edgepay:monnify_token:*")
		settings = frappe.get_doc("EdgePay Settings")
		settings.allow_external_http_calls = 0
		settings.save()
		cleanup_test_merchant_provider_account(self.merchant, self.provider_name)
		frappe.db.delete("EdgePay Provider", self.provider_name)
		super().tearDown()
		self.db_backup.restore()

	def test_external_http_calls_disabled_by_default(self):
		self.assertFalse(is_live_call_allowed(self.provider, self.provider_account))
		client = MonnifyClient(self.provider, self.provider_account)
		with self.assertRaises(frappe.ValidationError) as context:
			client.post("https://sandbox.monnify.com/api/v1/merchant/transactions/init-transaction", {})
		self.assertIn("external http calls are disabled", str(context.exception).lower())
		with self.assertRaises(frappe.ValidationError):
			client.get("https://sandbox.monnify.com/api/v1/merchant/transactions/query")

	@patch("requests.post")
	def test_live_monnify_client_makes_call_when_enabled(self, mock_post):
		self.settings.allow_external_http_calls = 1
		self.settings.save()
		self.assertTrue(is_live_call_allowed(self.provider, self.provider_account))

		login = MagicMock()
		login.json.return_value = {
			"requestSuccessful": True,
			"responseMessage": "success",
			"responseBody": {"accessToken": "mocked_bearer_token_abc_123", "expiresIn": 3600},
		}
		actual = MagicMock()
		actual.json.return_value = {"status": "SUCCESS"}
		mock_post.side_effect = [login, actual]

		client = MonnifyClient(self.provider, self.provider_account)
		res = client.post(
			"https://sandbox.monnify.com/api/v1/merchant/transactions/init-transaction", {"test": "data"}
		)
		self.assertEqual(res["status"], "SUCCESS")
		self.assertEqual(mock_post.call_count, 2)
		first_headers = mock_post.call_args_list[0][1]["headers"]
		second_headers = mock_post.call_args_list[1][1]["headers"]
		self.assertTrue(first_headers["Authorization"].startswith("Basic "))
		decoded = base64.b64decode(first_headers["Authorization"].split(" ", 1)[1]).decode()
		self.assertEqual(decoded, "live_test_api_key:live_test_secret_key")
		self.assertNotIn("global_api_key_must_not_be_used", decoded)
		self.assertEqual(second_headers["Authorization"], "Bearer mocked_bearer_token_abc_123")

	@patch("requests.post")
	def test_token_manager_caches_by_provider_account(self, mock_post):
		self.settings.allow_external_http_calls = 1
		self.settings.save()
		login = MagicMock()
		login.json.return_value = {
			"requestSuccessful": True,
			"responseMessage": "success",
			"responseBody": {"accessToken": "token_val_1", "expiresIn": 3600},
		}
		mock_post.return_value = login
		token1 = get_monnify_token(self.provider, self.provider_account)
		token2 = get_monnify_token(self.provider, self.provider_account)
		self.assertEqual(token1, "token_val_1")
		self.assertEqual(token2, "token_val_1")
		self.assertEqual(mock_post.call_count, 1)

	def test_disabled_provider_blocks_readiness(self):
		self.provider.enabled = 0
		self.provider.save()
		res = validate_live_provider_readiness(self.provider_name, self.provider_account.name)
		self.assertFalse(res["provider_enabled"])

	def test_missing_account_config_blocks_readiness(self):
		self.provider_account.api_key = ""
		self.provider_account.save()
		res = validate_live_provider_readiness(self.provider_name, self.provider_account.name)
		self.assertFalse(res["api_key_present"])

		self.provider_account.api_key = "live_test_api_key"
		self.provider_account.secret_key = ""
		self.provider_account.save()
		res = validate_live_provider_readiness(self.provider_name, self.provider_account.name)
		self.assertFalse(res["secret_key_present"])

	def test_missing_contract_code_blocks_scoped_validation(self):
		self.provider_account.contract_code = ""
		self.provider_account.save()
		self.settings.allow_external_http_calls = 1
		self.settings.save()
		provider = get_provider_instance(self.provider_name, self.provider_account.name)
		with self.assertRaises(frappe.ValidationError) as context:
			provider.validate_configuration()
		self.assertIn("contract code is required", str(context.exception).lower())

	@patch("requests.post")
	def test_secrets_redacted_from_exceptions(self, mock_post):
		self.settings.allow_external_http_calls = 1
		self.settings.save()
		mock_post.side_effect = Exception(
			"Failed connecting with Authorization: Basic bGl2ZV90ZXN0X2FwaV9rZXk6bGl2ZV90ZXN0X3NlY3JldF9rZXk="
		)
		client = MonnifyClient(self.provider, self.provider_account)
		with self.assertRaises(frappe.ValidationError) as context:
			client.post("https://sandbox.monnify.com/api/v1/merchant/transactions/init-transaction", {})
		err_msg = str(context.exception)
		self.assertNotIn("bGl2ZV90ZXN0X2FwaV9rZXk", err_msg)
		self.assertIn("[REDACTED]", err_msg)
