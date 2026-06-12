# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from edgepayv1.edgepay.services.providers.registry import get_provider_instance
from edgepayv1.edgepay.services.security import redact_secrets

class TestProviderFoundation(FrappeTestCase):
	def setUp(self):
		# Create test provider if it doesn't exist
		if not frappe.db.exists("EdgePay Provider", "Test Monnify"):
			self.provider = frappe.get_doc({
				"doctype": "EdgePay Provider",
				"provider_name": "Test Monnify",
				"provider_code": "monnify",
				"enabled": 1,
				"sandbox_mode": 1,
				"base_url": "https://sandbox.monnify.com/api",
				"api_key": "test_api_key",
				"secret_key": "test_secret_key",
				"provider_type": "Monnify",
				"status": "Active"
			}).insert()
		else:
			self.provider = frappe.get_doc("EdgePay Provider", "Test Monnify")
			# Ensure it is enabled and reset to original test values
			self.provider.enabled = 1
			self.provider.base_url = "https://sandbox.monnify.com/api"
			self.provider.sandbox_mode = 1
			self.provider.api_key = "test_api_key"
			self.provider.secret_key = "test_secret_key"
			self.provider.save()

	def test_registry_loads_monnify(self):
		instance = get_provider_instance("Test Monnify")
		self.assertEqual(instance.get_provider_code(), "monnify")

	def test_disabled_provider_rejected(self):
		# Temporarily disable the provider
		self.provider.enabled = 0
		self.provider.save()

		with self.assertRaises(frappe.ValidationError) as context:
			get_provider_instance("Test Monnify")
		self.assertIn("disabled", str(context.exception).lower())

		# Restore enabled state
		self.provider.enabled = 1
		self.provider.save()

	def test_unknown_provider_rejected(self):
		# Test using a doc with unsupported provider code (paystack is now unsupported)
		doc = frappe.get_doc({
			"doctype": "EdgePay Provider",
			"provider_name": "Unknown Pay",
			"provider_code": "paystack",
			"enabled": 1,
			"provider_type": "Other",
			"status": "Active"
		})
		with self.assertRaises(frappe.ValidationError) as context:
			get_provider_instance(doc)
		self.assertIn("unsupported provider code", str(context.exception).lower())

	def test_sandbox_url_resolution(self):
		instance = get_provider_instance("Test Monnify")
		self.assertEqual(instance.get_base_url(), "https://sandbox.monnify.com/api")

		self.provider.base_url = ""
		self.provider.sandbox_mode = 1
		self.provider.save()
		instance = get_provider_instance("Test Monnify")
		self.assertEqual(instance.get_base_url(), "https://sandbox.monnify.com/api")

		self.provider.sandbox_mode = 0
		settings = frappe.get_doc("EdgePay Settings")
		old_sandbox = settings.sandbox_mode
		settings.sandbox_mode = 0
		settings.save()
		
		self.provider.save()
		instance = get_provider_instance("Test Monnify")
		self.assertEqual(instance.get_base_url(), "https://api.monnify.com/api")
		
		settings.sandbox_mode = old_sandbox
		settings.save()

	def test_missing_config_caught(self):
		self.provider.api_key = ""
		self.provider.save()
		instance = get_provider_instance("Test Monnify")
		with self.assertRaises(frappe.ValidationError) as context:
			instance.validate_configuration()
		self.assertIn("api key", str(context.exception).lower())

	def test_secret_redaction(self):
		payload = {
			"api_key": "super_secret_api_key",
			"normal_field": "public_data",
			"headers": {
				"Authorization": "Bearer some_bearer_token_12345",
				"Custom": "Hello"
			},
			"list_field": [
				{"secret_key": "some_secret_key"},
				"plain_string"
			]
		}
		redacted = redact_secrets(payload)
		self.assertEqual(redacted["api_key"], "[REDACTED]")
		self.assertEqual(redacted["normal_field"], "public_data")
		self.assertEqual(redacted["headers"]["Authorization"], "[REDACTED]")
		self.assertEqual(redacted["headers"]["Custom"], "Hello")
		self.assertEqual(redacted["list_field"][0]["secret_key"], "[REDACTED]")
		self.assertEqual(redacted["list_field"][1], "plain_string")
