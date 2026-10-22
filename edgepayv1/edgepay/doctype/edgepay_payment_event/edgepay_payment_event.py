# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document


class EdgePayPaymentEvent(Document):
	def before_save(self):
		if not self.is_new():
			frappe.throw(_("Payment Events are immutable"), frappe.PermissionError)

	def on_trash(self):
		frappe.throw(_("Payment Events cannot be deleted"), frappe.PermissionError)
