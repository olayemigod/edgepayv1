<template>
	<EdgeAppShell
		product="edgepay"
		title="EdgePay"
		:tenant-name="merchantName"
		:branch-name="branchName"
		:user-name="userName"
		:active-route="activeRoute"
		@navigate="navigate"
	>
		<EdgePageLayout>
			<template #header>
				<EdgePageHeader
					eyebrow="EdgePay"
					:title="pageTitle"
					:subtitle="pageSubtitle"
					action-label="Refresh"
					@action="load"
				/>
			</template>

			<EdgeLoadingState
				v-if="loading"
				:message="`Loading ${pageTitle}...`"
				:skeleton="true"
			/>
			<EdgeErrorState
				v-else-if="error"
				:title="`${pageTitle} could not load`"
				:message="error"
				action-label="Try again"
				@retry="load"
			/>

			<template v-else>
				<section v-if="!hasMerchant" class="edgepay-empty-card">
					<h2>{{ canBootstrap ? "Set up EdgePay" : "No Merchant Context" }}</h2>
					<p>
						{{
							canBootstrap
								? "Create your merchant profile to begin onboarding. Live payments remain blocked until verification is complete."
								: "Ask an EdgePay administrator to add you to a merchant before using payment operations."
						}}
					</p>
					<button
						v-if="canBootstrap"
						type="button"
						class="edge-button edge-button--primary"
						@click="merchantModal = true"
					>
						Create Merchant
					</button>
				</section>

				<template v-else-if="workspaceMode === 'home'">
					<section class="edgepay-summary-grid">
						<div
							v-for="card in homeCards"
							:key="card.label"
							class="edgepay-summary-card"
						>
							<span>{{ card.label }}</span
							><strong>{{ card.value }}</strong>
						</div>
					</section>
					<ReadinessPanel :readiness="home.readiness" />
					<DataPanel
						title="Recent Payment Requests"
						description="Latest merchant-scoped payment activity."
						:columns="paymentColumns"
						:rows="home.recent_requests || []"
						empty-title="No payment requests"
					/>
				</template>

				<template v-else-if="workspaceMode === 'onboarding'">
					<section class="edgepay-summary-grid">
						<SummaryCard
							label="Onboarding"
							:value="onboarding.merchant?.onboarding_status || '—'"
						/>
						<SummaryCard
							label="Verification"
							:value="onboarding.merchant?.verification_status || '—'"
						/>
						<SummaryCard
							label="Live Payments"
							:value="
								onboarding.merchant?.live_payments_allowed
									? 'Allowed'
									: 'Not Allowed'
							"
						/>
					</section>
					<section class="edgepay-panel">
						<header>
							<div>
								<h2>Onboarding Readiness</h2>
								<p>
									Complete merchant identity, verification and provider
									readiness.
								</p>
							</div>
							<button
								type="button"
								class="edge-button edge-button--primary"
								@click="openIdentityDialog"
							>
								Verify Representative Identity
							</button>
						</header>
						<div class="edgepay-check-grid">
							<div
								v-for="check in onboarding.readiness?.checks || []"
								:key="check.label"
								class="edgepay-check-row"
							>
								<span>{{ check.label }}</span
								><strong>{{ check.complete ? "Complete" : "Pending" }}</strong>
							</div>
						</div>
					</section>
					<DataPanel
						title="Provider Accounts"
						description="Merchant-specific payment rail connections."
						:columns="providerColumns"
						:rows="onboarding.provider_accounts || []"
						empty-title="No provider accounts"
					/>
				</template>

				<template v-else-if="workspaceMode === 'payments'">
					<DataPanel
						title="Payment Requests"
						description="Amounts, payment position and customer references."
						:columns="paymentColumns"
						:rows="operations.requests || []"
						empty-title="No payment requests"
					/>
					<DataPanel
						title="Payment Attempts"
						description="Provider checkout attempts for this merchant."
						:columns="attemptColumns"
						:rows="operations.attempts || []"
						empty-title="No payment attempts"
					/>
					<DataPanel
						title="Payment Events"
						description="Immutable payment lifecycle events."
						:columns="eventColumns"
						:rows="operations.events || []"
						empty-title="No payment events"
					/>
				</template>

				<template v-else-if="workspaceMode === 'finance'">
					<DataPanel
						v-for="section in financeSections"
						:key="section.key"
						:title="section.title"
						:description="section.description"
						:columns="section.columns"
						:rows="finance[section.key] || []"
						:empty-title="`No ${section.title.toLowerCase()}`"
					/>
				</template>

				<template v-else-if="workspaceMode === 'integrations'">
					<DataPanel
						v-for="section in integrationSections"
						:key="section.key"
						:title="section.title"
						:description="section.description"
						:columns="section.columns"
						:rows="integrations[section.key] || []"
						:empty-title="`No ${section.title.toLowerCase()}`"
					/>
				</template>
			</template>
		</EdgePageLayout>

		<EdgeModal
			:open="merchantModal"
			title="Create EdgePay Merchant"
			subtitle="Creates a Draft merchant. KYC and live-payment approval remain separate."
			:busy="merchantBusy"
			size="lg"
			@close="merchantModal = false"
		>
			<div class="edgepay-form-grid">
				<EdgeInput
					v-model="merchantForm.merchant_name"
					label="Merchant / Trading Name"
					required
				/>
				<EdgeInput
					v-model="merchantForm.legal_name"
					label="Legal Business Name"
					required
				/>
				<EdgeInput v-model="merchantForm.email" type="email" label="Business Email" />
				<EdgeInput v-model="merchantForm.phone" label="Business Phone" />
				<EdgeInput v-model="merchantForm.country" label="Country" required />
				<EdgeInput
					v-model="merchantForm.default_currency"
					label="Default Currency"
					required
				/>
			</div>
			<template #footer>
				<button
					type="button"
					class="edge-button"
					:disabled="merchantBusy"
					@click="merchantModal = false"
				>
					Cancel
				</button>
				<button
					type="button"
					class="edge-button edge-button--primary"
					:disabled="merchantBusy"
					@click="createMerchant"
				>
					Create Merchant
				</button>
			</template>
		</EdgeModal>
	</EdgeAppShell>
