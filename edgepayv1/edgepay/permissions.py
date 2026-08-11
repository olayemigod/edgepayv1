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
	"EdgePay API Client": "merchant",
	"EdgePay API Request Nonce": "merchant",
	"EdgePay API Usage Log": "merchant",
	"EdgePay Delivery Endpoint": "merchant",
	"EdgePay Delivery": "merchant",
	"EdgePay Delivery Attempt": "merchant",
	"EdgePay Payment Link": "merchant",
	"EdgePay Payment Request": "merchant",
	"EdgePay Payment Attempt": "merchant",
	"EdgePay Payment Transaction": "merchant",
	"EdgePay Payment Event": "merchant",
	"EdgePay External Reference": "merchant",
	"EdgePay Refund Request": "merchant",
	"EdgePay Refund Processing Attempt": "merchant",
	"EdgePay Dispute": "merchant",
	"EdgePay Chargeback": "merchant",
	"EdgePay Fee Record": "merchant",
	"EdgePay Settlement Batch": "merchant",
	"EdgePay Settlement Item": "merchant",
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
	merchants = get_user_merchants(user or frappe.session.user)
	if merchants is None:
		return True
	merchant = doc.name if doc.doctype == "EdgePay Merchant" else getattr(doc, "merchant", None)
	return bool(merchant and merchant in merchants)


def payment_link_query(user=None): return merchant_permission_query("EdgePay Payment Link", user)
def payment_request_query(user=None): return merchant_permission_query("EdgePay Payment Request", user)
def payment_attempt_query(user=None): return merchant_permission_query("EdgePay Payment Attempt", user)
def payment_transaction_query(user=None): return merchant_permission_query("EdgePay Payment Transaction", user)
def payment_event_query(user=None): return merchant_permission_query("EdgePay Payment Event", user)
def external_reference_query(user=None): return merchant_permission_query("EdgePay External Reference", user)
def refund_request_query(user=None): return merchant_permission_query("EdgePay Refund Request", user)
def refund_processing_attempt_query(user=None): return merchant_permission_query("EdgePay Refund Processing Attempt", user)
def dispute_query(user=None): return merchant_permission_query("EdgePay Dispute", user)
def chargeback_query(user=None): return merchant_permission_query("EdgePay Chargeback", user)
def fee_record_query(user=None): return merchant_permission_query("EdgePay Fee Record", user)
def settlement_batch_query(user=None): return merchant_permission_query("EdgePay Settlement Batch", user)
def settlement_item_query(user=None): return merchant_permission_query("EdgePay Settlement Item", user)
def api_client_query(user=None): return merchant_permission_query("EdgePay API Client", user)
def api_nonce_query(user=None): return merchant_permission_query("EdgePay API Request Nonce", user)
def api_usage_query(user=None): return merchant_permission_query("EdgePay API Usage Log", user)
def delivery_endpoint_query(user=None): return merchant_permission_query("EdgePay Delivery Endpoint", user)
def delivery_query(user=None): return merchant_permission_query("EdgePay Delivery", user)
def delivery_attempt_query(user=None): return merchant_permission_query("EdgePay Delivery Attempt", user)
def merchant_query(user=None): return merchant_permission_query("EdgePay Merchant", user)
def merchant_account_query(user=None): return merchant_permission_query("EdgePay Merchant Account", user)
def merchant_branch_query(user=None): return merchant_permission_query("EdgePay Merchant Branch", user)
def provider_account_query(user=None): return merchant_permission_query("EdgePay Provider Account", user)
def merchant_verification_query(user=None): return merchant_permission_query("EdgePay Merchant Verification", user)
def verification_consent_query(user=None): return merchant_permission_query("EdgePay Verification Consent", user)
def identity_session_query(user=None): return merchant_permission_query("EdgePay Identity Verification Session", user)
def identity_check_query(user=None): return merchant_permission_query("EdgePay Identity Verification Check", user)
def webhook_event_query(user=None): return merchant_permission_query("EdgePay Webhook Event", user)
def handoff_event_query(user=None): return merchant_permission_query("EdgePay Status Handoff Event", user)
