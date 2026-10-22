<template>
	<section class="edgepay-operational-search">
		<div>
			<p class="edgepay-operational-search__eyebrow">Operational search</p>
			<h2>Find an EdgePay record</h2>
			<p>
				Search by exact EdgePay or provider reference, customer, status, or related
				operational context.
			</p>
		</div>
		<EdgeLinkField
			:model-value="selected"
			placeholder="Payment, provider reference, refund, settlement, dispute..."
			:searcher="searchOperations"
			@update:modelValue="selected = $event"
			@select="openResult"
			@clear="selected = ''"
		/>
	</section>
</template>

<script>
const DOCTYPE_BY_KIND = Object.freeze({
	"Payment Request": "EdgePay Payment Request",
	"Payment Attempt": "EdgePay Payment Attempt",
	"Payment Transaction": "EdgePay Payment Transaction",
	Refund: "EdgePay Refund Request",
	Settlement: "EdgePay Settlement Batch",
	Dispute: "EdgePay Dispute",
	Chargeback: "EdgePay Chargeback",
});

export default {
	name: "EdgePayOperationalSearch",
	data() {
		return { selected: "" };
	},
	methods: {
		async searchOperations(query) {
			const response = await frappe.call(
				"edgepayv1.api.operational_search.search_edgepay_operations",
				{ query: query || "", page_length: 20 }
			);
			return (response.message || []).map((row) => ({
				...row,
				label:
					row.reference && row.reference !== row.label
						? `${row.label} · ${row.reference}`
						: row.label,
				description: [row.kind, row.description].filter(Boolean).join(" · "),
			}));
		},
		openResult(row) {
			const doctype = DOCTYPE_BY_KIND[row?.kind];
			if (!doctype || !row?.value) return;
			this.selected = row.value;
			frappe.set_route("Form", doctype, row.value);
		},
	},
};
</script>

<style scoped>
.edgepay-operational-search {
	display: grid;
	grid-template-columns: minmax(0, 1fr) minmax(18rem, 30rem);
	align-items: end;
	gap: 1rem;
	margin-bottom: 1rem;
	padding: 1rem;
	border: 1px solid var(--border-color);
	border-radius: 12px;
	background: var(--card-bg);
}
.edgepay-operational-search h2,
.edgepay-operational-search p {
	margin: 0;
}
.edgepay-operational-search__eyebrow {
	font-size: 0.75rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.04em;
	color: var(--text-muted);
}
.edgepay-operational-search div > p:last-child {
	margin-top: 0.25rem;
	color: var(--text-muted);
}
@media (max-width: 760px) {
	.edgepay-operational-search {
		grid-template-columns: 1fr;
	}
}
</style>
