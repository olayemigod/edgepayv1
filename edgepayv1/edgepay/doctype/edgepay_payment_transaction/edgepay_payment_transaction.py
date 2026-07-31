# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class EdgePayPaymentTransaction(Document):
	def validate(self):
		self.set_scope_from_payment_request()
		self.validate_amount_and_currency()
		self.validate_provider()
		self.validate_status()
		self.validate_idempotency_key()

	def set_scope_from_payment_request(self):
		if not self.payment_request:
			return
		request = frappe.get_doc("EdgePay Payment Request", self.payment_request)
		self.merchant = request.merchant
		self.provider_account = request.provider_account
		self.provider = request.provider
		if self.merchant and self.provider_account:
			account_merchant = frappe.db.get_value("EdgePay Provider Account", self.provider_account, "merchant")
			if account_merchant != self.merchant:
				frappe.throw(_("Transaction Provider Account does not belong to the Payment Request Merchant"))

	def validate_idempotency_key(self):
		if self.idempotency_key:
			duplicate = frappe.db.get_value(
				"EdgePay Payment Transaction",
				{
					"merchant": self.merchant,
					"idempotency_key": self.idempotency_key,
					"status": ["!=", "Failed"],
					"name": ["!=", self.name],
				},
				"name",
			)
			if duplicate:
				frappe.throw(_("An active Payment Transaction with this Idempotency Key already exists: {0}").format(duplicate))

	def validate_amount_and_currency(self):
		if self.amount is not None and flt(self.amount) <= 0:
			frappe.throw(_("Amount must be greater than zero"))
		if self.amount is not None and not self.currency:
			frappe.throw(_("Currency is required when amount is set"))

	def validate_provider(self):
		if not self.provider:
			frappe.throw(_("Provider is required"))

	def validate_status(self):
		allowed_statuses = ["Pending", "Success", "Failed", "Refunded"]
		if self.status not in allowed_statuses:
			frappe.throw(_("Status must be one of: {0}").format(", ".join(allowed_statuses)))
