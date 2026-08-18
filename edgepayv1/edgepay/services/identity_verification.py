# -*- coding: utf-8 -*-
"""Provider-agnostic identity verification engine.

Raw NIN/BVN values are accepted only as in-memory method arguments and must never
be persisted, logged, queued, or returned.
"""
import importlib
import re
import frappe
from frappe import _
from frappe.utils import now_datetime
from edgepayv1.edgepay.services.authorization import require_merchant_access

RAW_ID_PATTERN = re.compile(r"^\d{11}$")
REQUIRED_PASSED_CHECKS = {"NIN", "BVN", "DOB", "NAME_MATCH", "LIVENESS", "FACE_MATCH"}


def mask_identity(value):
	value = str(value or "").strip()
	return "*******" + value[-4:] if len(value) >= 4 else "****"


def _provider_adapter(provider_doc):
	module_name, class_name = provider_doc.adapter_path.rsplit(".", 1)
	adapter_class = getattr(importlib.import_module(module_name), class_name)
	return adapter_class(provider_doc)


def start_identity_verification(session_name, nin=None, bvn=None, consent_token=None):
	session = frappe.get_doc("EdgePay Identity Verification Session", session_name)
	require_merchant_access(session.merchant)
	if session.status in ("Passed", "Revoked", "Expired"):
		frappe.throw(_("This verification session is already final"))
	if session.attempt_count and session.attempt_count >= 5:
		frappe.throw(_("Identity verification attempt limit reached"))
	if session.verification_method in ("NIN", "NIN_AND_BVN") and not RAW_ID_PATTERN.fullmatch(str(nin or "")):
		frappe.throw(_("A valid 11-digit NIN is required"))
	if session.verification_method in ("BVN", "NIN_AND_BVN") and not RAW_ID_PATTERN.fullmatch(str(bvn or "")):
		frappe.throw(_("A valid 11-digit BVN is required"))
	if session.verification_method in ("BVN", "NIN_AND_BVN") and not consent_token:
		frappe.throw(_("A BVN consent token is required"))

	provider = frappe.get_doc("EdgePay Verification Provider", session.provider)
	if not provider.enabled:
		frappe.throw(_("Verification Provider is disabled"))
	adapter = _provider_adapter(provider)
	session.status = "Provider Processing"
	session.started_on = session.started_on or now_datetime()
	session.attempt_count = (session.attempt_count or 0) + 1
	session.save(ignore_permissions=True)

	# Raw identifiers stay only in this call stack and are sent directly to the adapter.
	result = adapter.verify_identity({
		"method": session.verification_method,
		"nin": nin,
		"bvn": bvn,
		"consent_token": consent_token,
		"first_name": session.declared_first_name,
		"middle_name": session.declared_middle_name,
		"last_name": session.declared_last_name,
		"date_of_birth": str(session.declared_date_of_birth),
		"phone": session.declared_phone,
		"selfie_file": session.selfie_file,
	})
	_record_checks(session, provider, result, nin=nin, bvn=bvn)
	return _finalize_session(session)


def _record_checks(session, provider, result, nin=None, bvn=None):
	for check in result.get("checks", []):
		doc = frappe.new_doc("EdgePay Identity Verification Check")
		doc.merchant = session.merchant
		doc.verification_session = session.name
		doc.check_type = check.get("type")
		doc.provider = provider.name
		doc.status = check.get("status") or "Failed"
		doc.match_score = check.get("score")
		doc.provider_reference = check.get("reference")
		if doc.check_type == "NIN" and nin:
			doc.masked_reference = mask_identity(nin)
		elif doc.check_type == "BVN" and bvn:
			doc.masked_reference = mask_identity(bvn)
		doc.failure_code = check.get("failure_code")
		doc.failure_reason = check.get("failure_reason")
		doc.checked_on = now_datetime()
		doc.insert(ignore_permissions=True)
	session.provider_session_reference = result.get("provider_session_reference")


def _finalize_session(session):
	checks = frappe.get_all("EdgePay Identity Verification Check", filters={"verification_session": session.name}, fields=["check_type", "status", "match_score"])
	status_by_type = {row.check_type: row.status for row in checks}
	failed = [check for check, status in status_by_type.items() if status == "Failed"]
	manual = [check for check, status in status_by_type.items() if status == "Manual Review"]
	missing = REQUIRED_PASSED_CHECKS - {check for check, status in status_by_type.items() if status == "Passed"}
	if failed:
		session.status = "Failed"
		session.final_decision = "Failed"
	elif manual or missing:
		session.status = "Manual Review"
		session.final_decision = "Manual Review"
		session.manual_review_required = 1
	else:
		session.status = "Passed"
		session.final_decision = "Passed"
	session.completed_on = now_datetime()
	session.save(ignore_permissions=True)
	return {"session": session.name, "status": session.status, "final_decision": session.final_decision, "checks": checks}
