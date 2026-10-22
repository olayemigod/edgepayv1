# -*- coding: utf-8 -*-
import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime

ALLOWED_SCOPES = {"payments:create", "payments:read", "payments:verify", "transactions:read", "refunds:create", "webhooks:manage", "settlements:read"}


class EdgePayAPIClient(Document):
	def validate(self):
		if not self.client_id:
			self.client_id = f"EPC-{frappe.generate_hash(length=20).upper()}"
		if self.environment == "Live":
			merchant = frappe.get_doc("EdgePay Merchant", self.merchant)
			if merchant.verification_status != "Verified" or not merchant.live_payments_allowed:
				frappe.throw(_("Live API Clients require a verified Merchant with live payments enabled"))
		scopes = {value.strip() for value in (self.scopes or "").split(",") if value.strip()}
		invalid = scopes - ALLOWED_SCOPES
		if invalid:
			frappe.throw(_("Unsupported API scopes: {0}").format(", ".join(sorted(invalid))))
		for ip in [value.strip() for value in (self.allowed_ips or "").split(",") if value.strip()]:
			if not re.match(r"^[0-9a-fA-F:.]+$", ip):
				frappe.throw(_("Invalid IP allow-list value"))
		if self.is_new() and not self.client_secret:
			self.client_secret = frappe.generate_hash(length=48)
			self.last_rotated_on = now_datetime()
