# -*- coding: utf-8 -*-
"""Merchant onboarding readiness and verification services."""

import frappe
from frappe import _
from frappe.utils import now_datetime

VERIFIED_STATUS = "Verified"


def get_latest_passed_identity_session(merchant_name, verification_name=None):
	filters = {"merchant": merchant_name, "status": "Passed"}
	if verification_name:
		filters["merchant_verification"] = verification_name
	return frappe.db.get_value(
		"EdgePay Identity Verification Session", filters, "name", order_by="completed_on desc"
	)


def get_onboarding_readiness(merchant_name):
	merchant = frappe.get_doc("EdgePay Merchant", merchant_name)
	latest_name = frappe.db.get_value(
		"EdgePay Merchant Verification", {"merchant": merchant.name}, "name", order_by="modified desc"
	)
	verification = frappe.get_doc("EdgePay Merchant Verification", latest_name) if latest_name else None
	identity_session = get_latest_passed_identity_session(merchant.name, latest_name) if latest_name else None
	checks = [
		{"key": "legal_name", "label": _("Legal business name"), "complete": bool(merchant.legal_name)},
		{"key": "email", "label": _("Business email"), "complete": bool(merchant.email)},
		{"key": "phone", "label": _("Business phone"), "complete": bool(merchant.phone)},
		{"key": "country", "label": _("Country"), "complete": bool(merchant.country)},
		{"key": "currency", "label": _("Default currency"), "complete": bool(merchant.default_currency)},
		{"key": "identity", "label": _("Representative NIN, BVN, DOB and photo verification passed"), "complete": bool(identity_session)},
		{"key": "verification", "label": _("Merchant verification approved"), "complete": bool(verification and verification.status == VERIFIED_STATUS)},
	]
	completed = sum(1 for check in checks if check["complete"])
	return {
		"merchant": merchant.name,
		"onboarding_status": merchant.onboarding_status,
		"verification_status": merchant.verification_status,
		"verification_record": latest_name,
		"identity_session": identity_session,
		"live_payments_allowed": bool(merchant.live_payments_allowed),
		"completed": completed,
		"total": len(checks),
		"checks": checks,
		"ready": completed == len(checks) and bool(merchant.live_payments_allowed),
	}


def sync_merchant_verification_state(merchant_name, verification_name):
	verification = frappe.get_doc("EdgePay Merchant Verification", verification_name)
	merchant = frappe.get_doc("EdgePay Merchant", merchant_name)
	if verification.status == "Verified":
		identity_session = get_latest_passed_identity_session(merchant_name, verification_name)
		if not identity_session:
			frappe.throw(_("NIN, BVN, date of birth, liveness and face verification must pass before Merchant verification can be approved"))
		merchant.verification_status = "Verified"
		merchant.onboarding_status = "Completed"
		merchant.live_payments_allowed = 1
		merchant.verified_on = verification.reviewed_on or now_datetime()
		merchant.verified_by = verification.reviewed_by or frappe.session.user
		merchant.latest_verification = verification.name
	elif verification.status == "More Information Required":
		merchant.verification_status = "More Information Required"
		merchant.onboarding_status = "Action Required"
		merchant.live_payments_allowed = 0
		merchant.latest_verification = verification.name
	elif verification.status in ("Rejected", "Revoked", "Expired"):
		merchant.verification_status = verification.status
		merchant.onboarding_status = "Rejected" if verification.status == "Rejected" else "Review Required"
		merchant.live_payments_allowed = 0
		merchant.latest_verification = verification.name
	merchant.save(ignore_permissions=True)


def require_live_payment_eligibility(merchant_name):
	merchant = frappe.get_doc("EdgePay Merchant", merchant_name)
	if merchant.status != "Active":
		frappe.throw(_("Merchant must be Active before live payments can be processed"))
	if merchant.verification_status != VERIFIED_STATUS or not merchant.live_payments_allowed:
		frappe.throw(_("Merchant onboarding and verification must be completed before live payments can be processed"), frappe.PermissionError)
	if not get_latest_passed_identity_session(merchant_name, merchant.latest_verification):
		frappe.throw(_("Representative identity verification is missing or no longer valid"), frappe.PermissionError)
	return merchant