</template>

<script>
const API = Object.freeze({
	home: "edgepayv1.api.home.get_home_context",
	onboarding:
		"edgepayv1.edgepay.page.merchant_onboarding.merchant_onboarding.get_onboarding_page_data",
	payments: "edgepayv1.api.operations.get_payments_context",
	finance: "edgepayv1.api.operations.get_finance_context",
	integrations: "edgepayv1.api.operations.get_integrations_context",
	createMerchant:
		"edgepayv1.edgepay.page.merchant_onboarding.merchant_onboarding.create_first_merchant",
});

const call = (method, args = {}) =>
	new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: reject,
		});
	});

const SummaryCard = {
	props: { label: String, value: [String, Number] },
	template:
		'<div class="edgepay-summary-card"><span>{{ label }}</span><strong>{{ value }}</strong></div>',
};

const ReadinessPanel = {
	props: { readiness: Object },
	template: `<section class="edgepay-panel"><header><div><h2>Merchant Readiness</h2><p>{{ readiness?.message || "Review onboarding and payment readiness." }}</p></div><strong>{{ readiness?.status || "Unknown" }}</strong></header><div class="edgepay-check-grid"><div v-for="check in readiness?.checks || []" :key="check.label" class="edgepay-check-row"><span>{{ check.label }}</span><strong>{{ check.complete ? "Complete" : "Pending" }}</strong></div></div></section>`,
};

const DataPanel = {
	components: {},
	props: { title: String, description: String, columns: Array, rows: Array, emptyTitle: String },
	template: `<section class="edgepay-panel"><header><div><h2>{{ title }}</h2><p>{{ description }}</p></div></header><EdgeDataTable :columns="columns" :rows="rows" :empty-title="emptyTitle" empty-description="No matching records are available for this merchant." /></section>`,
};

