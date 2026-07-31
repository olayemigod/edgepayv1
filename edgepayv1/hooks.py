app_name = "edgepayv1"
app_title = "EdgePay"
app_publisher = "ProcessEdge Solutions Limited"
app_description = "Universal payment orchestration layer for Frappe, ERPNext, POSnext, and EdgeSuite apps"
app_email = "info@processedge.com.ng"
app_license = "mit"

fixtures = [
	{
		"dt": "Role",
		"filters": [["role_name", "in", ["EdgePay Admin", "EdgePay Manager", "EdgePay User", "EdgePay Auditor"]]],
	}
]

doctype_js = {
	"EdgePay Payment Request": "public/js/edgepay_payment_request.js",
}

permission_query_conditions = {
	"EdgePay Merchant": "edgepayv1.permissions.merchant_query",
	"EdgePay Merchant Account": "edgepayv1.permissions.merchant_account_query",
	"EdgePay Merchant Branch": "edgepayv1.permissions.merchant_branch_query",
	"EdgePay Provider Account": "edgepayv1.permissions.provider_account_query",
	"EdgePay Merchant Verification": "edgepayv1.permissions.merchant_verification_query",
	"EdgePay Payment Request": "edgepayv1.permissions.payment_request_query",
	"EdgePay Payment Transaction": "edgepayv1.permissions.payment_transaction_query",
	"EdgePay Webhook Event": "edgepayv1.permissions.webhook_event_query",
	"EdgePay Status Handoff Event": "edgepayv1.permissions.handoff_event_query",
}

has_permission = {
	"EdgePay Merchant": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Merchant Account": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Merchant Branch": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Provider Account": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Merchant Verification": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Payment Request": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Payment Transaction": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Webhook Event": "edgepayv1.permissions.has_merchant_permission",
	"EdgePay Status Handoff Event": "edgepayv1.permissions.has_merchant_permission",
}
