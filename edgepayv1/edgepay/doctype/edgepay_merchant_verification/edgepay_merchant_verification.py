# -*- coding: utf-8 -*-
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, today

FINAL_STATUSES = {"Verified", "Rejected", "Expired", "Revoked"}
REVIEW_STATUSES = {"Under Review", "More Information Required", "Verified", "Rejected", "Revoked"}


class EdgePayMerchantVerification(Document):
	def validate(self):
		self._validate_merchant()
		self._validate_sensitive_identity()
		self._validate_required_information()
		self._control_review_fields()

	def before_save(self):
		previous = self.get_doc_before_save()
		previous_status = previous.status if previous else None
		self.flags.previous_verification_status = previous_status
		if self.status == "Submitted" and previous_status != "Submitted":
			self.submitted_on = now_datetime()
		if self.status in REVIEW_STATUSES and previous_status != self.status:
			self._require_reviewer()
			self.reviewed_on = now_datetime()
			self.reviewed_by = frappe.session.user

	def on_update(self):
		previous_status = getattr(self.flags, "previous_verification_status", None)
		if previous_status != self.status:
			from edgepayv1.edgepay.services.verification_audit import record_verification_event
			record_verification_event(
				self,
				self.status if self.status in {"Submitted", "Under Review", "More Information Required", "Verified", "Rejected", "Revoked", "Expired"} else "Created",
				previous_status=previous_status,
				new_status=self.status,
				reason=self.rejection_reason,
			)
		if self.status in FINAL_STATUSES or self.status == "More Information Required":
			from edgepayv1.edgepay.services.merchant_onboarding import sync_merchant_verification_state
			sync_merchant_verification_state(self.merchant, self.name)

	def _validate_merchant(self):
		if not self.merchant or not frappe.db.exists("EdgePay Merchant", self.merchant):
			frappe.throw(_("A valid Merchant is required"))

	def _validate_sensitive_identity(self):
		value = (self.masked_identity_reference or "").strip()
		if not value:
			return
		if re.fullmatch(r"\d{11}", value):
			frappe.throw(_("Do not store a raw BVN or NIN. Store only a masked reference."))
		if sum(character.isdigit() for character in value) > 4 and "*" not in value:
			frappe.throw(_("Identity references must be masked and expose no more than four digits"))

	def _validate_required_information(self):
		if self.status == "Draft":
			return
		required = {
			"business_registration_number": _("CAC / Business Registration Number"),
			"business_type": _("Business Type"),
			"registered_address": _("Registered Business Address"),
			"representative_name": _("Authorised Representative Name"),
			"representative_email": _("Authorised Representative Email"),
			"representative_phone": _("Authorised Representative Phone"),
			"registration_document": _("Registration Document"),
			"address_document": _("Proof of Address"),
			"representative_identity_document": _("Representative Identity Document"),
		}
		missing = [label for fieldname, label in required.items() if not self.get(fieldname)]
		if missing:
			frappe.throw(_("Complete the following onboarding information before submission: {0}").format(", ".join(missing)))
		if self.status == "Verified" and not self.risk_rating:
			frappe.throw(_("Risk Rating is required before verification"))
		if self.status == "Rejected" and not self.rejection_reason:
			frappe.throw(_("Rejection Reason is required"))
		if self.status == "More Information Required" and not self.rejection_reason:
			frappe.throw(_("State the additional information required"))

	def _require_reviewer(self):
		roles = set(frappe.get_roles(frappe.session.user))
		if frappe.session.user != "Administrator" and not roles.intersection({"System Manager", "EdgePay Admin", "EdgePay Manager"}):
			frappe.throw(_("Only authorised EdgePay reviewers may change the verification decision"), frappe.PermissionError)

	def _control_review_fields(self):
		if self.expires_on and str(self.expires_on) < str(today()) and self.status == "Verified":
			self.status = "Expired"
