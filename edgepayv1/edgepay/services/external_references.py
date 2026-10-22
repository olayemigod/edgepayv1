# -*- coding: utf-8 -*-
import frappe
from frappe import _


def register_reference(reference_type, reference_value, payment_request, payment_attempt=None, payment_transaction=None):
	if not reference_value:
		return None
	request = frappe.get_doc("EdgePay Payment Request", payment_request)
	existing = frappe.db.get_value(
		"EdgePay External Reference",
		{
			"provider_account": request.provider_account,
			"reference_type": reference_type,
			"reference_value": reference_value,
			"active": 1,
		},
		["name", "payment_request", "payment_attempt", "payment_transaction"],
		as_dict=True,
	)
	if existing:
		if existing.payment_request != request.name:
			frappe.throw(_("External reference is already assigned to another Payment Request"))
		return existing.name
	doc = frappe.new_doc("EdgePay External Reference")
	doc.merchant = request.merchant
	doc.provider_account = request.provider_account
	doc.reference_type = reference_type
	doc.reference_value = reference_value
	doc.payment_request = request.name
	doc.payment_attempt = payment_attempt
	doc.payment_transaction = payment_transaction
	doc.active = 1
	doc.insert(ignore_permissions=True)
	return doc.name


def resolve_reference(reference_value, provider_account=None, reference_types=None):
	if not reference_value:
		return None
	filters = {"reference_value": reference_value, "active": 1}
	if provider_account:
		filters["provider_account"] = provider_account
	if reference_types:
		filters["reference_type"] = ["in", list(reference_types)]
	rows = frappe.get_all(
		"EdgePay External Reference",
		filters=filters,
		fields=["name", "merchant", "provider_account", "reference_type", "payment_request", "payment_attempt", "payment_transaction"],
		limit=2,
	)
	if len(rows) > 1:
		frappe.throw(_("External reference is ambiguous"))
	return rows[0] if rows else None
