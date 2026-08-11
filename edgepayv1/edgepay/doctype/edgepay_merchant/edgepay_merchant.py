# -*- coding: utf-8 -*-
import re

import frappe
from frappe import _
from frappe.model.document import Document

HEX_COLOUR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class EdgePayMerchant(Document):
	def validate(self):
		if not self.merchant_name:
			frappe.throw(_("Merchant Name is required"))
		if not self.public_id:
			self.public_id = f"MER-{frappe.generate_hash(length=12).upper()}"
		self.public_id = self.public_id.strip().upper()
		if self.checkout_primary_colour and not HEX_COLOUR_RE.match(self.checkout_primary_colour.strip()):
			frappe.throw(_("Checkout Primary Colour must be a six-digit hex colour such as #111827"))
		self._validate_live_activation()

	def _validate_live_activation(self):
		if self.status == "Active" and self.verification_status != "Verified":
			frappe.throw(_("Merchant verification must be completed before the merchant can be activated"))
		if self.live_payments_allowed and self.verification_status != "Verified":
			frappe.throw(_("Live payments cannot be enabled for an unverified merchant"))
		if self.status in ("Suspended", "Closed"):
			self.live_payments_allowed = 0
