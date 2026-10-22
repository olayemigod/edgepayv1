# -*- coding: utf-8 -*-
import secrets

import frappe
from frappe import _

from edgepayv1.edgepay.services.authorization import require_platform_configuration_role

FREE_SCOPES = "payments:create,payments:read,payments:verify,transactions:read,webhooks:manage"


def provision_coreedge_merchant(external_tenant_reference, legal_name, email, phone=None, country="Nigeria", currency="NGN"):
	require_platform_configuration_role()
	if not external_tenant_reference:
		frappe.throw(_("External tenant reference is required"))
	existing = frappe.db.get_value(
		"EdgePay Merchant",
		{"external_platform": "CoreEdge", "external_tenant_reference": external_tenant_reference},
		"name",
	)
	merchant = frappe.get_doc("EdgePay Merchant", existing) if existing else frappe.new_doc("EdgePay Merchant")
	merchant.legal_name = legal_name
	merchant.trading_name = merchant.trading_name or legal_name
	merchant.business_email = email
	merchant.business_phone = phone
	merchant.country = country
	merchant.default_currency = currency
	merchant.external_platform = "CoreEdge"
	merchant.external_tenant_reference = external_tenant_reference
	merchant.status = merchant.status or "Onboarding"
	if merchant.is_new():
		merchant.insert(ignore_permissions=True)
	else:
		merchant.save(ignore_permissions=True)

	client_name = frappe.db.get_value(
		"EdgePay API Client",
		{"merchant": merchant.name, "client_name": "CoreEdge Provisioning", "environment": "Sandbox"},
		"name",
	)
	created_secret = None
	if client_name:
		client = frappe.get_doc("EdgePay API Client", client_name)
	else:
		client = frappe.new_doc("EdgePay API Client")
		client.merchant = merchant.name
		client.client_name = "CoreEdge Provisioning"
		client.environment = "Sandbox"
		client.enabled = 1
		client.scopes = FREE_SCOPES
		created_secret = secrets.token_urlsafe(48)
		client.client_secret = created_secret
		client.insert(ignore_permissions=True)
	return {
		"merchant": merchant.name,
		"merchant_public_id": getattr(merchant, "public_merchant_id", None),
		"api_client": client.name,
		"client_id": client.client_id,
		"client_secret": created_secret,
		"show_secret_once": bool(created_secret),
		"tier": "EdgeSuite Free",
	}


@frappe.whitelist()
def provision_edgepay_for_coreedge(external_tenant_reference, legal_name, email, phone=None, country="Nigeria", currency="NGN"):
	return provision_coreedge_merchant(external_tenant_reference, legal_name, email, phone, country, currency)
