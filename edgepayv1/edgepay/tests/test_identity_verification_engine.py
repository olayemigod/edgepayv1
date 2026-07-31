# -*- coding: utf-8 -*-
from pathlib import Path
from frappe.tests.utils import FrappeTestCase

APP_ROOT = Path(__file__).resolve().parents[2]

class TestIdentityVerificationEngine(FrappeTestCase):
	def test_identity_verification_doctypes_exist(self):
		for path in (
			"edgepay/doctype/edgepay_verification_provider/edgepay_verification_provider.json",
			"edgepay/doctype/edgepay_verification_consent/edgepay_verification_consent.json",
			"edgepay/doctype/edgepay_identity_verification_session/edgepay_identity_verification_session.json",
			"edgepay/doctype/edgepay_identity_verification_check/edgepay_identity_verification_check.json",
		):
			self.assertTrue((APP_ROOT / path).exists(), path)

	def test_raw_identity_values_are_not_doctype_fields(self):
		for path in APP_ROOT.glob("edgepay/doctype/**/**.json"):
			text = path.read_text().lower()
			self.assertNotIn('"fieldname":"nin"', text)
			self.assertNotIn('"fieldname":"bvn"', text)

	def test_engine_and_sandbox_adapter_exist(self):
		engine = (APP_ROOT / "edgepay/services/identity_verification.py").read_text()
		adapters = (APP_ROOT / "edgepay/services/verification_adapters.py").read_text()
		self.assertIn("start_identity_verification", engine)
		self.assertIn("SandboxIdentityVerificationAdapter", adapters)
		self.assertIn("Raw NIN/BVN values", engine)

	def test_live_eligibility_requires_passed_identity(self):
		service = (APP_ROOT / "edgepay/services/merchant_onboarding.py").read_text()
		self.assertIn("get_latest_passed_identity_session", service)
		self.assertIn("Representative identity verification is missing", service)

	def test_frontend_uses_password_fields_and_safe_session_args(self):
		page = (APP_ROOT / "edgepay/page/merchant_onboarding/merchant_onboarding.js").read_text()
		self.assertIn("fieldtype: 'Password', label: __('NIN')", page)
		self.assertIn("fieldtype: 'Password', label: __('BVN')", page)
		self.assertIn("safeSessionArgs", page)
