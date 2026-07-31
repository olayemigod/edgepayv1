# -*- coding: utf-8 -*-
import frappe

PLATFORM_ROLES = {"System Manager", "EdgePay Admin", "EdgePay Manager"}
MERCHANT_SCOPED_DOCTYPES = {
	"EdgePay Merchant": "name",
	"EdgePay Merchant User": "merchant",
	"EdgePay Merchant Account": "merchant",
	"EdgePay Merchant Branch": "merchant",
	"EdgePay Provider Account": "merchant",
	"EdgePay Merchant Verification": "merchant",
	"EdgePay Verification Consent": "merchant",
	"EdgePay Identity Verification Session": "merchant",
	"EdgePay Identity Verification Check": "merchant",
	"EdgePay Payment Request": "merchant",
	"EdgePay Payment Transaction": "merchant",
	"EdgePay Webhook Event": "merchant",
	"EdgePay Status Handoff Event": "merchant",
}


def get_user_merchants(user=None):
	user = user or frappe.session.user
	if not user or user == "Guest":
		return []
	if PLATFORM_ROLES.intersection(frappe.get_roles(user)):
		return None
	return frappe.get_all("EdgePay Merchant User", filters={"user": user, "active": 1}, pluck="merchant")


def merchant_permission_query(doctype, user=None):
	merchants = get_user_merchants(user)
	if merchants is None:
		return ""
	fieldname = MERCHANT_SCOPED_DOCTYPES.get(doctype)
	if not fieldname or not merchants:
		return "1=0"
	merchant_values = ", ".join(frappe.db.escape(value) for value in merchants)
	return f"`tab{doctype}`.`{fieldname}` in ({merchant_values})"


def has_merchant_permission(doc, user=None, permission_type=None):
	user = user or frappe.session.user
	merchants = get_user_merchants(user)
	if merchants is None:
		return True
	merchant = doc.name if doc.doctype == "EdgePay Merchant" else getattr(doc, "merchant", None)
	return bool(merchant and merchant in merchants)


def merchant_record_query(user=None, doctype=None):
	if not doctype:
		return "1=0"
	return merchant_permission_query(doctype, user)


def payment_request_query(user=None): return merchant_permission_query("EdgePay Payment Request", user)
def payment_transaction_query(user=None): return merchant_permission_query("EdgePay Payment Transaction", user)
def merchant_query(user=None): return merchant_permission_query("EdgePay Merchant", user)
def merchant_account_query(user=None): return merchant_permission_query("EdgePay Merchant Account", user)
def merchant_branch_query(user=None): return merchant_permission_query("EdgePay Merchant Branch", user)
def provider_account_query(user=None): return merchant_permission_query("EdgePay Provider Account", user)
def merchant_verification_query(user=None): return merchant_permission_query("EdgePay Merchant Verification", user)
def webhook_event_query(user=None): return merchant_permission_query("EdgePay Webhook Event", user)
def handoff_event_query(user=None): return merchant_permission_query("EdgePay Status Handoff Event", user)
