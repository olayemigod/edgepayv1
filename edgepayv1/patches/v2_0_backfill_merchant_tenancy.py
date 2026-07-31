# -*- coding: utf-8 -*-
"""Idempotently backfill the Phase 2A merchant boundary for legacy records."""

import frappe

LEGACY_MERCHANT = "ProcessEdge Legacy Merchant"


def execute():
	merchant = _ensure_legacy_merchant()
	provider_accounts = _ensure_provider_accounts(merchant)
	_backfill_payment_requests(merchant, provider_accounts)
	_backfill_transactions()


def _ensure_legacy_merchant():
	if not frappe.db.exists("EdgePay Merchant", LEGACY_MERCHANT):
		doc = frappe.get_doc({
			"doctype": "EdgePay Merchant",
			"merchant_name": LEGACY_MERCHANT,
			"legal_name": "ProcessEdge Legacy EdgePay Data",
			"status": "Active",
			"country": "Nigeria" if frappe.db.exists("Country", "Nigeria") else None,
			"default_currency": "NGN" if frappe.db.exists("Currency", "NGN") else None,
			"external_platform": "Legacy",
		})
		doc.insert(ignore_permissions=True)
	return LEGACY_MERCHANT


def _ensure_provider_accounts(merchant):
	accounts = {}
	for provider in frappe.get_all("EdgePay Provider", pluck="name"):
		name = frappe.db.get_value(
			"EdgePay Provider Account",
			{"merchant": merchant, "provider": provider, "account_label": "Legacy"},
			"name",
		)
		if not name:
			provider_doc = frappe.get_doc("EdgePay Provider", provider)
			account = frappe.get_doc({
				"doctype": "EdgePay Provider Account",
				"merchant": merchant,
				"provider": provider,
				"account_label": "Legacy",
				"environment": "Sandbox" if provider_doc.sandbox_mode else "Live",
				"enabled": provider_doc.enabled,
				"status": "Active" if provider_doc.enabled else "Disabled",
				"api_key": provider_doc.get_password("api_key") if provider_doc.api_key else None,
				"secret_key": provider_doc.get_password("secret_key") if provider_doc.secret_key else None,
				"contract_code": provider_doc.contract_code,
			})
			account.insert(ignore_permissions=True)
			name = account.name
		accounts[provider] = name
	return accounts


def _backfill_payment_requests(merchant, provider_accounts):
	for row in frappe.get_all(
		"EdgePay Payment Request",
		filters=[["merchant", "is", "not set"]],
		fields=["name", "provider"],
	):
		frappe.db.set_value(
			"EdgePay Payment Request",
			row.name,
			{"merchant": merchant, "provider_account": provider_accounts.get(row.provider)},
			update_modified=False,
		)


def _backfill_transactions():
	for row in frappe.get_all(
		"EdgePay Payment Transaction",
		filters=[["merchant", "is", "not set"]],
		fields=["name", "payment_request"],
	):
		scope = frappe.db.get_value(
			"EdgePay Payment Request",
			row.payment_request,
			["merchant", "provider_account", "provider"],
			as_dict=True,
		)
		if scope:
			frappe.db.set_value(
				"EdgePay Payment Transaction",
				row.name,
				scope,
				update_modified=False,
			)
