# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from edgepayv1.edgepay.services.clients import set_client_override, clear_client_overrides, SimulatedMonnifyClient
from edgepayv1.edgepay.tests.utils import DatabaseStateBackup
from edgepayv1.edgepay.sdk import (
	create_source_payment_request,
	initialize_source_checkout,
	verify_source_payment,
	get_source_payment_status,
	get_source_transaction_status,
	get_connector_profile,
	CONNECTOR_PROFILES,
	ConnectorProfile
)
import json
import os

class TestEdgePaySDK(FrappeTestCase):
	def setUp(self):
		self.db_backup = DatabaseStateBackup()
		self.db_backup.backup()
		super(TestEdgePaySDK, self).setUp()
		clear_client_overrides()
		
		# Override client with simulator to prevent external calls
		self.mock_client = SimulatedMonnifyClient()
		self.mock_client.mock_amount = 3000.00
		set_client_override("monnify", self.mock_client)
		
		# Configure settings to enable EdgePay in sandbox mode
		self.settings = frappe.get_doc("EdgePay Settings")
		self.settings.sandbox_mode = 1
		self.settings.enable_edgepay = 1
		self.settings.allow_external_http_calls = 0
		self.settings.save()
		
		# Set up mock provider
		self.provider_name = "Test SDK Provider"
		frappe.db.delete("EdgePay Provider", {"provider_code": "monnify"})

		self.provider = frappe.get_doc({
			"doctype": "EdgePay Provider",
			"provider_name": self.provider_name,
			"provider_code": "monnify",
			"enabled": 1,
			"sandbox_mode": 1,
			"provider_type": "Monnify",
			"status": "Active",
			"base_url": "https://sandbox.monnify.com/api",
			"api_key": "test_api_key",
			"secret_key": "test_secret_key"
		}).insert()

		frappe.set_user("Administrator")

	def tearDown(self):
		clear_client_overrides()
		frappe.set_user("Administrator")
		if frappe.db.exists("EdgePay Provider", self.provider_name):
			frappe.db.delete("EdgePay Provider", self.provider_name)
		# Clean up any created Payment Requests during test
		frappe.db.delete("EdgePay Payment Request", {"provider": self.provider_name})
		super(TestEdgePaySDK, self).tearDown()
		self.db_backup.restore()

	def test_sdk_create_source_payment_request(self):
		context = {
			"provider": "Test SDK Provider",
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-SDK-0001",
			"amount": 3000.00,
			"currency": "NGN",
			"customer_name": "Bob",
			"customer_email": "bob@retail.com"
		}
		res = create_source_payment_request(context)
		self.assertTrue(res["ok"])
		self.assertEqual(res["status"], "success")
		self.assertEqual(res["data"]["amount"], 3000.00)
		self.assertEqual(res["data"]["currency"], "NGN")
		self.assertEqual(res["data"]["provider"], "Test SDK Provider")

		# Verify DB document exists
		pr_name = res["data"]["payment_request"]
		pr = frappe.get_doc("EdgePay Payment Request", pr_name)
		self.assertEqual(pr.source_app, "RetailEdge")
		self.assertEqual(pr.source_doctype, "Sales Invoice")
		self.assertEqual(pr.source_name, "SINV-SDK-0001")

	def test_sdk_initialize_source_checkout(self):
		context = {
			"provider": "Test SDK Provider",
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-SDK-0002",
			"amount": 3000.00,
			"currency": "NGN",
			"customer_name": "Bob",
			"customer_email": "bob@retail.com"
		}
		res = create_source_payment_request(context)
		pr_name = res["data"]["payment_request"]

		# Initialize checkout via SDK
		init_res = initialize_source_checkout(pr_name)
		self.assertTrue(init_res["ok"])
		self.assertEqual(init_res["status"], "success")
		
		# Verify safe checkout fields returned only
		data = init_res["data"]
		self.assertEqual(data["payment_request"], pr_name)
		self.assertEqual(data["status"], "Initiated")
		pr = frappe.get_doc("EdgePay Payment Request", pr_name)
		self.assertEqual(data["checkout_url"], pr.checkout_url)
		self.assertEqual(data["provider_reference"], pr.provider_reference)
		self.assertTrue("expires_on" in data)

		# Verify raw/private provider fields are NOT returned
		self.assertNotIn("apiKey", data)
		self.assertNotIn("clientTemplates", data)
		self.assertNotIn("secretKey", data)

	def test_sdk_verify_source_payment(self):
		context = {
			"provider": "Test SDK Provider",
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-SDK-0003",
			"amount": 3000.00,
			"currency": "NGN",
			"customer_name": "Bob",
			"customer_email": "bob@retail.com"
		}
		res = create_source_payment_request(context)
		pr_name = res["data"]["payment_request"]

		# Initialize checkout first
		initialize_source_checkout(pr_name)

		# Verify payment via SDK
		verify_res = verify_source_payment(pr_name)
		self.assertTrue(verify_res["ok"])
		self.assertEqual(verify_res["status"], "success")

		# Verify safe status fields returned only
		data = verify_res["data"]
		self.assertEqual(data["payment_request"], pr_name)
		self.assertEqual(data["request_status"], "Paid")
		self.assertEqual(data["transaction_status"], "Success")
		pr = frappe.get_doc("EdgePay Payment Request", pr_name)
		self.assertEqual(data["provider_reference"], pr.provider_reference)
		self.assertEqual(data["amount"], 3000.00)
		self.assertEqual(data["currency"], "NGN")
		self.assertTrue("paid_on" in data)

		# Ensure no secrets leak
		self.assertNotIn("secret_key", data)
		self.assertNotIn("api_key", data)

	def test_sdk_status_functions_do_not_mutate(self):
		context = {
			"provider": "Test SDK Provider",
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-SDK-0004",
			"amount": 3000.00,
			"currency": "NGN",
			"customer_name": "Bob",
			"customer_email": "bob@retail.com"
		}
		res = create_source_payment_request(context)
		pr_name = res["data"]["payment_request"]

		# Capture status in DB before calling get_source_payment_status
		pr_before = frappe.get_doc("EdgePay Payment Request", pr_name)
		
		# Get payment status
		status_res = get_source_payment_status(pr_name)
		self.assertTrue(status_res["ok"])
		self.assertEqual(status_res["data"]["status"], "Draft")

		# Ensure it's in Draft and DB was not mutated
		pr_after = frappe.get_doc("EdgePay Payment Request", pr_name)
		self.assertEqual(pr_after.status, "Draft")
		self.assertEqual(pr_before.modified, pr_after.modified)

		# Verify transaction status check handles no transaction gracefully without mutating
		tx_res = get_source_transaction_status(payment_request_name=pr_name)
		self.assertFalse(tx_res["ok"])
		self.assertEqual(tx_res["status"], "error")
		self.assertIn("transaction not found", tx_res["message"].lower())

	def test_connector_profiles_without_imports(self):
		# Verify known profiles exist
		for app in ["erpnext", "posnext", "retailedge", "vetedge", "edgesuite"]:
			profile = get_connector_profile(app)
			self.assertEqual(profile.name, app)
			self.assertTrue(len(profile.expected_fields) > 0)

		# Verify fallback generic profile
		fallback = get_connector_profile("unknown_app")
		self.assertEqual(fallback.name, "generic")
		self.assertIn("source_app", fallback.expected_fields)

	def test_sdk_responses_redact_secrets(self):
		context = {
			"provider": "Test SDK Provider",
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-SDK-0005",
			"amount": 3000.00,
			"currency": "NGN",
			"customer_name": "Bob",
			"customer_email": "bob@retail.com",
			"metadata_json": '{"api_key": "my_secret_key", "bearer_token": "my_token"}'
		}
		res = create_source_payment_request(context)
		self.assertTrue(res["ok"])

		res_str = json.dumps(res).lower()
		self.assertNotIn("my_secret_key", res_str)
		self.assertNotIn("my_token", res_str)

	def test_static_import_scan_for_decoupling(self):
		import os
		edgepay_dir = os.path.dirname(os.path.dirname(__file__))
		
		# Define absolute non-import patterns for external apps dynamically to avoid self-matching
		forbidden_apps = ["erpnext", "posnext", "retailedge", "vetedge", "coreedge", "pos_next"]

		for root, _, files in os.walk(edgepay_dir):
			# Skip virtualenv/cache/etc if they are in the directory
			if "node_modules" in root or "__pycache__" in root or ".frappe" in root:
				continue
			for file in files:
				if file.endswith(".py"):
					file_path = os.path.join(root, file)
					with open(file_path, "r", encoding="utf-8") as f:
						content = f.read()
						for app in forbidden_apps:
							self.assertNotIn(
								f"import {app}", 
								content, 
								f"Forbidden import pattern 'import {app}' found in {file_path}"
							)
							self.assertNotIn(
								f"from {app}", 
								content, 
								f"Forbidden import pattern 'from {app}' found in {file_path}"
							)
