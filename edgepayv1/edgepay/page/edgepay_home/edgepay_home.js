frappe.pages["edgepay-home"].on_page_load = function (wrapper) {
	wrapper.page = frappe.ui.make_app_page({ parent: wrapper, title: __("EdgePay"), single_column: true });
};

frappe.pages["edgepay-home"].on_page_show = function (wrapper) {
	const page = wrapper.page;
	$(page.body).empty();
	const root = document.createElement("div");
	root.className = "edgepay-home p-4";
	root.dataset.edgeProduct = "edgepay";
	page.body.appendChild(root);
	const esc = (v) => frappe.utils.escape_html(String(v ?? ""));
	const pill = (s) => ["Paid", "Verified", "Active", "Ready"].includes(s) ? "green" : ["Failed", "Chargeback", "Rejected"].includes(s) ? "red" : ["Initiated", "Partly Paid", "Refund Pending", "In Progress"].includes(s) ? "orange" : "gray";
	const linkCard = (label, value, route) => `<a class="card h-100 text-decoration-none" href="${route}"><div class="card-body"><div class="text-muted small">${esc(__(label))}</div><div class="h3 mb-0">${esc(value || 0)}</div></div></a>`;
	const render = (ctx) => {
		const merchant = ctx.merchant || {};
		const reg = ctx.registration || {};
		const summary = ctx.summary || {};
		const counts = summary.counts || {};
		const ops = ctx.operations || {};
		const rows = (ctx.recent_requests || []).map((r) => `<tr><td><a href="/app/edgepay-payment-request/${encodeURIComponent(r.name)}">${esc(r.request_reference || r.name)}</a></td><td>${esc(r.customer_name)}</td><td>${esc(r.currency)} ${esc(r.amount)}</td><td>${esc(r.currency)} ${esc(r.paid_amount || 0)}</td><td>${esc(r.currency)} ${esc(r.outstanding_amount || 0)}</td><td><span class="indicator-pill ${pill(r.status)}">${esc(r.status)}</span></td></tr>`).join("") || `<tr><td colspan="6" class="text-center text-muted p-4">${esc(__("No payments yet."))}</td></tr>`;
		root.innerHTML = `<div class="d-flex justify-content-between align-items-start mb-4"><div><h2 class="mb-1">${esc(merchant.trading_name || merchant.legal_name || __("EdgePay"))}</h2><div class="text-muted">${esc(__("Payments, settlements, integration health and merchant readiness"))}</div></div><div><span class="indicator-pill ${pill(merchant.verification_status)}">${esc(merchant.verification_status || __("Unverified"))}</span></div></div>
		<div class="row mb-4"><div class="col-md-3 mb-3">${linkCard("Paid payments", counts.Paid, "/app/edgepay-payment-request?status=Paid")}</div><div class="col-md-3 mb-3">${linkCard("Partly paid", counts["Partly Paid"], "/app/edgepay-payment-request?status=Partly%20Paid")}</div><div class="col-md-3 mb-3">${linkCard("Open refunds", ops.refunds_open, "/app/edgepay-refund-request")}</div><div class="col-md-3 mb-3">${linkCard("Delivery exceptions", ops.dead_letters, "/app/edgepay-delivery?status=Dead%20Letter")}</div></div>
		<section class="card mb-4" id="merchant-readiness"><div class="card-body"><div class="d-flex justify-content-between"><div><h4>${esc(__("Merchant readiness"))}</h4><p class="text-muted mb-0">${esc(reg.message || "")}</p></div><span class="indicator-pill ${pill(reg.status)}">${esc(reg.status || __("Unknown"))}</span></div><div class="mt-3"><a class="btn btn-primary btn-sm" href="/app/merchant-onboarding">${esc(__("Open onboarding"))}</a></div></div></section>
		<section class="card mb-4"><div class="card-body"><h4>${esc(__("Integration and settlement health"))}</h4><div class="row"><div class="col-md-3"><div class="text-muted small">${esc(__("Provider accounts"))}</div><strong>${esc(ops.provider_accounts || 0)}</strong></div><div class="col-md-3"><div class="text-muted small">${esc(__("API clients"))}</div><strong>${esc(ops.api_clients || 0)}</strong></div><div class="col-md-3"><div class="text-muted small">${esc(__("Delivery endpoints"))}</div><strong>${esc(ops.delivery_endpoints || 0)}</strong></div><div class="col-md-3"><div class="text-muted small">${esc(__("Open settlements"))}</div><strong>${esc(ops.settlements_open || 0)}</strong></div></div></div></section>
		<section class="card"><div class="card-body"><div class="d-flex justify-content-between mb-2"><h4>${esc(__("Recent payments"))}</h4><a class="btn btn-default btn-sm" href="/app/edgepay-payment-request">${esc(__("View all"))}</a></div><div class="table-responsive"><table class="table table-hover"><thead><tr><th>${esc(__("Reference"))}</th><th>${esc(__("Customer"))}</th><th>${esc(__("Requested"))}</th><th>${esc(__("Paid"))}</th><th>${esc(__("Outstanding"))}</th><th>${esc(__("Status"))}</th></tr></thead><tbody>${rows}</tbody></table></div></div></section>`;
	};
	root.innerHTML = `<div class="text-center text-muted p-5">${esc(__("Loading EdgePay…"))}</div>`;
	frappe.require("edgesuite_ui.bundle.js", () => {
		if (!(window.EdgeSuiteUI || window.EdgeUI)) { root.innerHTML = `<div class="alert alert-danger">${esc(__("EdgeSuite UI runtime is unavailable."))}</div>`; return; }
		frappe.call({ method: "edgepayv1.api.home.get_home_context", callback: (r) => render(r.message || {}), error: (e) => { root.innerHTML = `<div class="alert alert-danger">${esc(e?.message || e)}</div>`; } });
	});
};
