# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from edgepayv1.edgepay.services.clients import set_client_override, clear_client_overrides, SimulatedMonnifyClient, MonnifyClient
from edgepayv1.edgepay.tests.utils import DatabaseStateBackup
from edgepayv1.edgepay.services.checkout import initialize_checkout, initialize_payment_request_checkout
from edgepayv1.edgepay.services.providers.registry import get_provider_instance
import json

class TestCheckout(FrappeTestCase):
	def setUp(self):
		self.db_backup = DatabaseStateBackup()
		self.db_backup.backup()
		super(TestCheckout, self).setUp()
		clear_client_overrides()
		
		self.mock_client = SimulatedMonnifyClient()
		set_client_override("monnify", self.mock_client)
		
		# Set up settings sandbox_mode
		self.settings = frappe.get_doc("EdgePay Settings")
		self.settings.sandbox_mode = 1
		self.settings.allow_external_http_calls = 0
		self.settings.save()
		
		# Set up mock provider
		self.provider_name = "Test Monnify Checkout Provider"
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
				"api_key": "test_checkout_api_key",
				"secret_key": "test_checkout_secret_key"
			}).insert()
		else:
			self.provider = frappe.get_doc("EdgePay Provider", self.provider_name)
			self.provider.enabled = 1
			self.provider.api_key = "test_checkout_api_key"
			self.provider.secret_key = "test_checkout_secret_key"
			self.provider.save()
			
		# Set up mock payment request
		self.req_ref = "REQ-CHECKOUT-TEST-001"
		if frappe.db.exists("EdgePay Payment Request", {"request_reference": self.req_ref}):
			frappe.db.delete("EdgePay Payment Request", {"request_reference": self.req_ref})
			
		self.payment_request = frappe.get_doc({
			"doctype": "EdgePay Payment Request",
			"request_reference": self.req_ref,
			"provider": self.provider_name,
			"status": "Draft",
			"amount": 1500.50,
			"currency": "NGN",
			"customer_name": "Test Customer",
			"customer_email": "test@customer.com"
		}).insert()

	def tearDown(self):
		clear_client_overrides()
		if frappe.db.exists("EdgePay Payment Request", {"request_reference": self.req_ref}):
			frappe.db.delete("EdgePay Payment Request", {"request_reference": self.req_ref})
		if frappe.db.exists("EdgePay Provider", self.provider_name):
			frappe.db.delete("EdgePay Provider", self.provider_name)
		super(TestCheckout, self).tearDown()
		self.db_backup.restore()

	def test_successful_checkout_initialization(self):
		res = initialize_checkout(self.payment_request.name)
		
		doc = frappe.get_doc("EdgePay Payment Request", self.payment_request.name)
		self.assertEqual(doc.status, "Initiated")
		self.assertEqual(res["status"], "Initiated")
		self.assertTrue(doc.checkout_url.startswith("https://sandbox.monnify.com/checkout/"))
		self.assertTrue(doc.provider_reference.startswith(f"MON-{doc.name}-"))
		self.assertTrue(doc.provider_reference.endswith("-TX"))
		
		self.assertEqual(res["checkout_url"], doc.checkout_url)
		self.assertEqual(res["provider_reference"], doc.provider_reference)

	def test_provider_registry_loads_monnify(self):
		provider_instance = get_provider_instance(self.provider_name)
		self.assertEqual(provider_instance.get_provider_code(), "monnify")

	def test_no_external_http_calls_are_made(self):
		set_client_override("monnify", MonnifyClient(self.provider))
		
		with self.assertRaises(frappe.ValidationError) as context:
			initialize_checkout(self.payment_request.name)
		self.assertIn("external http calls are disabled", str(context.exception).lower())

	def test_initialization_is_idempotent(self):
		res1 = initialize_checkout(self.payment_request.name)
		ref1 = res1["provider_reference"]
		url1 = res1["checkout_url"]
		
		res2 = initialize_checkout(self.payment_request.name)
		
		self.assertEqual(res2["provider_reference"], ref1)
		self.assertEqual(res2["checkout_url"], url1)
		self.assertEqual(res2["status"], "Initiated")

	def test_disabled_provider_blocks_initialization(self):
		self.provider.enabled = 0
		self.provider.save()
		
		with self.assertRaises(frappe.ValidationError) as context:
			initialize_checkout(self.payment_request.name)
		self.assertIn("disabled", str(context.exception).lower())

	def test_missing_provider_config_blocks_initialization(self):
		self.provider.api_key = ""
		self.provider.save()
		
		with self.assertRaises(frappe.ValidationError) as context:
			initialize_checkout(self.payment_request.name)
		self.assertIn("api key", str(context.exception).lower())

	def test_invalid_payment_amount_blocks_initialization(self):
		self.payment_request.amount = 0
		self.payment_request.db_set("amount", 0)
		
		with self.assertRaises(frappe.ValidationError) as context:
			initialize_checkout(self.payment_request.name)
		self.assertIn("amount must be greater than zero", str(context.exception).lower())

	def test_invalid_payment_request_status_blocks_initialization(self):
		for status in ["Paid", "Failed", "Expired", "Cancelled"]:
			self.payment_request.status = status
			self.payment_request.db_set("status", status)
			
			with self.assertRaises(frappe.ValidationError) as context:
				initialize_checkout(self.payment_request.name)
			self.assertIn("cannot initialize checkout for a payment request with status", str(context.exception).lower())

	def test_no_secret_value_in_api_response(self):
		frappe.set_user("Administrator")
		res = initialize_payment_request_checkout(self.payment_request.name)
		
		self.assertIn("payment_request", res)
		self.assertIn("status", res)
		self.assertIn("checkout_url", res)
		self.assertIn("provider_reference", res)
		
		res_str = json.dumps(res).lower()
		self.assertNotIn("key", res_str)
		self.assertNotIn("secret", res_str)
		self.assertNotIn("token", res_str)
