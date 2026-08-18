# -*- coding: utf-8 -*-
import secrets

import frappe
from frappe import _
from frappe.utils import now_datetime

from edgepayv1.edgepay.services.authorization import require_merchant_access


@frappe.whitelist()
def rotate_api_client_secret(api_client):
	client = frappe.get_doc("EdgePay API Client", api_client)
	require_merchant_access(client.merchant)
	roles = set(frappe.get_roles(frappe.session.user))
	if frappe.session.user != "Administrator" and not roles.intersection({"EdgePay Admin", "EdgePay Manager", "System Manager"}):
		frappe.throw(_("Not permitted to rotate this API credential"), frappe.PermissionError)
	new_secret = secrets.token_urlsafe(48)
	client.client_secret = new_secret
	client.last_rotated_on = now_datetime()
	client.save(ignore_permissions=True)
	return {"api_client": client.name, "client_id": client.client_id, "client_secret": new_secret, "shown_once": True}
