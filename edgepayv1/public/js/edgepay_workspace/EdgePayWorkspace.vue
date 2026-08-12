<template>
	<EdgeAppShell
		product="edgepay"
		title="EdgePay"
		:tenant-name="merchantDisplayName"
		:branch-name="branchName"
		:user-name="userName"
		:active-route="activeRoute"
		@navigate="openRoute"
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

			<EdgeLoadingState v-if="loading" :message="`Loading ${pageTitle}...`" :skeleton="true" />
			<EdgeErrorState
				v-else-if="error"
				:title="`${pageTitle} could not load`"
				:message="error"
				action-label="Try again"
				@retry="load"
			/>

			<template v-else>
				<section v-if="!hasMerchantContext" class="edgepay-empty-card">
					<h2>{{ canBootstrap ? 'Set up EdgePay' : 'No Merchant Context' }}</h2>
					<p>
						{{
							canBootstrap
								? 'Create your merchant profile to begin onboarding. Live payments remain unavailable until verification is complete.'
								: 'Ask an EdgePay administrator to add you to an active merchant before using merchant payment operations.'
						}}
					</p>
					<button v-if="canBootstrap" type="button" class="edge-button edge-button--primary" @click="openMerchantDialog">
						Create Merchant
					</button>
				</section>

				<template v-else-if="workspaceMode === 'home'">
					<section class="edgepay-summary-grid">
						<div v-for="card in homeCards" :key="card.label" class="edgepay-summary-card">
							<span>{{ card.label }}</span><strong>{{ card.value }}</strong>
						</div>
					</section>
					<section class="edgepay-panel">
						<header><div><h2>Merchant readiness</h2><p>{{ home.readiness?.message || 'Review onboarding and live-payment readiness.' }}</p></div><strong>{{ home.readiness?.status || 'Unknown' }}</strong></header>
					<div class="edgepay-check-grid">
						<div v-for="check in home.readiness?.checks || []" :key="check.label" class="edgepay-check-row">
							<span>{{ check.label }}</span><strong>{{ check.complete ? 'Complete' : 'Pending' }}</strong>
						</div>
					</div>
					</section>
					<section class="edgepay-panel">
						<header><div><h2>Recent payment requests</h2><p>Latest merchant-scoped payment activity.</p></div></header>
					<EdgeDataTable :columns="paymentColumns" :rows="home.recent_requests || []" empty-title="No payment requests" empty-description="Payment requests will appear here when they are created." @row-click="openPaymentRequest" />
					</section>
				</template>

				<template v-else-if="workspaceMode === 'onboarding'">
					<section class="edgepay-summary-grid">
						<div class="edgepay-summary-card"><span>Onboarding</span><strong>{{ onboarding.merchant?.onboarding_status || '—' }}</strong></div>
						<div class="edgepay-summary-card"><span>Verification</span><strong>{{ onboarding.merchant?.verification_status || '—' }}</strong></div>
						<div class="edgepay-summary-card"><span>Live Payments</span><strong>{{ onboarding.merchant?.live_payments_allowed ? 'Allowed' : 'Not Allowed' }}</strong></div>
					</section>
					<section class="edgepay-panel">
						<header><div><h2>Onboarding readiness</h2><p>Complete merchant identity, verification and provider readiness.</p></div></header>
					<div class="edgepay-check-grid">
						<div v-for="check in onboarding.readiness?.checks || []" :key="check.label" class="edgepay-check-row">
							<span>{{ check.label }}</span><strong>{{ check.complete ? 'Complete' : 'Pending' }}</strong>
						</div>
					</div>
					</section>
					<section class="edgepay-panel">
						<header><div><h2>Provider accounts</h2><p>Merchant-specific payment rail configuration.</p></div></header>
					<EdgeDataTable :columns="providerColumns" :rows="onboarding.provider_accounts || []" empty-title="No provider accounts" empty-description="Configure a sandbox provider account before payment lifecycle testing." />
					</section>
				</template>

				<template v-else-if="workspaceMode === 'payments'">
					<section class="edgepay-panel">
						<header><div><h2>Payment requests</h2><p>Amounts, payment position and customer references.</p></div></header>
					<EdgeDataTable :columns="paymentColumns" :rows="operations.requests || []" empty-title="No payment requests" empty-description="Create or receive a payment request to begin." @row-click="openPaymentRequest" />
					</section>
					<section class="edgepay-panel">
						<header><div><h2>Payment attempts</h2><p>Provider checkout attempts for this merchant.</p></div></header>
					<EdgeDataTable :columns="attemptColumns" :rows="operations.attempts || []" empty-title="No payment attempts" empty-description="Attempts appear after checkout initialization." />
					</section>
					<section class="edgepay-panel">
						<header><div><h2>Payment events</h2><p>Immutable payment lifecycle events.</p></div></header>
					<EdgeDataTable :columns="eventColumns" :rows="operations.events || []" empty-title="No payment events" empty-description="Lifecycle events will appear here." />
					</section>
				</template>

				<template v-else-if="workspaceMode === 'finance'">
					<section v-for="section in financeSections" :key="section.key" class="edgepay-panel">
						<header><div><h2>{{ section.title }}</h2><p>{{ section.description }}</p></div></header>
						<EdgeDataTable :columns="section.columns" :rows="finance[section.key] || []" :empty-title="`No ${section.title.toLowerCase()}`" empty-description="No matching records are available for this merchant." />
					</section>
				</template>

				<template v-else-if="workspaceMode === 'integrations'">
					<section v-for="section in integrationSections" :key="section.key" class="edgepay-panel">
						<header><div><h2>{{ section.title }}</h2><p>{{ section.description }}</p></div></header>
						<EdgeDataTable :columns="section.columns" :rows="integrations[section.key] || []" :empty-title="`No ${section.title.toLowerCase()}`" empty-description="No matching integration records are configured for this merchant." />
					</section>
				</template>
			</template>
		</EdgePageLayout>

		<EdgeModal :open="merchantDialog.open" title="Create EdgePay Merchant" subtitle="Create a Draft merchant profile. KYC and live-payment approval remain separate." :busy="merchantDialog.busy" size="lg" @close="closeMerchantDialog">
			<div class="edgepay-form-grid">
				<EdgeInput v-model="merchantDialog.values.merchant_name" label="Merchant / Trading Name" required />
				<EdgeInput v-model="merchantDialog.values.legal_name" label="Legal Business Name" required />
				<EdgeInput v-model="merchantDialog.values.email" type="email" label="Business Email" />
				<EdgeInput v-model="merchantDialog.values.phone" label="Business Phone" />
				<EdgeInput v-model="merchantDialog.values.country" label="Country" required />
				<EdgeInput v-model="merchantDialog.values.default_currency" label="Default Currency" required />
			</div>
			<template #footer>
				<button type="button" class="edge-button" :disabled="merchantDialog.busy" @click="closeMerchantDialog">Cancel</button>
				<button type="button" class="edge-button edge-button--primary" :disabled="merchantDialog.busy" @click="createMerchant">Create Merchant</button>
			</template>
		</EdgeModal>
	</EdgeAppShell>
