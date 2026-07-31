# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document


class EdgePayMerchant(Document):
	def validate(self):
		if not self.merchant_name:
			frappe.throw(_("Merchant Name is required"))
		if not self.public_id:
			self.public_id = f"MER-{frappe.generate_hash(length=12).upper()}"
		self.public_id = self.public_id.strip().upper()
