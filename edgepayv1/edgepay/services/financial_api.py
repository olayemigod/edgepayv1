# -*- coding: utf-8 -*-
import json

import frappe
from frappe import _

from edgepayv1.edgepay.services.authorization import require_authenticated_user, require_platform_operations_access


def _require_merchant_doc(doctype, name, ptype="read"):
	doc = frappe.get_doc(doctype, name)
	if not frappe.has_permission(doctype, ptype, doc=doc):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return doc


@frappe.whitelist()
def submit_refund_request(refund_request_name):
	require_authenticated_user()
	_require_merchant_doc("EdgePay Refund Request", refund_request_name, "write")
	from edgepayv1.edgepay.services.refund_processing import submit_refund
	return submit_refund(refund_request_name).as_dict()


@frappe.whitelist()
def complete_refund_request(refund_request_name, provider_reference=None):
	require_platform_operations_access()
	from edgepayv1.edgepay.services.refund_processing import complete_refund
	return complete_refund(refund_request_name, provider_reference=provider_reference).as_dict()


@frappe.whitelist()
def create_dispute(payment_transaction, amount, reason_code=None, provider_reference=None):
	require_authenticated_user()
	_require_merchant_doc("EdgePay Payment Transaction", payment_transaction, "read")
	from edgepayv1.edgepay.services.financial_operations import open_dispute
	return open_dispute(payment_transaction, amount, reason_code, provider_reference).as_dict()


@frappe.whitelist()
def create_chargeback(payment_transaction, amount, reason_code=None, provider_reference=None):
	require_platform_operations_access()
	from edgepayv1.edgepay.services.financial_operations import open_chargeback
	return open_chargeback(payment_transaction, amount, reason_code, provider_reference).as_dict()


@frappe.whitelist()
def create_fee_record(payment_transaction, fee_type, amount, tax_amount=0, source_reference=None):
	require_platform_operations_access()
	from edgepayv1.edgepay.services.financial_operations import record_fee
	return record_fee(payment_transaction, fee_type, amount, tax_amount, source_reference).as_dict()


@frappe.whitelist()
def create_settlement(merchant, provider_account, transaction_names, settlement_reference=None, expected_on=None):
	require_platform_operations_access()
	if isinstance(transaction_names, str):
		transaction_names = json.loads(transaction_names)
	from edgepayv1.edgepay.services.financial_operations import create_settlement_batch
	return create_settlement_batch(merchant, provider_account, transaction_names, settlement_reference, expected_on).as_dict()
