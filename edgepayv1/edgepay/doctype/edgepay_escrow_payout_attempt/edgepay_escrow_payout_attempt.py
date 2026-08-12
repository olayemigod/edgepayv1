import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class EdgePayEscrowPayoutAttempt(Document):
	def validate(self):
		agreement = frappe.get_doc("EdgePay Escrow Agreement", self.escrow_agreement)
		self.merchant = agreement.merchant
		self.provider_account = agreement.provider_account
		self.currency = agreement.currency
		self.beneficiary_reference = agreement.beneficiary_reference
		if flt(self.amount) <= 0:
			frappe.throw(_("Payout amount must be greater than zero"))
		if flt(self.amount) > flt(agreement.held_amount):
			frappe.throw(_("Payout amount cannot exceed the held escrow balance"))
		if self.provider_account != agreement.provider_account:
			frappe.throw(_("Payout Provider Account must match the Escrow Agreement"))
