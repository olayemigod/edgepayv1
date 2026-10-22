# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document


class EdgePayMerchantBranch(Document):
	def validate(self):
		if not self.merchant or not self.merchant_account or not self.branch_name:
			frappe.throw(_("Merchant, Merchant Account, and Branch Name are required"))
		account_merchant = frappe.db.get_value("EdgePay Merchant Account", self.merchant_account, "merchant")
		if account_merchant != self.merchant:
			frappe.throw(_("Merchant Account does not belong to the selected Merchant"))
		duplicate = frappe.db.get_value(
			"EdgePay Merchant Branch",
			{"merchant_account": self.merchant_account, "branch_name": self.branch_name, "name": ["!=", self.name]},
			"name",
		)
		if duplicate:
			frappe.throw(_("A Branch with this name already exists under the Merchant Account"))
