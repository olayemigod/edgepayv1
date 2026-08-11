# -*- coding: utf-8 -*-
"""Permission-aware Merchant onboarding API."""

import frappe
from frappe import _

from edgepayv1.edgepay.services.authorization import (
	require_document_permission,
	require_merchant_access,
	require_platform_operations_access,
)
from edgepayv1.edgepay.services.merchant_onboarding import get_onboarding_readiness
from edgepayv1.edgepay.services.security import redact_secrets


def _error(exc):
	return {"ok": False, "status": "error", "message": redact_secrets(str(exc)), "data": None}


@frappe.whitelist()
def get_merchant_onboarding_readiness(merchant):
	try:
		require_merchant_access(merchant)
		return {"ok": True, "status": "success", "data": get_onboarding_readiness(merchant)}
	except Exception as exc:
		return _error(exc)


@frappe.whitelist()
def submit_merchant_verification(verification):
	try:
		doc = require_document_permission("EdgePay Merchant Verification", verification, ptype="write")
		require_merchant_access(doc.merchant)
		if doc.status not in ("Draft", "More Information Required"):
			frappe.throw(_("Only Draft or More Information Required verification records can be submitted"))
		doc.status = "Submitted"
		doc.save()
		merchant = frappe.get_doc("EdgePay Merchant", doc.merchant)
		merchant.onboarding_status = "Submitted"
		merchant.verification_status = "Submitted"
		merchant.live_payments_allowed = 0
		merchant.latest_verification = doc.name
		merchant.save(ignore_permissions=True)
		return {"ok": True, "status": "success", "message": _("Merchant verification submitted"), "data": {"verification": doc.name, "merchant": doc.merchant}}
	except Exception as exc:
		return _error(exc)


@frappe.whitelist()
def review_merchant_verification(verification, decision, risk_rating=None, notes=None, reason=None, expires_on=None):
	try:
		require_platform_operations_access()
		doc = frappe.get_doc("EdgePay Merchant Verification", verification)
		allowed = {"Under Review", "More Information Required", "Verified", "Rejected", "Revoked"}
		if decision not in allowed:
			frappe.throw(_("Unsupported verification decision"))
		doc.status = decision
		doc.risk_rating = risk_rating
		doc.review_notes = notes
		doc.rejection_reason = reason
		doc.expires_on = expires_on
		doc.save(ignore_permissions=True)
		return {"ok": True, "status": "success", "message": _("Merchant verification decision recorded"), "data": {"verification": doc.name, "merchant": doc.merchant, "decision": doc.status}}
	except Exception as exc:
		return _error(exc)
