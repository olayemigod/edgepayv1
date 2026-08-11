# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document


class EdgePayProviderAccount(Document):
	def validate(self):
		if not self.merchant or not self.provider:
			frappe.throw(_("Merchant and Provider are required"))
		if self.environment not in ("Sandbox", "Live"):
			frappe.throw(_("Environment must be Sandbox or Live"))
		self._validate_live_eligibility()
		duplicate = frappe.db.get_value(
			"EdgePay Provider Account",
			{
				"merchant": self.merchant,
				"provider": self.provider,
				"environment": self.environment,
				"account_label": self.account_label,
				"name": ["!=", self.name],
			},
			"name",
		)
		if duplicate:
			frappe.throw(_("A matching provider account already exists for this merchant"))

	def _validate_live_eligibility(self):
		if self.environment != "Live":
			return
		if self.enabled or self.status == "Active":
			from edgepayv1.edgepay.services.merchant_onboarding import require_live_payment_eligibility
			require_live_payment_eligibility(self.merchant)
