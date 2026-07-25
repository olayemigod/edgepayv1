app_name = "edgepayv1"
app_title = "EdgePay"
app_publisher = "ProcessEdge Solutions Limited"
app_description = "Universal payment orchestration layer for Frappe, ERPNext, POSnext, and EdgeSuite apps"
app_email = "info@processedge.com.ng"
app_license = "mit"

# EdgePay uses the independent local EdgeSuite UI runtime. CoreEdge remains a
# remote platform authority and is not required to render EdgePay Desk pages.
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
			[
				"role_name",
				"in",
				[
					"EdgePay Admin",
					"EdgePay Manager",
					"EdgePay User",
					"EdgePay Auditor",
				],
			]
		],
	}
]
