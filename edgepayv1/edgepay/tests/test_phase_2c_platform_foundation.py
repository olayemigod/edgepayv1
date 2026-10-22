# -*- coding: utf-8 -*-
from pathlib import Path

from frappe.tests.utils import FrappeTestCase

APP_ROOT = Path(__file__).resolve().parents[2]


class TestPhase2CPlatformFoundation(FrappeTestCase):
	def test_api_client_and_audit_event_doctypes_exist(self):
		for path in (
			"edgepay/doctype/edgepay_api_client/edgepay_api_client.json",
			"edgepay/doctype/edgepay_verification_audit_event/edgepay_verification_audit_event.json",
		):
			self.assertTrue((APP_ROOT / path).exists(), path)

	def test_onboarding_page_exists(self):
		for path in (
			"edgepay/page/merchant_onboarding/merchant_onboarding.json",
			"edgepay/page/merchant_onboarding/merchant_onboarding.py",
			"edgepay/page/merchant_onboarding/merchant_onboarding.js",
		):
			self.assertTrue((APP_ROOT / path).exists(), path)

	def test_integrity_and_webhook_resolution_services_exist(self):
		for path in (
			"edgepay/services/integrity_audit.py",
			"edgepay/services/webhook_resolution.py",
			"edgepay/services/merchant_context.py",
			"edgepay/services/verification_audit.py",
		):
			self.assertTrue((APP_ROOT / path).exists(), path)
