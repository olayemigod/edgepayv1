# -*- coding: utf-8 -*-
"""Central authorization helpers for EdgePay service and API operations."""

import frappe
from frappe import _

PLATFORM_CONFIGURATION_ROLES = {"System Manager", "EdgePay Admin"}
PLATFORM_OPERATIONS_ROLES = {"System Manager", "EdgePay Admin", "EdgePay Manager"}


def require_authenticated_user():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Authentication required to access this API"), frappe.PermissionError)
	return user


def require_any_role(roles, message=None):
	user = require_authenticated_user()
	if not set(frappe.get_roles(user)).intersection(set(roles)):
		frappe.throw(message or _("You are not permitted to perform this EdgePay operation"), frappe.PermissionError)
	return user


def is_platform_user(user=None):
	user = user or frappe.session.user
	return bool(user == "Administrator" or set(frappe.get_roles(user)).intersection(PLATFORM_OPERATIONS_ROLES))


def require_platform_configuration_access():
	return require_any_role(PLATFORM_CONFIGURATION_ROLES, _("Only an EdgePay Administrator may manage or inspect provider configuration"))


def require_platform_operations_access():
	return require_any_role(PLATFORM_OPERATIONS_ROLES, _("You are not permitted to manage EdgePay platform operations"))


def get_active_merchant_membership(merchant, user=None):
	user = user or require_authenticated_user()
	if is_platform_user(user):
		return None
	name = frappe.db.get_value(
		"EdgePay Merchant User",
		{"merchant": merchant, "user": user, "active": 1},
		"name",
	)
	return frappe.get_doc("EdgePay Merchant User", name) if name else None


def require_merchant_access(merchant, allowed_roles=None, user=None):
	user = user or require_authenticated_user()
	if is_platform_user(user):
		return None
	membership = get_active_merchant_membership(merchant, user=user)
	if not membership:
		frappe.throw(_("You do not have access to this EdgePay merchant"), frappe.PermissionError)
	if allowed_roles and membership.merchant_role not in set(allowed_roles):
		frappe.throw(_("Your merchant role does not permit this operation"), frappe.PermissionError)
	return membership


def require_doctype_permission(doctype, ptype="read"):
	require_authenticated_user()
	if not frappe.has_permission(doctype, ptype=ptype):
		frappe.throw(_("Not permitted to {0} {1}").format(ptype, doctype), frappe.PermissionError)


def require_document_permission(doctype, name, ptype="read"):
	require_authenticated_user()
	if not name or not frappe.db.exists(doctype, name):
		frappe.throw(_("{0} {1} was not found").format(doctype, name))
	doc = frappe.get_doc(doctype, name)
	if not doc.has_permission(ptype=ptype):
		frappe.throw(_("Not permitted to {0} {1} {2}").format(ptype, doctype, name), frappe.PermissionError)
	if hasattr(doc, "merchant") and doc.merchant:
		require_merchant_access(doc.merchant)
	return doc


def require_provider_access(provider_name, ptype="read"):
	return require_document_permission("EdgePay Provider", provider_name, ptype=ptype)


def require_provider_account_access(provider_account_name, ptype="read"):
	return require_document_permission("EdgePay Provider Account", provider_account_name, ptype=ptype)


def require_payment_request_access(payment_request_name, ptype="read"):
	return require_document_permission("EdgePay Payment Request", payment_request_name, ptype=ptype)


def require_payment_transaction_access(transaction_name, ptype="read"):
	return require_document_permission("EdgePay Payment Transaction", transaction_name, ptype=ptype)
