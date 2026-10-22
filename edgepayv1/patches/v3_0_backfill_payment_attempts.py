# -*- coding: utf-8 -*-
import frappe


def execute():
	for row in frappe.get_all("EdgePay Payment Request", fields=["name", "merchant", "merchant_account", "merchant_branch", "provider_account", "provider", "status", "provider_reference", "checkout_url", "expires_on"]):
		if frappe.db.exists("EdgePay Payment Attempt", {"payment_request": row.name}):
			continue
		attempt = frappe.new_doc("EdgePay Payment Attempt")
		attempt.payment_request = row.name
		attempt.attempt_number = 1
		attempt.merchant = row.merchant
		attempt.merchant_account = row.merchant_account
		attempt.merchant_branch = row.merchant_branch
		attempt.provider_account = row.provider_account
		attempt.provider = row.provider
		attempt.provider_payment_reference = row.provider_reference
		attempt.checkout_url = row.checkout_url
		attempt.expires_on = row.expires_on
		attempt.status = {"Paid": "Successful", "Failed": "Failed", "Expired": "Expired", "Cancelled": "Cancelled", "Initiated": "Initiated"}.get(row.status, "Created")
		attempt.insert(ignore_permissions=True)
		for txn in frappe.get_all("EdgePay Payment Transaction", filters={"payment_request": row.name}, fields=["name", "transaction_reference", "provider_reference"]):
			frappe.db.set_value("EdgePay Payment Transaction", txn.name, "payment_attempt", attempt.name, update_modified=False)
			if txn.transaction_reference:
				attempt.provider_transaction_reference = txn.transaction_reference
			if txn.provider_reference and not attempt.provider_payment_reference:
				attempt.provider_payment_reference = txn.provider_reference
		attempt.save(ignore_permissions=True)
