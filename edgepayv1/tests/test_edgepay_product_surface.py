from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from edgepayv1 import hooks
from edgepayv1.api.product_context import get_product_availability

APP_ROOT = Path(__file__).resolve().parents[1]


class TestEdgePayProductSurface(unittest.TestCase):
	def test_hooks_register_independent_edgesuite_consumer(self):
		self.assertEqual(hooks.required_apps, ["edgesuite_ui"])
		self.assertEqual(hooks.app_home, "/app/edgepay-home")
		self.assertIn("/assets/edgepayv1/js/edgepay_product_menu.js", hooks.app_include_js)
		self.assertEqual(
			hooks.add_to_apps_screen[0]["has_permission"],
			"edgepayv1.api.permission.has_app_permission",
		)

	def test_provider_returns_stable_descriptor_only_when_available(self):
		with patch("edgepayv1.api.product_context.has_app_permission", return_value=True):
			product = get_product_availability()
		self.assertEqual(product["key"], "edgepay")
		self.assertEqual(product["label"], "EdgePay")
		self.assertEqual(product["home_route"], "/app/edgepay-home")

		with patch("edgepayv1.api.product_context.has_app_permission", return_value=False):
			self.assertIsNone(get_product_availability())

	def test_menu_uses_canonical_runtime(self):
		menu = (APP_ROOT / "public/js/edgepay_product_menu.js").read_text()
		self.assertIn('PRODUCT_KEY = "edgepay"', menu)
		self.assertIn('"edgesuite_ui.bundle.js"', menu)
		self.assertNotIn('"edgeui.bundle.js"', menu)
		self.assertNotIn("/app/edgepay-provider", menu)

	def test_home_surface_does_not_expose_platform_secrets(self):
		home_api = (APP_ROOT / "api/home.py").read_text()
		home_page = (APP_ROOT / "edgepay/page/edgepay_home/edgepay_home.js").read_text()
		combined = f"{home_api}\n{home_page}".lower()
		for forbidden in (
			"api_key",
			"secret_key",
			"contract_code",
			"allow_external_http_calls",
		):
			self.assertNotIn(forbidden, combined)
		self.assertIn("registration-readiness", home_page)
		self.assertIn("payment-summary", home_page)


if __name__ == "__main__":
	unittest.main()
