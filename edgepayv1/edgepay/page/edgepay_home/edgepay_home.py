from __future__ import annotations

import frappe
from frappe import _

from edgepayv1.api.permission import has_app_permission


def get_context(context):
	if not has_app_permission():
		frappe.throw(_("You are not permitted to access EdgePay."), frappe.PermissionError)
	return context
