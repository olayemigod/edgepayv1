# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document

class EdgePayIdentityVerificationSession(Document):
	def validate(self):
		verification = frappe.db.get_value("EdgePay Merchant Verification", self.merchant_verification, ["merchant", "status"], as_dict=True)
		if not verification or verification.merchant != self.merchant:
			frappe.throw(_("Identity session Merchant must match the Merchant Verification"))
		consent = frappe.db.get_value("EdgePay Verification Consent", self.consent, ["merchant", "granted", "withdrawn_on"], as_dict=True)
		if not consent or consent.merchant != self.merchant or not consent.granted or consent.withdrawn_on:
			frappe.throw(_("A valid active consent is required"))
		if self.attempt_count and self.attempt_count > 5:
			frappe.throw(_("Identity verification attempt limit reached"))
