from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from edgepayv1.edgepay.services.escrow import _agreement_response, _get_writable_escrow, _record_event
from edgepayv1.edgepay.services.provider_financial_adapters import get_financial_adapter
from edgepayv1.edgepay.services.refunds import create_refund_request
from edgepayv1.edgepay.services.security import redact_secrets


def submit_payout(escrow_name: str, amount=None, idempotency_key: str | None = None) -> dict:
	agreement = _get_writable_escrow(escrow_name)
	if agreement.status != "Settlement Pending":
		frappe.throw(_("Escrow must be Settlement Pending before payout submission"))
	payout_amount = flt(amount or agreement.held_amount)
	if payout_amount <= 0 or payout_amount > flt(agreement.held_amount):
		frappe.throw(_("Payout amount must be within the held escrow balance"))
	key = idempotency_key or f"Escrow:{agreement.name}:Payout:{payout_amount}:{agreement.currency}"
	existing = frappe.db.get_value("EdgePay Escrow Payout Attempt", {"idempotency_key": key}, "name")
	if existing:
		return _payout_response(frappe.get_doc("EdgePay Escrow Payout Attempt", existing), agreement)

	latest = (
		frappe.db.get_value(
			"EdgePay Escrow Payout Attempt",
			{"escrow_agreement": agreement.name},
			"attempt_number",
			order_by="attempt_number desc",
		)
		or 0
	)
	attempt = frappe.new_doc("EdgePay Escrow Payout Attempt")
	attempt.escrow_agreement = agreement.name
	attempt.amount = payout_amount
	attempt.idempotency_key = key
	attempt.attempt_number = int(latest) + 1
	attempt.started_on = now_datetime()
	attempt.request_json = json.dumps(
		redact_secrets(
			{
				"escrow_agreement": agreement.name,
				"escrow_reference": agreement.agreement_reference,
				"beneficiary_reference": agreement.beneficiary_reference,
				"amount": payout_amount,
				"currency": agreement.currency,
			}
		),
		sort_keys=True,
	)
	attempt.insert(ignore_permissions=True)
	adapter = get_financial_adapter(agreement.provider_account)
	try:
		result = adapter.submit_payout(attempt, agreement) or {}
		attempt.status = result.get("status") or "Submitted"
		attempt.provider_reference = result.get("provider_payout_reference")
		attempt.response_json = json.dumps(redact_secrets(result), default=str, sort_keys=True)
		attempt.save(ignore_permissions=True)
		_record_event(
			agreement,
			"Payout Submitted",
			status_from=agreement.status,
			status_to=agreement.status,
			amount=payout_amount,
			actor_type="Provider Adapter",
			actor_reference=agreement.provider_account,
			details={"payout_attempt": attempt.name, "status": attempt.status},
		)
		return _payout_response(attempt, agreement)
	except Exception as exc:
		attempt.status = "Failed"
		attempt.error_message = str(exc)
		attempt.completed_on = now_datetime()
		attempt.save(ignore_permissions=True)
		_record_event(
			agreement,
			"Payout Failed",
			status_from=agreement.status,
			status_to=agreement.status,
			amount=payout_amount,
			actor_type="Provider Adapter",
			actor_reference=agreement.provider_account,
			details={"payout_attempt": attempt.name, "error": redact_secrets(str(exc))},
		)
		raise


def complete_payout(payout_attempt_name: str, provider_reference: str | None = None) -> dict:
	attempt = frappe.get_doc("EdgePay Escrow Payout Attempt", payout_attempt_name)
	agreement = _get_writable_escrow(attempt.escrow_agreement)
	if attempt.status == "Completed":
		return _payout_response(attempt, agreement)
	if attempt.status not in {"Created", "Submitted", "Processing"}:
		frappe.throw(_("Payout attempt is not awaiting completion"))
	if flt(attempt.amount) > flt(agreement.held_amount):
		frappe.throw(_("Confirmed payout exceeds the current held escrow balance"))
	attempt.status = "Completed"
	attempt.completed_on = now_datetime()
	if provider_reference:
		attempt.provider_reference = provider_reference
	attempt.save(ignore_permissions=True)

	agreement.released_amount = flt(agreement.released_amount) + flt(attempt.amount)
	agreement.held_amount = max(
		0, flt(agreement.funded_amount) - flt(agreement.released_amount) - flt(agreement.refunded_amount)
	)
	old_status = agreement.status
	if agreement.held_amount == 0:
		agreement.status = "Released"
		agreement.released_on = now_datetime()
	agreement.save(ignore_permissions=True)
	_record_event(
		agreement,
		"Payout Completed",
		status_from=old_status,
		status_to=agreement.status,
		amount=attempt.amount,
		actor_type="Provider or Trustee",
		actor_reference=attempt.provider_reference or agreement.provider_account,
		source_event_reference=attempt.provider_reference,
		details={"payout_attempt": attempt.name},
	)
	return _payout_response(attempt, agreement)


