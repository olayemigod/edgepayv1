from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cint

from edgepayv1.api.operations import _edgepay_context

CANDIDATE_LIMIT = 100
MAX_RESULTS = 50


def _ranker():
	try:
		from edgesuite_ui.search_ranking import rank_search_records
	except (ImportError, ModuleNotFoundError):
		return None
	return rank_search_records


def _limit(value: int | str | None) -> int:
	return min(max(cint(value) or 20, 1), MAX_RESULTS)


def _rows(doctype: str, merchant: str, fields: list[str], order_by: str = "modified desc") -> list[dict]:
	if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
		return []
	meta = frappe.get_meta(doctype)
	available = [fieldname for fieldname in fields if fieldname == "name" or meta.has_field(fieldname)]
	if "name" not in available:
		available.insert(0, "name")
	return [
		dict(row)
		for row in frappe.get_list(
			doctype,
			filters={"merchant": merchant},
			fields=available,
			order_by=order_by,
			limit_page_length=CANDIDATE_LIMIT,
		)
	]


def _fallback_rank(rows: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
	needle = str(query or "").strip().lower()
	if not needle:
		return rows[:limit]
	exact = []
	contains = []
	for row in rows:
		value = str(row.get("value") or "").lower()
		label = str(row.get("label") or "").lower()
		description = str(row.get("description") or "").lower()
		if needle == value or needle == label:
			exact.append(row)
		elif needle in value or needle in label or needle in description:
			contains.append(row)
	return (exact + contains)[:limit]


def _rank(rows: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
	ranker = _ranker()
	if ranker is None:
		return _fallback_rank(rows, query, limit)
	return list(
		ranker(
			rows,
			str(query or "").strip(),
			exact_fields=("value", "reference", "provider_reference", "transaction_reference"),
			search_fields=("label", "description"),
			limit=limit,
		)
	)


def _candidate(
	row: dict,
	*,
	kind: str,
	label: str,
	reference: str | None = None,
	provider_reference: str | None = None,
	transaction_reference: str | None = None,
	description_parts: tuple[Any, ...] = (),
) -> dict:
	return {
		"value": row.get("name"),
		"kind": kind,
		"label": label or row.get("name"),
		"reference": reference or row.get("name"),
		"provider_reference": provider_reference,
		"transaction_reference": transaction_reference,
		"description": " · ".join(str(value) for value in description_parts if value not in (None, "")),
	}


@frappe.whitelist()
def search_edgepay_operations(query: str = "", page_length: int | str = 20) -> list[dict]:
	"""Search merchant-scoped EdgePay operational records for discovery only.

	The result is never used to authorize, allocate, settle, refund, dispute, or
	otherwise mutate a financial record. Exact identifiers are deliberately ranked
	ahead of fuzzy text similarity.
	"""
	context = _edgepay_context()
	merchant = context.get("merchant")
	if not merchant:
		return []

	candidates: list[dict] = []
	for row in _rows(
		"EdgePay Payment Request",
		merchant,
		["name", "request_reference", "customer_name", "status", "amount", "currency", "source_app"],
	):
		candidates.append(
			_candidate(
				row,
				kind="Payment Request",
				label=row.get("customer_name") or row.get("request_reference") or row.get("name"),
				reference=row.get("request_reference") or row.get("name"),
				description_parts=(
					row.get("status"),
					row.get("amount"),
					row.get("currency"),
					row.get("source_app"),
				),
			)
		)

	for row in _rows(
		"EdgePay Payment Attempt",
		merchant,
		[
			"name",
			"payment_request",
			"provider_payment_reference",
			"status",
			"payment_method",
			"attempt_number",
		],
	):
		candidates.append(
			_candidate(
				row,
				kind="Payment Attempt",
				label=row.get("provider_payment_reference") or row.get("payment_request") or row.get("name"),
				reference=row.get("payment_request") or row.get("name"),
				provider_reference=row.get("provider_payment_reference"),
				description_parts=(row.get("status"), row.get("payment_method"), row.get("attempt_number")),
			)
		)

	for row in _rows(
		"EdgePay Payment Transaction",
		merchant,
		[
			"name",
			"payment_request",
			"transaction_reference",
			"provider_reference",
			"status",
			"amount",
			"currency",
		],
	):
		candidates.append(
			_candidate(
				row,
				kind="Payment Transaction",
				label=row.get("transaction_reference") or row.get("provider_reference") or row.get("name"),
				reference=row.get("payment_request") or row.get("name"),
				provider_reference=row.get("provider_reference"),
				transaction_reference=row.get("transaction_reference"),
				description_parts=(row.get("status"), row.get("amount"), row.get("currency")),
			)
		)

	for doctype, kind, fields in (
		("EdgePay Refund Request", "Refund", ["name", "payment_request", "status", "amount", "currency"]),
		(
			"EdgePay Settlement Batch",
			"Settlement",
			["name", "provider_account", "status", "gross_amount", "net_amount", "currency"],
		),
		(
			"EdgePay Dispute",
			"Dispute",
			["name", "payment_request", "payment_transaction", "status", "amount", "currency"],
		),
		(
			"EdgePay Chargeback",
			"Chargeback",
			["name", "payment_request", "payment_transaction", "status", "amount", "currency"],
		),
	):
		for row in _rows(doctype, merchant, fields):
			candidates.append(
				_candidate(
					row,
					kind=kind,
					label=row.get("payment_request") or row.get("provider_account") or row.get("name"),
					reference=row.get("payment_request") or row.get("payment_transaction") or row.get("name"),
					transaction_reference=row.get("payment_transaction"),
					description_parts=(
						row.get("status"),
						row.get("amount"),
						row.get("gross_amount"),
						row.get("net_amount"),
						row.get("currency"),
					),
				)
			)

	return _rank(candidates, query, _limit(page_length))
