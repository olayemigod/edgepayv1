# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class EdgePayRefundRequest(Document):
	def validate(self):
		self._set_scope()
		self._validate_transaction()
		self._validate_amount()
		self._set_audit_fields()

	def _set_scope(self):
		transaction = frappe.get_doc("EdgePay Payment Transaction", self.payment_transaction)
		self.payment_request = transaction.payment_request
		self.merchant = transaction.merchant
		self.provider_account = transaction.provider_account
		self.currency = transaction.currency

	def _validate_transaction(self):
		transaction = frappe.get_doc("EdgePay Payment Transaction", self.payment_transaction)
		if transaction.status not in {"Success", "Refunded"}:
			frappe.throw(_("Only successful transactions can be refunded"))

	def _validate_amount(self):
		transaction = frappe.get_doc("EdgePay Payment Transaction", self.payment_transaction)
		completed = frappe.db.sql(
			"""select coalesce(sum(amount), 0) from `tabEdgePay Refund Request`
			where payment_transaction=%s and status='Completed' and name!=%s""",
			(self.payment_transaction, self.name or ""),
		)[0][0]
		available = flt(transaction.amount) - flt(completed)
		if flt(self.amount) <= 0:
			frappe.throw(_("Refund amount must be greater than zero"))
		if flt(self.amount) > available:
			frappe.throw(_("Refund amount exceeds the refundable balance of {0}").format(available))
		self.refund_type = "Full" if flt(self.amount) == available else "Partial"

	def _set_audit_fields(self):
		previous = self.get_doc_before_save()
		previous_status = previous.status if previous else None
		if self.status == "Requested" and previous_status != "Requested":
			self.requested_by = frappe.session.user
			self.requested_on = now_datetime()
		if self.status == "Approved" and previous_status != "Approved":
			roles = set(frappe.get_roles(frappe.session.user))
			if frappe.session.user != "Administrator" and not roles.intersection({"EdgePay Admin", "EdgePay Manager", "System Manager"}):
				frappe.throw(_("Only authorised EdgePay reviewers may approve refunds"), frappe.PermissionError)
			self.approved_by = frappe.session.user
			self.approved_on = now_datetime()
		if self.status == "Completed" and previous_status != "Completed":
			self.completed_on = now_datetime()
