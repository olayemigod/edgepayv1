# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class EdgePayExternalReference(Document):
	def validate(self):
		if not self.created_on:
			self.created_on = now_datetime()
		self._validate_scope()
		self._validate_uniqueness()

	def _validate_scope(self):
		request = frappe.get_doc("EdgePay Payment Request", self.payment_request)
		if request.merchant != self.merchant or request.provider_account != self.provider_account:
			frappe.throw(_("External Reference scope must match the Payment Request"))
		if self.payment_attempt:
			attempt = frappe.get_doc("EdgePay Payment Attempt", self.payment_attempt)
			if attempt.payment_request != self.payment_request:
				frappe.throw(_("Payment Attempt does not belong to the Payment Request"))
		if self.payment_transaction:
			transaction = frappe.get_doc("EdgePay Payment Transaction", self.payment_transaction)
			if transaction.payment_request != self.payment_request:
				frappe.throw(_("Payment Transaction does not belong to the Payment Request"))

	def _validate_uniqueness(self):
		duplicate = frappe.db.get_value(
			"EdgePay External Reference",
			{
				"provider_account": self.provider_account,
				"reference_type": self.reference_type,
				"reference_value": self.reference_value,
				"active": 1,
				"name": ["!=", self.name],
			},
			"name",
		)
		if duplicate:
			frappe.throw(_("This active external reference already exists: {0}").format(duplicate))
