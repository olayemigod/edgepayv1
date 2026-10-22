import frappe
from frappe.tests.utils import FrappeTestCase

from edgepayv1.edgepay.page.merchant_onboarding.merchant_onboarding import create_first_merchant
from edgepayv1.edgepay.services.merchant_context import get_default_merchant_context


class TestFirstRunMerchantBootstrap(FrappeTestCase):
	merchant_name = "QA First Run Merchant"

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self._cleanup()

	def tearDown(self):
		frappe.set_user("Administrator")
		self._cleanup()
		super().tearDown()

	def _cleanup(self):
		merchant = frappe.db.get_value("EdgePay Merchant", {"merchant_name": self.merchant_name}, "name")
		if not merchant:
			return
		frappe.db.delete("EdgePay Merchant User", {"merchant": merchant})
		frappe.db.delete("EdgePay Merchant Branch", {"merchant": merchant})
		frappe.db.delete("EdgePay Merchant Account", {"merchant": merchant})
		frappe.db.delete("EdgePay Merchant Verification", {"merchant": merchant})
		frappe.db.delete("EdgePay Merchant", {"name": merchant})

	def test_administrator_can_bootstrap_draft_merchant_context(self):
		result = create_first_merchant(
			merchant_name=self.merchant_name,
			legal_name="QA First Run Merchant Limited",
			email="qa-first-run@example.com",
			phone="08000000000",
			country="Nigeria",
			default_currency="NGN",
		)
		merchant = frappe.get_doc("EdgePay Merchant", result["merchant"])
		self.assertEqual(merchant.status, "Draft")
		self.assertEqual(merchant.onboarding_status, "In Progress")
		self.assertEqual(merchant.verification_status, "Not Submitted")
		self.assertFalse(merchant.live_payments_allowed)

		account = frappe.get_doc("EdgePay Merchant Account", result["merchant_account"])
		self.assertEqual(account.merchant, merchant.name)
		self.assertEqual(account.account_type, "Primary Business")
		self.assertEqual(account.status, "Active")

		membership = frappe.get_doc("EdgePay Merchant User", result["membership"])
		self.assertEqual(membership.user, "Administrator")
		self.assertEqual(membership.merchant, merchant.name)
		self.assertEqual(membership.merchant_role, "Owner")
		self.assertTrue(membership.active)
		self.assertTrue(membership.is_default)

		context = get_default_merchant_context("Administrator")
		self.assertEqual(context["merchant"], merchant.name)
		self.assertEqual(context["merchant_account"], account.name)
