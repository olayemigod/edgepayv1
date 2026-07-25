frappe.pages["edgepay-home"].on_page_load = function (wrapper) {
	wrapper.page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("EdgePay Home"),
		single_column: true,
	});
};

frappe.pages["edgepay-home"].on_page_show = function (wrapper) {
	const page = wrapper.page;
	$(page.body).empty();

	const root = document.createElement("div");
	root.className = "edgepay-home p-4";
	root.dataset.edgeProduct = "edgepay";
	page.body.appendChild(root);

	const escape = (value) => frappe.utils.escape_html(String(value ?? ""));
	const statusClass = (status) => {
		if (["Paid", "Ready"].includes(status)) return "indicator-pill green";
		if (["Failed", "Expired", "Restricted"].includes(status)) return "indicator-pill red";
		if (["Initiated", "In Progress"].includes(status)) return "indicator-pill orange";
		return "indicator-pill gray";
	};

	const renderError = (message) => {
		root.innerHTML = `
			<div class="alert alert-danger">
				<strong>${escape(__("EdgePay Home failed to load"))}</strong>
				<div>${escape(message)}</div>
			</div>`;
	};

	const render = (context) => {
		const counts = context.request_counts || {};
		const registration = context.registration || {};
		const settings = context.settings || {};
		const recent = context.recent_requests || [];
		const countCards = ["Paid", "Initiated", "Failed", "Expired"]
			.map(
				(status) => `
				<div class="col-sm-6 col-lg-3 mb-3">
					<div class="card h-100">
						<div class="card-body">
							<div class="text-muted small">${escape(__(status))}</div>
							<div class="h3 mb-0">${escape(counts[status] || 0)}</div>
						</div>
					</div>
				</div>`,
			)
			.join("");
		const checks = (registration.checks || [])
			.map(
				(check) => `
				<li class="list-group-item d-flex justify-content-between align-items-center">
					<span>${escape(check.label)}</span>
					<span class="${check.complete ? "indicator-pill green" : "indicator-pill gray"}">
						${escape(check.complete ? __("Complete") : __("Pending"))}
					</span>
				</li>`,
			)
			.join("");
		const rows = recent.length
			? recent
					.map(
						(row) => `
						<tr>
							<td><a href="/app/edgepay-payment-request/${encodeURIComponent(row.name)}">${escape(row.request_reference || row.name)}</a></td>
							<td>${escape(row.customer_name)}</td>
							<td>${escape(row.currency)} ${escape(row.amount)}</td>
							<td><span class="${statusClass(row.status)}">${escape(row.status)}</span></td>
							<td>${escape(row.source_app || row.source_doctype || "")}</td>
						</tr>`,
					)
					.join("")
			: `<tr><td colspan="5" class="text-center text-muted p-4">${escape(__("No payment requests are available."))}</td></tr>`;

		root.innerHTML = `
			<div class="mb-4">
				<h2 class="mb-1">${escape(__("Payment operations and readiness"))}</h2>
				<p class="text-muted mb-0">${escape(__("Review verified payment activity, setup readiness and recent requests without exposing provider credentials."))}</p>
			</div>
			<section id="payment-summary" class="mb-4">
				<div class="d-flex justify-content-between align-items-center mb-2">
					<h4 class="mb-0">${escape(__("Payment summary"))}</h4>
					<a class="btn btn-default btn-sm" href="/app/edgepay-payment-request">${escape(__("Open Payment Requests"))}</a>
				</div>
				<div class="row">${countCards}</div>
			</section>
			<section id="registration-readiness" class="card mb-4">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-start mb-3">
						<div>
							<h4 class="mb-1">${escape(__("Registration and activation readiness"))}</h4>
							<p class="text-muted mb-0">${escape(registration.message || "")}</p>
						</div>
						<span class="${statusClass(registration.status)}">${escape(registration.status || __("Unknown"))}</span>
					</div>
					<ul class="list-group list-group-flush">${checks || `<li class="list-group-item text-muted">${escape(__("No readiness checks are visible for your role."))}</li>`}</ul>
				</div>
			</section>
			<section id="tenant-settings" class="card mb-4">
				<div class="card-body">
					<h4>${escape(__("Tenant payment information"))}</h4>
					<div class="row">
						<div class="col-md-4"><div class="text-muted small">${escape(__("Default currency"))}</div><strong>${escape(settings.default_currency || __("Not set"))}</strong></div>
						<div class="col-md-4"><div class="text-muted small">${escape(__("Default provider"))}</div><strong>${escape(settings.default_provider || __("Not set"))}</strong></div>
						<div class="col-md-4"><div class="text-muted small">${escape(__("Environment"))}</div><strong>${escape(settings.sandbox_mode ? __("Sandbox") : __("Configured mode"))}</strong></div>
					</div>
					<p class="text-muted small mt-3 mb-0">${escape(__("Provider credentials, live-call gates and webhook secrets are intentionally not displayed here."))}</p>
				</div>
			</section>
			<section class="card">
				<div class="card-body">
					<h4>${escape(__("Recent payment requests"))}</h4>
					<div class="table-responsive">
						<table class="table table-hover">
							<thead><tr><th>${escape(__("Reference"))}</th><th>${escape(__("Customer"))}</th><th>${escape(__("Amount"))}</th><th>${escape(__("Status"))}</th><th>${escape(__("Source"))}</th></tr></thead>
							<tbody>${rows}</tbody>
						</table>
					</div>
				</div>
			</section>`;
	};

	root.innerHTML = `<div class="text-center text-muted p-5">${escape(__("Loading EdgePay information…"))}</div>`;
	frappe.require("edgesuite_ui.bundle.js", () => {
		const runtime = window.EdgeSuiteUI || window.EdgeUI;
		if (!runtime) {
			renderError(__("The standalone EdgeSuite UI runtime is unavailable."));
			return;
		}
		frappe.call({
			method: "edgepayv1.api.home.get_home_context",
			callback(response) {
				render(response.message || {});
			},
			error(error) {
				renderError(error?.message || String(error));
			},
		});
	});
};
