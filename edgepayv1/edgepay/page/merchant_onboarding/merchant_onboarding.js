function edgepayMountMerchantOnboarding(wrapper) {
	const page = wrapper.page;
	$(page.body).empty();

	const root = document.createElement("div");
	root.className = "edgepay-onboarding p-4";
	root.dataset.edgeProduct = "edgepay";
	page.body.appendChild(root);

	let pageData = {};
	const esc = (value) => frappe.utils.escape_html(String(value ?? ""));

	function openCreateMerchantDialog() {
		const dialog = new frappe.ui.Dialog({
			title: __("Create EdgePay Merchant"),
			fields: [
				{
					fieldname: "merchant_name",
					fieldtype: "Data",
					label: __("Merchant / Trading Name"),
					reqd: 1,
				},
				{
					fieldname: "legal_name",
					fieldtype: "Data",
					label: __("Legal Business Name"),
					reqd: 1,
				},
				{
					fieldname: "email",
					fieldtype: "Data",
					options: "Email",
					label: __("Business Email"),
				},
				{ fieldname: "phone", fieldtype: "Data", label: __("Business Phone") },
				{
					fieldname: "country",
					fieldtype: "Link",
					options: "Country",
					label: __("Country"),
					default: "Nigeria",
					reqd: 1,
				},
				{
					fieldname: "default_currency",
					fieldtype: "Link",
					options: "Currency",
					label: __("Default Currency"),
					default: "NGN",
					reqd: 1,
				},
			],
			primary_action_label: __("Create Merchant"),
			primary_action(values) {
				dialog.get_primary_btn().prop("disabled", true);
				frappe.call({
					method: "edgepayv1.edgepay.page.merchant_onboarding.merchant_onboarding.create_first_merchant",
					args: values,
					callback(response) {
						if (!(response.message || {}).merchant) return;
						dialog.hide();
						frappe.show_alert({
							message: __("Merchant created. Continue onboarding and verification."),
							indicator: "green",
						});
						refresh();
					},
					always() {
						dialog.get_primary_btn().prop("disabled", false);
					},
				});
			},
		});
		dialog.show();
	}

	function openIdentityDialog() {
		if (!pageData.merchant) return;
		const dialog = new frappe.ui.Dialog({
			title: __("Representative Identity Verification"),
			fields: [
				{
					fieldname: "merchant_verification",
					fieldtype: "Link",
					options: "EdgePay Merchant Verification",
					label: __("Merchant Verification"),
					reqd: 1,
					get_query: () => ({ filters: { merchant: pageData.merchant.name } }),
				},
				{
					fieldname: "provider",
					fieldtype: "Link",
					options: "EdgePay Verification Provider",
					label: __("Verification Provider"),
					reqd: 1,
					get_query: () => ({ filters: { enabled: 1 } }),
				},
				{ fieldname: "first_name", fieldtype: "Data", label: __("First Name"), reqd: 1 },
				{ fieldname: "middle_name", fieldtype: "Data", label: __("Middle Name") },
				{ fieldname: "last_name", fieldtype: "Data", label: __("Surname"), reqd: 1 },
				{ fieldname: "date_of_birth", fieldtype: "Date", label: __("Date of Birth"), reqd: 1 },
				{ fieldname: "phone", fieldtype: "Data", label: __("Phone"), reqd: 1 },
				{
					fieldname: "selfie_file",
					fieldtype: "Attach Image",
					label: __("Live Selfie / Photo"),
					reqd: 1,
					description: __("A production provider must replace simple upload with its camera liveness SDK."),
				},
				{
					fieldname: "consent",
					fieldtype: "Check",
					label: __("I consent to NIN, BVN, DOB, liveness and face verification for merchant onboarding."),
					reqd: 1,
				},
				{
					fieldname: "nin",
					fieldtype: "Password",
					label: __("NIN"),
					reqd: 1,
					description: __("Used only for this provider request and not stored by EdgePay."),
				},
				{
					fieldname: "bvn",
					fieldtype: "Password",
					label: __("BVN"),
					reqd: 1,
					description: __("Used only for this provider request and not stored by EdgePay."),
				},
				{
					fieldname: "bvn_consent_token",
					fieldtype: "Password",
					label: __("BVN Consent Token"),
					reqd: 1,
				},
			],
			primary_action_label: __("Verify Identity"),
			primary_action(values) {
				if (!values.consent) {
					frappe.msgprint(__("Consent is required."));
					return;
				}
				const safeSessionArgs = {
					merchant_verification: values.merchant_verification,
					provider: values.provider,
					first_name: values.first_name,
					middle_name: values.middle_name,
					last_name: values.last_name,
					date_of_birth: values.date_of_birth,
					phone: values.phone,
					selfie_file: values.selfie_file,
				};
				frappe.call({
					method: "edgepayv1.edgepay.services.identity_verification_api.create_identity_session",
					args: safeSessionArgs,
					callback(created) {
						const session = created.message && created.message.session;
						if (!session) return;
						frappe.call({
							method: "edgepayv1.edgepay.services.identity_verification_api.submit_identity_values",
							args: {
								session_name: session,
								nin: values.nin,
								bvn: values.bvn,
								bvn_consent_token: values.bvn_consent_token,
							},
							callback(result) {
								dialog.hide();
								frappe.msgprint(
									__("Identity verification status: {0}", [
										(result.message || {}).status || __("Unknown"),
									])
								);
								refresh();
							},
						});
					},
				});
			},
		});
		dialog.show();
	}

	function renderNoContext() {
		const bootstrap = pageData.bootstrap || {};
		if (bootstrap.can_bootstrap) {
			const heading = bootstrap.merchant_count
				? __("Create or connect your merchant context")
				: __("Set up your first EdgePay merchant");
			const message = bootstrap.merchant_count
				? __("You have platform administration access but no merchant is assigned as your working context. Create a merchant here or assign yourself to an existing merchant from administration.")
				: __("Create the first merchant to begin onboarding. This creates a Draft merchant and primary business account; live payments remain blocked until verification is complete.");
			root.innerHTML = `
				<section class="card"><div class="card-body p-4">
					<div class="d-flex justify-content-between align-items-start gap-3 flex-wrap">
						<div><h3 class="mb-2">${esc(heading)}</h3><p class="text-muted mb-0">${esc(message)}</p></div>
						<button class="btn btn-primary" id="edgepay-create-merchant">${esc(__("Create Merchant"))}</button>
					</div>
					<div class="alert alert-info mt-4 mb-0">${esc(__("Merchant activation and live payments are not enabled by this action. KYC and merchant verification are still required."))}</div>
				</div></section>`;
			root.querySelector("#edgepay-create-merchant")?.addEventListener("click", openCreateMerchantDialog);
			return;
		}
		root.innerHTML = `
			<section class="card"><div class="card-body p-4">
				<h3 class="mb-2">${esc(__("No Merchant Context"))}</h3>
				<p class="text-muted mb-0">${esc(__("Ask an EdgePay administrator to add you to a merchant before using merchant payment operations."))}</p>
			</div></section>`;
	}

	function render() {
		if (!pageData.merchant) {
			renderNoContext();
			return;
		}
		const merchant = pageData.merchant;
		const readiness = pageData.readiness || {};
		const checks = (readiness.checks || [])
			.map(
				(check) =>
					`<li class="list-group-item d-flex justify-content-between align-items-center"><span>${esc(check.label)}</span><span class="indicator-pill ${check.complete ? "green" : "orange"}">${esc(check.complete ? __("Complete") : __("Pending"))}</span></li>`
			)
			.join("");
		const providers =
			(pageData.provider_accounts || [])
				.map(
					(row) =>
						`<div class="border rounded p-3 mb-2"><strong>${esc(row.name)}</strong><div class="text-muted small">${esc(row.provider || "")} · ${esc(row.environment || "")} · ${esc(row.status || "")}</div></div>`
				)
				.join("") || `<div class="text-muted">${esc(__("No provider accounts configured yet."))}</div>`;
		root.innerHTML = `
			<div class="d-flex justify-content-between align-items-start gap-3 flex-wrap mb-4">
				<div><h2 class="mb-1">${esc(merchant.merchant_name || merchant.name)}</h2><p class="text-muted mb-0">${esc(__("Complete merchant identity, verification and provider readiness."))}</p></div>
				<a class="btn btn-default btn-sm" href="/app/edgepay-home">${esc(__("Back to EdgePay Home"))}</a>
			</div>
			<div class="row mb-4">
				<div class="col-md-4 mb-3"><div class="card h-100"><div class="card-body"><div class="text-muted small">${esc(__("Onboarding"))}</div><strong>${esc(merchant.onboarding_status || "—")}</strong></div></div></div>
				<div class="col-md-4 mb-3"><div class="card h-100"><div class="card-body"><div class="text-muted small">${esc(__("Verification"))}</div><strong>${esc(merchant.verification_status || "—")}</strong></div></div></div>
				<div class="col-md-4 mb-3"><div class="card h-100"><div class="card-body"><div class="text-muted small">${esc(__("Live Payments"))}</div><strong>${esc(merchant.live_payments_allowed ? __("Allowed") : __("Not Allowed"))}</strong></div></div></div>
			</div>
			<section class="card mb-4"><div class="card-body"><div class="d-flex justify-content-between align-items-center gap-3 mb-3"><h4 class="mb-0">${esc(__("Onboarding Readiness"))}</h4><button class="btn btn-primary btn-sm" id="edgepay-verify-identity">${esc(__("Verify Representative Identity"))}</button></div><ul class="list-group list-group-flush">${checks}</ul></div></section>
			<section class="card"><div class="card-body"><h4>${esc(__("Provider Accounts"))}</h4>${providers}</div></section>`;
		root.querySelector("#edgepay-verify-identity")?.addEventListener("click", openIdentityDialog);
	}

	function refresh() {
		root.innerHTML = `<div class="text-center text-muted p-5">${esc(__("Loading merchant onboarding…"))}</div>`;
		frappe.call({
			method: "edgepayv1.edgepay.page.merchant_onboarding.merchant_onboarding.get_onboarding_page_data",
			callback(response) {
				pageData = response.message || {};
				render();
			},
			error(error) {
				root.innerHTML = `<div class="alert alert-danger">${esc(error?.message || String(error))}</div>`;
			},
		});
	}

	wrapper.edgepayOnboardingRefresh = refresh;
	refresh();
	frappe.require("edgesuite_ui.bundle.js", () => {});
}

frappe.pages["merchant-onboarding"].on_page_load = function (wrapper) {
	wrapper.page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Merchant Onboarding"),
		single_column: true,
	});
	edgepayMountMerchantOnboarding(wrapper);
};

frappe.pages["merchant-onboarding"].on_page_show = function (wrapper) {
	if (wrapper.edgepayOnboardingRefresh) {
		wrapper.edgepayOnboardingRefresh();
		return;
	}
	edgepayMountMerchantOnboarding(wrapper);
};
