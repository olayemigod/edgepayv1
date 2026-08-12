# -*- coding: utf-8 -*-
from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from edgepayv1.edgepay.services.authorization import require_merchant_access
from edgepayv1.edgepay.services.escrow_adapters import normalize_escrow_payload
from edgepayv1.edgepay.services.payment_requests import create_payment_request_record, resolve_provider_account
from edgepayv1.edgepay.services.security import redact_secrets


ACTIVE_TERMINAL_STATUSES = {"Released", "Refunded", "Cancelled"}


def create_escrow(source_adapter: str, payload: dict) -> dict:
	normalized = normalize_escrow_payload(source_adapter, payload)
	account = resolve_provider_account(
		normalized["provider"],
		provider_account=normalized.get("provider_account"),
	)
	require_merchant_access(account.merchant)

	idempotency_key = normalized.get("idempotency_key")
	if idempotency_key:
		existing = frappe.db.get_value(
			"EdgePay Escrow Agreement",
			{
				"merchant": account.merchant,
				"idempotency_key": idempotency_key,
				"status": ["not in", list(ACTIVE_TERMINAL_STATUSES)],
			},
			"name",
		)
		if existing:
			return _agreement_response(frappe.get_doc("EdgePay Escrow Agreement", existing), "Existing active escrow retrieved successfully")

	agreement = frappe.new_doc("EdgePay Escrow Agreement")
	agreement.agreement_reference = f"ESC-{frappe.generate_hash(length=14)}"
	agreement.merchant = account.merchant
	agreement.provider_account = account.name
	agreement.provider = account.provider
	agreement.status = "Draft"
	for fieldname in (
		"source_adapter",
		"source_app",
		"source_doctype",
		"source_name",
		"external_trade_reference",
		"external_tenant_reference",
		"external_company_reference",
		"external_branch_reference",
		"buyer_reference",
		"buyer_name",
		"buyer_email",
		"buyer_phone",
		"beneficiary_reference",
		"beneficiary_name",
		"amount",
		"currency",
		"custody_mode",
		"release_policy",
		"acceptance_deadline",
		"dispute_deadline",
		"idempotency_key",
	):
		setattr(agreement, fieldname, normalized.get(fieldname))
	agreement.source_payload_json = json.dumps(redact_secrets(normalized["source_payload"]), default=str, sort_keys=True)
	agreement.metadata_json = json.dumps(redact_secrets(normalized.get("metadata") or {}), default=str, sort_keys=True)
	agreement.insert()
	_record_event(agreement, "Escrow Created", status_from=None, status_to="Draft", details={"source_adapter": normalized["source_adapter"]})

	payment = create_payment_request_record(
		provider=account.provider,
		provider_account=account.name,
		merchant=account.merchant,
		amount=agreement.amount,
		currency=agreement.currency,
		customer_name=agreement.buyer_name,
		customer_email=agreement.buyer_email,
		customer_phone=agreement.buyer_phone,
		payment_purpose=normalized.get("payment_purpose"),
		source_app=agreement.source_app,
		source_doctype=agreement.source_doctype,
		source_name=agreement.source_name,
		external_tenant_reference=agreement.external_tenant_reference,
		external_company_reference=agreement.external_company_reference,
		external_branch_reference=agreement.external_branch_reference,
		metadata_json={"escrow_agreement": agreement.name, "escrow_reference": agreement.agreement_reference},
		idempotency_key=f"Escrow:{agreement.agreement_reference}:funding",
	)
	payment_name = (payment.get("data") or {}).get("payment_request")
	agreement.payment_request = payment_name
	_transition(agreement, "Awaiting Funding", "Funding Requested", details={"payment_request": payment_name})
	return _agreement_response(agreement, "Escrow created and funding request prepared")


def sync_from_payment_request(payment_request_name: str) -> None:
	agreement_name = frappe.db.get_value("EdgePay Escrow Agreement", {"payment_request": payment_request_name}, "name")
	if not agreement_name:
		return
	agreement = frappe.get_doc("EdgePay Escrow Agreement", agreement_name)
	payment_request = frappe.get_doc("EdgePay Payment Request", payment_request_name)
	paid = flt(getattr(payment_request, "paid_amount", 0))
	agreement.funded_amount = min(paid, flt(agreement.amount))
	agreement.held_amount = max(0, agreement.funded_amount - flt(agreement.released_amount) - flt(agreement.refunded_amount))
	if agreement.funded_amount >= flt(agreement.amount) and agreement.status in {"Awaiting Funding", "Funded"}:
		old_status = agreement.status
		agreement.status = "Held"
		if not agreement.funded_on:
			agreement.funded_on = now_datetime()
		agreement.save(ignore_permissions=True)
		_record_event(agreement, "Funding Confirmed", status_from=old_status, status_to="Held", amount=agreement.funded_amount)
	else:
		agreement.save(ignore_permissions=True)


def request_release(escrow_name: str, actor_reference: str, evidence_reference: str | None = None, details: dict | None = None) -> dict:
	agreement = _get_writable_escrow(escrow_name)
	if agreement.status != "Held":
		frappe.throw(_("Only a fully funded held escrow can enter release review"))
	if agreement.release_policy == "Evidence Approval" and not evidence_reference:
		frappe.throw(_("Evidence reference is required by this escrow release policy"))
	_transition(
		agreement,
		"Release Pending",
		"Release Requested",
		actor_type="Source Party",
		actor_reference=actor_reference,
		evidence_reference=evidence_reference,
		details=details,
	)
	return _agreement_response(agreement, "Escrow release request recorded")


