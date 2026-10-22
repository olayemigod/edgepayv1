# -*- coding: utf-8 -*-
import re
import frappe
from frappe import _
from frappe.model.document import Document

ALLOWED_CHECKS = {"NIN", "BVN", "DOB", "NAME_MATCH", "PHONE_MATCH", "LIVENESS", "FACE_MATCH", "WATCHLIST"}

class EdgePayVerificationProvider(Document):
	def validate(self):
		self.provider_code = (self.provider_code or "").strip().upper()
		if not re.fullmatch(r"[A-Z0-9_]+", self.provider_code):
			frappe.throw(_("Provider Code may contain only letters, numbers, and underscores"))
		checks = {value.strip().upper() for value in (self.supported_checks or "").split(",") if value.strip()}
		unknown = checks - ALLOWED_CHECKS
		if unknown:
			frappe.throw(_("Unsupported verification checks: {0}").format(", ".join(sorted(unknown))))
		if self.environment == "Live" and self.base_url and not str(self.base_url).startswith("https://"):
			frappe.throw(_("Live verification providers must use HTTPS"))
