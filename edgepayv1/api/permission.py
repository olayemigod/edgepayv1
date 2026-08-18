from __future__ import annotations

import frappe

EDGEPAY_ROLES = {
	"EdgePay Admin",
	"EdgePay Manager",
	"EdgePay User",
	"EdgePay Auditor",
}


def has_app_permission(user: str | None = None) -> bool:
	resolved_user = user or frappe.session.user
	if not resolved_user or resolved_user == "Guest":
		return False
	if resolved_user == "Administrator":
		return True
	if not EDGEPAY_ROLES.intersection(frappe.get_roles(resolved_user)):
		return False
	return any(
		frappe.has_permission(doctype, "read", user=resolved_user)
		for doctype in ("EdgePay Merchant", "EdgePay Payment Request")
		if frappe.db.exists("DocType", doctype)
	)
