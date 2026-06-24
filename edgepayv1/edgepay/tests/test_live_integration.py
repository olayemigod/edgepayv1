# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from edgepayv1.edgepay.services.clients import MonnifyClient, SimulatedMonnifyClient, get_client, is_live_call_allowed
from edgepayv1.edgepay.services.providers.monnify_auth import get_monnify_token
from edgepayv1.edgepay.services.api import validate_live_provider_readiness
from edgepayv1.edgepay.tests.utils import DatabaseStateBackup
from unittest.mock import patch, MagicMock
import base64
import json

class TestLiveIntegration(FrappeTestCase):
	def setUp(self):
		self.db_backup = DatabaseStateBackup()
		self.db_backup.backup()
		super(TestLiveIntegration, self).setUp()
		
		# Set up settings
		self.settings = frappe.get_doc("EdgePay Settings")
		self.settings.enable_edgepay = 1
		self.settings.allow_external_http_calls = 0 # disabled by default
		self.settings.sandbox_mode = 1
		self.settings.save()
		
		# Set up provider
		self.provider_name = "Test Monnify Live Integration Provider"
		frappe.db.delete("EdgePay Provider", {"provider_code": "monnify"})
		if not frappe.db.exists("EdgePay Provider", self.provider_name):
			self.provider = frappe.get_doc({
				"doctype": "EdgePay Provider",
				"provider_name": self.provider_name,
				"provider_code": "monnify",
				"enabled": 1,
				"sandbox_mode": 1,
				"provider_type": "Monnify",
				"status": "Active",
				"base_url": "https://sandbox.monnify.com/api",
				"api_key": "live_test_api_key",
				"secret_key": "live_test_secret_key",
				"contract_code": "live_test_contract_code"
			}).insert()
		else:
			self.provider = frappe.get_doc("EdgePay Provider", self.provider_name)
			self.provider.enabled = 1
			self.provider.sandbox_mode = 1
			self.provider.api_key = "live_test_api_key"
			self.provider.secret_key = "live_test_secret_key"
			self.provider.contract_code = "live_test_contract_code"
			self.provider.save()

		# Ensure cache is clean
		frappe.cache().delete_keys("edgepay:monnify_token:*")

	def tearDown(self):
		frappe.cache().delete_keys("edgepay:monnify_token:*")
		# Reset settings
		settings = frappe.get_doc("EdgePay Settings")
		settings.allow_external_http_calls = 0
		settings.save()
		if frappe.db.exists("EdgePay Provider", self.provider_name):
			frappe.db.delete("EdgePay Provider", self.provider_name)
		super(TestLiveIntegration, self).tearDown()
		self.db_backup.restore()

	def test_external_http_calls_disabled_by_default(self):
		# Default allow_external_http_calls is 0
		self.assertFalse(is_live_call_allowed(self.provider))

		client = MonnifyClient(self.provider)
		with self.assertRaises(frappe.ValidationError) as context:
			client.post("https://sandbox.monnify.com/api/v1/merchant/transactions/init-transaction", {})
		self.assertIn("external http calls are disabled", str(context.exception).lower())

		with self.assertRaises(frappe.ValidationError) as context:
			client.get("https://sandbox.monnify.com/api/v1/merchant/transactions/query")
		self.assertIn("external http calls are disabled", str(context.exception).lower())

	@patch('requests.post')
	def test_live_monnify_client_makes_call_when_enabled(self, mock_post):
		self.settings.allow_external_http_calls = 1
		self.settings.save()
		self.assertTrue(is_live_call_allowed(self.provider))

		# Mock auth token login response and actual post response
		# First call is token login
		mock_login_resp = MagicMock()
		mock_login_resp.json.return_value = {
			"requestSuccessful": True,
			"responseMessage": "success",
			"responseBody": {
				"accessToken": "mocked_bearer_token_abc_123",
				"expiresIn": 3600
			}
		}
		
		# Second call is the actual client post
		mock_actual_resp = MagicMock()
		mock_actual_resp.json.return_value = {"status": "SUCCESS"}
		
		mock_post.side_effect = [mock_login_resp, mock_actual_resp]

		client = MonnifyClient(self.provider)
		url = "https://sandbox.monnify.com/api/v1/merchant/transactions/init-transaction"
		res = client.post(url, {"test": "data"})

		self.assertEqual(res["status"], "SUCCESS")
		self.assertEqual(mock_post.call_count, 2)

		# Verify token login headers had Basic Auth
		first_call_headers = mock_post.call_args_list[0][1]['headers']
		self.assertTrue(first_call_headers['Authorization'].startswith('Basic '))

		# Verify client post headers had Bearer Auth
		second_call_headers = mock_post.call_args_list[1][1]['headers']
		self.assertEqual(second_call_headers['Authorization'], 'Bearer mocked_bearer_token_abc_123')

	@patch('requests.post')
	def test_token_manager_caches_token_and_refreshes_when_expired(self, mock_post):
		self.settings.allow_external_http_calls = 1
		self.settings.save()

		# Mock auth response
		mock_login_resp = MagicMock()
		mock_login_resp.json.return_value = {
			"requestSuccessful": True,
			"responseMessage": "success",
			"responseBody": {
				"accessToken": "token_val_1",
				"expiresIn": 3600
			}
		}
		mock_post.return_value = mock_login_resp

		# 1. Fetch token first time: makes request
		token1 = get_monnify_token(self.provider)
		self.assertEqual(token1, "token_val_1")
		self.assertEqual(mock_post.call_count, 1)

		# 2. Fetch token second time: gets from cache, does not hit API
		token2 = get_monnify_token(self.provider)
		self.assertEqual(token2, "token_val_1")
		self.assertEqual(mock_post.call_count, 1)

		# 3. Force cache expiration (delete key) and fetch again: hits API
		frappe.cache().delete_keys("edgepay:monnify_token:*")
		
		mock_login_resp_2 = MagicMock()
		mock_login_resp_2.json.return_value = {
			"requestSuccessful": True,
			"responseMessage": "success",
			"responseBody": {
				"accessToken": "token_val_2",
				"expiresIn": 3600
			}
		}
		mock_post.return_value = mock_login_resp_2

		token3 = get_monnify_token(self.provider)
		self.assertEqual(token3, "token_val_2")
		self.assertEqual(mock_post.call_count, 2)

	def test_disabled_provider_blocks_readiness(self):
		self.provider.enabled = 0
		self.provider.save()

		res = validate_live_provider_readiness(self.provider_name)
		self.assertFalse(res["provider_enabled"])

	def test_missing_config_blocks_readiness(self):
		self.provider.api_key = ""
		self.provider.save()

		res = validate_live_provider_readiness(self.provider_name)
		self.assertFalse(res["api_key_present"])

		self.provider.api_key = "live_test_api_key"
		self.provider.secret_key = ""
		self.provider.save()

		res = validate_live_provider_readiness(self.provider_name)
		self.assertFalse(res["secret_key_present"])

	def test_missing_contract_code_blocks_live_validation(self):
		self.provider.contract_code = ""
		self.provider.save()

		self.settings.allow_external_http_calls = 1
		self.settings.save()

		# validate_configuration should throw error when contract_code is missing
		from edgepayv1.edgepay.services.providers.registry import get_provider_instance
		provider_instance = get_provider_instance(self.provider_name)
		with self.assertRaises(frappe.ValidationError) as context:
			provider_instance.validate_configuration()
		self.assertIn("contract code is required", str(context.exception).lower())

	@patch('requests.post')
	def test_secrets_redacted_from_exceptions(self, mock_post):
		self.settings.allow_external_http_calls = 1
		self.settings.save()

		# Make requests throw an exception containing the Basic authorization header or key
		mock_post.side_effect = Exception("Failed connecting with Authorization: Basic "
										  "bGl2ZV90ZXN0X2FwaV9rZXk6bGl2ZV90ZXN0X3NlY3JldF9rZXk=")

		client = MonnifyClient(self.provider)
		url = "https://sandbox.monnify.com/api/v1/merchant/transactions/init-transaction"
		
		with self.assertRaises(frappe.ValidationError) as context:
			client.post(url, {"test": "data"})
		
		# Check that basic authorization is redacted
		err_msg = str(context.exception)
		self.assertNotIn("bGl2ZV90ZXN0X2FwaV9rZXk", err_msg)
		self.assertIn("[REDACTED]", err_msg)
