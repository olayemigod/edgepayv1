# -*- coding: utf-8 -*-
import json

import frappe

from edgepayv1.edgepay.services.authorization import require_authenticated_user, require_doctype_permission
from edgepayv1.edgepay.services.escrow import approve_release, create_escrow, open_escrow_dispute, request_release
from edgepayv1.edgepay.services.security import redact_secrets


def _payload(value):
	if isinstance(value, dict):
		return value
	if isinstance(value, str):
		parsed = json.loads(value)
		if isinstance(parsed, dict):
			return parsed
	raise ValueError("payload must be a JSON object")


def _safe_error(exc):
	return {"ok": False, "status": "error", "message": redact_secrets(str(exc)), "data": None}


@frappe.whitelist(methods=["POST"])
def create_escrow_agreement(source_adapter: str, payload):
	try:
		require_authenticated_user()
		require_doctype_permission("EdgePay Escrow Agreement", ptype="create")
		return create_escrow(source_adapter, _payload(payload))
	except Exception as exc:
		return _safe_error(exc)


@frappe.whitelist(methods=["POST"])
def request_escrow_release(escrow_name: str, actor_reference: str, evidence_reference: str | None = None, details=None):
	try:
		require_authenticated_user()
		return request_release(escrow_name, actor_reference, evidence_reference, _payload(details) if details else None)
	except Exception as exc:
		return _safe_error(exc)


@frappe.whitelist(methods=["POST"])
def approve_escrow_release(escrow_name: str, actor_reference: str, evidence_reference: str | None = None, details=None):
	try:
		require_authenticated_user()
		return approve_release(escrow_name, actor_reference, evidence_reference, _payload(details) if details else None)
	except Exception as exc:
		return _safe_error(exc)


@frappe.whitelist(methods=["POST"])
def dispute_escrow(escrow_name: str, actor_reference: str, reason: str, evidence_reference: str | None = None):
	try:
		require_authenticated_user()
		return open_escrow_dispute(escrow_name, actor_reference, reason, evidence_reference)
	except Exception as exc:
		return _safe_error(exc)
