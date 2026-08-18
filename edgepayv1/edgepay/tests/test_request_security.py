# -*- coding: utf-8 -*-
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from edgepayv1.edgepay.services.request_security import (
	DEFAULT_MAX_WEBHOOK_BYTES,
	get_max_webhook_bytes,
	require_post_request,
	validate_webhook_body,
)


class TestRequestSecurity(FrappeTestCase):
	def test_default_webhook_limit_is_bounded(self):
		with patch.object(frappe, "conf", {}):
			self.assertEqual(get_max_webhook_bytes(), DEFAULT_MAX_WEBHOOK_BYTES)

	def test_webhook_limit_cannot_exceed_two_megabytes(self):
		with patch.object(frappe, "conf", {"edgepay_max_webhook_bytes": 50 * 1024 * 1024}):
			self.assertEqual(get_max_webhook_bytes(), 2 * 1024 * 1024)

	def test_empty_webhook_body_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			validate_webhook_body(b"")

	def test_oversized_webhook_body_is_rejected(self):
		with patch.object(frappe, "conf", {"edgepay_max_webhook_bytes": 1024}):
			with self.assertRaises(frappe.ValidationError):
				validate_webhook_body(b"x" * 1025)

	def test_non_post_public_request_is_rejected(self):
		request = type("Request", (), {"method": "GET"})()
		with patch.object(frappe.local, "request", request, create=True):
			with self.assertRaises(frappe.ValidationError):
				require_post_request()
