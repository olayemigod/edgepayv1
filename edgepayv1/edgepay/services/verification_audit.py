# -*- coding: utf-8 -*-
import json

import frappe
from frappe.utils import now_datetime

from edgepayv1.edgepay.services.security import redact_secrets


def record_verification_event(verification, event_type, previous_status=None, new_status=None, reason=None, provider_reference=None):
	"""Append an immutable, redacted merchant verification audit event."""
	doc = frappe.get_doc("EdgePay Merchant Verification", verification) if isinstance(verification, str) else verification
	event = frappe.new_doc("EdgePay Verification Audit Event")
	event.merchant = doc.merchant
	event.verification = doc.name
	event.event_type = event_type
	event.previous_status = previous_status
	event.new_status = new_status or doc.status
	event.actor = frappe.session.user or "Administrator"
	event.occurred_on = now_datetime()
	event.reason = reason
	event.provider_reference = provider_reference or getattr(doc, "provider_verification_reference", None)
	event.snapshot_json = json.dumps(redact_secrets({
		"verification_type": doc.verification_type,
		"status": doc.status,
		"risk_rating": getattr(doc, "risk_rating", None),
		"expires_on": getattr(doc, "expires_on", None),
	}), default=str)
	event.insert(ignore_permissions=True)
	return event.name
