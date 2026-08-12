import frappe
from frappe import _
from frappe.model.document import Document


class EdgePayEscrowEvidence(Document):
	def validate(self):
		agreement = frappe.get_doc("EdgePay Escrow Agreement", self.escrow_agreement)
		self.merchant = agreement.merchant
		if not self.submitted_by_reference:
			frappe.throw(_("Evidence submitter reference is required"))

	def before_save(self):
		if not self.is_new():
			frappe.throw(_("Escrow Evidence is immutable; submit a new evidence record instead"))

	def on_trash(self):
		frappe.throw(_("Escrow Evidence cannot be deleted"))
