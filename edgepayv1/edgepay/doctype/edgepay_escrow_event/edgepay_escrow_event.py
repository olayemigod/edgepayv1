# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document


class EdgePayEscrowEvent(Document):
	def before_save(self):
		if not self.is_new():
			frappe.throw(_("Escrow Events are immutable"))

	def on_trash(self):
		frappe.throw(_("Escrow Events cannot be deleted"))
