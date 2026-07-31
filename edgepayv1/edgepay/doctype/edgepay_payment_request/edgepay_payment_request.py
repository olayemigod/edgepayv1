# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class EdgePayPaymentRequest(Document):
	def validate(self):
		self.validate_merchant_scope()
		self.validate_amount_and_currency()
		self.validate_status()
		self.validate_idempotency_key()

	def validate_merchant_scope(self):
		if not self.merchant:
			frappe.throw(_("Merchant is required"))
		if not self.provider_account:
			frappe.throw(_("Provider Account is required"))
		account = frappe.get_doc("EdgePay Provider Account", self.provider_account)
		if account.merchant != self.merchant:
			frappe.throw(_("Provider Account does not belong to the selected Merchant"))
		if self.provider and account.provider != self.provider:
			frappe.throw(_("Provider Account does not match the selected Provider"))
		self.provider = account.provider

	def validate_idempotency_key(self):
		if self.idempotency_key:
			duplicate = frappe.db.get_value(
				"EdgePay Payment Request",
				{
					"merchant": self.merchant,
					"idempotency_key": self.idempotency_key,
					"status": ["not in", ["Cancelled", "Failed", "Expired"]],
					"name": ["!=", self.name],
				},
				"name",
			)
			if duplicate:
				frappe.throw(_("An active Payment Request with this Idempotency Key already exists: {0}").format(duplicate))

	def validate_amount_and_currency(self):
		if self.amount is not None and flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero"))
		if self.amount is not None and not self.currency:
			frappe.throw(_("Currency is required when amount is set"))

	def validate_status(self):
		allowed_statuses = ["Draft", "Initiated", "Paid", "Failed", "Expired", "Cancelled"]
		if self.status not in allowed_statuses:
			frappe.throw(_("Status must be one of: {0}").format(", ".join(allowed_statuses)))
