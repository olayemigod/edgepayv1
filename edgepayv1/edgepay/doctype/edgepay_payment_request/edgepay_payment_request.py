# -*- coding: utf-8 -*-
# Copyright (c) 2026, ProcessEdge Solutions Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from frappe import _
from frappe.utils import flt

class EdgePayPaymentRequest(Document):
	def validate(self):
		self.validate_amount_and_currency()
		self.validate_provider()
		self.validate_status()
		self.validate_idempotency_key()

	def validate_idempotency_key(self):
		if self.idempotency_key:
			duplicate = frappe.db.get_value(
				"EdgePay Payment Request",
				{
					"idempotency_key": self.idempotency_key,
					"status": ["not in", ["Cancelled", "Failed", "Expired"]],
					"name": ["!=", self.name]
				},
				"name"
			)
			if duplicate:
				frappe.throw(_("An active Payment Request with this Idempotency Key ({0}) already exists: {1}").format(self.idempotency_key, duplicate))

	def validate_amount_and_currency(self):
		if self.amount is not None:
			if flt(self.amount) <= 0:
				frappe.throw(_("Amount must be greater than zero"))
			if not self.currency:
				frappe.throw(_("Currency is required when amount is set"))

	def validate_provider(self):
		if not self.provider:
			frappe.throw(_("Provider is required"))

	def validate_status(self):
		allowed_statuses = ["Draft", "Initiated", "Paid", "Failed", "Expired", "Cancelled"]
		if self.status not in allowed_statuses:
			frappe.throw(_("Status must be one of: {0}").format(", ".join(allowed_statuses)))
