# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe import _

class EdgePayStatusHandoffEvent(Document):
	def validate(self):
		self.validate_status()
		self.validate_idempotency_key()

	def validate_idempotency_key(self):
		if self.idempotency_key:
			duplicate = frappe.db.get_value(
				"EdgePay Status Handoff Event",
				{
					"idempotency_key": self.idempotency_key,
					"name": ["!=", self.name]
				},
				"name"
			)
			if duplicate:
				frappe.throw(_("An active Status Handoff Event with this Idempotency Key ({0}) already exists: {1}").format(self.idempotency_key, duplicate))

	def validate_status(self):
		allowed_statuses = ["Pending", "Delivered", "Failed", "Ignored"]
		if self.processing_status not in allowed_statuses:
			frappe.throw(_("Processing Status must be one of: {0}").format(", ".join(allowed_statuses)))
