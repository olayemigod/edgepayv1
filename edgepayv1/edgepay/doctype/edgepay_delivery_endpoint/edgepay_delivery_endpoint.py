# -*- coding: utf-8 -*-
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document


class EdgePayDeliveryEndpoint(Document):
	def validate(self):
		parsed = urlparse(self.endpoint_url or "")
		if parsed.scheme != "https" or not parsed.netloc:
			frappe.throw(_("Delivery Endpoint URL must use HTTPS"))
		if self.environment == "Live":
			merchant = frappe.get_doc("EdgePay Merchant", self.merchant)
			if not merchant.live_payments_allowed:
				frappe.throw(_("Merchant is not approved for live delivery endpoints"))
