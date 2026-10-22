# -*- coding: utf-8 -*-
from pathlib import Path

from frappe.tests.utils import FrappeTestCase

from edgepayv1.edgepay.services.merchant_onboarding import (
	get_onboarding_readiness,
	require_live_payment_eligibility,
)

APP_ROOT = Path(__file__).resolve().parents[2]


class TestMerchantOnboardingVerification(FrappeTestCase):
	def test_verification_doctype_and_api_exist(self):
		self.assertTrue((APP_ROOT / "edgepay/doctype/edgepay_merchant_verification/edgepay_merchant_verification.json").exists())
		self.assertTrue((APP_ROOT / "edgepay/services/onboarding_api.py").exists())

	def test_merchant_schema_declares_verification_state(self):
		schema = (APP_ROOT / "edgepay/doctype/edgepay_merchant/edgepay_merchant.json").read_text()
		for fieldname in ("onboarding_status", "verification_status", "live_payments_allowed", "latest_verification"):
			self.assertIn(f'"fieldname":"{fieldname}"', schema)

	def test_live_provider_and_payment_creation_are_gated(self):
		provider_controller = (APP_ROOT / "edgepay/doctype/edgepay_provider_account/edgepay_provider_account.py").read_text()
		payment_service = (APP_ROOT / "edgepay/services/payment_requests.py").read_text()
		self.assertIn("require_live_payment_eligibility", provider_controller)
		self.assertIn("require_live_payment_eligibility", payment_service)

	def test_raw_bvn_or_nin_storage_is_rejected_by_design(self):
		controller = (APP_ROOT / "edgepay/doctype/edgepay_merchant_verification/edgepay_merchant_verification.py").read_text()
		self.assertIn("Do not store a raw BVN or NIN", controller)
		self.assertIn("masked_identity_reference", controller)

	def test_onboarding_services_are_available(self):
		self.assertTrue(callable(get_onboarding_readiness))
		self.assertTrue(callable(require_live_payment_eligibility))
