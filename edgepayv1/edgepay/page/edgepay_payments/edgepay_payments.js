frappe.pages["edgepay-payments"].on_page_load = function (wrapper) {
	wrapper.page = frappe.ui.make_app_page({ parent: wrapper, title: __("Payments"), single_column: true });
};

frappe.pages["edgepay-payments"].on_page_show = function (wrapper) {
	const root = document.createElement("div");
	root.className = "edgepay-operations p-4";
	root.dataset.edgeProduct = "edgepay";
	$(wrapper.page.body).empty().append(root);
	const esc = (value) => frappe.utils.escape_html(String(value ?? ""));
	const table = (title, rows, columns, emptyText) => {
		const body = rows.length
			? rows.map((row) => `<tr>${columns.map((column) => `<td>${column.render ? column.render(row) : esc(row[column.field])}</td>`).join("")}</tr>`).join("")
			: `<tr><td colspan="${columns.length}" class="text-center text-muted p-4">${esc(emptyText)}</td></tr>`;
		return `<section class="card mb-4"><div class="card-body"><h4>${esc(title)}</h4><div class="table-responsive"><table class="table table-hover"><thead><tr>${columns.map((column) => `<th>${esc(column.label)}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div></div></section>`;
	};
	const render = (context) => {
		const requests = context.requests || [];
		const attempts = context.attempts || [];
		const events = context.events || [];
		const requested = requests.reduce((sum, row) => sum + Number(row.amount || 0), 0);
		const paid = requests.reduce((sum, row) => sum + Number(row.paid_amount || 0), 0);
		const outstanding = requests.reduce((sum, row) => sum + Number(row.outstanding_amount || 0), 0);
		root.innerHTML = `
			<div class="d-flex justify-content-between align-items-start gap-3 flex-wrap mb-4">
				<div><h2 class="mb-1">${esc(__("Payment Operations"))}</h2><p class="text-muted mb-0">${esc(__("Merchant-scoped payment requests, attempts and immutable events."))}</p></div>
				<a class="btn btn-default btn-sm" href="/app/edgepay-home">${esc(__("Back to EdgePay Home"))}</a>
			</div>
			<div class="row mb-2">
				<div class="col-md-4 mb-3"><div class="card h-100"><div class="card-body"><div class="text-muted small">${esc(__("Requested"))}</div><div class="h4 mb-0">${esc(requested.toLocaleString())}</div></div></div></div>
				<div class="col-md-4 mb-3"><div class="card h-100"><div class="card-body"><div class="text-muted small">${esc(__("Paid"))}</div><div class="h4 mb-0">${esc(paid.toLocaleString())}</div></div></div></div>
				<div class="col-md-4 mb-3"><div class="card h-100"><div class="card-body"><div class="text-muted small">${esc(__("Outstanding"))}</div><div class="h4 mb-0">${esc(outstanding.toLocaleString())}</div></div></div></div>
			</div>
			${table(__("Payment Requests"), requests, [
				{ label: __("Reference"), render: (row) => `<a href="/app/edgepay-payment-request/${encodeURIComponent(row.name)}">${esc(row.request_reference || row.name)}</a>` },
				{ label: __("Customer"), field: "customer_name" },
				{ label: __("Amount"), render: (row) => `${esc(row.currency)} ${esc(row.amount)}` },
				{ label: __("Paid"), render: (row) => `${esc(row.currency)} ${esc(row.paid_amount || 0)}` },
				{ label: __("Outstanding"), render: (row) => `${esc(row.currency)} ${esc(row.outstanding_amount || 0)}` },
				{ label: __("Status"), field: "status" },
			], __("No payment requests are available."))}
			${table(__("Recent Attempts"), attempts, [
				{ label: __("Attempt"), render: (row) => `<a href="/app/edgepay-payment-attempt/${encodeURIComponent(row.name)}">${esc(row.name)}</a>` },
				{ label: __("Payment Request"), field: "payment_request" },
				{ label: __("No."), field: "attempt_number" },
				{ label: __("Method"), field: "payment_method" },
				{ label: __("Status"), field: "status" },
			], __("No payment attempts are available."))}
			${table(__("Recent Payment Events"), events, [
				{ label: __("Event"), field: "event_type" },
				{ label: __("Payment Request"), field: "payment_request" },
				{ label: __("Previous"), field: "previous_status" },
				{ label: __("New"), field: "new_status" },
				{ label: __("Source"), field: "event_source" },
				{ label: __("Occurred"), field: "occurred_on" },
			], __("No payment events are available."))}`;
	};
	root.innerHTML = `<div class="text-center text-muted p-5">${esc(__("Loading payment operations…"))}</div>`;
	frappe.require("edgesuite_ui.bundle.js", () => {
		const runtime = window.EdgeSuiteUI || window.EdgeUI;
		if (!runtime) {
			root.innerHTML = `<div class="alert alert-danger">${esc(__("The standalone EdgeSuite UI runtime is unavailable."))}</div>`;
			return;
		}
		frappe.call({
			method: "edgepayv1.api.operations.get_payments_context",
			callback: (response) => render(response.message || {}),
			error: (error) => { root.innerHTML = `<div class="alert alert-danger">${esc(error?.message || String(error))}</div>`; },
		});
	});
};
