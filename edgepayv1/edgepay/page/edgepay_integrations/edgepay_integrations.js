frappe.pages["edgepay-integrations"].on_page_load = function (wrapper) {
	wrapper.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Integrations"), single_column: true });
};

frappe.pages["edgepay-integrations"].on_page_show = function (wrapper) {
	const root = document.createElement("div");
	root.className = "edgepay-operations p-4";
	root.dataset.edgeProduct = "edgepay";
	$(wrapper.page.body).empty().append(root);
	const esc = (value) => frappe.utils.escape_html(String(value ?? ""));
	const cards = (title, rows, formatter) => `<section class="card mb-4"><div class="card-body"><h4>${esc(title)}</h4><div class="row">${rows.length ? rows.map(formatter).join("") : `<div class="col-12 text-muted">${esc(__("No records available."))}</div>`}</div></div></section>`;
	const item = (title, subtitle, status, href) => `<div class="col-md-6 col-xl-4 mb-3"><div class="border rounded p-3 h-100"><div class="d-flex justify-content-between gap-2"><a href="${href}"><strong>${esc(title)}</strong></a><span class="text-muted small">${esc(status || "")}</span></div><div class="text-muted small mt-1">${esc(subtitle || "")}</div></div></div>`;
	const renderNoContext = (state) => {
		const action = state.can_bootstrap
			? `<a class="btn btn-primary" href="/app/merchant-onboarding">${esc(__("Set Up Merchant"))}</a>`
			: `<a class="btn btn-default" href="/app/edgepay-home">${esc(__("Back to EdgePay Home"))}</a>`;
		root.innerHTML = `<section class="card"><div class="card-body p-4"><h3 class="mb-2">${esc(__("Merchant context required"))}</h3><p class="text-muted">${esc(state.message || __("A merchant must be assigned before integration operations can be used."))}</p>${action}</div></section>`;
	};
	const render = (context) => {
		const state = context.context_state || {};
		if (!state.has_context) {
			renderNoContext(state);
			return;
		}
		root.innerHTML = `
			<div class="d-flex justify-content-between align-items-start gap-3 flex-wrap mb-4"><div><h2 class="mb-1">${esc(__("Integration Operations"))}</h2><p class="text-muted mb-0">${esc(__("Merchant provider accounts, signed API clients and delivery health without exposing secrets."))}</p></div><a class="btn btn-default btn-sm" href="/app/edgepay-home">${esc(__("Back to EdgePay Home"))}</a></div>
			${cards(__("Provider Accounts"), context.provider_accounts || [], (row) => item(row.account_label || row.name, `${row.provider || ""} · ${row.environment || ""}`, row.status, `/app/edgepay-provider-account/${encodeURIComponent(row.name)}`))}
			${cards(__("API Clients"), context.api_clients || [], (row) => item(row.client_name || row.name, row.client_id || "", row.enabled ? __("Enabled") : __("Disabled"), `/app/edgepay-api-client/${encodeURIComponent(row.name)}`))}
			${cards(__("Delivery Endpoints"), context.delivery_endpoints || [], (row) => item(row.endpoint_name || row.name, row.endpoint_url || "", row.enabled ? __("Enabled") : __("Disabled"), `/app/edgepay-delivery-endpoint/${encodeURIComponent(row.name)}`))}
			${cards(__("Recent Deliveries"), context.deliveries || [], (row) => item(row.event_type || row.name, row.name, row.status, `/app/edgepay-delivery/${encodeURIComponent(row.name)}`))}`;
	};
	root.innerHTML = `<div class="text-center text-muted p-5">${esc(__("Loading integration operations…"))}</div>`;
	frappe.require("edgesuite_ui.bundle.js", () => {
		if (!(window.EdgeSuiteUI || window.EdgeUI)) {
			root.innerHTML = `<div class="alert alert-danger">${esc(__("The standalone EdgeSuite UI runtime is unavailable."))}</div>`;
			return;
		}
		frappe.call({
			method: "edgepayv1.api.operations.get_integrations_context",
			callback: (response) => render(response.message || {}),
			error: (error) => {
				root.innerHTML = `<div class="alert alert-danger">${esc(error?.message || String(error))}</div>`;
			},
		});
	});
};
