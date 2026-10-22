# -*- coding: utf-8 -*-
import re

import frappe
from frappe import _
from frappe.model.document import Document


class EdgePayMerchantAccount(Document):
	def validate(self):
		if not self.merchant or not self.account_name or not self.legal_name:
			frappe.throw(_("Merchant, Business Account Name, and Legal Name are required"))
		if self.settlement_account_number_masked:
			value = str(self.settlement_account_number_masked).strip()
			if re.fullmatch(r"\d{10}", value):
				frappe.throw(_("Do not store a complete settlement account number; use a masked value"))
			if not re.fullmatch(r"[Xx*•-]{4,}\d{4}", value):
				frappe.throw(_("Masked settlement account number must conceal all but the last four digits"))
		duplicate = frappe.db.get_value(
			"EdgePay Merchant Account",
			{"merchant": self.merchant, "account_name": self.account_name, "name": ["!=", self.name]},
			"name",
		)
		if duplicate:
			frappe.throw(_("A Merchant Account with this name already exists for the Merchant"))
