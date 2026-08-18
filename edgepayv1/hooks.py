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

_PERMISSION_MODULE = "edgepayv1.edgepay.permissions"

permission_query_conditions = {
	"EdgePay Merchant": f"{_PERMISSION_MODULE}.merchant_query",
	"EdgePay Merchant Account": f"{_PERMISSION_MODULE}.merchant_account_query",
	"EdgePay Merchant Branch": f"{_PERMISSION_MODULE}.merchant_branch_query",
	"EdgePay Provider Account": f"{_PERMISSION_MODULE}.provider_account_query",
	"EdgePay Merchant Verification": f"{_PERMISSION_MODULE}.merchant_verification_query",
	"EdgePay Verification Consent": f"{_PERMISSION_MODULE}.verification_consent_query",
	"EdgePay Identity Verification Session": f"{_PERMISSION_MODULE}.identity_session_query",
	"EdgePay Identity Verification Check": f"{_PERMISSION_MODULE}.identity_check_query",
	"EdgePay API Client": f"{_PERMISSION_MODULE}.api_client_query",
	"EdgePay API Request Nonce": f"{_PERMISSION_MODULE}.api_nonce_query",
	"EdgePay API Usage Log": f"{_PERMISSION_MODULE}.api_usage_query",
	"EdgePay Delivery Endpoint": f"{_PERMISSION_MODULE}.delivery_endpoint_query",
	"EdgePay Delivery": f"{_PERMISSION_MODULE}.delivery_query",
	"EdgePay Delivery Attempt": f"{_PERMISSION_MODULE}.delivery_attempt_query",
	"EdgePay Payment Request": f"{_PERMISSION_MODULE}.payment_request_query",
	"EdgePay Payment Attempt": f"{_PERMISSION_MODULE}.payment_attempt_query",
	"EdgePay Payment Transaction": f"{_PERMISSION_MODULE}.payment_transaction_query",
	"EdgePay Payment Event": f"{_PERMISSION_MODULE}.payment_event_query",
	"EdgePay External Reference": f"{_PERMISSION_MODULE}.external_reference_query",
	"EdgePay Refund Request": f"{_PERMISSION_MODULE}.refund_request_query",
	"EdgePay Refund Processing Attempt": f"{_PERMISSION_MODULE}.refund_processing_attempt_query",
	"EdgePay Dispute": f"{_PERMISSION_MODULE}.dispute_query",
	"EdgePay Chargeback": f"{_PERMISSION_MODULE}.chargeback_query",
	"EdgePay Fee Record": f"{_PERMISSION_MODULE}.fee_record_query",
	"EdgePay Settlement Batch": f"{_PERMISSION_MODULE}.settlement_batch_query",
	"EdgePay Settlement Item": f"{_PERMISSION_MODULE}.settlement_item_query",
	"EdgePay Webhook Event": f"{_PERMISSION_MODULE}.webhook_event_query",
	"EdgePay Status Handoff Event": f"{_PERMISSION_MODULE}.handoff_event_query",
}

has_permission = {
	doctype: f"{_PERMISSION_MODULE}.has_merchant_permission"
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
