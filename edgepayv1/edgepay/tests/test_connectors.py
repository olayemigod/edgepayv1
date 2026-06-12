# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from edgepayv1.edgepay.services.clients import set_client_override, clear_client_overrides, SimulatedMonnifyClient
from edgepayv1.edgepay.services.connectors.generic import GenericSourceConnector
from edgepayv1.edgepay.services.connectors.registry import (
	get_connector,
	create_payment_request_from_source,
	notify_source_payment_status
)
import json
import sys

class TestConnectors(FrappeTestCase):
	def setUp(self):
		super(TestConnectors, self).setUp()
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
		self.provider_name = "Test Connector Provider"
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
		super(TestConnectors, self).tearDown()

	def test_generic_connector_validates_valid_source_context(self):
		connector = GenericSourceConnector()
		context = {
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-2026-0001",
			"amount": 3000.00,
			"currency": "NGN"
		}
		# Should not raise any error
		connector.validate_source_context(context)

	def test_generic_connector_rejects_missing_fields(self):
		connector = GenericSourceConnector()
		base_context = {
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-2026-0001",
			"amount": 3000.00,
			"currency": "NGN"
		}

		for field in ["source_app", "source_doctype", "source_name", "currency"]:
			bad_context = base_context.copy()
			bad_context[field] = ""
			with self.assertRaises(frappe.ValidationError) as ctx:
				connector.validate_source_context(bad_context)
			self.assertIn("missing required source context field", str(ctx.exception).lower())

	def test_generic_connector_rejects_invalid_amount(self):
		connector = GenericSourceConnector()
		context = {
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-2026-0001",
			"amount": -50.00,
			"currency": "NGN"
		}
		with self.assertRaises(frappe.ValidationError) as ctx:
			connector.validate_source_context(context)
		self.assertIn("amount must be greater than zero", str(ctx.exception).lower())

	def test_create_payment_request_from_source(self):
		context = {
			"provider": self.provider_name,
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-2026-0001",
			"amount": 3000.00,
			"currency": "NGN",
			"customer_name": "Alice",
			"customer_email": "alice@retail.com"
		}
		res = create_payment_request_from_source(context)
		self.assertTrue(res["ok"])
		self.assertEqual(res["status"], "success")
		self.assertEqual(res["data"]["amount"], 3000.00)
		self.assertEqual(res["data"]["currency"], "NGN")
		self.assertEqual(res["data"]["provider"], self.provider_name)
		
		# Verify DB document
		pr = frappe.get_doc("EdgePay Payment Request", res["data"]["payment_request"])
		self.assertEqual(pr.source_app, "RetailEdge")
		self.assertEqual(pr.source_doctype, "Sales Invoice")
		self.assertEqual(pr.source_name, "SINV-2026-0001")

	def test_create_payment_request_from_source_idempotency(self):
		ikey = "idemp_source_test_key_999"
		context = {
			"provider": self.provider_name,
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-2026-0001",
			"amount": 3000.00,
			"currency": "NGN",
			"customer_name": "Alice",
			"customer_email": "alice@retail.com",
			"idempotency_key": ikey
		}
		
		res1 = create_payment_request_from_source(context)
		self.assertTrue(res1["ok"])
		pr1_name = res1["data"]["payment_request"]
		
		res2 = create_payment_request_from_source(context)
		self.assertTrue(res2["ok"])
		pr2_name = res2["data"]["payment_request"]
		
		self.assertEqual(pr1_name, pr2_name)
		self.assertIn("retrieved successfully (idempotent)", res2["message"])

	def test_source_metadata_storage_safety(self):
		context = {
			"provider": self.provider_name,
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-2026-0001",
			"amount": 3000.00,
			"currency": "NGN",
			"customer_name": "Alice",
			"customer_email": "alice@retail.com",
			"metadata_json": '{"secret_key": "super_secret_123", "api_key": "some_api_key_456"}'
		}
		res = create_payment_request_from_source(context)
		self.assertTrue(res["ok"])
		
		pr = frappe.get_doc("EdgePay Payment Request", res["data"]["payment_request"])
		meta = json.loads(pr.metadata_json)
		self.assertEqual(meta["secret_key"], "[REDACTED]")
		self.assertEqual(meta["api_key"], "[REDACTED]")

	def test_unknown_source_app_falls_back_to_generic(self):
		connector = get_connector("VetEdge")
		self.assertIsInstance(connector, GenericSourceConnector)

	def test_connector_registry_does_not_import_unwanted_apps(self):
		import os
		connectors_dir = os.path.dirname(os.path.dirname(__file__))
		connectors_path = os.path.join(connectors_dir, "connectors")
		
		unwanted_imports = ["erpnext", "posnext", "retailedge", "vetedge", "coreedge", "pos_next"]
		
		for root, _, files in os.walk(connectors_path):
			for file in files:
				if file.endswith(".py"):
					file_path = os.path.join(root, file)
					with open(file_path, "r", encoding="utf-8") as f:
						content = f.read()
						for imp in unwanted_imports:
							self.assertNotIn(f"import {imp}", content)
							self.assertNotIn(f"from {imp}", content)

	def test_status_notification_handoff_noop_default(self):
		# Create a payment request
		context = {
			"provider": self.provider_name,
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-2026-0001",
			"amount": 3000.00,
			"currency": "NGN",
			"customer_name": "Alice",
			"customer_email": "alice@retail.com"
		}
		res = create_payment_request_from_source(context)
		pr_name = res["data"]["payment_request"]
		
		# Should execute without error and safely log/noop
		notify_source_payment_status(pr_name)
		
		# Verify that no document mutations were performed on the non-existent source Sales Invoice
		# (It remains unmodified/read-only since it doesn't even exist in the test DB)
		self.assertFalse(frappe.db.exists("Sales Invoice", "SINV-2026-0001"))

	def test_no_credentials_leak_in_connector_responses(self):
		context = {
			"provider": self.provider_name,
			"source_app": "RetailEdge",
			"source_doctype": "Sales Invoice",
			"source_name": "SINV-2026-0001",
			"amount": 3000.00,
			"currency": "NGN",
			"customer_name": "Alice",
			"customer_email": "alice@retail.com",
			"metadata_json": '{"secret_key": "some_secret"}'
		}
		
		from edgepayv1.edgepay.services.api import create_payment_request_from_source as api_call
		res = api_call(context)
		self.assertTrue(res["ok"])
		
		res_str = json.dumps(res).lower()
		self.assertNotIn("secret_key", res_str)
		self.assertNotIn("some_secret", res_str)
		self.assertNotIn("api_key", res_str)
