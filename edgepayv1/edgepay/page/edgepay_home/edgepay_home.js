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
		if (["Paid", "Successful", "Ready", "Active", "Verified", "Completed"].includes(status)) {
			return "indicator-pill green";
		}
		if (["Failed", "Expired", "Action Required", "Suspended", "Rejected", "Chargeback"].includes(status)) {
			return "indicator-pill red";
		}
		if (["Initiated", "Pending", "In Progress", "Limited View", "Under Review", "Partly Paid"].includes(status)) {
			return "indicator-pill orange";
		}
		return "indicator-pill gray";
	};
	const displayCount = (value) => (value === null || value === undefined ? __("Restricted") : value);

	const renderError = (message) => {
		root.innerHTML = `
			<div class="alert alert-danger">
				<strong>${escape(__("EdgePay Home failed to load"))}</strong>
				<div>${escape(message)}</div>
			</div>`;
	};

	const render = (context) => {
		const counts = context.request_counts || {};
		const attempts = context.attempt_counts || {};
		const readiness = context.readiness || {};
		const merchant = context.merchant || {};
		const operational = context.operational || {};
		const recent = context.recent_requests || [];
		const merchantContext = context.merchant_context || {};

		const countCards = ["Paid", "Partly Paid", "Initiated", "Failed"]
			.map(
				(status) => `
				<div class="col-sm-6 col-lg-3 mb-3">
					<div class="card h-100"><div class="card-body">
						<div class="text-muted small">${escape(__(status))}</div>
						<div class="h3 mb-0">${escape(counts[status] || 0)}</div>
					</div></div>
				</div>`
			)
			.join("");

		const checks = (readiness.checks || [])
			.map((check) => {
				const label = check.visible === false ? __("Restricted") : check.complete ? __("Complete") : __("Pending");
				const klass = check.visible === false ? "indicator-pill gray" : check.complete ? "indicator-pill green" : "indicator-pill orange";
				return `
					<li class="list-group-item d-flex justify-content-between align-items-center">
						<span>${escape(check.label)}</span><span class="${klass}">${escape(label)}</span>
					</li>`;
			})
			.join("");

		const rows = recent.length
			? recent
					.map(
						(row) => `
						<tr>
							<td><a href="/app/edgepay-payment-request/${encodeURIComponent(row.name)}">${escape(row.request_reference || row.name)}</a></td>
							<td>${escape(row.customer_name)}</td>
							<td>${escape(row.currency)} ${escape(row.amount)}</td>
							<td>${escape(row.currency)} ${escape(row.paid_amount || 0)}</td>
							<td><span class="${statusClass(row.status)}">${escape(row.status)}</span></td>
							<td>${escape(row.source_app || row.source_doctype || "")}</td>
						</tr>`
					)
					.join("")
			: `<tr><td colspan="6" class="text-center text-muted p-4">${escape(__("No payment requests are available for this merchant."))}</td></tr>`;

		const merchantBlock = merchant.visible
			? `
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-start gap-3 flex-wrap">
						<div>
							<h4 class="mb-1">${escape(merchant.merchant_name || merchant.name)}</h4>
							<div class="text-muted small">${escape(merchant.public_id || merchant.name)}</div>
						</div>
						<span class="${statusClass(merchant.status)}">${escape(merchant.status || __("Unknown"))}</span>
					</div>
					<div class="row mt-3">
						<div class="col-md-3"><div class="text-muted small">${escape(__("Onboarding"))}</div><strong>${escape(merchant.onboarding_status || "—")}</strong></div>
						<div class="col-md-3"><div class="text-muted small">${escape(__("Verification"))}</div><strong>${escape(merchant.verification_status || "—")}</strong></div>
						<div class="col-md-3"><div class="text-muted small">${escape(__("Currency"))}</div><strong>${escape(merchant.default_currency || "—")}</strong></div>
						<div class="col-md-3"><div class="text-muted small">${escape(__("Live payments"))}</div><strong>${escape(merchant.live_payments_allowed ? __("Approved") : __("Not approved"))}</strong></div>
					</div>
				</div>`
			: `
				<div class="card-body">
					<h4>${escape(__("No merchant context assigned"))}</h4>
					<p class="text-muted mb-0">${escape(__("Assign an active EdgePay Merchant User membership before reviewing merchant payment operations."))}</p>
				</div>`;

		root.innerHTML = `
			<div class="d-flex justify-content-between align-items-start gap-3 flex-wrap mb-4">
				<div>
					<h2 class="mb-1">${escape(__("Payment operations and merchant readiness"))}</h2>
					<p class="text-muted mb-0">${escape(__("Review merchant-scoped payment activity, onboarding and integration readiness without exposing provider or API secrets."))}</p>
				</div>
				<div class="d-flex gap-2">
					<a class="btn btn-default btn-sm" href="/app/merchant-onboarding">${escape(__("Merchant Onboarding"))}</a>
					<a class="btn btn-primary btn-sm" href="/app/edgepay-payment-request">${escape(__("Payment Requests"))}</a>
				</div>
			</div>

			<section class="card mb-4" id="merchant-context">${merchantBlock}</section>

			<section id="payment-summary" class="mb-4">
				<div class="d-flex justify-content-between align-items-center mb-2">
					<h4 class="mb-0">${escape(__("Payment request summary"))}</h4>
					<div class="text-muted small">${escape(merchantContext.merchant_branch || merchantContext.merchant_account || "")}</div>
				</div>
				<div class="row">${countCards}</div>
				<div class="text-muted small">${escape(__("Attempts"))}: ${escape(__("Successful"))} ${escape(attempts.Successful || 0)} · ${escape(__("Pending"))} ${escape(attempts.Pending || 0)} · ${escape(__("Failed"))} ${escape(attempts.Failed || 0)}</div>
			</section>

			<section id="registration-readiness" class="card mb-4">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-start mb-3 gap-3">
						<div><h4 class="mb-1">${escape(__("Merchant activation readiness"))}</h4><p class="text-muted mb-0">${escape(readiness.message || "")}</p></div>
						<span class="${statusClass(readiness.status)}">${escape(readiness.status || __("Unknown"))}</span>
					</div>
					<ul class="list-group list-group-flush">${checks || `<li class="list-group-item text-muted">${escape(__("No readiness checks are available."))}</li>`}</ul>
				</div>
			</section>

			<section id="integration-readiness" class="card mb-4">
				<div class="card-body">
					<h4>${escape(__("Integration readiness"))}</h4>
					<div class="row">
						<div class="col-md-4"><div class="text-muted small">${escape(__("Active provider accounts"))}</div><strong>${escape(displayCount(operational.active_provider_accounts))}</strong></div>
						<div class="col-md-4"><div class="text-muted small">${escape(__("Enabled API clients"))}</div><strong>${escape(displayCount(operational.enabled_api_clients))}</strong></div>
						<div class="col-md-4"><div class="text-muted small">${escape(__("Enabled delivery endpoints"))}</div><strong>${escape(displayCount(operational.enabled_delivery_endpoints))}</strong></div>
					</div>
					<p class="text-muted small mt-3 mb-0">${escape(__("Provider credentials, API client secrets, webhook signing secrets, raw provider payloads and live-call control fields are intentionally excluded."))}</p>
				</div>
			</section>

			<section class="card">
				<div class="card-body">
					<h4>${escape(__("Recent payment requests"))}</h4>
					<div class="table-responsive"><table class="table table-hover">
						<thead><tr><th>${escape(__("Reference"))}</th><th>${escape(__("Customer"))}</th><th>${escape(__("Amount"))}</th><th>${escape(__("Paid"))}</th><th>${escape(__("Status"))}</th><th>${escape(__("Source"))}</th></tr></thead>
						<tbody>${rows}</tbody>
					</table></div>
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
