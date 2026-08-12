frappe.pages["edgepay-finance"].on_page_load = function (wrapper) {
	wrapper.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Finance & Exceptions"), single_column: true });
};

frappe.pages["edgepay-finance"].on_page_show = function (wrapper) {
	const root = document.createElement("div");
	root.className = "edgepay-operations p-4";
	root.dataset.edgeProduct = "edgepay";
	$(wrapper.page.body).empty().append(root);
	const esc = (value) => frappe.utils.escape_html(String(value ?? ""));
	const section = (title, rows, hrefBase, amountField = "amount") => `<section class="card mb-4"><div class="card-body"><h4>${esc(title)}</h4><div class="table-responsive"><table class="table table-hover"><thead><tr><th>${esc(__("Reference"))}</th><th>${esc(__("Amount"))}</th><th>${esc(__("Status"))}</th><th>${esc(__("Modified"))}</th></tr></thead><tbody>${rows.length ? rows.map((row) => `<tr><td><a href="${hrefBase}/${encodeURIComponent(row.name)}">${esc(row.name)}</a></td><td>${esc(row.currency || "")} ${esc(row[amountField] || row.net_amount || 0)}</td><td>${esc(row.status || "")}</td><td>${esc(row.modified || "")}</td></tr>`).join("") : `<tr><td colspan="4" class="text-center text-muted p-4">${esc(__("No records available."))}</td></tr>`}</tbody></table></div></div></section>`;
	const render = (context) => {
		root.innerHTML = `
			<div class="d-flex justify-content-between align-items-start gap-3 flex-wrap mb-4"><div><h2 class="mb-1">${esc(__("Finance & Exceptions"))}</h2><p class="text-muted mb-0">${esc(__("Merchant-scoped refunds, settlements, disputes and chargebacks."))}</p></div><a class="btn btn-default btn-sm" href="/app/edgepay-home">${esc(__("Back to EdgePay Home"))}</a></div>
			${section(__("Refund Requests"), context.refunds || [], "/app/edgepay-refund-request")}
			${section(__("Settlement Batches"), context.settlements || [], "/app/edgepay-settlement-batch", "net_amount")}
			${section(__("Disputes"), context.disputes || [], "/app/edgepay-dispute")}
			${section(__("Chargebacks"), context.chargebacks || [], "/app/edgepay-chargeback")}`;
	};
	root.innerHTML = `<div class="text-center text-muted p-5">${esc(__("Loading finance operations…"))}</div>`;
	frappe.require("edgesuite_ui.bundle.js", () => {
		if (!(window.EdgeSuiteUI || window.EdgeUI)) { root.innerHTML = `<div class="alert alert-danger">${esc(__("The standalone EdgeSuite UI runtime is unavailable."))}</div>`; return; }
		frappe.call({ method: "edgepayv1.api.operations.get_finance_context", callback: (response) => render(response.message || {}), error: (error) => { root.innerHTML = `<div class="alert alert-danger">${esc(error?.message || String(error))}</div>`; } });
	});
};
