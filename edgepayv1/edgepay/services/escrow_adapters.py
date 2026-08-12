"""Source adapters for the reusable EdgePay escrow domain.

Adapters normalize product-specific trade payloads into the stable EdgePay escrow
contract. The original source payload is always retained separately so product
fields can evolve without leaking product-specific schema into the escrow core.
"""

from __future__ import annotations

from copy import deepcopy

import frappe
from frappe import _
from frappe.utils import flt

from edgepayv1.edgepay.services.security import redact_secrets


def normalize_escrow_payload(source_adapter: str, payload: dict) -> dict:
	adapter = (source_adapter or "generic").strip().lower()
	if not isinstance(payload, dict):
		frappe.throw(_("Escrow source payload must be a JSON object"))
	if adapter in {"agricedge", "agricedge_trade", "agricedge-trade"}:
		return _normalize_agricedge(payload)
	if adapter in {"generic", "edgepay"}:
		return _normalize_generic(payload)
	frappe.throw(_("Unsupported escrow source adapter: {0}").format(source_adapter))


def _normalize_agricedge(payload: dict) -> dict:
	trade_id = _required(payload, "trade_id")
	buyer_id = _required(payload, "buyer_id")
	seller_id = _required(payload, "seller_id")
	if buyer_id == seller_id:
		frappe.throw(_("AgricEdge buyer and seller must be different parties"))

	normalized = {
		"source_adapter": "AgricEdge",
		"source_app": "AgricEdge",
		"source_doctype": str(payload.get("source_doctype") or "AgricEdge Trade"),
		"source_name": trade_id,
		"external_trade_reference": trade_id,
		"external_tenant_reference": payload.get("tenant_reference")
		or payload.get("external_tenant_reference"),
		"external_company_reference": payload.get("company_reference")
		or payload.get("external_company_reference"),
		"external_branch_reference": payload.get("branch_reference")
		or payload.get("external_branch_reference"),
		"buyer_reference": buyer_id,
		"buyer_name": _required(payload, "buyer_name"),
		"buyer_email": _required(payload, "buyer_email"),
		"buyer_phone": payload.get("buyer_phone"),
		"beneficiary_reference": seller_id,
		"beneficiary_name": payload.get("seller_name"),
		"amount": flt(_required(payload, "amount")),
		"currency": str(payload.get("currency") or "NGN").upper(),
		"provider": _required(payload, "provider"),
		"provider_account": payload.get("provider_account"),
		"custody_mode": str(payload.get("custody_mode") or "Provider Managed"),
		"release_policy": str(payload.get("release_policy") or "Buyer Acceptance"),
		"acceptance_deadline": payload.get("acceptance_deadline"),
		"dispute_deadline": payload.get("dispute_deadline"),
		"idempotency_key": str(
			payload.get("idempotency_key") or f"AgricEdge:Trade:{trade_id}:escrow"
		),
		"payment_purpose": str(
			payload.get("description") or f"AgricEdge Trade {trade_id} escrow funding"
		),
		"metadata": _agricedge_metadata(payload),
		"source_payload": redact_secrets(deepcopy(payload)),
	}
	_validate_normalized(normalized)
	return normalized


def _normalize_generic(payload: dict) -> dict:
	normalized = {
		"source_adapter": str(payload.get("source_adapter") or "Generic"),
		"source_app": _required(payload, "source_app"),
		"source_doctype": payload.get("source_doctype"),
		"source_name": payload.get("source_name"),
		"external_trade_reference": payload.get("external_trade_reference")
		or payload.get("source_name"),
		"external_tenant_reference": payload.get("external_tenant_reference"),
		"external_company_reference": payload.get("external_company_reference"),
		"external_branch_reference": payload.get("external_branch_reference"),
		"buyer_reference": _required(payload, "buyer_reference"),
		"buyer_name": _required(payload, "buyer_name"),
		"buyer_email": _required(payload, "buyer_email"),
		"buyer_phone": payload.get("buyer_phone"),
		"beneficiary_reference": _required(payload, "beneficiary_reference"),
		"beneficiary_name": payload.get("beneficiary_name"),
		"amount": flt(_required(payload, "amount")),
		"currency": str(payload.get("currency") or "NGN").upper(),
		"provider": _required(payload, "provider"),
		"provider_account": payload.get("provider_account"),
		"custody_mode": str(payload.get("custody_mode") or "Provider Managed"),
		"release_policy": str(payload.get("release_policy") or "Manual Approval"),
		"acceptance_deadline": payload.get("acceptance_deadline"),
		"dispute_deadline": payload.get("dispute_deadline"),
		"idempotency_key": payload.get("idempotency_key"),
		"payment_purpose": payload.get("payment_purpose") or "Escrow funding",
		"metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
		"source_payload": redact_secrets(deepcopy(payload)),
	}
	_validate_normalized(normalized)
	return normalized


def _agricedge_metadata(payload: dict) -> dict:
	"""Capture business context useful to moderation without owning AgricEdge schema."""
	reserved = {
		"provider",
		"provider_account",
		"amount",
		"currency",
		"buyer_email",
		"buyer_phone",
	}
	return {
		key: value
		for key, value in redact_secrets(deepcopy(payload)).items()
		if key not in reserved
	}


def _required(payload: dict, fieldname: str):
	value = payload.get(fieldname)
	if value is None or (isinstance(value, str) and not value.strip()):
		frappe.throw(_("{0} is required for escrow").format(fieldname))
	return str(value).strip() if isinstance(value, str) else value


def _validate_normalized(payload: dict):
	if flt(payload["amount"]) <= 0:
		frappe.throw(_("Escrow amount must be greater than zero"))
	if len(str(payload["currency"])) != 3:
		frappe.throw(_("Escrow currency must be a 3-letter code"))
	if payload["buyer_reference"] == payload["beneficiary_reference"]:
		frappe.throw(_("Buyer and beneficiary must be different parties"))
