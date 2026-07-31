# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document


class EdgePayMerchantUser(Document):
	def validate(self):
		if not self.merchant or not self.user:
			frappe.throw(_("Merchant and User are required"))
		duplicate = frappe.db.get_value(
			"EdgePay Merchant User",
			{"merchant": self.merchant, "user": self.user, "name": ["!=", self.name]},
			"name",
		)
		if duplicate:
			frappe.throw(_("This user is already linked to the selected merchant"))
