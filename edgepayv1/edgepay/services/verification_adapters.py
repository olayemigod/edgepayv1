# -*- coding: utf-8 -*-
"""Verification provider adapter contracts and deterministic sandbox adapter."""
import hashlib
import frappe
from frappe import _

class BaseIdentityVerificationAdapter:
	def __init__(self, provider_doc):
		self.provider_doc = provider_doc

	def verify_identity(self, payload):
		raise NotImplementedError

class SandboxIdentityVerificationAdapter(BaseIdentityVerificationAdapter):
	"""Deterministic non-production adapter for UI, migration, and failure-path QA."""
	def verify_identity(self, payload):
		if self.provider_doc.environment != "Sandbox":
			frappe.throw(_("Sandbox adapter cannot be used for a Live provider"))
		seed = "|".join(str(payload.get(key) or "") for key in ("first_name", "last_name", "date_of_birth", "phone"))
		reference = "SBX-" + hashlib.sha256(seed.encode()).hexdigest()[:16].upper()
		selfie_present = bool(payload.get("selfie_file"))
		checks = []
		if payload.get("method") in ("NIN", "NIN_AND_BVN"):
			checks.append({"type":"NIN","status":"Passed","reference":reference + "-NIN"})
		if payload.get("method") in ("BVN", "NIN_AND_BVN"):
			checks.append({"type":"BVN","status":"Passed","reference":reference + "-BVN"})
		checks.extend([
			{"type":"DOB","status":"Passed","score":100,"reference":reference + "-DOB"},
			{"type":"NAME_MATCH","status":"Passed","score":98,"reference":reference + "-NAME"},
			{"type":"PHONE_MATCH","status":"Passed","score":100,"reference":reference + "-PHONE"},
			{"type":"LIVENESS","status":"Passed" if selfie_present else "Manual Review","score":99 if selfie_present else 0,"reference":reference + "-LIVE"},
			{"type":"FACE_MATCH","status":"Passed" if selfie_present else "Manual Review","score":96 if selfie_present else 0,"reference":reference + "-FACE"},
			{"type":"WATCHLIST","status":"Passed","reference":reference + "-WATCH"},
		])
		return {"provider_session_reference": reference, "checks": checks}
