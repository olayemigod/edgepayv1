import json

import frappe
from frappe.tests.utils import FrappeTestCase

from edgepayv1.edgepay.services.clients import (
	MonnifyClient,
	SimulatedMonnifyClient,
	clear_client_overrides,
	set_client_override,
)
from edgepayv1.edgepay.services.verification import verify_payment_request_transaction, verify_transaction
from edgepayv1.edgepay.tests.utils import (
	DatabaseStateBackup,
	cleanup_test_merchant_provider_account,
	create_test_merchant_provider_account,
)


class TestVerification(FrappeTestCase):
	def setUp(self):
		self.db_backup = DatabaseStateBackup()
		self.db_backup.backup()
		super(TestVerification, self).setUp()
		clear_client_overrides()

		self.mock_client = SimulatedMonnifyClient()
		set_client_override("monnify", self.mock_client)

		self.settings = frappe.get_doc("EdgePay Settings")
		self.settings.sandbox_mode = 1
		self.settings.allow_external_http_calls = 0
		self.settings.save()

		self.provider_name = "Test Monnify Verification Provider"
		frappe.db.delete("EdgePay Provider", {"provider_code": "monnify"})
		if not frappe.db.exists("EdgePay Provider", self.provider_name):
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
					"api_key": "test_verification_api_key",
					"secret_key": "test_verification_secret_key",
				}
			).insert()
		else:
			self.provider = frappe.get_doc("EdgePay Provider", self.provider_name)
			self.provider.enabled = 1
			self.provider.api_key = "test_verification_api_key"
			self.provider.secret_key = "test_verification_secret_key"
			self.provider.save()

		self.merchant, self.provider_account = create_test_merchant_provider_account(
			self.provider_name,
			"Test Verification Merchant",
			api_key="test_verification_api_key",
			secret_key="test_verification_secret_key",
		)

		self.req_ref = "REQ-VERIFY-TEST-001"
		if frappe.db.exists("EdgePay Payment Request", {"request_reference": self.req_ref}):
			frappe.db.delete("EdgePay Payment Request", {"request_reference": self.req_ref})

		self.payment_request = frappe.get_doc(
			{
				"doctype": "EdgePay Payment Request",
				"request_reference": self.req_ref,
				"merchant": self.merchant.name,
				"provider_account": self.provider_account.name,
				"provider": self.provider_name,
				"status": "Initiated",
				"amount": 1500.50,
				"currency": "NGN",
				"customer_name": "Test Customer",
				"customer_email": "test@customer.com",
				"provider_reference": "MON-REQ-VERIFY-TEST-001-TX",
			}
		).insert()

		frappe.db.delete("EdgePay Payment Transaction", {"payment_request": self.payment_request.name})

	def tearDown(self):
		clear_client_overrides()
		if frappe.db.exists("EdgePay Payment Request", {"request_reference": self.req_ref}):
			frappe.db.delete("EdgePay Payment Request", {"request_reference": self.req_ref})
		frappe.db.delete("EdgePay Payment Transaction", {"payment_request": self.payment_request.name})
		cleanup_test_merchant_provider_account(self.merchant, self.provider_name)
		if frappe.db.exists("EdgePay Provider", self.provider_name):
			frappe.db.delete("EdgePay Provider", self.provider_name)
		super(TestVerification, self).tearDown()
		self.db_backup.restore()

	def test_successful_verification(self):
		self.mock_client.mock_status = "PAID"
		self.mock_client.mock_amount = 1500.50

		res = verify_transaction(self.payment_request.name)

		pr = frappe.get_doc("EdgePay Payment Request", self.payment_request.name)
		self.assertEqual(pr.status, "Paid")
		self.assertEqual(res["request_status"], "Paid")

		txns = frappe.get_all("EdgePay Payment Transaction", filters={"payment_request": self.payment_request.name})
		self.assertEqual(len(txns), 1)

		txn = frappe.get_doc("EdgePay Payment Transaction", txns[0].name)
		self.assertEqual(txn.status, "Success")
		self.assertEqual(txn.amount, 1500.50)
		self.assertEqual(txn.currency, "NGN")
		self.assertEqual(txn.provider_reference, "MON-REQ-VERIFY-TEST-001-TX")

	def test_failed_verification(self):
		self.mock_client.mock_status = "FAILED"

		res = verify_transaction(self.payment_request.name)

		pr = frappe.get_doc("EdgePay Payment Request", self.payment_request.name)
		self.assertEqual(pr.status, "Failed")
		self.assertEqual(res["request_status"], "Failed")

		txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"payment_request": self.payment_request.name})
		txn = frappe.get_doc("EdgePay Payment Transaction", txn_name)
		self.assertEqual(txn.status, "Failed")

	def test_pending_verification(self):
		self.mock_client.mock_status = "PENDING"

		res = verify_transaction(self.payment_request.name)

		pr = frappe.get_doc("EdgePay Payment Request", self.payment_request.name)
		self.assertEqual(pr.status, "Initiated")
		self.assertEqual(res["request_status"], "Initiated")

		txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"payment_request": self.payment_request.name})
		txn = frappe.get_doc("EdgePay Payment Transaction", txn_name)
		self.assertEqual(txn.status, "Pending")

	def test_idempotent_repeat_verification(self):
		self.mock_client.mock_status = "PAID"

		res1 = verify_transaction(self.payment_request.name)
		txn1_name = res1["transaction"]

		res2 = verify_transaction(self.payment_request.name)

		self.assertEqual(res2["transaction"], txn1_name)
		txns = frappe.get_all("EdgePay Payment Transaction", filters={"payment_request": self.payment_request.name})
		self.assertEqual(len(txns), 1)

	def test_missing_provider_reference_blocked(self):
		self.payment_request.provider_reference = ""
		self.payment_request.save()

		with self.assertRaises(frappe.ValidationError) as context:
			verify_transaction(self.payment_request.name)
		self.assertIn("no provider reference generated", str(context.exception).lower())

	def test_disabled_provider_blocks_verification(self):
		self.provider.enabled = 0
		self.provider.save()

		with self.assertRaises(frappe.ValidationError) as context:
			verify_transaction(self.payment_request.name)
		self.assertIn("disabled", str(context.exception).lower())

	def test_invalid_final_status_blocks_verification(self):
		for status in ["Paid", "Failed", "Expired", "Cancelled"]:
			self.payment_request.status = status
			self.payment_request.db_set("status", status)

			with self.assertRaises(frappe.ValidationError) as context:
				verify_transaction(self.payment_request.name)
			self.assertIn(
				"cannot verify transaction for a payment request with final status", str(context.exception).lower()
			)

	def test_no_external_http_calls(self):
		set_client_override("monnify", MonnifyClient(self.provider))

		with self.assertRaises(frappe.ValidationError) as context:
			verify_transaction(self.payment_request.name)
		self.assertIn("external http calls are disabled", str(context.exception).lower())

	def test_secrets_redacted_in_raw_response(self):
		self.mock_client.mock_paid_on = "2026-06-12 18:00:00"
		original_get = self.mock_client.get

		def custom_get(url, headers=None):
			res = original_get(url, headers)
			res["secret_key"] = "mock_secret_key"
			res["api_key"] = "mock_api_key"
			res["headers"] = {"Authorization": "Bearer token123"}
			return res

		self.mock_client.get = custom_get

		verify_transaction(self.payment_request.name)

		txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"payment_request": self.payment_request.name})
		txn = frappe.get_doc("EdgePay Payment Transaction", txn_name)

		raw_resp = json.loads(txn.raw_response_json)
		self.assertEqual(raw_resp.get("secret_key"), "[REDACTED]")
		self.assertEqual(raw_resp.get("api_key"), "[REDACTED]")
		self.assertEqual(raw_resp.get("headers", {}).get("Authorization"), "[REDACTED]")

	def test_amount_mismatch_blocks_verification(self):
		self.mock_client.mock_status = "PAID"
		self.mock_client.mock_amount = 9999.99

		with self.assertRaises(frappe.ValidationError) as context:
			verify_transaction(self.payment_request.name)
		self.assertIn("amount mismatch", str(context.exception).lower())

	def test_currency_mismatch_blocks_verification(self):
		self.mock_client.mock_status = "PAID"
		self.mock_client.mock_amount = 1500.50

		original_get = self.mock_client.get

		def custom_get(url, headers=None):
			res = original_get(url, headers)
			res["currencyCode"] = "USD"
			return res

		self.mock_client.get = custom_get

		with self.assertRaises(frappe.ValidationError) as context:
			verify_transaction(self.payment_request.name)
		self.assertIn("currency mismatch", str(context.exception).lower())

	def test_no_secret_in_api_response(self):
		frappe.set_user("Administrator")
		res = verify_payment_request_transaction(self.payment_request.name)

		self.assertIn("payment_request", res)
		self.assertIn("request_status", res)
		self.assertIn("transaction", res)
		self.assertIn("transaction_status", res)
		self.assertIn("provider_reference", res)

		res_str = json.dumps(res).lower()
		self.assertNotIn("key", res_str)
		self.assertNotIn("secret", res_str)
		self.assertNotIn("token", res_str)
