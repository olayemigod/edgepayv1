# -*- coding: utf-8 -*-
import frappe
from frappe import _

from edgepayv1.edgepay.services.authorization import require_merchant_access


PLATFORM_BOOTSTRAP_ROLES = {"EdgePay Admin"}


def can_bootstrap_merchant(user=None):
	user = user or frappe.session.user
	if not user or user == "Guest":
		return False
	if user == "Administrator":
		return True
	return bool(PLATFORM_BOOTSTRAP_ROLES.intersection(frappe.get_roles(user)))


def get_default_merchant_context(user=None):
	user = user or frappe.session.user
	membership = frappe.db.get_value(
		"EdgePay Merchant User",
		{"user": user, "active": 1, "is_default": 1},
		["merchant", "name"],
		as_dict=True,
	)
	if not membership:
		membership = frappe.db.get_value(
			"EdgePay Merchant User", {"user": user, "active": 1}, ["merchant", "name"], as_dict=True
		)
	if not membership:
		return {
			"merchant": None,
			"merchant_account": None,
			"merchant_branch": None,
			"can_bootstrap": can_bootstrap_merchant(user),
		}
	require_merchant_access(membership.merchant, user=user)
	account = frappe.db.get_value(
		"EdgePay Merchant Account",
		{"merchant": membership.merchant, "account_type": "Primary Business", "status": "Active"},
		"name",
	)
	if not account:
		account = frappe.db.get_value(
			"EdgePay Merchant Account", {"merchant": membership.merchant, "status": "Active"}, "name"
		)
	branch = (
		frappe.db.get_value(
			"EdgePay Merchant Branch",
			{"merchant": membership.merchant, "merchant_account": account, "status": "Active"},
			"name",
		)
		if account
		else None
	)
	return {
		"merchant": membership.merchant,
		"merchant_account": account,
		"merchant_branch": branch,
		"can_bootstrap": can_bootstrap_merchant(user),
	}


@frappe.whitelist()
def get_my_default_merchant_context() -> dict:
	if frappe.session.user == "Guest":
		frappe.throw(_("Authentication required"), frappe.PermissionError)
	return get_default_merchant_context()
