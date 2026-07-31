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
