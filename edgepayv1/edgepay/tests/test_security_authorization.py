# -*- coding: utf-8 -*-
import inspect

import frappe
from frappe.tests.utils import FrappeTestCase

from edgepayv1.edgepay.services import api
from edgepayv1.edgepay.services.authorization import require_authenticated_user


class TestSecurityAuthorization(FrappeTestCase):
	def setUp(self):
		super().setUp()
		self.original_user = frappe.session.user

	def tearDown(self):
		frappe.set_user(self.original_user or "Administrator")
		super().tearDown()

	def test_create_payment_request_does_not_expose_authentication_bypass(self):
		parameters = inspect.signature(api.create_payment_request).parameters
		self.assertNotIn("ignore_auth", parameters)

	def test_guest_is_rejected_by_central_authentication_helper(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			require_authenticated_user()

	def test_guest_cannot_create_payment_request(self):
		frappe.set_user("Guest")
		result = api.create_payment_request(
			provider="Missing Provider",
			amount=100,
			currency="NGN",
			customer_name="Test Customer",
			customer_email="customer@example.com",
		)
		self.assertFalse(result["ok"])
		self.assertEqual(result["status"], "error")
		self.assertIn("Authentication required", result["message"])

	def test_guest_cannot_inspect_provider_configuration(self):
		frappe.set_user("Guest")
		result = api.validate_provider_configuration("Missing Provider")
		self.assertEqual(result["status"], "error")
		self.assertIn("Authentication required", result["message"])
