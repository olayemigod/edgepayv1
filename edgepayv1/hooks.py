app_name = "edgepayv1"
app_title = "EdgePay"
app_publisher = "ProcessEdge Solutions Limited"
app_description = "Universal payment orchestration layer for Frappe, ERPNext, POSnext, and EdgeSuite apps"
app_email = "info@processedge.com.ng"
app_license = "mit"

fixtures = [{"dt": "Role", "filters": [["role_name", "in", ["EdgePay Admin", "EdgePay Manager", "EdgePay User", "EdgePay Auditor"]]]}]

doctype_js = {"EdgePay Payment Request": "public/js/edgepay_payment_request.js"}

permission_query_conditions = {
	"EdgePay Merchant": "edgepayv1.permissions.merchant_query",
	"EdgePay Merchant Account": "edgepayv1.permissions.merchant_account_query",
	"EdgePay Merchant Branch": "edgepayv1.permissions.merchant_branch_query",
	"EdgePay Provider Account": "edgepayv1.permissions.provider_account_query",
	"EdgePay Merchant Verification": "edgepayv1.permissions.merchant_verification_query",
	"EdgePay Verification Consent": "edgepayv1.permissions.verification_consent_query",
	"EdgePay Identity Verification Session": "edgepayv1.permissions.identity_session_query",
	"EdgePay Identity Verification Check": "edgepayv1.permissions.identity_check_query",
	"EdgePay Payment Request": "edgepayv1.permissions.payment_request_query",
	"EdgePay Payment Attempt": "edgepayv1.permissions.payment_attempt_query",
	"EdgePay Payment Transaction": "edgepayv1.permissions.payment_transaction_query",
	"EdgePay Payment Event": "edgepayv1.permissions.payment_event_query",
	"EdgePay External Reference": "edgepayv1.permissions.external_reference_query",
	"EdgePay Refund Request": "edgepayv1.permissions.refund_request_query",
	"EdgePay Refund Processing Attempt": "edgepayv1.permissions.refund_processing_attempt_query",
	"EdgePay Dispute": "edgepayv1.permissions.dispute_query",
	"EdgePay Chargeback": "edgepayv1.permissions.chargeback_query",
	"EdgePay Fee Record": "edgepayv1.permissions.fee_record_query",
	"EdgePay Settlement Batch": "edgepayv1.permissions.settlement_batch_query",
	"EdgePay Settlement Item": "edgepayv1.permissions.settlement_item_query",
	"EdgePay Webhook Event": "edgepayv1.permissions.webhook_event_query",
	"EdgePay Status Handoff Event": "edgepayv1.permissions.handoff_event_query",
}

has_permission = {
	"EdgePay Merchant": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Merchant Account": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Merchant Branch": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Provider Account": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Merchant Verification": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Verification Consent": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Identity Verification Session": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Identity Verification Check": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Payment Request": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Payment Attempt": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Payment Transaction": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Payment Event": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay External Reference": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Refund Request": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Refund Processing Attempt": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Dispute": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Chargeback": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Fee Record": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Settlement Batch": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Settlement Item": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Webhook Event": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Status Handoff Event": "edgepayv1.permissions.has_merchant_permission",
}