export default {
	name: "EdgePayWorkspaceShell",
	components: { SummaryCard, ReadinessPanel, DataPanel },
	data() {
		return {
			workspaceMode: "home",
			loading: true,
			error: "",
			home: {},
			onboarding: {},
			operations: {},
			finance: {},
			integrations: {},
			merchantModal: false,
			merchantBusy: false,
			merchantForm: {
				merchant_name: "",
				legal_name: "",
				email: "",
				phone: "",
				country: "Nigeria",
				default_currency: "NGN",
			},
			paymentColumns: [
				{ key: "request_reference", label: "Reference" },
				{ key: "customer_name", label: "Customer" },
				{ key: "amount", label: "Amount" },
				{ key: "paid_amount", label: "Paid" },
				{ key: "outstanding_amount", label: "Outstanding" },
				{ key: "currency", label: "Currency" },
				{ key: "status", label: "Status", type: "status" },
			],
			attemptColumns: [
				{ key: "payment_request", label: "Payment Request" },
				{ key: "attempt_number", label: "Attempt" },
				{ key: "payment_method", label: "Method" },
				{ key: "provider_payment_reference", label: "Provider Reference" },
				{ key: "status", label: "Status", type: "status" },
				{ key: "modified", label: "Updated" },
			],
			eventColumns: [
				{ key: "payment_request", label: "Payment Request" },
				{ key: "event_type", label: "Event" },
				{ key: "previous_status", label: "From" },
				{ key: "new_status", label: "To", type: "status" },
				{ key: "event_source", label: "Source" },
				{ key: "occurred_on", label: "Occurred" },
			],
			providerColumns: [
				{ key: "provider", label: "Provider" },
				{ key: "name", label: "Account" },
				{ key: "environment", label: "Environment" },
				{ key: "status", label: "Status", type: "status" },
			],
		};
	},
	computed: {
		pageTitle() {
			return (
				{
					home: "EdgePay Home",
					onboarding: "Merchant Onboarding",
					payments: "Payments",
					finance: "Financial Operations",
					integrations: "Integrations",
				}[this.workspaceMode] || "EdgePay"
			);
		},
		pageSubtitle() {
			return (
				{
					home: "Merchant-scoped payment activity, readiness and operational health.",
					onboarding: "Complete merchant identity, verification and provider readiness.",
					payments: "Track payment requests, attempts and immutable payment events.",
					finance: "Review refunds, settlements, disputes and chargebacks.",
					integrations:
						"Review provider accounts, API clients and signed delivery health.",
				}[this.workspaceMode] || ""
			);
		},
		activeRoute() {
			return `/app/${
				this.workspaceMode === "onboarding"
					? "merchant-onboarding"
					: `edgepay-${this.workspaceMode}`
			}`;
		},
		userName() {
			return frappe.session?.user || "";
		},
		currentData() {
			return (
				{
					home: this.home,
					onboarding: this.onboarding,
					payments: this.operations,
					finance: this.finance,
					integrations: this.integrations,
				}[this.workspaceMode] || {}
			);
		},
		hasMerchant() {
			if (this.workspaceMode === "home") return Boolean(this.home.merchant?.visible);
			if (this.workspaceMode === "onboarding") return Boolean(this.onboarding.merchant);
			return Boolean(
				this.currentData.context_state?.has_context || this.currentData.merchant
			);
		},
		canBootstrap() {
			if (this.workspaceMode === "home")
				return Boolean(this.home.merchant_context?.can_bootstrap);
			if (this.workspaceMode === "onboarding")
				return Boolean(this.onboarding.bootstrap?.can_bootstrap);
			return Boolean(this.currentData.context_state?.can_bootstrap);
		},
		merchantName() {
			return (
				this.home.merchant?.merchant_name ||
				this.onboarding.merchant?.merchant_name ||
				this.currentData.merchant ||
				""
			);
		},
		branchName() {
			return this.home.merchant_context?.merchant_branch || "";
		},
		homeCards() {
			const c = this.home.request_counts || {};
			return [
				{ label: "Paid", value: c.Paid || 0 },
				{ label: "Partly Paid", value: c["Partly Paid"] || 0 },
				{ label: "Initiated", value: c.Initiated || 0 },
				{ label: "Failed", value: c.Failed || 0 },
			];
		},
		financeSections() {
			const common = [
				{ key: "payment_request", label: "Payment Request" },
				{ key: "amount", label: "Amount" },
				{ key: "currency", label: "Currency" },
				{ key: "status", label: "Status", type: "status" },
				{ key: "modified", label: "Updated" },
			];
			return [
				{
					key: "refunds",
					title: "Refunds",
					description: "Merchant refund requests and status.",
					columns: common,
				},
				{
					key: "settlements",
					title: "Settlements",
					description: "Provider settlement batches and net positions.",
					columns: [
						{ key: "name", label: "Batch" },
						{ key: "provider_account", label: "Provider Account" },
						{ key: "gross_amount", label: "Gross" },
						{ key: "net_amount", label: "Net" },
						{ key: "currency", label: "Currency" },
						{ key: "status", label: "Status", type: "status" },
					],
				},
				{
					key: "disputes",
					title: "Disputes",
					description: "Payment disputes requiring review.",
					columns: common,
				},
				{
					key: "chargebacks",
					title: "Chargebacks",
					description: "Chargeback exposure and resolution status.",
					columns: common,
				},
			];
		},
		integrationSections() {
			return [
				{
					key: "provider_accounts",
					title: "Provider Accounts",
					description: "Merchant-specific payment rail connections.",
					columns: [
						{ key: "provider", label: "Provider" },
						{ key: "account_label", label: "Account" },
						{ key: "environment", label: "Environment" },
						{ key: "status", label: "Status", type: "status" },
						{ key: "enabled", label: "Enabled" },
					],
				},
				{
					key: "api_clients",
					title: "API Clients",
					description: "Signed API integrations without exposing client secrets.",
					columns: [
						{ key: "client_name", label: "Client" },
						{ key: "client_id", label: "Client ID" },
						{ key: "enabled", label: "Enabled" },
						{ key: "modified", label: "Updated" },
					],
				},
				{
					key: "delivery_endpoints",
					title: "Delivery Endpoints",
					description: "Signed merchant event delivery destinations.",
					columns: [
						{ key: "endpoint_name", label: "Endpoint" },
						{ key: "endpoint_url", label: "URL" },
						{ key: "enabled", label: "Enabled" },
						{ key: "modified", label: "Updated" },
					],
				},
				{
					key: "deliveries",
					title: "Delivery Health",
					description: "Recent delivery attempts and dead-letter visibility.",
					columns: [
						{ key: "event_type", label: "Event" },
						{ key: "status", label: "Status", type: "status" },
						{ key: "attempt_count", label: "Attempts" },
						{ key: "next_attempt_on", label: "Next Attempt" },
						{ key: "modified", label: "Updated" },
					],
				},
			];
		},
	},
	mounted() {
		this.load();
	},
	methods: {
		navigate(route) {
			if (route) frappe.set_route(String(route).replace(/^\/app\//, ""));
		},
		async load() {
			this.loading = true;
			this.error = "";
			try {
				const data = await call(API[this.workspaceMode]);
				if (this.workspaceMode === "home") this.home = data;
				else if (this.workspaceMode === "onboarding") this.onboarding = data;
				else if (this.workspaceMode === "payments") this.operations = data;
				else if (this.workspaceMode === "finance") this.finance = data;
				else if (this.workspaceMode === "integrations") this.integrations = data;
			} catch (error) {
				this.error = error?.message || String(error);
			} finally {
				this.loading = false;
			}
		},
		async createMerchant() {
			const v = this.merchantForm;
			if (!v.merchant_name || !v.legal_name || !v.country || !v.default_currency) {
				frappe.show_alert({
					message: "Complete the required merchant fields.",
					indicator: "orange",
				});
				return;
			}
			this.merchantBusy = true;
			try {
				await call(API.createMerchant, v);
				this.merchantModal = false;
				frappe.show_alert({
					message: "Merchant created. Continue onboarding and verification.",
					indicator: "green",
				});
				await this.load();
			} catch (error) {
				frappe.msgprint(error?.message || String(error));
			} finally {
				this.merchantBusy = false;
			}
		},
		openIdentityDialog() {
			if (!this.onboarding.merchant) return;
			const dialog = new frappe.ui.Dialog({
				title: __("Representative Identity Verification"),
				fields: [
					{
						fieldname: "merchant_verification",
						fieldtype: "Link",
						options: "EdgePay Merchant Verification",
						label: __("Merchant Verification"),
						reqd: 1,
						get_query: () => ({
							filters: { merchant: this.onboarding.merchant.name },
						}),
					},
					{
						fieldname: "provider",
						fieldtype: "Link",
						options: "EdgePay Verification Provider",
						label: __("Verification Provider"),
						reqd: 1,
						get_query: () => ({ filters: { enabled: 1 } }),
					},
					{
						fieldname: "first_name",
						fieldtype: "Data",
						label: __("First Name"),
						reqd: 1,
					},
					{ fieldname: "middle_name", fieldtype: "Data", label: __("Middle Name") },
					{ fieldname: "last_name", fieldtype: "Data", label: __("Surname"), reqd: 1 },
					{
						fieldname: "date_of_birth",
						fieldtype: "Date",
						label: __("Date of Birth"),
						reqd: 1,
					},
					{ fieldname: "phone", fieldtype: "Data", label: __("Phone"), reqd: 1 },
					{
						fieldname: "selfie_file",
						fieldtype: "Attach Image",
						label: __("Live Selfie / Photo"),
						reqd: 1,
					},
					{
						fieldname: "consent",
						fieldtype: "Check",
						label: __(
							"I consent to NIN, BVN, DOB, liveness and face verification for merchant onboarding."
						),
						reqd: 1,
					},
					{ fieldname: "nin", fieldtype: "Password", label: __("NIN"), reqd: 1 },
					{ fieldname: "bvn", fieldtype: "Password", label: __("BVN"), reqd: 1 },
					{
						fieldname: "bvn_consent_token",
						fieldtype: "Password",
						label: __("BVN Consent Token"),
						reqd: 1,
					},
				],
				primary_action_label: __("Verify Identity"),
				primary_action: (values) => {
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
						callback: (created) => {
							const session = created.message?.session;
							if (!session) return;
							frappe.call({
								method: "edgepayv1.edgepay.services.identity_verification_api.submit_identity_values",
								args: {
									session_name: session,
									nin: values.nin,
									bvn: values.bvn,
									bvn_consent_token: values.bvn_consent_token,
								},
								callback: (result) => {
									dialog.hide();
									frappe.msgprint(
										__("Identity verification status: {0}", [
											(result.message || {}).status || __("Unknown"),
										])
									);
									this.load();
								},
							});
						},
					});
				},
			});
			dialog.show();
		},
	},
};
</script>

