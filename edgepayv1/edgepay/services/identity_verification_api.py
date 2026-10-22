# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import now_datetime
from edgepayv1.edgepay.services.authorization import require_merchant_access
from edgepayv1.edgepay.services.identity_verification import start_identity_verification

@frappe.whitelist()
def create_identity_session(merchant_verification, provider, first_name, last_name, date_of_birth, phone, middle_name=None, selfie_file=None, consent_version="1.0"):
	verification = frappe.get_doc("EdgePay Merchant Verification", merchant_verification)
	require_merchant_access(verification.merchant)
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required"), frappe.PermissionError)
	provider_doc = frappe.get_doc("EdgePay Verification Provider", provider)
	if not provider_doc.enabled:
		frappe.throw(_("Verification Provider is disabled"))
	consent = frappe.new_doc("EdgePay Verification Consent")
	consent.merchant = verification.merchant
	consent.merchant_verification = verification.name
	consent.representative_user = frappe.session.user
	consent.purpose = "Merchant representative identity, liveness and fraud-risk verification"
	consent.consent_version = consent_version
	consent.provider = provider
	consent.granted = 1
	consent.insert()

	session = frappe.new_doc("EdgePay Identity Verification Session")
	session.merchant = verification.merchant
	session.merchant_verification = verification.name
	session.consent = consent.name
	session.provider = provider
	session.representative_user = frappe.session.user
	session.verification_method = "NIN_AND_BVN"
	session.status = "Information Required"
	session.declared_first_name = first_name
	session.declared_middle_name = middle_name
	session.declared_last_name = last_name
	session.declared_date_of_birth = date_of_birth
	session.declared_phone = phone
	session.selfie_file = selfie_file
	session.insert()
	return {"session": session.name, "consent": consent.name, "status": session.status}

@frappe.whitelist()
def submit_identity_values(session_name, nin, bvn, bvn_consent_token):
	"""Submit raw identity values directly to the provider adapter.

	The values are never persisted or returned by this method.
	"""
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required"), frappe.PermissionError)
	return start_identity_verification(session_name, nin=nin, bvn=bvn, consent_token=bvn_consent_token)

@frappe.whitelist()
def get_identity_session_status(session_name):
	session = frappe.get_doc("EdgePay Identity Verification Session", session_name)
	require_merchant_access(session.merchant)
	checks = frappe.get_all("EdgePay Identity Verification Check", filters={"verification_session": session.name}, fields=["check_type", "status", "match_score", "failure_code", "failure_reason", "checked_on"], order_by="creation asc")
	return {"session": session.name, "status": session.status, "final_decision": session.final_decision, "manual_review_required": bool(session.manual_review_required), "checks": checks}
