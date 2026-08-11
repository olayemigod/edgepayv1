# -*- coding: utf-8 -*-
import base64
import io
from urllib.parse import quote

import frappe
from frappe import _
from frappe.utils import get_url
import segno

from edgepayv1.edgepay.services.authorization import require_merchant_access


@frappe.whitelist()
def get_payment_link_qr(payment_link):
	link = frappe.get_doc("EdgePay Payment Link", payment_link)
	require_merchant_access(link.merchant)
	if not frappe.has_permission("EdgePay Payment Link", "read", doc=link):
		frappe.throw(_("Not permitted to access this Payment Link"), frappe.PermissionError)
	public_url = get_url(f"/pay?link={quote(link.public_slug)}")
	qr = segno.make_qr(public_url, error="M")
	buffer = io.BytesIO()
	qr.save(buffer, kind="svg", scale=6, border=2, xmldecl=False, svgns=True)
	encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
	return {
		"payment_link": link.name,
		"public_url": public_url,
		"data_uri": f"data:image/svg+xml;base64,{encoded}",
	}
