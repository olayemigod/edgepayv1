from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cint

from edgepayv1.api.operations import _edgepay_context

CANDIDATE_LIMIT = 100
MAX_RESULTS = 50
MAX_ANCHORS = 4


def _ranker():
	try:
		from edgesuite_ui.search_ranking import rank_search_records
	except (ImportError, ModuleNotFoundError):
		return None
	return rank_search_records


def _limit(value: int | str | None) -> int:
	return min(max(cint(value) or 20, 1), MAX_RESULTS)


def _candidate_anchors(query: str) -> tuple[str, ...]:
	term = " ".join(str(query or "").strip().casefold().split())
	if not term:
		return ()
	anchors = [term]
	for token in term.split():
		if len(token) >= 3:
			anchors.append(token[:3])
		if len(token) >= 2:
			anchors.append(token[-2:])
	unique: list[str] = []
	for anchor in anchors:
		if anchor and anchor not in unique:
			unique.append(anchor)
		if len(unique) >= MAX_ANCHORS:
			break
	return tuple(unique)


def _rows(
	doctype: str,
	merchant: str,
	fields: list[str],
	*,
	query: str = "",
	search_fields: tuple[str, ...] = ("name",),
	order_by: str = "modified desc",
) -> list[dict]:
	if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
		return []
	meta = frappe.get_meta(doctype)
	available = [fieldname for fieldname in fields if fieldname == "name" or meta.has_field(fieldname)]
	if "name" not in available:
		available.insert(0, "name")
	available_search = tuple(
		fieldname
		for fieldname in dict.fromkeys(("name", *search_fields))
		if fieldname == "name" or meta.has_field(fieldname)
	)
	search_text = str(query or "").strip()
	if not search_text:
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

	rows: list[dict] = []
	seen: set[str] = set()

	exact = frappe.get_list(
		doctype,
		filters={"merchant": merchant},
		or_filters={fieldname: search_text for fieldname in available_search},
		fields=available,
		order_by=order_by,
		limit_page_length=CANDIDATE_LIMIT,
	)
	for source in exact:
		row = dict(source)
		name = str(row.get("name") or "")
		if name and name not in seen:
			seen.add(name)
			rows.append(row)

	for anchor in _candidate_anchors(search_text):
		remaining = CANDIDATE_LIMIT - len(rows)
		if remaining <= 0:
			break
		matches = frappe.get_list(
			doctype,
			filters={"merchant": merchant},
			or_filters={fieldname: ["like", f"%{anchor}%"] for fieldname in available_search},
			fields=available,
			order_by=order_by,
			limit_page_length=remaining,
		)
		for source in matches:
			row = dict(source)
			name = str(row.get("name") or "")
			if not name or name in seen:
				continue
			seen.add(name)
			rows.append(row)
			if len(rows) >= CANDIDATE_LIMIT:
				break

	return rows


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

	search_text = str(query or "").strip()
	candidates: list[dict] = []
	for row in _rows(
		"EdgePay Payment Request",
		merchant,
		["name", "request_reference", "customer_name", "status", "amount", "currency", "source_app"],
		query=search_text,
		search_fields=("request_reference", "customer_name", "source_app"),
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
		query=search_text,
		search_fields=("payment_request", "provider_payment_reference", "payment_method"),
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
		query=search_text,
		search_fields=("payment_request", "transaction_reference", "provider_reference"),
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

	for doctype, kind, fields, search_fields in (
		(
			"EdgePay Refund Request",
			"Refund",
			["name", "payment_request", "status", "amount", "currency"],
			("payment_request",),
		),
		(
			"EdgePay Settlement Batch",
			"Settlement",
			["name", "provider_account", "status", "gross_amount", "net_amount", "currency"],
			("provider_account",),
		),
		(
			"EdgePay Dispute",
			"Dispute",
			["name", "payment_request", "payment_transaction", "status", "amount", "currency"],
			("payment_request", "payment_transaction"),
		),
		(
			"EdgePay Chargeback",
			"Chargeback",
			["name", "payment_request", "payment_transaction", "status", "amount", "currency"],
			("payment_request", "payment_transaction"),
		),
	):
		for row in _rows(
			doctype,
			merchant,
			fields,
			query=search_text,
			search_fields=search_fields,
		):
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

	return _rank(candidates, search_text, _limit(page_length))
