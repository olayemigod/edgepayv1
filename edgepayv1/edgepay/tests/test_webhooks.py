# -*- coding: utf-8 -*-
import frappe
from frappe.tests.utils import FrappeTestCase
from edgepayv1.edgepay.services.webhooks import process_webhook_event, process_provider_webhook
from edgepayv1.edgepay.services.clients import clear_client_overrides
from edgepayv1.edgepay.tests.utils import DatabaseStateBackup
import json
import hmac
import hashlib

class TestWebhooks(FrappeTestCase):
	def setUp(self):
		self.db_backup = DatabaseStateBackup()
		self.db_backup.backup()
		super(TestWebhooks, self).setUp()
		clear_client_overrides()
		
		self.settings = frappe.get_doc("EdgePay Settings")
		self.settings.sandbox_mode = 1
		self.settings.allow_external_http_calls = 0
		self.settings.save()
		
		self.provider_name = "Test Monnify Webhook Provider"
		self.secret_key = "test_webhook_secret_key"
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
				"api_key": "test_webhook_api_key",
				"secret_key": self.secret_key
			}).insert()
		else:
			self.provider = frappe.get_doc("EdgePay Provider", self.provider_name)
			self.provider.enabled = 1
			self.provider.api_key = "test_webhook_api_key"
			self.provider.secret_key = self.secret_key
			self.provider.save()
			
		self.req_ref = "REQ-WEBHOOK-TEST-001"
		if frappe.db.exists("EdgePay Payment Request", {"request_reference": self.req_ref}):
			frappe.db.delete("EdgePay Payment Request", {"request_reference": self.req_ref})
			
		self.payment_request = frappe.get_doc({
			"doctype": "EdgePay Payment Request",
			"request_reference": self.req_ref,
			"provider": self.provider_name,
			"status": "Initiated",
			"amount": 1500.50,
			"currency": "NGN",
			"customer_name": "Test Customer",
			"customer_email": "test@customer.com",
			"provider_reference": "MON-REQ-WEBHOOK-TEST-001-TX"
		}).insert()
		
		frappe.db.delete("EdgePay Webhook Event", {"provider": self.provider_name})
		frappe.db.delete("EdgePay Payment Transaction", {"payment_request": self.payment_request.name})

	def tearDown(self):
		clear_client_overrides()
		frappe.set_user("Administrator")
		if frappe.db.exists("EdgePay Payment Request", {"request_reference": self.req_ref}):
			frappe.db.delete("EdgePay Payment Request", {"request_reference": self.req_ref})
		if frappe.db.exists("EdgePay Provider", self.provider_name):
			frappe.db.delete("EdgePay Provider", self.provider_name)
		frappe.db.delete("EdgePay Webhook Event", {"provider": self.provider_name})
		frappe.db.delete("EdgePay Payment Transaction", {"payment_request": self.payment_request.name})
		super(TestWebhooks, self).tearDown()
		self.db_backup.restore()

	def _get_headers_and_body(self, payload):
		body_str = json.dumps(payload)
		signature = hmac.new(self.secret_key.encode('utf-8'), body_str.encode('utf-8'), hashlib.sha512).hexdigest()
		headers = {"monnify-signature": signature}
		return headers, body_str

	def _get_valid_payload(self, event_ref="EVT-001", status="PAID", amount=1500.50, currency="NGN"):
		return {
			"eventType": "SUCCESSFUL_TRANSACTION",
			"eventReference": event_ref,
			"eventData": {
				"amountPaid": amount,
				"currency": currency,
				"paymentStatus": status,
				"paymentReference": self.req_ref,
				"transactionReference": "MON-REQ-WEBHOOK-TEST-001-TX",
				"paidOn": "2026-06-12 19:00:00",
				"settlementStatus": "Settled",
				"secret_key": "raw_sensitive_secret_inside_payload_json"
			}
		}

	def test_valid_signed_webhook_logged(self):
		payload = self._get_valid_payload()
		headers, body = self._get_headers_and_body(payload)
		
		res = process_webhook_event("monnify", headers, body)
		self.assertEqual(res["status"], "success")
		self.assertEqual(res["processing_status"], "Processed")
		
		event_name = res["event"]
		event = frappe.get_doc("EdgePay Webhook Event", event_name)
		self.assertEqual(event.signature_valid, 1)
		self.assertEqual(event.processing_status, "Processed")
		self.assertEqual(event.event_reference, "EVT-001")

	def test_valid_signed_success_webhook_updates_request(self):
		payload = self._get_valid_payload()
		headers, body = self._get_headers_and_body(payload)
		
		process_webhook_event("monnify", headers, body)
		
		pr = frappe.get_doc("EdgePay Payment Request", self.payment_request.name)
		self.assertEqual(pr.status, "Paid")

	def test_valid_signed_success_webhook_updates_transaction(self):
		payload = self._get_valid_payload()
		headers, body = self._get_headers_and_body(payload)
		
		process_webhook_event("monnify", headers, body)
		
		txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"payment_request": self.payment_request.name})
		self.assertTrue(txn_name)
		
		txn = frappe.get_doc("EdgePay Payment Transaction", txn_name)
		self.assertEqual(txn.status, "Success")
		self.assertEqual(txn.amount, 1500.50)
		self.assertEqual(txn.currency, "NGN")

	def test_duplicate_webhook_is_idempotent(self):
		payload = self._get_valid_payload()
		headers, body = self._get_headers_and_body(payload)
		
		res1 = process_webhook_event("monnify", headers, body)
		self.assertFalse(res1.get("duplicate"))
		
		res2 = process_webhook_event("monnify", headers, body)
		self.assertTrue(res2.get("duplicate"))
		self.assertEqual(res2["event"], res1["event"])
		
		txns = frappe.get_all("EdgePay Payment Transaction", filters={"payment_request": self.payment_request.name})
		self.assertEqual(len(txns), 1)

	def test_invalid_signature_logged_but_no_mutation(self):
		payload = self._get_valid_payload()
		headers, body = self._get_headers_and_body(payload)
		headers["monnify-signature"] = "invalid_signature_hash_123"
		
		res = process_webhook_event("monnify", headers, body)
		self.assertEqual(res["status"], "failed")
		self.assertEqual(res["processing_status"], "Failed")
		
		event = frappe.get_doc("EdgePay Webhook Event", res["event"])
		self.assertEqual(event.signature_valid, 0)
		self.assertEqual(event.processing_status, "Failed")
		
		pr = frappe.get_doc("EdgePay Payment Request", self.payment_request.name)
		self.assertEqual(pr.status, "Initiated")
		
		txn_exists = frappe.db.exists("EdgePay Payment Transaction", {"payment_request": self.payment_request.name})
		self.assertFalse(txn_exists)

	def test_unknown_provider_rejected(self):
		payload = self._get_valid_payload()
		headers, body = self._get_headers_and_body(payload)
		
		with self.assertRaises(frappe.ValidationError) as context:
			process_webhook_event("paystack", headers, body)
		self.assertIn("unsupported provider code", str(context.exception).lower())

	def test_disabled_provider_rejected(self):
		payload = self._get_valid_payload()
		headers, body = self._get_headers_and_body(payload)
		
		self.provider.enabled = 0
		self.provider.save()
		
		with self.assertRaises(frappe.ValidationError) as context:
			process_webhook_event("monnify", headers, body)
		self.assertIn("disabled", str(context.exception).lower())

	def test_missing_payment_reference_handled_safely(self):
		payload = self._get_valid_payload()
		payload["eventData"]["paymentReference"] = "NON-EXISTENT-REQUEST-REF"
		payload["eventData"]["transactionReference"] = "NON-EXISTENT-PROVIDER-REF"
		headers, body = self._get_headers_and_body(payload)
		
		res = process_webhook_event("monnify", headers, body)
		self.assertEqual(res["status"], "failed")
		
		event = frappe.get_doc("EdgePay Webhook Event", res["event"])
		self.assertEqual(event.processing_status, "Failed")
		self.assertIn("payment request not resolved", event.error_message.lower())

	def test_amount_mismatch_blocks_mutation(self):
		payload = self._get_valid_payload(amount=9999.99)
		headers, body = self._get_headers_and_body(payload)
		
		res = process_webhook_event("monnify", headers, body)
		self.assertEqual(res["status"], "failed")
		
		event = frappe.get_doc("EdgePay Webhook Event", res["event"])
		self.assertEqual(event.processing_status, "Failed")
		self.assertIn("amount mismatch", event.error_message.lower())
		
		pr = frappe.get_doc("EdgePay Payment Request", self.payment_request.name)
		self.assertEqual(pr.status, "Initiated")

	def test_currency_mismatch_blocks_mutation(self):
		payload = self._get_valid_payload(currency="USD")
		headers, body = self._get_headers_and_body(payload)
		
		res = process_webhook_event("monnify", headers, body)
		self.assertEqual(res["status"], "failed")
		
		event = frappe.get_doc("EdgePay Webhook Event", res["event"])
		self.assertEqual(event.processing_status, "Failed")
		self.assertIn("currency mismatch", event.error_message.lower())
		
		pr = frappe.get_doc("EdgePay Payment Request", self.payment_request.name)
		self.assertEqual(pr.status, "Initiated")

	def test_pending_webhook_does_not_mark_paid(self):
		payload = self._get_valid_payload(status="PENDING")
		headers, body = self._get_headers_and_body(payload)
		
		res = process_webhook_event("monnify", headers, body)
		self.assertEqual(res["status"], "success")
		
		pr = frappe.get_doc("EdgePay Payment Request", self.payment_request.name)
		self.assertEqual(pr.status, "Initiated")
		
		txn_name = frappe.db.get_value("EdgePay Payment Transaction", {"payment_request": self.payment_request.name})
		txn = frappe.get_doc("EdgePay Payment Transaction", txn_name)
		self.assertEqual(txn.status, "Pending")

	def test_failed_webhook_does_not_downgrade_paid_request(self):
		self.payment_request.status = "Paid"
		self.payment_request.save()
		
		txn = frappe.get_doc({
			"doctype": "EdgePay Payment Transaction",
			"payment_request": self.payment_request.name,
			"provider": self.provider_name,
			"status": "Success",
			"amount": 1500.50,
			"currency": "NGN",
			"transaction_reference": "MON-REQ-WEBHOOK-TEST-001-TX",
			"provider_reference": "MON-REQ-WEBHOOK-TEST-001-TX"
		}).insert()
		
		payload = self._get_valid_payload(status="FAILED")
		headers, body = self._get_headers_and_body(payload)
		
		res = process_webhook_event("monnify", headers, body)
		self.assertEqual(res["status"], "success")
		
		pr = frappe.get_doc("EdgePay Payment Request", self.payment_request.name)
		self.assertEqual(pr.status, "Paid")
		
		txn = frappe.get_doc("EdgePay Payment Transaction", txn.name)
		self.assertEqual(txn.status, "Success")

	def test_stale_pending_webhook_does_not_downgrade_success_transaction(self):
		self.payment_request.status = "Paid"
		self.payment_request.save()
		
		txn = frappe.get_doc({
			"doctype": "EdgePay Payment Transaction",
			"payment_request": self.payment_request.name,
			"provider": self.provider_name,
			"status": "Success",
			"amount": 1500.50,
			"currency": "NGN",
			"transaction_reference": "MON-REQ-WEBHOOK-TEST-001-TX",
			"provider_reference": "MON-REQ-WEBHOOK-TEST-001-TX"
		}).insert()
		
		payload = self._get_valid_payload(status="PENDING")
		headers, body = self._get_headers_and_body(payload)
		
		res = process_webhook_event("monnify", headers, body)
		self.assertEqual(res["status"], "success")
		
		pr = frappe.get_doc("EdgePay Payment Request", self.payment_request.name)
		self.assertEqual(pr.status, "Paid")
		
		txn = frappe.get_doc("EdgePay Payment Transaction", txn.name)
		self.assertEqual(txn.status, "Success")

	def test_secrets_redacted_in_webhook_event(self):
		payload = self._get_valid_payload()
		headers, body = self._get_headers_and_body(payload)
		
		res = process_webhook_event("monnify", headers, body)
		event = frappe.get_doc("EdgePay Webhook Event", res["event"])
		
		parsed_json = json.loads(event.payload_json)
		self.assertEqual(parsed_json["eventData"]["secret_key"], "[REDACTED]")

	def test_guest_api_webhook_processing(self):
		payload = self._get_valid_payload(event_ref="EVT-GUEST")
		headers, body = self._get_headers_and_body(payload)
		
		class MockRequest(object):
			def __init__(self, data, headers):
				self.data = data
				self.headers = headers
			def get_data(self):
				return self.data
				
		frappe.local.request = MockRequest(body, headers)
		
		frappe.set_user("Guest")
		try:
			res = process_provider_webhook("monnify")
		finally:
			frappe.set_user("Administrator")
		
		self.assertEqual(res["status"], "success")
		self.assertEqual(res["processing_status"], "Processed")
		self.assertFalse(res["duplicate"])
		
		if hasattr(frappe.local, "request"):
			del frappe.local.request
