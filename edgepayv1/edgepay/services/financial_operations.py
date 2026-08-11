# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from edgepayv1.edgepay.services.payment_state import record_event


def open_dispute(payment_transaction, amount, reason_code=None, provider_reference=None):
	txn = frappe.get_doc("EdgePay Payment Transaction", payment_transaction)
	if txn.status != "Success":
		frappe.throw(_("Only successful transactions can be disputed"))
	if flt(amount) <= 0 or flt(amount) > flt(txn.amount):
		frappe.throw(_("Dispute amount must be within the successful transaction amount"))
	doc = frappe.new_doc("EdgePay Dispute")
	doc.merchant = txn.merchant
	doc.payment_request = txn.payment_request
	doc.payment_transaction = txn.name
	doc.provider_account = txn.provider_account
	doc.amount = flt(amount)
	doc.currency = txn.currency
	doc.reason_code = reason_code
	doc.provider_dispute_reference = provider_reference
	doc.opened_on = now_datetime()
	doc.insert(ignore_permissions=True)
	request = frappe.get_doc("EdgePay Payment Request", txn.payment_request)
	request.status = "Disputed"
	request.save(ignore_permissions=True)
	record_event(request, transaction=txn, event_type="Dispute Opened", event_source="dispute", details={"dispute": doc.name, "amount": doc.amount})
	return doc


def open_chargeback(payment_transaction, amount, reason_code=None, provider_reference=None):
	txn = frappe.get_doc("EdgePay Payment Transaction", payment_transaction)
	if txn.status != "Success":
		frappe.throw(_("Only successful transactions can receive a chargeback"))
	if flt(amount) <= 0 or flt(amount) > flt(txn.amount):
		frappe.throw(_("Chargeback amount must be within the successful transaction amount"))
	doc = frappe.new_doc("EdgePay Chargeback")
	doc.merchant = txn.merchant
	doc.payment_request = txn.payment_request
	doc.payment_transaction = txn.name
	doc.provider_account = txn.provider_account
	doc.amount = flt(amount)
	doc.currency = txn.currency
	doc.reason_code = reason_code
	doc.provider_chargeback_reference = provider_reference
	doc.opened_on = now_datetime()
	doc.insert(ignore_permissions=True)
	request = frappe.get_doc("EdgePay Payment Request", txn.payment_request)
	request.status = "Chargeback"
	request.save(ignore_permissions=True)
	record_event(request, transaction=txn, event_type="Chargeback Opened", event_source="chargeback", details={"chargeback": doc.name, "amount": doc.amount})
	return doc


def record_fee(payment_transaction, fee_type, amount, tax_amount=0, source_reference=None):
	txn = frappe.get_doc("EdgePay Payment Transaction", payment_transaction)
	if flt(amount) < 0 or flt(tax_amount) < 0:
		frappe.throw(_("Fee and tax amounts cannot be negative"))
	doc = frappe.new_doc("EdgePay Fee Record")
	doc.merchant = txn.merchant
	doc.payment_request = txn.payment_request
	doc.payment_transaction = txn.name
	doc.provider_account = txn.provider_account
	doc.fee_type = fee_type
	doc.amount = flt(amount)
	doc.tax_amount = flt(tax_amount)
	doc.net_effect = flt(amount) + flt(tax_amount)
	doc.currency = txn.currency
	doc.source_reference = source_reference
	doc.calculated_on = now_datetime()
	doc.insert(ignore_permissions=True)
	return doc


def create_settlement_batch(merchant, provider_account, transaction_names, settlement_reference=None, expected_on=None):
	if not transaction_names:
		frappe.throw(_("At least one transaction is required"))
	transactions = [frappe.get_doc("EdgePay Payment Transaction", name) for name in transaction_names]
	for txn in transactions:
		if txn.merchant != merchant or txn.provider_account != provider_account or txn.status != "Success":
			frappe.throw(_("All settlement transactions must be successful and belong to the selected Merchant and Provider Account"))
	currencies = {txn.currency for txn in transactions}
	if len(currencies) != 1:
		frappe.throw(_("A settlement batch cannot mix currencies"))
	batch = frappe.new_doc("EdgePay Settlement Batch")
	batch.merchant = merchant
	batch.provider_account = provider_account
	batch.settlement_reference = settlement_reference
	batch.currency = currencies.pop()
	batch.expected_on = expected_on
	batch.insert(ignore_permissions=True)
	gross = provider_fees = edgepay_fees = taxes = 0
	for txn in transactions:
		fee_rows = frappe.get_all("EdgePay Fee Record", filters={"payment_transaction": txn.name}, fields=["fee_type", "amount", "tax_amount"])
		provider_fee = sum(flt(row.amount) for row in fee_rows if row.fee_type == "Provider Fee")
		edgepay_fee = sum(flt(row.amount) for row in fee_rows if row.fee_type == "EdgePay Fee")
		tax = sum(flt(row.tax_amount) for row in fee_rows)
		item = frappe.new_doc("EdgePay Settlement Item")
		item.merchant = merchant
		item.settlement_batch = batch.name
		item.payment_request = txn.payment_request
		item.payment_transaction = txn.name
		item.gross_amount = txn.amount
		item.provider_fee = provider_fee
		item.edgepay_fee = edgepay_fee
		item.tax_amount = tax
		item.net_amount = flt(txn.amount) - provider_fee - edgepay_fee - tax
		item.insert(ignore_permissions=True)
		gross += flt(txn.amount)
		provider_fees += provider_fee
		edgepay_fees += edgepay_fee
		taxes += tax
	batch.gross_amount = gross
	batch.provider_fees = provider_fees
	batch.edgepay_fees = edgepay_fees
	batch.tax_amount = taxes
	batch.net_amount = gross - provider_fees - edgepay_fees - taxes
	batch.save(ignore_permissions=True)
	return batch