def approve_release(escrow_name: str, actor_reference: str, evidence_reference: str | None = None, details: dict | None = None) -> dict:
	agreement = _get_writable_escrow(escrow_name)
	if agreement.status not in {"Held", "Release Pending"}:
		frappe.throw(_("Escrow is not eligible for release approval"))
	# Approval is intentionally not treated as money movement. Provider/trustee payout
	# confirmation must later move Settlement Pending -> Released.
	_transition(
		agreement,
		"Settlement Pending",
		"Release Approved",
		actor_type="Approver",
		actor_reference=actor_reference,
		evidence_reference=evidence_reference,
		details=details,
	)
	return _agreement_response(agreement, "Escrow release approved; settlement confirmation is pending")


def open_escrow_dispute(escrow_name: str, actor_reference: str, reason: str, evidence_reference: str | None = None) -> dict:
	agreement = _get_writable_escrow(escrow_name)
	if agreement.status not in {"Held", "Release Pending", "Settlement Pending"}:
		frappe.throw(_("Escrow cannot be disputed in its current state"))
	_transition(
		agreement,
		"Disputed",
		"Escrow Disputed",
		actor_type="Source Party",
		actor_reference=actor_reference,
		evidence_reference=evidence_reference,
		details={"reason": reason},
	)
	return _agreement_response(agreement, "Escrow dispute opened")


def record_settlement(escrow_name: str, amount, actor_reference: str, source_event_reference: str | None = None) -> dict:
	agreement = _get_writable_escrow(escrow_name)
	if agreement.status != "Settlement Pending":
		frappe.throw(_("Escrow must be Settlement Pending before settlement confirmation"))
	settlement_amount = flt(amount)
	if settlement_amount <= 0 or settlement_amount > flt(agreement.held_amount):
		frappe.throw(_("Settlement amount must be within the held escrow balance"))
	agreement.released_amount = flt(agreement.released_amount) + settlement_amount
	agreement.held_amount = max(0, flt(agreement.funded_amount) - flt(agreement.released_amount) - flt(agreement.refunded_amount))
	old_status = agreement.status
	if agreement.held_amount == 0:
		agreement.status = "Released"
		agreement.released_on = now_datetime()
	agreement.save(ignore_permissions=True)
	_record_event(
		agreement,
		"Settlement Confirmed",
		status_from=old_status,
		status_to=agreement.status,
		amount=settlement_amount,
		actor_type="Provider or Trustee",
		actor_reference=actor_reference,
		source_event_reference=source_event_reference,
	)
	return _agreement_response(agreement, "Escrow settlement recorded")


def _get_writable_escrow(name):
	doc = frappe.get_doc("EdgePay Escrow Agreement", name)
	require_merchant_access(doc.merchant)
	if not doc.has_permission("write"):
		frappe.throw(_("You are not permitted to update this Escrow Agreement"), frappe.PermissionError)
	return doc


def _transition(doc, target, event_type, actor_type="System", actor_reference=None, evidence_reference=None, details=None):
	old_status = doc.status
	doc.status = target
	doc.save(ignore_permissions=True)
	_record_event(
		doc,
		event_type,
		status_from=old_status,
		status_to=target,
		actor_type=actor_type,
		actor_reference=actor_reference,
		evidence_reference=evidence_reference,
		details=details,
	)


def _record_event(
	doc,
	event_type,
	status_from=None,
	status_to=None,
	amount=0,
	actor_type="System",
	actor_reference=None,
	evidence_reference=None,
	source_event_reference=None,
	details=None,
):
	if source_event_reference:
		existing = frappe.db.get_value(
			"EdgePay Escrow Event",
			{"merchant": doc.merchant, "source_event_reference": source_event_reference},
			"name",
		)
		if existing:
			return frappe.get_doc("EdgePay Escrow Event", existing)
	event = frappe.new_doc("EdgePay Escrow Event")
	event.merchant = doc.merchant
	event.escrow_agreement = doc.name
	event.event_type = event_type
	event.status_from = status_from
	event.status_to = status_to
	event.amount = flt(amount)
	event.currency = doc.currency
	event.actor_type = actor_type
	event.actor_reference = actor_reference
	event.evidence_reference = evidence_reference
	event.source_event_reference = source_event_reference
	event.occurred_on = now_datetime()
	event.details_json = json.dumps(redact_secrets(details or {}), default=str, sort_keys=True)
	event.insert(ignore_permissions=True)
	return event


def _agreement_response(doc, message):
	return {
		"ok": True,
		"status": "success",
		"message": message,
		"data": redact_secrets(
			{
				"escrow_agreement": doc.name,
				"agreement_reference": doc.agreement_reference,
				"merchant": doc.merchant,
				"status": doc.status,
				"amount": doc.amount,
				"funded_amount": doc.funded_amount,
				"held_amount": doc.held_amount,
				"released_amount": doc.released_amount,
				"refunded_amount": doc.refunded_amount,
				"currency": doc.currency,
				"payment_request": doc.payment_request,
				"source_adapter": doc.source_adapter,
				"source_app": doc.source_app,
				"source_name": doc.source_name,
			}
		),
	}