def request_escrow_refund(escrow_name: str, amount, reason: str, actor_reference: str) -> dict:
	agreement = _get_writable_escrow(escrow_name)
	if agreement.status not in {"Held", "Release Pending", "Settlement Pending", "Disputed"}:
		frappe.throw(_("Escrow is not eligible for a refund"))
	requested = flt(amount)
	if requested <= 0 or requested > flt(agreement.held_amount):
		frappe.throw(_("Refund amount must be within the held escrow balance"))

	remaining = requested
	refunds = []
	transactions = frappe.get_all(
		"EdgePay Payment Transaction",
		filters={"payment_request": agreement.payment_request, "status": ["in", ["Success", "Refunded"]]},
		fields=["name", "amount"],
		order_by="paid_on asc, creation asc",
	)
	for row in transactions:
		completed = frappe.db.get_value(
			"EdgePay Refund Request",
			{"payment_transaction": row.name, "status": "Completed"},
			"sum(amount)",
		) or 0
		available = max(0, flt(row.amount) - flt(completed))
		allocation = min(remaining, available)
		if allocation <= 0:
			continue
		refund = create_refund_request(row.name, allocation, reason)
		refunds.append(refund.name)
		remaining -= allocation
		if remaining <= 0:
			break
	if remaining > 0:
		frappe.throw(_("Verified payment transactions do not have enough refundable balance"))
	old_status = agreement.status
	agreement.status = "Refund Pending"
	agreement.save(ignore_permissions=True)
	_record_event(
		agreement,
		"Escrow Refund Requested",
		status_from=old_status,
		status_to="Refund Pending",
		amount=requested,
		actor_type="Source Party",
		actor_reference=actor_reference,
		details={"refund_requests": refunds, "reason": reason},
	)
	response = _agreement_response(agreement, "Escrow refund requests created")
	response["data"]["refund_requests"] = refunds
	return response


def sync_from_refund_request(refund_request_name: str) -> None:
	refund = frappe.get_doc("EdgePay Refund Request", refund_request_name)
	agreement_name = frappe.db.get_value(
		"EdgePay Escrow Agreement", {"payment_request": refund.payment_request}, "name"
	)
	if not agreement_name:
		return
	agreement = frappe.get_doc("EdgePay Escrow Agreement", agreement_name)
	completed = frappe.db.sql(
		"""select coalesce(sum(r.amount), 0)
		from `tabEdgePay Refund Request` r
		where r.payment_request=%s and r.status='Completed'""",
		(agreement.payment_request,),
	)[0][0]
	new_total = min(flt(completed), flt(agreement.funded_amount) - flt(agreement.released_amount))
	previous_total = flt(agreement.refunded_amount)
	agreement.refunded_amount = new_total
	agreement.held_amount = max(
		0, flt(agreement.funded_amount) - flt(agreement.released_amount) - flt(agreement.refunded_amount)
	)
	old_status = agreement.status
	if agreement.held_amount == 0 and agreement.refunded_amount > 0:
		agreement.status = "Refunded" if agreement.released_amount == 0 else "Released"
		agreement.refunded_on = now_datetime()
	elif agreement.status == "Refund Pending" and new_total > previous_total:
		agreement.status = "Held"
	agreement.save(ignore_permissions=True)
	if new_total > previous_total:
		_record_event(
			agreement,
			"Escrow Refund Completed",
			status_from=old_status,
			status_to=agreement.status,
			amount=new_total - previous_total,
			actor_type="Provider",
			actor_reference=refund.provider_account,
			source_event_reference=refund.provider_reference,
			details={"refund_request": refund.name},
		)


def add_evidence(
	escrow_name: str,
	evidence_type: str,
	submitted_by_type: str,
	submitted_by_reference: str,
	external_reference: str | None = None,
	file_url: str | None = None,
	description: str | None = None,
	source_payload: dict | None = None,
):
	agreement = _get_writable_escrow(escrow_name)
	evidence = frappe.new_doc("EdgePay Escrow Evidence")
	evidence.escrow_agreement = agreement.name
	evidence.evidence_type = evidence_type
	evidence.submitted_by_type = submitted_by_type
	evidence.submitted_by_reference = submitted_by_reference
	evidence.external_reference = external_reference
	evidence.file_url = file_url
	evidence.description = description
	evidence.occurred_on = now_datetime()
	evidence.source_payload_json = json.dumps(redact_secrets(source_payload or {}), default=str, sort_keys=True)
	evidence.insert(ignore_permissions=True)
	_record_event(
		agreement,
		"Evidence Submitted",
		status_from=agreement.status,
		status_to=agreement.status,
		actor_type=submitted_by_type,
		actor_reference=submitted_by_reference,
		evidence_reference=evidence.name,
		details={"evidence_type": evidence_type, "external_reference": external_reference},
	)
	return evidence


def _payout_response(attempt, agreement):
	return {
		"ok": True,
		"status": "success",
		"message": "Escrow payout state updated",
		"data": redact_secrets(
			{
				"payout_attempt": attempt.name,
				"payout_status": attempt.status,
				"provider_reference": attempt.provider_reference,
				"amount": attempt.amount,
				"currency": attempt.currency,
				"escrow_agreement": agreement.name,
				"escrow_status": agreement.status,
				"held_amount": agreement.held_amount,
				"released_amount": agreement.released_amount,
			}
		),
	}
