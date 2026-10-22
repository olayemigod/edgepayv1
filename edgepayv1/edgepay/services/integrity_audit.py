# -*- coding: utf-8 -*-
import frappe
from frappe import _

from edgepayv1.edgepay.services.authorization import require_platform_operations_access

CHECKS = (
	("payment_requests_missing_merchant", "EdgePay Payment Request", {"merchant": ["is", "not set"]}),
	("transactions_missing_merchant", "EdgePay Payment Transaction", {"merchant": ["is", "not set"]}),
	("webhooks_missing_merchant", "EdgePay Webhook Event", {"merchant": ["is", "not set"]}),
	("handoffs_missing_merchant", "EdgePay Status Handoff Event", {"merchant": ["is", "not set"]}),
	("provider_accounts_missing_merchant", "EdgePay Provider Account", {"merchant": ["is", "not set"]}),
)


def run_merchant_integrity_audit():
	results = []
	for key, doctype, filters in CHECKS:
		count = frappe.db.count(doctype, filters=filters)
		results.append({"check": key, "doctype": doctype, "count": count, "status": "Pass" if not count else "Fail"})

	cross_scope = frappe.db.sql("""
		select count(*)
		from `tabEdgePay Payment Request` pr
		join `tabEdgePay Provider Account` pa on pa.name = pr.provider_account
		where ifnull(pr.merchant, '') != ifnull(pa.merchant, '')
	""")[0][0]
	results.append({"check": "payment_request_provider_account_scope", "doctype": "EdgePay Payment Request", "count": cross_scope, "status": "Pass" if not cross_scope else "Fail"})

	return {"ok": all(row["status"] == "Pass" for row in results), "results": results}


@frappe.whitelist()
def get_merchant_integrity_audit():
	require_platform_operations_access()
	return run_merchant_integrity_audit()
