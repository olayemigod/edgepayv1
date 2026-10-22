# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document


class EdgePayDeliveryAttempt(Document):
	def validate(self):
		if self.is_new() is False:
			frappe.throw(_("Delivery Attempt records are immutable"))
