# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document


class EdgePayAPIRequestNonce(Document):
	def before_save(self):
		if not self.is_new():
			frappe.throw("API Request Nonce records are immutable")

	def on_trash(self):
		if not frappe.flags.in_patch:
			frappe.throw("API Request Nonce records cannot be deleted manually")
