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


def has_merchant_permission(doc, user=None, permission_type=None, **kwargs):
	merchants = get_user_merchants(user or frappe.session.user)
	if merchants is None:
		return True
	merchant = doc.name if doc.doctype == "EdgePay Merchant" else getattr(doc, "merchant", None)
	return bool(merchant and merchant in merchants)


def _query(scope_doctype, user=None, **kwargs):
	return merchant_permission_query(scope_doctype, user)


def payment_request_query(user=None, **kwargs):
	return _query("EdgePay Payment Request", user, **kwargs)


def payment_attempt_query(user=None, **kwargs):
	return _query("EdgePay Payment Attempt", user, **kwargs)


def payment_transaction_query(user=None, **kwargs):
	return _query("EdgePay Payment Transaction", user, **kwargs)


def payment_event_query(user=None, **kwargs):
	return _query("EdgePay Payment Event", user, **kwargs)


def external_reference_query(user=None, **kwargs):
	return _query("EdgePay External Reference", user, **kwargs)


def refund_request_query(user=None, **kwargs):
	return _query("EdgePay Refund Request", user, **kwargs)


def refund_processing_attempt_query(user=None, **kwargs):
	return _query("EdgePay Refund Processing Attempt", user, **kwargs)


def dispute_query(user=None, **kwargs):
	return _query("EdgePay Dispute", user, **kwargs)


def chargeback_query(user=None, **kwargs):
	return _query("EdgePay Chargeback", user, **kwargs)


def fee_record_query(user=None, **kwargs):
	return _query("EdgePay Fee Record", user, **kwargs)


def settlement_batch_query(user=None, **kwargs):
	return _query("EdgePay Settlement Batch", user, **kwargs)


def settlement_item_query(user=None, **kwargs):
	return _query("EdgePay Settlement Item", user, **kwargs)


def api_client_query(user=None, **kwargs):
	return _query("EdgePay API Client", user, **kwargs)


def api_nonce_query(user=None, **kwargs):
	return _query("EdgePay API Request Nonce", user, **kwargs)


def api_usage_query(user=None, **kwargs):
	return _query("EdgePay API Usage Log", user, **kwargs)


def delivery_endpoint_query(user=None, **kwargs):
	return _query("EdgePay Delivery Endpoint", user, **kwargs)


def delivery_query(user=None, **kwargs):
	return _query("EdgePay Delivery", user, **kwargs)


def delivery_attempt_query(user=None, **kwargs):
	return _query("EdgePay Delivery Attempt", user, **kwargs)


def merchant_query(user=None, **kwargs):
	return _query("EdgePay Merchant", user, **kwargs)


def merchant_account_query(user=None, **kwargs):
	return _query("EdgePay Merchant Account", user, **kwargs)


def merchant_branch_query(user=None, **kwargs):
	return _query("EdgePay Merchant Branch", user, **kwargs)


def provider_account_query(user=None, **kwargs):
	return _query("EdgePay Provider Account", user, **kwargs)


def merchant_verification_query(user=None, **kwargs):
	return _query("EdgePay Merchant Verification", user, **kwargs)


def verification_consent_query(user=None, **kwargs):
	return _query("EdgePay Verification Consent", user, **kwargs)


def identity_session_query(user=None, **kwargs):
	return _query("EdgePay Identity Verification Session", user, **kwargs)


def identity_check_query(user=None, **kwargs):
	return _query("EdgePay Identity Verification Check", user, **kwargs)


def webhook_event_query(user=None, **kwargs):
	return _query("EdgePay Webhook Event", user, **kwargs)


def handoff_event_query(user=None, **kwargs):
	return _query("EdgePay Status Handoff Event", user, **kwargs)
