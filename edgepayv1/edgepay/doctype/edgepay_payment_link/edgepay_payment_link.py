import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, get_datetime, now_datetime
from urllib.parse import urlparse


class EdgePayPaymentLink(Document):
	def autoname(self):
		if not self.public_slug:
			self.public_slug = f"pay_{frappe.generate_hash(length=18)}"
		self.name = self.public_slug

	def validate(self):
		if self.merchant_account and frappe.db.get_value("EdgePay Merchant Account", self.merchant_account, "merchant") != self.merchant:
			frappe.throw(_("Merchant Account does not belong to the selected Merchant"))
		if self.merchant_branch and frappe.db.get_value("EdgePay Merchant Branch", self.merchant_branch, "merchant") != self.merchant:
			frappe.throw(_("Merchant Branch does not belong to the selected Merchant"))
		account = frappe.get_doc("EdgePay Provider Account", self.provider_account)
		if account.merchant != self.merchant:
			frappe.throw(_("Provider Account does not belong to the selected Merchant"))
		if self.amount_mode == "Fixed" and flt(self.amount) <= 0:
			frappe.throw(_("Fixed Payment Links require an amount greater than zero"))
		if self.amount_mode == "Customer Entered" and self.minimum_amount and self.maximum_amount and flt(self.minimum_amount) > flt(self.maximum_amount):
			frappe.throw(_("Minimum Amount cannot exceed Maximum Amount"))
		if self.redirect_url:
			parsed = urlparse(self.redirect_url)
			if parsed.scheme != "https" or not parsed.netloc:
				frappe.throw(_("Return URL must be an absolute HTTPS URL"))
		if self.expires_on and get_datetime(self.expires_on) <= now_datetime() and self.status == "Active":
			self.status = "Expired"
		if self.is_new():
			self.created_by = frappe.session.user
