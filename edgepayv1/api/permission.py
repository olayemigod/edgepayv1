from __future__ import annotations

import frappe

EDGEPAY_ROLES = {"EdgePay Admin", "EdgePay Manager", "EdgePay User", "EdgePay Auditor"}


def has_app_permission(user: str | None = None) -> bool:
	resolved_user = user or frappe.session.user
	if not resolved_user or resolved_user == "Guest":
		return False
	if resolved_user == "Administrator":
		return True
	roles = set(frappe.get_roles(resolved_user))
	if not EDGEPAY_ROLES.intersection(roles):
		return False
	if roles.intersection({"EdgePay Admin", "EdgePay Manager", "System Manager"}):
		return True
	return bool(frappe.get_all("EdgePay Merchant User", filters={"user": resolved_user, "active": 1}, limit=1))
