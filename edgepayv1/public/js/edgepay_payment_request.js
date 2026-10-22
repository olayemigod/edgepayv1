frappe.ui.form.on("EdgePay Payment Request", {
	setup(frm) {
		frm.set_query("merchant_account", () => ({
			query: "edgepayv1.edgepay.services.merchant_queries.merchant_account_query",
			filters: { merchant: frm.doc.merchant },
		}));
		frm.set_query("merchant_branch", () => ({
			query: "edgepayv1.edgepay.services.merchant_queries.merchant_branch_query",
			filters: {
				merchant: frm.doc.merchant,
				merchant_account: frm.doc.merchant_account,
			},
		}));
		frm.set_query("provider_account", () => ({
			query: "edgepayv1.edgepay.services.merchant_queries.provider_account_query",
			filters: {
				merchant: frm.doc.merchant,
				provider: frm.doc.provider,
			},
		}));
	},
	merchant(frm) {
		frm.set_value("merchant_account", null);
		frm.set_value("merchant_branch", null);
		frm.set_value("provider_account", null);
	},
	merchant_account(frm) {
		frm.set_value("merchant_branch", null);
	},
	provider(frm) {
		frm.set_value("provider_account", null);
	},
});
