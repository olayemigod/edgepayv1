# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from edgepayv1.edgepay.tools.monnify_sandbox_smoke import run_monnify_sandbox_smoke
from unittest.mock import patch, MagicMock
from edgepayv1.edgepay.tests.utils import DatabaseStateBackup
import os

class TestSmokeUtility(FrappeTestCase):
	def setUp(self):
		self.db_backup = DatabaseStateBackup()
		self.db_backup.backup()
		super(TestSmokeUtility, self).setUp()
		frappe.db.delete("EdgePay Provider", {"provider_code": "monnify"})
		self.settings = frappe.get_doc("EdgePay Settings")
		self.settings.enable_edgepay = 0
		self.settings.allow_external_http_calls = 0
		self.settings.sandbox_mode = 0
		self.settings.save()
		frappe.db.commit()

	def tearDown(self):
		# Clean up any temporary smoke provider and requests if they leaked
		if frappe.db.exists("EdgePay Provider", "Monnify Sandbox Smoke Test"):
			frappe.db.delete("EdgePay Provider", "Monnify Sandbox Smoke Test")
		
		# Find any requests created by smoke test
		requests = frappe.get_all("EdgePay Payment Request", filters={"source_app": "EdgePay Developer Utility"})
		for r in requests:
			frappe.db.delete("EdgePay Payment Request", r.name)
			frappe.db.delete("EdgePay Payment Transaction", {"payment_request": r.name})

		settings = frappe.get_doc("EdgePay Settings")
		settings.enable_edgepay = 0
		settings.allow_external_http_calls = 0
		settings.sandbox_mode = 0
		settings.save()
		frappe.db.commit()
		super(TestSmokeUtility, self).tearDown()
		self.db_backup.restore()

	def test_refuses_when_env_flag_not_set(self):
		# Enforce environment flag is not set
		with patch.dict(os.environ, {}, clear=True):
			res = run_monnify_sandbox_smoke()
			self.assertFalse(res)

	def test_refuses_when_missing_env_credentials(self):
		with patch.dict(os.environ, {"EDGEPAY_RUN_MONNIFY_SANDBOX_SMOKE": "1"}):
			res = run_monnify_sandbox_smoke()
			self.assertFalse(res)

	@patch('requests.post')
	def test_restores_settings_in_failure_scenarios(self, mock_post):
		# Make requests throw an exception containing the Basic credentials
		mock_post.side_effect = Exception("Monnify API basic credentials: Basic secrets_123_abc")

		# Set environment variables
		env_vars = {
			"EDGEPAY_RUN_MONNIFY_SANDBOX_SMOKE": "1",
			"EDGEPAY_MONNIFY_SANDBOX_API_KEY": "test_api_key",
			"EDGEPAY_MONNIFY_SANDBOX_SECRET_KEY": "test_secret_key",
			"EDGEPAY_MONNIFY_SANDBOX_CONTRACT_CODE": "test_contract_code"
		}
		
		with patch.dict(os.environ, env_vars):
			with self.assertRaises(Exception) as context:
				run_monnify_sandbox_smoke()
			
			# Ensure credentials are redacted from error output
			err_msg = str(context.exception)
			self.assertNotIn("secrets_123_abc", err_msg)
			self.assertIn("[REDACTED]", err_msg)

		# Verify settings are restored to default (disabled)
		settings = frappe.get_doc("EdgePay Settings")
		self.assertEqual(settings.enable_edgepay, 0)
		self.assertEqual(getattr(settings, "allow_external_http_calls", 0), 0)
		self.assertEqual(settings.sandbox_mode, 0)

	@patch('requests.post')
	@patch('requests.get')
	def test_successful_mocked_smoke_run(self, mock_get, mock_post):
		# Mock login response
		mock_login_resp = MagicMock()
		mock_login_resp.json.return_value = {
			"requestSuccessful": True,
			"responseMessage": "success",
			"responseBody": {
				"accessToken": "smoke_mocked_token",
				"expiresIn": 3600
			}
		}
		
		# Mock checkout response
		mock_checkout_resp = MagicMock()
		mock_checkout_resp.json.return_value = {
			"checkoutUrl": "https://sandbox.monnify.com/checkout/SMOKE-REF",
			"transactionReference": "MON-SMOKE-TX",
			"status": "PAID"
		}
		mock_post.side_effect = [mock_login_resp, mock_checkout_resp]

		# Mock verification response
		mock_verify_resp = MagicMock()
		mock_verify_resp.json.return_value = {
			"amount": 10.00,
			"currencyCode": "NGN",
			"paymentStatus": "PAID",
			"transactionReference": "MON-SMOKE-TX",
			"paidOn": "2026-06-12 22:00:00",
			"settlementStatus": "Unsettled"
		}
		mock_get.return_value = mock_verify_resp

		env_vars = {
			"EDGEPAY_RUN_MONNIFY_SANDBOX_SMOKE": "1",
			"EDGEPAY_MONNIFY_SANDBOX_API_KEY": "test_api_key",
			"EDGEPAY_MONNIFY_SANDBOX_SECRET_KEY": "test_secret_key",
			"EDGEPAY_MONNIFY_SANDBOX_CONTRACT_CODE": "test_contract_code"
		}

		with patch.dict(os.environ, env_vars):
			res = run_monnify_sandbox_smoke()
			self.assertTrue(res)

		# Verify settings are restored
		settings = frappe.get_doc("EdgePay Settings")
		self.assertEqual(settings.enable_edgepay, 0)
		self.assertEqual(getattr(settings, "allow_external_http_calls", 0), 0)
