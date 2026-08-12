import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from edgepayv1.edgepay.services.merchant_queries import validate_branch_context

ALLOWED_STATUSES = {
	"Draft",
	"Awaiting Funding",
	"Funded",
	"Held",
	"Release Pending",
	"Settlement Pending",
	"Released",
	"Refund Pending",
	"Refunded",
	"Disputed",
	"Cancelled",
}


class EdgePayEscrowAgreement(Document):
	def validate(self):
		self._validate_scope()
		self._validate_parties()
		self._validate_amounts()
		self._validate_status()
		self._validate_idempotency()

	def _validate_scope(self):
		if not self.merchant:
			frappe.throw(_("Merchant is required"))
		validate_branch_context(self.merchant, self.merchant_account, self.merchant_branch)
		if not self.provider_account:
			frappe.throw(_("Provider Account is required"))
		account = frappe.get_doc("EdgePay Provider Account", self.provider_account)
		if account.merchant != self.merchant:
			frappe.throw(_("Provider Account does not belong to the selected Merchant"))
		if self.provider and account.provider != self.provider:
			frappe.throw(_("Provider Account does not match the selected Provider"))
		self.provider = account.provider

	def _validate_parties(self):
		if not self.buyer_reference or not self.beneficiary_reference:
			frappe.throw(_("Buyer and Beneficiary references are required"))
		if self.buyer_reference == self.beneficiary_reference:
			frappe.throw(_("Buyer and Beneficiary must be different parties"))

	def _validate_amounts(self):
		if flt(self.amount) <= 0:
			frappe.throw(_("Escrow amount must be greater than zero"))
		for fieldname in ("funded_amount", "held_amount", "released_amount", "refunded_amount"):
			if flt(getattr(self, fieldname, 0)) < 0:
				frappe.throw(_("Escrow financial totals cannot be negative"))
		if flt(self.released_amount) + flt(self.refunded_amount) > flt(self.funded_amount):
			frappe.throw(_("Released and refunded amounts cannot exceed funded amount"))

	def _validate_status(self):
		if self.status not in ALLOWED_STATUSES:
			frappe.throw(_("Invalid escrow status"))

	def _validate_idempotency(self):
		if not self.idempotency_key:
			return
		duplicate = frappe.db.get_value(
			"EdgePay Escrow Agreement",
			{
				"merchant": self.merchant,
				"idempotency_key": self.idempotency_key,
				"name": ["!=", self.name],
				"status": ["not in", ["Cancelled", "Refunded", "Released"]],
			},
			"name",
		)
		if duplicate:
			frappe.throw(
				_("An active Escrow Agreement with this Idempotency Key already exists: {0}").format(
					duplicate
				)
			)