</template>

<script>
const API = Object.freeze({
	home: 'edgepayv1.api.home.get_home_context',
	onboarding: 'edgepayv1.edgepay.page.merchant_onboarding.merchant_onboarding.get_onboarding_page_data',
	payments: 'edgepayv1.api.operations.get_payments_context',
	finance: 'edgepayv1.api.operations.get_finance_context',
	integrations: 'edgepayv1.api.operations.get_integrations_context',
	createMerchant: 'edgepayv1.edgepay.page.merchant_onboarding.merchant_onboarding.create_first_merchant',
});

const call = (method, args = {}) =>
	new Promise((resolve, reject) => {
		frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject });
	});

export default {
	name: 'EdgePayWorkspace',
	data() {
		return {
			workspaceMode: 'home',
			loading: true,
			error: '',
			home: {},
			onboarding: {},
			operations: {},
			finance: {},
			integrations: {},
			merchantDialog: {
				open: false,
				busy: false,
				values: { merchant_name: '', legal_name: '', email: '', phone: '', country: 'Nigeria', default_currency: 'NGN' },
			},
			paymentColumns: [
				{ key: 'request_reference', label: 'Reference' }, { key: 'customer_name', label: 'Customer' },
				{ key: 'amount', label: 'Amount' }, { key: 'paid_amount', label: 'Paid' },
				{ key: 'outstanding_amount', label: 'Outstanding' }, { key: 'currency', label: 'Currency' },
				{ key: 'status', label: 'Status', type: 'status' },
			],
			attemptColumns: [
				{ key: 'payment_request', label: 'Payment Request' }, { key: 'attempt_number', label: 'Attempt' },
				{ key: 'payment_method', label: 'Method' }, { key: 'provider_payment_reference', label: 'Provider Reference' },
				{ key: 'status', label: 'Status', type: 'status' }, { key: 'modified', label: 'Updated' },
			],
			eventColumns: [
				{ key: 'payment_request', label: 'Payment Request' }, { key: 'event_type', label: 'Event' },
				{ key: 'previous_status', label: 'From' }, { key: 'new_status', label: 'To', type: 'status' },
				{ key: 'event_source', label: 'Source' }, { key: 'occurred_on', label: 'Occurred' },
			],
			providerColumns: [
				{ key: 'provider', label: 'Provider' }, { key: 'name', label: 'Account' },
				{ key: 'environment', label: 'Environment' }, { key: 'status', label: 'Status', type: 'status' },
			],
		};
	},
	computed: {
		pageTitle() {
			return { home: 'EdgePay Home', onboarding: 'Merchant Onboarding', payments: 'Payments', finance: 'Financial Operations', integrations: 'Integrations' }[this.workspaceMode] || 'EdgePay';
		},
		pageSubtitle() {
			return {
				home: 'Merchant-scoped payment activity, readiness and operational health.',
				onboarding: 'Complete merchant identity, verification and provider readiness.',
				payments: 'Track payment requests, attempts and immutable payment events.',
				finance: 'Review refunds, settlements, disputes and chargebacks.',
				integrations: 'Review provider accounts, API clients and signed delivery health.',
			}[this.workspaceMode] || '';
		},
		activeRoute() { return `/app/${this.workspaceMode === 'onboarding' ? 'merchant-onboarding' : `edgepay-${this.workspaceMode}`}`; },
		userName() { return frappe.session?.user || ''; },
		currentData() { return { home: this.home, onboarding: this.onboarding, payments: this.operations, finance: this.finance, integrations: this.integrations }[this.workspaceMode] || {}; },
		hasMerchantContext() {
			if (this.workspaceMode === 'home') return Boolean(this.home.merchant?.visible || this.home.merchant_context?.merchant);
			if (this.workspaceMode === 'onboarding') return Boolean(this.onboarding.merchant);
			return Boolean(this.currentData.context_state?.has_context || this.currentData.merchant);
		},
		canBootstrap() {
			if (this.workspaceMode === 'home') return Boolean(this.home.merchant_context?.can_bootstrap);
			if (this.workspaceMode === 'onboarding') return Boolean(this.onboarding.bootstrap?.can_bootstrap);
			return Boolean(this.currentData.context_state?.can_bootstrap);
		},
		merchantDisplayName() {
			return this.home.merchant?.merchant_name || this.onboarding.merchant?.merchant_name || this.currentData.merchant || '';
		},
		branchName() { return this.home.merchant_context?.merchant_branch || ''; },
		homeCards() {
			const counts = this.home.request_counts || {};
			return [
				{ label: 'Paid', value: counts.Paid || 0 }, { label: 'Partly Paid', value: counts['Partly Paid'] || 0 },
				{ label: 'Initiated', value: counts.Initiated || 0 }, { label: 'Failed', value: counts.Failed || 0 },
			];
		},
		financeSections() {
			const common = [{ key: 'payment_request', label: 'Payment Request' }, { key: 'amount', label: 'Amount' }, { key: 'currency', label: 'Currency' }, { key: 'status', label: 'Status', type: 'status' }, { key: 'modified', label: 'Updated' }];
			return [
				{ key: 'refunds', title: 'Refunds', description: 'Merchant refund requests and status.', columns: common },
				{ key: 'settlements', title: 'Settlements', description: 'Provider settlement batches and net positions.', columns: [{ key: 'name', label: 'Batch' }, { key: 'provider_account', label: 'Provider Account' }, { key: 'gross_amount', label: 'Gross' }, { key: 'net_amount', label: 'Net' }, { key: 'currency', label: 'Currency' }, { key: 'status', label: 'Status', type: 'status' }] },
				{ key: 'disputes', title: 'Disputes', description: 'Payment disputes requiring review.', columns: common },
				{ key: 'chargebacks', title: 'Chargebacks', description: 'Chargeback exposure and resolution status.', columns: common },
			];
		},
		integrationSections() {
			return [
				{ key: 'provider_accounts', title: 'Provider Accounts', description: 'Merchant-specific payment rail connections.', columns: [{ key: 'provider', label: 'Provider' }, { key: 'account_label', label: 'Account' }, { key: 'environment', label: 'Environment' }, { key: 'status', label: 'Status', type: 'status' }, { key: 'enabled', label: 'Enabled' }] },
				{ key: 'api_clients', title: 'API Clients', description: 'Signed API integrations without exposing client secrets.', columns: [{ key: 'client_name', label: 'Client' }, { key: 'client_id', label: 'Client ID' }, { key: 'enabled', label: 'Enabled' }, { key: 'modified', label: 'Updated' }] },
				{ key: 'delivery_endpoints', title: 'Delivery Endpoints', description: 'Signed merchant event delivery destinations.', columns: [{ key: 'endpoint_name', label: 'Endpoint' }, { key: 'endpoint_url', label: 'URL' }, { key: 'enabled', label: 'Enabled' }, { key: 'modified', label: 'Updated' }] },
				{ key: 'deliveries', title: 'Delivery Health', description: 'Recent delivery attempts and dead-letter visibility.', columns: [{ key: 'event_type', label: 'Event' }, { key: 'status', label: 'Status', type: 'status' }, { key: 'attempt_count', label: 'Attempts' }, { key: 'next_attempt_on', label: 'Next Attempt' }, { key: 'modified', label: 'Updated' }] },
			];
		},
	},
	mounted() { this.load(); },
	methods: {
		openRoute(route) { if (route) frappe.set_route(String(route).replace(/^\/app\//, '')); },
		openPaymentRequest(row) { if (row?.name) frappe.set_route('Form', 'EdgePay Payment Request', row.name); },
		async load() {
			this.loading = true; this.error = '';
			try {
				const data = await call(API[this.workspaceMode]);
				if (this.workspaceMode === 'home') this.home = data;
				else if (this.workspaceMode === 'onboarding') this.onboarding = data;
				else if (this.workspaceMode === 'payments') this.operations = data;
				else if (this.workspaceMode === 'finance') this.finance = data;
				else if (this.workspaceMode === 'integrations') this.integrations = data;
			} catch (error) { this.error = error?.message || String(error); }
			finally { this.loading = false; }
		},
		openMerchantDialog() { this.merchantDialog.open = true; },
		closeMerchantDialog() { if (!this.merchantDialog.busy) this.merchantDialog.open = false; },
		async createMerchant() {
			const values = this.merchantDialog.values;
			if (!values.merchant_name || !values.legal_name || !values.country || !values.default_currency) {
				frappe.show_alert({ message: 'Complete the required merchant fields.', indicator: 'orange' }); return;
			}
			this.merchantDialog.busy = true;
			try {
				await call(API.createMerchant, values);
				this.merchantDialog.open = false;
				frappe.show_alert({ message: 'Merchant created. Continue onboarding and verification.', indicator: 'green' });
				await this.load();
			} catch (error) { frappe.msgprint(error?.message || String(error)); }
			finally { this.merchantDialog.busy = false; }
		},
	},
};
</script>

<style scoped>
.edgepay-summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-bottom: 1rem; }
.edgepay-summary-card, .edgepay-panel, .edgepay-empty-card { border: 1px solid var(--edge-border, #dbe3ec); border-radius: 14px; background: var(--edge-surface, #fff); padding: 1rem; }
.edgepay-summary-card span { display: block; color: var(--edge-muted, #667085); font-size: .82rem; margin-bottom: .35rem; }
.edgepay-summary-card strong { font-size: 1.35rem; }
.edgepay-panel { margin-bottom: 1rem; }
.edgepay-panel > header { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; margin-bottom: 1rem; }
.edgepay-panel h2, .edgepay-empty-card h2 { margin: 0 0 .25rem; font-size: 1.05rem; }
.edgepay-panel p, .edgepay-empty-card p { margin: 0; color: var(--edge-muted, #667085); }
.edgepay-check-grid { display: grid; gap: .6rem; }
.edgepay-check-row { display: flex; justify-content: space-between; gap: 1rem; padding: .75rem 0; border-top: 1px solid var(--edge-border, #eef2f6); }
.edgepay-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
@media (max-width: 720px) { .edgepay-form-grid { grid-template-columns: 1fr; } }
</style>