<style scoped>
.edgepay-summary-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
	gap: 1rem;
	margin-bottom: 1rem;
}
.edgepay-summary-card,
.edgepay-panel,
.edgepay-empty-card {
	border: 1px solid var(--edge-border, #dbe3ec);
	border-radius: 14px;
	background: var(--edge-surface, #fff);
	padding: 1rem;
}
.edgepay-summary-card span {
	display: block;
	color: var(--edge-muted, #667085);
	font-size: 0.82rem;
	margin-bottom: 0.35rem;
}
.edgepay-summary-card strong {
	font-size: 1.35rem;
}
.edgepay-panel {
	margin-bottom: 1rem;
}
.edgepay-panel > header {
	display: flex;
	justify-content: space-between;
	gap: 1rem;
	align-items: flex-start;
	margin-bottom: 1rem;
	flex-wrap: wrap;
}
.edgepay-panel h2,
.edgepay-empty-card h2 {
	margin: 0 0 0.25rem;
	font-size: 1.05rem;
}
.edgepay-panel p,
.edgepay-empty-card p {
	margin: 0;
	color: var(--edge-muted, #667085);
}
.edgepay-check-grid {
	display: grid;
	gap: 0.6rem;
}
.edgepay-check-row {
	display: flex;
	justify-content: space-between;
	gap: 1rem;
	padding: 0.75rem 0;
	border-top: 1px solid var(--edge-border, #eef2f6);
}
.edgepay-form-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 1rem;
}
@media (max-width: 720px) {
	.edgepay-form-grid {
		grid-template-columns: 1fr;
	}
}
</style>
