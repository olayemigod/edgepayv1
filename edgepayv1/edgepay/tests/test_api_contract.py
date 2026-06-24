# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from edgepayv1.edgepay.services.clients import set_client_override, clear_client_overrides, SimulatedMonnifyClient, MonnifyClient
from edgepayv1.edgepay.tests.utils import DatabaseStateBackup
from edgepayv1.edgepay.services.api import (
	create_payment_request,
	initialize_payment_request_checkout,
	verify_payment_request_transaction,
	get_payment_request_status,
	get_payment_transaction_status,
	handle_checkout_callback
)
from edgepayv1.edgepay.services.checkout import check_and_mark_expired
import json
from frappe.utils import add_to_date, now_datetime

class TestApiContract(FrappeTestCase):
	def setUp(self):
		self.db_backup = DatabaseStateBackup()
		self.db_backup.backup()
		super(TestApiContract, self).setUp()
		clear_client_overrides()
		
		# Delete any existing provider with provider_code = 'monnify' to avoid unique constraint conflict
		frappe.db.delete("EdgePay Provider", {"provider_code": "monnify"})

		# Override client with simulator to prevent external calls
		self.mock_client = SimulatedMonnifyClient()
		self.mock_client.mock_amount = 2500.00
		set_client_override("monnify", self.mock_client)
		
		# Configure settings to enable EdgePay in sandbox mode
		self.settings = frappe.get_doc("EdgePay Settings")
		self.settings.sandbox_mode = 1
		self.settings.enable_edgepay = 1
		self.settings.allow_external_http_calls = 0
		self.settings.save()
		
		# Set up mock provider
		self.provider_name = "Test API Contract Provider"
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
				"api_key": "test_api_key",
				"secret_key": "test_secret_key"
			}).insert()
		else:
			self.provider = frappe.get_doc("EdgePay Provider", self.provider_name)
			self.provider.enabled = 1
			self.provider.api_key = "test_api_key"
			self.provider.secret_key = "test_secret_key"
			self.provider.save()
			
		self.req_ref = "REQ-CONTRACT-TEST-001"
		if frappe.db.exists("EdgePay Payment Request", {"request_reference": self.req_ref}):
			frappe.db.delete("EdgePay Payment Request", {"request_reference": self.req_ref})
			
		self.payment_request = frappe.get_doc({
			"doctype": "EdgePay Payment Request",
			"request_reference": self.req_ref,
			"provider": self.provider_name,
			"status": "Draft",
			"amount": 2500.00,
			"currency": "NGN",
			"customer_name": "API Test Customer",
			"customer_email": "api_test@customer.com",
			"provider_reference": "MON-REQ-CONTRACT-TEST-001-TX"
		}).insert()

		frappe.db.delete("EdgePay Payment Transaction", {"payment_request": self.payment_request.name})
		frappe.set_user("Administrator")

	def tearDown(self):
		clear_client_overrides()
		frappe.set_user("Administrator")
		if frappe.db.exists("EdgePay Payment Request", {"request_reference": self.req_ref}):
			frappe.db.delete("EdgePay Payment Request", {"request_reference": self.req_ref})
		if frappe.db.exists("EdgePay Provider", self.provider_name):
			frappe.db.delete("EdgePay Provider", self.provider_name)
		frappe.db.delete("EdgePay Payment Transaction", {"payment_request": self.payment_request.name})
		super(TestApiContract, self).tearDown()
		self.db_backup.restore()

	def test_expired_payment_request_cannot_be_initialized(self):
		# Set expires_on to past
		self.payment_request.expires_on = add_to_date(now_datetime(), minutes=-10)
		self.payment_request.save()
		
		# Attempt initialization
		res = initialize_payment_request_checkout(self.payment_request.name)
		self.assertFalse(res["ok"])
		self.assertIn("expired", res["message"].lower())
		
		# Verify DB status changed to Expired
		db_status = frappe.db.get_value("EdgePay Payment Request", self.payment_request.name, "status")
		self.assertEqual(db_status, "Expired")

	def test_non_expired_payment_request_can_be_initialized(self):
		# Set expires_on to future
		self.payment_request.expires_on = add_to_date(now_datetime(), minutes=30)
		self.payment_request.save()
		
		res = initialize_payment_request_checkout(self.payment_request.name)
		self.assertTrue(res["ok"])
		self.assertEqual(res["data"]["status"], "Initiated")

	def test_create_payment_request_creates_valid_request(self):
		res = create_payment_request(
			provider=self.provider_name,
			amount=5000.00,
			currency="NGN",
			customer_name="John Doe",
			customer_email="john@doe.com"
		)
		self.assertTrue(res["ok"])
		self.assertEqual(res["data"]["status"], "Draft")
		self.assertEqual(res["data"]["amount"], 5000.00)
		self.assertEqual(res["data"]["currency"], "NGN")
		self.assertTrue(res["data"]["payment_request"])
		self.assertTrue(res["data"]["request_reference"])
		
		# Cleanup
		frappe.db.delete("EdgePay Payment Request", res["data"]["payment_request"])

	def test_create_payment_request_is_idempotent_with_key(self):
		ikey = "idemp_test_key_123"
		# Ensure no old request exists with this key
		frappe.db.delete("EdgePay Payment Request", {"idempotency_key": ikey})

		res1 = create_payment_request(
			provider=self.provider_name,
			amount=1000.00,
			currency="NGN",
			customer_name="Alice",
			customer_email="alice@test.com",
			idempotency_key=ikey
		)
		self.assertTrue(res1["ok"])
		pr1_name = res1["data"]["payment_request"]

		# Request again with same key
		res2 = create_payment_request(
			provider=self.provider_name,
			amount=1000.00,
			currency="NGN",
			customer_name="Alice",
			customer_email="alice@test.com",
			idempotency_key=ikey
		)
		self.assertTrue(res2["ok"])
		pr2_name = res2["data"]["payment_request"]

		self.assertEqual(pr1_name, pr2_name)
		self.assertIn("retrieved successfully (idempotent)", res2["message"])

		# Cleanup
		frappe.db.delete("EdgePay Payment Request", pr1_name)

	def test_create_payment_request_rejects_invalid_amount(self):
		res = create_payment_request(
			provider=self.provider_name,
			amount=-150.00,
			currency="NGN",
			customer_name="John Doe",
			customer_email="john@doe.com"
		)
		self.assertFalse(res["ok"])
		self.assertIn("amount must be greater than zero", res["message"].lower())

	def test_create_payment_request_rejects_disabled_provider(self):
		self.provider.enabled = 0
		self.provider.save()

		res = create_payment_request(
			provider=self.provider_name,
			amount=5000.00,
			currency="NGN",
			customer_name="John Doe",
			customer_email="john@doe.com"
		)
		self.assertFalse(res["ok"])
		self.assertIn("disabled", res["message"].lower())

	def test_checkout_api_returns_only_safe_fields(self):
		res = initialize_payment_request_checkout(self.payment_request.name)
		self.assertTrue(res["ok"])
		
		# Expected safe keys in data
		expected_keys = {"payment_request", "status", "checkout_url", "provider_reference", "expires_on"}
		data_keys = set(res["data"].keys())
		self.assertTrue(data_keys.issubset(expected_keys))

		# Make sure no credential headers are present
		res_str = json.dumps(res).lower()
		self.assertNotIn("key", res_str)
		self.assertNotIn("secret", res_str)
		self.assertNotIn("token", res_str)
		self.assertNotIn("authorization", res_str)

	def test_verification_api_returns_only_safe_fields(self):
		self.payment_request.status = "Initiated"
		self.payment_request.save()
		
		res = verify_payment_request_transaction(self.payment_request.name)
		self.assertTrue(res["ok"])
		
		# Expected safe keys in data
		expected_keys = {
			"payment_request", "request_status", "transaction", "transaction_status",
			"provider_reference", "amount", "currency", "paid_on"
		}
		data_keys = set(res["data"].keys())
		self.assertTrue(data_keys.issubset(expected_keys))

		res_str = json.dumps(res).lower()
		self.assertNotIn("key", res_str)
		self.assertNotIn("secret", res_str)
		self.assertNotIn("token", res_str)
		self.assertNotIn("authorization", res_str)

	def test_status_api_does_not_mutate_records(self):
		# Set request status to Draft, expires_on in past
		self.payment_request.status = "Draft"
		self.payment_request.expires_on = add_to_date(now_datetime(), minutes=-10)
		self.payment_request.save()

		# Call status API
		res = get_payment_request_status(self.payment_request.name)
		self.assertTrue(res["ok"])
		self.assertEqual(res["data"]["status"], "Expired")

		# Check DB status - it should STILL be Draft (no mutation)
		db_status = frappe.db.get_value("EdgePay Payment Request", self.payment_request.name, "status")
		self.assertEqual(db_status, "Draft")

	def test_callback_performs_server_side_verification(self):
		# Set up payment request in Initiated
		self.payment_request.status = "Initiated"
		self.payment_request.save()

		self.mock_client.mock_status = "PAID"
		self.mock_client.mock_amount = 2500.00
		
		res = handle_checkout_callback(
			payment_request=self.payment_request.name,
			provider_reference="MON-REQ-CONTRACT-TEST-001-TX",
			status="PAID"
		)
		self.assertTrue(res["ok"])
		self.assertEqual(res["data"]["status"], "Paid")
		
		# Double check that the database actually got updated through verify_transaction
		db_status = frappe.db.get_value("EdgePay Payment Request", self.payment_request.name, "status")
		self.assertEqual(db_status, "Paid")

	def test_callback_does_not_mark_paid_from_query_parameters_alone(self):
		self.payment_request.status = "Initiated"
		self.payment_request.save()

		# Mock verification server-side response as PENDING
		self.mock_client.mock_status = "PENDING"
		
		res = handle_checkout_callback(
			payment_request=self.payment_request.name,
			provider_reference="MON-REQ-CONTRACT-TEST-001-TX",
			status="PAID" # Untrusted callback query hint
		)
		self.assertTrue(res["ok"])
		self.assertEqual(res["data"]["status"], "Initiated") # Still Initiated, not Paid!
		
		db_status = frappe.db.get_value("EdgePay Payment Request", self.payment_request.name, "status")
		self.assertEqual(db_status, "Initiated")

	def test_guest_cannot_access_authenticated_apis(self):
		frappe.set_user("Guest")
		
		res1 = create_payment_request(self.provider_name, 100.00, "NGN", "A", "a@a.com")
		self.assertFalse(res1["ok"])
		self.assertIn("authentication required", res1["message"].lower())

		res2 = initialize_payment_request_checkout(self.payment_request.name)
		self.assertFalse(res2["ok"])
		
		res3 = verify_payment_request_transaction(self.payment_request.name)
		self.assertFalse(res3["ok"])

		res4 = get_payment_request_status(self.payment_request.name)
		self.assertFalse(res4["ok"])

	def test_guest_callback_exposure_gating(self):
		frappe.set_user("Guest")
		
		# Trigger error inside callback (e.g. non-existent payment request)
		res = handle_checkout_callback(payment_request="NON-EXISTENT-PR-NAME")
		self.assertFalse(res["ok"])
		self.assertEqual(res["message"], "An error occurred during verification")
		self.assertIsNone(res["data"])

	def test_no_secrets_leaked_in_exceptions(self):
		# Intentionally fail creation with sensitive keywords in args to see if they are redacted in response message
		res = create_payment_request(
			provider=self.provider_name,
			amount=100.00,
			currency="NGN",
			customer_name="Test",
			customer_email="test@test.com",
			metadata_json='{"secret_key": "some_secret_123", "api_key": "raw_api_key"}'
		)
		self.assertTrue(res["ok"])
		
		# Now check metadata_json stored in DB has been redacted
		pr_name = res["data"]["payment_request"]
		pr_doc = frappe.get_doc("EdgePay Payment Request", pr_name)
		metadata = json.loads(pr_doc.metadata_json)
		self.assertEqual(metadata["secret_key"], "[REDACTED]")
		self.assertEqual(metadata["api_key"], "[REDACTED]")

		# Cleanup
		frappe.db.delete("EdgePay Payment Request", pr_name)

	def test_no_external_calls_during_tests(self):
		# Override with standard client to make sure it raises external calls disabled exception
		set_client_override("monnify", MonnifyClient(self.provider))
		
		# Force a run that would trigger GET verification
		self.payment_request.status = "Initiated"
		self.payment_request.save()
		
		res = verify_payment_request_transaction(self.payment_request.name)
		self.assertFalse(res["ok"])
		self.assertIn("external http calls are disabled", res["message"].lower())
