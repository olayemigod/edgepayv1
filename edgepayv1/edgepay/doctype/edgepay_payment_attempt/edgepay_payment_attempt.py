# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document


ALLOWED_STATUSES = {"Created", "Initiated", "Pending", "Successful", "Failed", "Expired", "Cancelled"}


class EdgePayPaymentAttempt(Document):
	def validate(self):
		self._set_scope_from_request()
		self._validate_attempt_number()
		self._validate_status()

	def _set_scope_from_request(self):
		if not self.payment_request:
			frappe.throw(_("Payment Request is required"))
		payment_request = frappe.get_doc("EdgePay Payment Request", self.payment_request)
		self.merchant = payment_request.merchant
		self.merchant_account = payment_request.merchant_account
		self.merchant_branch = payment_request.merchant_branch
		self.provider_account = payment_request.provider_account
		self.provider = payment_request.provider

	def _validate_attempt_number(self):
		if not self.attempt_number or int(self.attempt_number) < 1:
			frappe.throw(_("Attempt Number must be greater than zero"))
		duplicate = frappe.db.get_value(
			"EdgePay Payment Attempt",
			{
				"payment_request": self.payment_request,
				"attempt_number": self.attempt_number,
				"name": ["!=", self.name],
			},
			"name",
		)
		if duplicate:
			frappe.throw(_("Attempt Number {0} already exists for this Payment Request").format(self.attempt_number))

	def _validate_status(self):
		if self.status not in ALLOWED_STATUSES:
			frappe.throw(_("Invalid Payment Attempt status: {0}").format(self.status))
