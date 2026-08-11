import json

import frappe
from frappe.tests.utils import FrappeTestCase

from edgepayv1.edgepay.services.checkout import initialize_checkout, initialize_payment_request_checkout
from edgepayv1.edgepay.services.clients import (
	MonnifyClient,
	SimulatedMonnifyClient,
	clear_client_overrides,
	set_client_override,
)
from edgepayv1.edgepay.services.providers.registry import get_provider_instance
from edgepayv1.edgepay.tests.utils import (
	DatabaseStateBackup,
	cleanup_test_merchant_provider_account,
	create_test_merchant_provider_account,
)


class TestCheckout(FrappeTestCase):
	def setUp(self):
		self.db_backup = DatabaseStateBackup()
		self.db_backup.backup()
		super().setUp()
		clear_client_overrides()
		self.mock_client = SimulatedMonnifyClient()
		set_client_override("monnify", self.mock_client)
		self.settings = frappe.get_doc("EdgePay Settings")
		self.settings.sandbox_mode = 1
		self.settings.allow_external_http_calls = 0
		self.settings.save()
		self.provider_name = "Test Monnify Checkout Provider"
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
				"api_key": "global_api_key_should_not_be_used",
				"secret_key": "global_secret_should_not_be_used",
				"contract_code": "GLOBAL-CONTRACT",
			}
		).insert()
		self.merchant, self.provider_account = create_test_merchant_provider_account(
			self.provider_name,
			"Test Checkout Merchant",
			api_key="merchant_api_key",
			secret_key="merchant_secret_key",
			contract_code="MERCHANT-CONTRACT",
		)
		self.req_ref = "REQ-CHECKOUT-TEST-001"
		frappe.db.delete("EdgePay Payment Request", {"request_reference": self.req_ref})
		self.payment_request = frappe.get_doc(
			{
				"doctype": "EdgePay Payment Request",
				"request_reference": self.req_ref,
				"merchant": self.merchant.name,
				"provider_account": self.provider_account.name,
				"provider": self.provider_name,
				"status": "Draft",
				"amount": 1500.50,
				"currency": "NGN",
				"customer_name": "Test Customer",
				"customer_email": "test@customer.com",
			}
		).insert()

	def tearDown(self):
		clear_client_overrides()
		frappe.db.delete("EdgePay Payment Request", {"request_reference": self.req_ref})
		cleanup_test_merchant_provider_account(self.merchant, self.provider_name)
		frappe.db.delete("EdgePay Provider", self.provider_name)
		super().tearDown()
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

	def test_checkout_uses_provider_account_contract_code(self):
		provider_instance = get_provider_instance(self.provider_name, self.provider_account.name)
		payload = provider_instance.build_checkout_payload(self.payment_request)
		self.assertEqual(payload["contractCode"], "MERCHANT-CONTRACT")
		self.assertNotEqual(payload["contractCode"], self.provider.contract_code)

	def test_no_external_http_calls_are_made(self):
		set_client_override("monnify", MonnifyClient(self.provider, self.provider_account))
		with self.assertRaises(frappe.ValidationError) as context:
			initialize_checkout(self.payment_request.name)
		self.assertIn("external http calls are disabled", str(context.exception).lower())

	def test_initialization_is_idempotent(self):
		res1 = initialize_checkout(self.payment_request.name)
		res2 = initialize_checkout(self.payment_request.name)
		self.assertEqual(res2["provider_reference"], res1["provider_reference"])
		self.assertEqual(res2["checkout_url"], res1["checkout_url"])
		self.assertEqual(res2["status"], "Initiated")

	def test_disabled_provider_blocks_initialization(self):
		self.provider.enabled = 0
		self.provider.save()
		with self.assertRaises(frappe.ValidationError) as context:
			initialize_checkout(self.payment_request.name)
		self.assertIn("disabled", str(context.exception).lower())

	def test_missing_provider_config_blocks_initialization(self):
		self.provider_account.api_key = ""
		self.provider_account.save()
		with self.assertRaises(frappe.ValidationError) as context:
			initialize_checkout(self.payment_request.name)
		self.assertIn("api key", str(context.exception).lower())

	def test_invalid_payment_amount_blocks_initialization(self):
		self.payment_request.db_set("amount", 0)
		with self.assertRaises(frappe.ValidationError) as context:
			initialize_checkout(self.payment_request.name)
		self.assertIn("amount must be greater than zero", str(context.exception).lower())

	def test_invalid_payment_request_status_blocks_initialization(self):
		for status in ["Paid", "Failed", "Expired", "Cancelled"]:
			self.payment_request.db_set("status", status)
			with self.assertRaises(frappe.ValidationError) as context:
				initialize_checkout(self.payment_request.name)
			self.assertIn(
				"cannot initialize checkout for a payment request with status", str(context.exception).lower()
			)

	def test_no_secret_value_in_api_response(self):
		frappe.set_user("Administrator")
		res = initialize_payment_request_checkout(self.payment_request.name)
		for key in ["payment_request", "status", "checkout_url", "provider_reference"]:
			self.assertIn(key, res)
		res_str = json.dumps(res).lower()
		self.assertNotIn("merchant_api_key", res_str)
		self.assertNotIn("merchant_secret_key", res_str)
		self.assertNotIn("global_secret_should_not_be_used", res_str)
