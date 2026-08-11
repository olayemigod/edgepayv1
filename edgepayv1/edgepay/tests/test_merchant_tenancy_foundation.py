# -*- coding: utf-8 -*-
from pathlib import Path

from frappe.tests.utils import FrappeTestCase

from edgepayv1.edgepay.services.authorization import require_merchant_access
from edgepayv1.edgepay.services.payment_requests import resolve_provider_account

APP_ROOT = Path(__file__).resolve().parents[2]


class TestMerchantTenancyFoundation(FrappeTestCase):
	def test_required_tenancy_doctypes_are_declared(self):
		for path in (
			"edgepay/doctype/edgepay_merchant/edgepay_merchant.json",
			"edgepay/doctype/edgepay_merchant_user/edgepay_merchant_user.json",
			"edgepay/doctype/edgepay_provider_account/edgepay_provider_account.json",
		):
			self.assertTrue((APP_ROOT / path).exists(), path)

	def test_payment_records_declare_merchant_scope(self):
		request_schema = (APP_ROOT / "edgepay/doctype/edgepay_payment_request/edgepay_payment_request.json").read_text()
		transaction_schema = (APP_ROOT / "edgepay/doctype/edgepay_payment_transaction/edgepay_payment_transaction.json").read_text()
		for schema in (request_schema, transaction_schema):
			self.assertIn('"fieldname":"merchant"', schema)
			self.assertIn('"fieldname":"provider_account"', schema)

	def test_tenancy_helpers_are_available(self):
		self.assertTrue(callable(require_merchant_access))
		self.assertTrue(callable(resolve_provider_account))

	def test_legacy_backfill_is_registered(self):
		patches = (APP_ROOT / "patches.txt").read_text()
		self.assertIn("edgepayv1.patches.v2_0_backfill_merchant_tenancy", patches)
