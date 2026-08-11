# -*- coding: utf-8 -*-
import frappe
from frappe import _


def resolve_webhook_scope(provider, payment_reference=None, provider_reference=None):
	"""Resolve an exact merchant/provider-account scope for an incoming provider event.

	Phase 2C intentionally refuses ambiguous cross-merchant matches. Webhook V2 will
	add endpoint tokens and provider-account-specific routes on top of this helper.
	"""
	filters = []
	if payment_reference:
		filters.append({"request_reference": payment_reference, "provider": provider})
		filters.append({"name": payment_reference, "provider": provider})
	if provider_reference:
		filters.append({"provider_reference": provider_reference, "provider": provider})

	matches = set()
	for candidate in filters:
		for name in frappe.get_all("EdgePay Payment Request", filters=candidate, pluck="name", limit_page_length=2):
			matches.add(name)
	if not matches:
		return None
	if len(matches) != 1:
		frappe.throw(_("Webhook reference is ambiguous across payment records"))
	request = frappe.get_doc("EdgePay Payment Request", matches.pop())
	if not request.merchant or not request.provider_account:
		frappe.throw(_("Webhook target does not have complete merchant scope"))
	account = frappe.get_doc("EdgePay Provider Account", request.provider_account)
	if account.merchant != request.merchant or account.provider != provider:
		frappe.throw(_("Webhook target merchant/provider scope is inconsistent"))
	return {
		"payment_request": request.name,
		"merchant": request.merchant,
		"merchant_account": getattr(request, "merchant_account", None),
		"merchant_branch": getattr(request, "merchant_branch", None),
		"provider_account": request.provider_account,
		"provider": provider,
	}
