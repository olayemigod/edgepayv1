# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

class EdgePayVerificationConsent(Document):
	def before_insert(self):
		if not self.granted:
			frappe.throw(_("Consent must be granted before identity verification"))
		self.granted_on = now_datetime()
		self.representative_user = self.representative_user or frappe.session.user
		request = getattr(frappe.local, "request", None)
		self.ip_address = getattr(request, "remote_addr", None)
		self.user_agent = str(getattr(request, "user_agent", "") or "")[:500]

	def validate(self):
		verification_merchant = frappe.db.get_value("EdgePay Merchant Verification", self.merchant_verification, "merchant")
		if verification_merchant != self.merchant:
			frappe.throw(_("Consent Merchant must match the Merchant Verification"))
