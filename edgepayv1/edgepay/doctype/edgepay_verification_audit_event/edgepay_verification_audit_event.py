# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document


class EdgePayVerificationAuditEvent(Document):
	def validate(self):
		if not self.is_new():
			frappe.throw(_("Verification Audit Events are immutable"))

	def on_trash(self):
		frappe.throw(_("Verification Audit Events cannot be deleted"))
