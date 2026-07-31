# -*- coding: utf-8 -*-
from pathlib import Path

from frappe.tests.utils import FrappeTestCase

from edgepayv1 import hooks
from edgepayv1.edgepay.services import merchant_queries

APP_ROOT = Path(__file__).resolve().parents[2]


class TestMerchantOperationsScope(FrappeTestCase):
	def test_business_account_and_branch_doctypes_exist(self):
		for relative in (
			"edgepay/doctype/edgepay_merchant_account/edgepay_merchant_account.json",
			"edgepay/doctype/edgepay_merchant_branch/edgepay_merchant_branch.json",
		):
			self.assertTrue((APP_ROOT / relative).exists(), relative)

	def test_payment_request_has_account_and_branch_context(self):
		schema = (APP_ROOT / "edgepay/doctype/edgepay_payment_request/edgepay_payment_request.json").read_text()
		self.assertIn('"fieldname":"merchant_account"', schema)
		self.assertIn('"fieldname":"merchant_branch"', schema)

	def test_webhook_and_handoff_are_merchant_scoped(self):
		for relative in (
			"edgepay/doctype/edgepay_webhook_event/edgepay_webhook_event.json",
			"edgepay/doctype/edgepay_status_handoff_event/edgepay_status_handoff_event.json",
		):
			schema = (APP_ROOT / relative).read_text()
			self.assertIn('"fieldname":"merchant"', schema)
			self.assertIn('"fieldname":"provider_account"', schema)

	def test_permission_queries_are_registered(self):
		self.assertIn("EdgePay Payment Request", hooks.permission_query_conditions)
		self.assertIn("EdgePay Webhook Event", hooks.permission_query_conditions)
		self.assertIn("EdgePay Status Handoff Event", hooks.permission_query_conditions)

	def test_smart_queries_and_form_script_exist(self):
		self.assertTrue(callable(merchant_queries.merchant_account_query))
		self.assertTrue(callable(merchant_queries.merchant_branch_query))
		self.assertTrue(callable(merchant_queries.provider_account_query))
		self.assertTrue((APP_ROOT / "public/js/edgepay_payment_request.js").exists())
