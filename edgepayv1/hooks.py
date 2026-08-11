app_name = "edgepayv1"
app_title = "EdgePay"
app_publisher = "ProcessEdge Solutions Limited"
app_description = "Universal payment orchestration layer for Frappe, ERPNext, POSnext, and EdgeSuite apps"
app_email = "info@processedge.com.ng"
app_license = "mit"

# EdgePay renders through the independent local EdgeSuite UI runtime. CoreEdge
# may provision platform access, but it is not a frontend runtime dependency.
required_apps = ["edgesuite_ui"]
app_home = "/app/edgepay-home"
app_include_js = ["/assets/edgepayv1/js/edgepay_product_menu.js"]

add_to_apps_screen = [
	{
		"name": "edgepayv1",
		"logo": "/assets/edgepayv1/logo.png",
		"title": "EdgePay",
		"route": "/app/edgepay-home",
		"has_permission": "edgepayv1.api.permission.has_app_permission",
	}
]

fixtures = [
	{
		"dt": "Role",
		"filters": [
			["role_name", "in", ["EdgePay Admin", "EdgePay Manager", "EdgePay User", "EdgePay Auditor"]]
		],
	}
]

doctype_js = {"EdgePay Payment Request": "public/js/edgepay_payment_request.js"}

scheduler_events = {
	"cron": {
		"*/5 * * * *": ["edgepayv1.edgepay.services.delivery_worker.process_pending_deliveries"],
	},
	"daily": ["edgepayv1.edgepay.services.delivery_worker.cleanup_expired_api_nonces"],
}

permission_query_conditions = {
	"EdgePay Merchant": "edgepayv1.permissions.merchant_query",
	"EdgePay Merchant Account": "edgepayv1.permissions.merchant_account_query",
	"EdgePay Merchant Branch": "edgepayv1.permissions.merchant_branch_query",
	"EdgePay Provider Account": "edgepayv1.permissions.provider_account_query",
	"EdgePay Merchant Verification": "edgepayv1.permissions.merchant_verification_query",
	"EdgePay Verification Consent": "edgepayv1.permissions.verification_consent_query",
	"EdgePay Identity Verification Session": "edgepayv1.permissions.identity_session_query",
	"EdgePay Identity Verification Check": "edgepayv1.permissions.identity_check_query",
	"EdgePay API Client": "edgepayv1.permissions.api_client_query",
	"EdgePay API Request Nonce": "edgepayv1.permissions.api_nonce_query",
	"EdgePay API Usage Log": "edgepayv1.permissions.api_usage_query",
	"EdgePay Delivery Endpoint": "edgepayv1.permissions.delivery_endpoint_query",
	"EdgePay Delivery": "edgepayv1.permissions.delivery_query",
	"EdgePay Delivery Attempt": "edgepayv1.permissions.delivery_attempt_query",
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
	doctype: "edgepayv1.permissions.has_merchant_permission"
	for doctype in [
		"EdgePay Merchant",
		"EdgePay Merchant Account",
		"EdgePay Merchant Branch",
		"EdgePay Provider Account",
		"EdgePay Merchant Verification",
		"EdgePay Verification Consent",
		"EdgePay Identity Verification Session",
		"EdgePay Identity Verification Check",
		"EdgePay API Client",
		"EdgePay API Request Nonce",
		"EdgePay API Usage Log",
		"EdgePay Delivery Endpoint",
		"EdgePay Delivery",
		"EdgePay Delivery Attempt",
		"EdgePay Payment Request",
		"EdgePay Payment Attempt",
		"EdgePay Payment Transaction",
		"EdgePay Payment Event",
		"EdgePay External Reference",
		"EdgePay Refund Request",
		"EdgePay Refund Processing Attempt",
		"EdgePay Dispute",
		"EdgePay Chargeback",
		"EdgePay Fee Record",
		"EdgePay Settlement Batch",
		"EdgePay Settlement Item",
		"EdgePay Webhook Event",
		"EdgePay Status Handoff Event",
	]
}
