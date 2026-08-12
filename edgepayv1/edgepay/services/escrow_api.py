import json

import frappe

from edgepayv1.edgepay.services.authorization import (
	require_authenticated_user,
	require_doctype_permission,
)
from edgepayv1.edgepay.services.escrow import (
	approve_release,
	create_escrow,
	open_escrow_dispute,
	request_release,
)
from edgepayv1.edgepay.services.escrow_financial import (
	add_evidence,
	request_escrow_refund,
	submit_payout,
)
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
def request_escrow_release(
	escrow_name: str,
	actor_reference: str,
	evidence_reference: str | None = None,
	details=None,
):
	try:
		require_authenticated_user()
		return request_release(
			escrow_name,
			actor_reference,
			evidence_reference,
			_payload(details) if details else None,
		)
	except Exception as exc:
		return _safe_error(exc)


@frappe.whitelist(methods=["POST"])
def approve_escrow_release(
	escrow_name: str,
	actor_reference: str,
	evidence_reference: str | None = None,
	details=None,
):
	try:
		require_authenticated_user()
		return approve_release(
			escrow_name,
			actor_reference,
			evidence_reference,
			_payload(details) if details else None,
		)
	except Exception as exc:
		return _safe_error(exc)


@frappe.whitelist(methods=["POST"])
def dispute_escrow(
	escrow_name: str,
	actor_reference: str,
	reason: str,
	evidence_reference: str | None = None,
):
	try:
		require_authenticated_user()
		return open_escrow_dispute(escrow_name, actor_reference, reason, evidence_reference)
	except Exception as exc:
		return _safe_error(exc)


@frappe.whitelist(methods=["POST"])
def request_escrow_refund_api(escrow_name: str, amount, reason: str, actor_reference: str):
	try:
		require_authenticated_user()
		return request_escrow_refund(escrow_name, amount, reason, actor_reference)
	except Exception as exc:
		return _safe_error(exc)


@frappe.whitelist(methods=["POST"])
def submit_escrow_payout(escrow_name: str, amount=None, idempotency_key: str | None = None):
	try:
		require_authenticated_user()
		require_doctype_permission("EdgePay Escrow Payout Attempt", ptype="create")
		return submit_payout(escrow_name, amount=amount, idempotency_key=idempotency_key)
	except Exception as exc:
		return _safe_error(exc)


@frappe.whitelist(methods=["POST"])
def add_escrow_evidence(escrow_name: str, payload):
	try:
		require_authenticated_user()
		require_doctype_permission("EdgePay Escrow Evidence", ptype="create")
		data = _payload(payload)
		evidence = add_evidence(
			escrow_name,
			evidence_type=data.get("evidence_type") or "Other",
			submitted_by_type=data.get("submitted_by_type") or "Marketplace",
			submitted_by_reference=data.get("submitted_by_reference") or frappe.session.user,
			external_reference=data.get("external_reference"),
			file_url=data.get("file_url"),
			description=data.get("description"),
			source_payload=data,
		)
		return {
			"ok": True,
			"status": "success",
			"message": "Escrow evidence recorded",
			"data": {"evidence": evidence.name, "escrow_agreement": evidence.escrow_agreement},
		}
	except Exception as exc:
		return _safe_error(exc)
