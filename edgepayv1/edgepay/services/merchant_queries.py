# -*- coding: utf-8 -*-
import frappe
from frappe import _

from edgepayv1.edgepay.services.authorization import require_merchant_access


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def merchant_account_query(doctype, txt, searchfield, start, page_len, filters):
	merchant = (filters or {}).get("merchant")
	if not merchant:
		return []
	require_merchant_access(merchant)
	return frappe.db.sql(
		"""
		select name, account_name
		from `tabEdgePay Merchant Account`
		where merchant=%s and status='Active'
		  and (name like %s or account_name like %s)
		order by account_name
		limit %s, %s
		""",
		(merchant, f"%{txt}%", f"%{txt}%", start, page_len),
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def merchant_branch_query(doctype, txt, searchfield, start, page_len, filters):
	merchant = (filters or {}).get("merchant")
	merchant_account = (filters or {}).get("merchant_account")
	if not merchant:
		return []
	require_merchant_access(merchant)
	conditions = ["merchant=%s", "status='Active'", "(name like %s or branch_name like %s)"]
	values = [merchant, f"%{txt}%", f"%{txt}%"]
	if merchant_account:
		conditions.append("merchant_account=%s")
		values.append(merchant_account)
	values.extend([start, page_len])
	return frappe.db.sql(
		f"select name, branch_name from `tabEdgePay Merchant Branch` where {' and '.join(conditions)} order by branch_name limit %s, %s",
		values,
	)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def provider_account_query(doctype, txt, searchfield, start, page_len, filters):
	merchant = (filters or {}).get("merchant")
	provider = (filters or {}).get("provider")
	if not merchant:
		return []
	require_merchant_access(merchant)
	conditions = ["merchant=%s", "enabled=1", "status='Active'", "(name like %s or account_label like %s)"]
	values = [merchant, f"%{txt}%", f"%{txt}%"]
	if provider:
		conditions.append("provider=%s")
		values.append(provider)
	values.extend([start, page_len])
	return frappe.db.sql(
		f"select name, account_label from `tabEdgePay Provider Account` where {' and '.join(conditions)} order by account_label limit %s, %s",
		values,
	)


def validate_branch_context(merchant, merchant_account=None, merchant_branch=None):
	if merchant_account:
		account_merchant = frappe.db.get_value("EdgePay Merchant Account", merchant_account, "merchant")
		if account_merchant != merchant:
			frappe.throw(_("Merchant Account does not belong to the selected Merchant"))
	if merchant_branch:
		branch = frappe.db.get_value(
			"EdgePay Merchant Branch",
			merchant_branch,
			["merchant", "merchant_account"],
			as_dict=True,
		)
		if not branch or branch.merchant != merchant:
			frappe.throw(_("Merchant Branch does not belong to the selected Merchant"))
		if merchant_account and branch.merchant_account != merchant_account:
			frappe.throw(_("Merchant Branch does not belong to the selected Merchant Account"))
