import hashlib
import hmac
import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from edgepayv1.edgepay.sdk import (
	create_source_payment_request,
	get_pending_payment_handoffs,
	initialize_source_checkout,
	mark_payment_handoff_delivered,
	mark_payment_handoff_failed,
	verify_source_payment,
)
from edgepayv1.edgepay.services.clients import SimulatedMonnifyClient, clear_client_overrides, set_client_override
from edgepayv1.edgepay.services.webhooks import process_webhook_event
from edgepayv1.edgepay.tests.utils import (
	DatabaseStateBackup,
	cleanup_test_merchant_provider_account,
	create_test_merchant_provider_account,
)


class TestHandoffQueue(FrappeTestCase):
	def setUp(self):
		self.db_backup = DatabaseStateBackup()
		self.db_backup.backup()
		super(TestHandoffQueue, self).setUp()
		clear_client_overrides()

		self.mock_client = SimulatedMonnifyClient()
		self.mock_client.mock_amount = 3000.00
		set_client_override("monnify", self.mock_client)

		self.settings = frappe.get_doc("EdgePay Settings")
		self.settings.sandbox_mode = 1
		self.settings.enable_edgepay = 1
		self.settings.allow_external_http_calls = 0
		self.settings.save()

		self.provider_name = "Test Handoff Provider"
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
				"api_key": "test_api_key",
				"secret_key": "test_secret_key",
			}
		).insert()
		self.merchant, self.provider_account = create_test_merchant_provider_account(
			self.provider_name,
			"Test Handoff Merchant",
			api_key="test_api_key",
			secret_key="test_secret_key",
		)

		frappe.set_user("Administrator")
		frappe.db.delete("EdgePay Webhook Event", {"event_reference": "TXN-MOCK-WEBHOOK-999"})
		pr_names = frappe.get_all("EdgePay Payment Request", filters={"provider": self.provider_name}, pluck="name")
		if pr_names:
			frappe.db.delete("EdgePay Status Handoff Event", {"payment_request": ["in", pr_names]})
			frappe.db.delete("EdgePay Webhook Event", {"linked_payment_request": ["in", pr_names]})

	def tearDown(self):
		clear_client_overrides()
		frappe.set_user("Administrator")
		pr_names = frappe.get_all("EdgePay Payment Request", filters={"provider": self.provider_name}, pluck="name")
		if pr_names:
			frappe.db.delete("EdgePay Payment Transaction", {"payment_request": ["in", pr_names]})
			frappe.db.delete("EdgePay Status Handoff Event", {"payment_request": ["in", pr_names]})
			frappe.db.delete("EdgePay Webhook Event", {"linked_payment_request": ["in", pr_names]})
			frappe.db.delete("EdgePay Payment Request", {"name": ["in", pr_names]})
		cleanup_test_merchant_provider_account(self.merchant, self.provider_name)
		if frappe.db.exists("EdgePay Provider", self.provider_name):
			frappe.db.delete("EdgePay Provider", self.provider_name)
		super(TestHandoffQueue, self).tearDown()
		self.db_backup.restore()

	def _context(self, source_name, source_app="RetailEdge", source_doctype="Sales Invoice", **extra):
		context = {
			"provider": self.provider_name,
			"source_app": source_app,
			"source_doctype": source_doctype,
			"source_name": source_name,
			"amount": 3000.00,
			"currency": "NGN",
			"customer_name": "Charlie",
			"customer_email": "charlie@retail.com",
		}
		context.update(extra)
		return context

	def test_handoff_event_created_on_checkout_initialization(self):
		res = create_source_payment_request(self._context("SINV-HO-0001"))
		pr_name = res["data"]["payment_request"]
		pending = frappe.get_all("EdgePay Status Handoff Event", filters={"payment_request": pr_name})
		self.assertEqual(len(pending), 0)
		initialize_source_checkout(pr_name)
		events = frappe.get_all("EdgePay Status Handoff Event", filters={"payment_request": pr_name}, fields=["*"])
		self.assertEqual(len(events), 1)
		self.assertEqual(events[0].event_source, "Checkout")
		self.assertEqual(events[0].event_type, "Payment Initiated")
		self.assertEqual(events[0].processing_status, "Pending")
		self.assertEqual(events[0].source_app, "RetailEdge")
		self.assertEqual(events[0].source_doctype, "Sales Invoice")
		self.assertEqual(events[0].source_name, "SINV-HO-0001")
		self.assertFalse(frappe.db.exists("Sales Invoice", "SINV-HO-0001"))

	def test_handoff_event_created_on_successful_verification(self):
		res = create_source_payment_request(self._context("SINV-HO-0002"))
		pr_name = res["data"]["payment_request"]
		initialize_source_checkout(pr_name)
		frappe.db.delete("EdgePay Status Handoff Event", {"payment_request": pr_name})
		verify_source_payment(pr_name)
		events = frappe.get_all("EdgePay Status Handoff Event", filters={"payment_request": pr_name}, fields=["*"])
		self.assertEqual(len(events), 1)
		self.assertEqual(events[0].event_source, "Verification")
		self.assertEqual(events[0].event_type, "Payment Paid")
		self.assertEqual(events[0].processing_status, "Pending")

	def test_handoff_event_created_on_failed_verification(self):
		res = create_source_payment_request(self._context("SINV-HO-0003"))
		pr_name = res["data"]["payment_request"]
		initialize_source_checkout(pr_name)
		frappe.db.delete("EdgePay Status Handoff Event", {"payment_request": pr_name})
		self.mock_client.mock_status = "FAILED"
		verify_source_payment(pr_name)
		events = frappe.get_all("EdgePay Status Handoff Event", filters={"payment_request": pr_name}, fields=["*"])
		self.assertEqual(len(events), 1)
		self.assertEqual(events[0].event_source, "Verification")
		self.assertEqual(events[0].event_type, "Payment Failed")
		self.assertEqual(events[0].processing_status, "Pending")

	def test_handoff_event_created_on_valid_webhook(self):
		res = create_source_payment_request(self._context("SINV-HO-0004"))
		pr_name = res["data"]["payment_request"]
		pr = frappe.get_doc("EdgePay Payment Request", pr_name)
		initialize_source_checkout(pr_name)
		frappe.db.delete("EdgePay Status Handoff Event", {"payment_request": pr_name})
		body = {
			"eventType": "SUCCESSFUL_TRANSACTION",
			"eventData": {
				"paymentReference": pr.request_reference,
				"transactionReference": "TXN-MOCK-WEBHOOK-999",
				"amountPaid": 3000.00,
				"currency": "NGN",
				"paymentStatus": "PAID",
				"paidOn": "2026-06-12 18:00:00",
			},
		}
		body_str = json.dumps(body)
		signature = hmac.new(
			"test_secret_key".encode("utf-8"), body_str.encode("utf-8"), hashlib.sha512
		).hexdigest()
		headers = {"content-type": "application/json", "monnify-signature": signature}
		self.mock_client.mock_webhook_signature = True
		process_webhook_event("monnify", headers, body_str)
		events = frappe.get_all("EdgePay Status Handoff Event", filters={"payment_request": pr_name}, fields=["*"])
		self.assertEqual(len(events), 1)
		self.assertEqual(events[0].event_source, "Webhook")
		self.assertEqual(events[0].event_type, "Payment Paid")
		self.assertEqual(events[0].processing_status, "Pending")

	def test_duplicate_verification_does_not_create_duplicate_handoff_events(self):
		res = create_source_payment_request(self._context("SINV-HO-0005"))
		pr_name = res["data"]["payment_request"]
		initialize_source_checkout(pr_name)
		frappe.db.delete("EdgePay Status Handoff Event", {"payment_request": pr_name})
		verify_source_payment(pr_name)
		self.assertEqual(frappe.db.count("EdgePay Status Handoff Event", {"payment_request": pr_name}), 1)
		verify_source_payment(pr_name)
		self.assertEqual(frappe.db.count("EdgePay Status Handoff Event", {"payment_request": pr_name}), 1)

	def test_handoff_payload_is_safe_and_redacted(self):
		res = create_source_payment_request(
			self._context(
				"SINV-HO-0006",
				metadata_json='{"secret_key": "my_webhook_secret_key", "bearer_token": "token123"}',
			)
		)
		pr_name = res["data"]["payment_request"]
		initialize_source_checkout(pr_name)
		events = frappe.get_all(
			"EdgePay Status Handoff Event", filters={"payment_request": pr_name}, fields=["payload_json"]
		)
		payload_str = json.dumps(json.loads(events[0].payload_json)).lower()
		self.assertNotIn("my_webhook_secret_key", payload_str)
		self.assertNotIn("token123", payload_str)

	def test_pending_handoff_events_listing_and_marking(self):
		res = create_source_payment_request(
			self._context("POS-HO-0001", source_app="POSnext", source_doctype="POS Invoice")
		)
		pr_name = res["data"]["payment_request"]
		initialize_source_checkout(pr_name)
		pending = get_pending_payment_handoffs(source_app="POSnext")
		self.assertTrue(pending["ok"])
		self.assertTrue(len(pending["data"]) > 0)
		event_name = pending["data"][0]["name"]
		deliv = mark_payment_handoff_delivered(event_name)
		self.assertTrue(deliv["ok"])
		self.assertEqual(
			frappe.db.get_value("EdgePay Status Handoff Event", event_name, "processing_status"), "Delivered"
		)
		self.assertEqual(frappe.db.get_value("EdgePay Status Handoff Event", event_name, "delivery_attempts"), 1)
		fail = mark_payment_handoff_failed(
			event_name,
			error_message="Connection timeout to POSnext using api_key test_api_key and secret_key test_secret_key",
		)
		self.assertTrue(fail["ok"])
		self.assertEqual(
			frappe.db.get_value("EdgePay Status Handoff Event", event_name, "processing_status"), "Failed"
		)
		self.assertEqual(frappe.db.get_value("EdgePay Status Handoff Event", event_name, "delivery_attempts"), 2)
		err_msg = frappe.db.get_value("EdgePay Status Handoff Event", event_name, "error_message")
		self.assertNotIn("test_api_key", err_msg.lower())
		self.assertNotIn("test_secret_key", err_msg.lower())

	def test_handoff_apis_gated_against_guest(self):
		frappe.set_user("Guest")
		res1 = get_pending_payment_handoffs(source_app="RetailEdge")
		self.assertFalse(res1["ok"])
		self.assertIn("authentication required", res1["message"].lower())
		res2 = mark_payment_handoff_delivered("EP-SHE-2026-00001")
		self.assertFalse(res2["ok"])
		self.assertIn("authentication required", res2["message"].lower())
		res3 = mark_payment_handoff_failed("EP-SHE-2026-00001", "error")
		self.assertFalse(res3["ok"])
		self.assertIn("authentication required", res3["message"].lower())
		from edgepayv1.edgepay.services.api import (
			get_pending_payment_handoffs as api_get_pending,
			mark_payment_handoff_delivered as api_mark_delivered,
			mark_payment_handoff_failed as api_mark_failed,
		)

		res4 = api_get_pending(source_app="RetailEdge")
		self.assertFalse(res4["ok"])
		self.assertIn("authentication required", res4["message"].lower())
		res5 = api_mark_delivered("EP-SHE-2026-00001")
		self.assertFalse(res5["ok"])
		self.assertIn("authentication required", res5["message"].lower())
		res6 = api_mark_failed("EP-SHE-2026-00001", "error")
		self.assertFalse(res6["ok"])
		self.assertIn("authentication required", res6["message"].lower())

	def test_static_import_scan_for_decoupling(self):
		edgepay_dir = os.path.dirname(os.path.dirname(__file__))
		forbidden_apps = ["erpnext", "posnext", "retailedge", "vetedge", "coreedge", "pos_next"]
		for root, _, files in os.walk(edgepay_dir):
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
								f"Forbidden import pattern 'import {app}' found in {file_path}",
							)
							self.assertNotIn(
								f"from {app}",
								content,
								f"Forbidden import pattern 'from {app}' found in {file_path}",
							)
