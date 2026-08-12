from __future__ import annotations

from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from edgepayv1 import hooks
from edgepayv1.api.product_context import PRODUCT_DESCRIPTOR


class TestEdgePayProductSurface(FrappeTestCase):
	def app_path(self, *parts: str) -> Path:
		return Path(frappe.get_app_path("edgepayv1", *parts))

	def test_edgesuite_dependency_preserves_domain_hooks(self):
		self.assertEqual(hooks.required_apps, ["edgesuite_ui"])
		self.assertEqual(hooks.app_home, "/app/edgepay-home")
		self.assertIn("/assets/edgepayv1/js/edgepay_product_menu.js", hooks.app_include_js)
		self.assertIn("cron", hooks.scheduler_events)
		self.assertIn("daily", hooks.scheduler_events)
		self.assertIn("EdgePay Payment Attempt", hooks.permission_query_conditions)
		self.assertIn("EdgePay Delivery Endpoint", hooks.permission_query_conditions)

	def test_permission_hooks_resolve_from_canonical_module(self):
		for doctype, method in hooks.permission_query_conditions.items():
			self.assertTrue(method.startswith("edgepayv1.edgepay.permissions."))
			fn = frappe.get_attr(method)
			self.assertTrue(callable(fn))
			condition = frappe.call(fn, "Administrator", doctype=doctype)
			self.assertIsInstance(condition, str)
		for method in set(hooks.has_permission.values()):
			self.assertEqual(method, "edgepayv1.edgepay.permissions.has_merchant_permission")
			self.assertTrue(callable(frappe.get_attr(method)))

	def test_product_descriptor_is_stable(self):
		self.assertEqual(PRODUCT_DESCRIPTOR["key"], "edgepay")
		self.assertEqual(PRODUCT_DESCRIPTOR["home_route"], "/app/edgepay-home")
		self.assertIn("/app/merchant-onboarding*", PRODUCT_DESCRIPTOR["route_patterns"])

	def test_product_menu_routes_normal_work_to_edgesuite_pages(self):
		source = self.app_path("public", "js", "edgepay_product_menu.js").read_text()
		for route in (
			"/app/edgepay-home",
			"/app/merchant-onboarding",
			"/app/edgepay-payments",
			"/app/edgepay-finance",
			"/app/edgepay-integrations",
		):
			self.assertIn(route, source)
		for raw_route in (
			'route: "/app/edgepay-payment-request"',
			'route: "/app/edgepay-payment-attempt"',
			'route: "/app/edgepay-payment-event"',
			'route: "/app/edgepay-refund-request"',
			'route: "/app/edgepay-settlement-batch"',
			'route: "/app/edgepay-api-client"',
			'route: "/app/edgepay-delivery-endpoint"',
		):
			self.assertNotIn(raw_route, source)
		self.assertNotIn("/app/edgepay-settings", source)

	def test_all_operational_pages_mount_shared_edgesuite_workspace(self):
		pages = {
			"edgepay_home": "home",
			"merchant_onboarding": "onboarding",
			"edgepay_payments": "payments",
			"edgepay_finance": "finance",
			"edgepay_integrations": "integrations",
		}
		for page, mode in pages.items():
			folder = "merchant_onboarding" if page == "merchant_onboarding" else page
			source = self.app_path("edgepay", "page", folder, f"{page}.js").read_text()
			self.assertIn("edgepay_page_loader.js", source)
			self.assertIn(f"mount(wrapper, '{mode}')", source)

	def test_workspace_uses_true_edgesuite_shell(self):
		loader = self.app_path("public", "js", "edgepay_page_loader.js").read_text()
		bundle = self.app_path("public", "js", "edgepay_workspace.bundle.js").read_text()
		workspace = self.app_path("public", "js", "edgepay_workspace", "EdgePayWorkspace.vue").read_text()
		self.assertIn("edgeui.bundle.js", loader)
		self.assertIn("EdgeAppShell", loader)
		self.assertIn("createEdgeApp", loader + bundle)
		self.assertIn("mountEdgePayWorkspace", loader + bundle)
		self.assertIn("<EdgeAppShell", workspace)
		self.assertIn("<EdgePageLayout>", workspace)
		self.assertIn("<EdgePageHeader", workspace)
		self.assertIn("<EdgeDataTable", workspace)

	def test_home_context_is_merchant_scoped(self):
		source = self.app_path("api", "home.py").read_text()
		self.assertIn("get_default_merchant_context", source)
		self.assertIn('merchant_filter = {"merchant": merchant_name}', source)
		self.assertIn('"can_bootstrap": bool(context.get("can_bootstrap"))', source)
		self.assertIn("EdgePay Payment Attempt", source)
		self.assertIn("EdgePay Provider Account", source)
		self.assertIn("EdgePay API Client", source)
		self.assertIn("EdgePay Delivery Endpoint", source)
		self.assertNotIn("ignore_permissions", source)

	def test_operations_api_is_merchant_scoped(self):
		source = self.app_path("api", "operations.py").read_text()
		self.assertIn("get_default_merchant_context", source)
		self.assertIn('filters={"merchant": merchant}', source)
		self.assertIn("frappe.get_list", source)
		self.assertNotIn("ignore_permissions", source)

	def test_normal_surface_does_not_reference_secret_fields(self):
		paths = [
			self.app_path("api", "home.py"),
			self.app_path("api", "operations.py"),
			self.app_path("public", "js", "edgepay_product_menu.js"),
			self.app_path("public", "js", "edgepay_workspace", "EdgePayWorkspace.vue"),
		]
		combined = "\n".join(path.read_text() for path in paths)
		for fieldname in (
			"api_key",
			"secret_key",
			"contract_code",
			"webhook_token",
			"client_secret",
			"checkout_token",
		):
			self.assertNotIn(fieldname, combined)
