"""Provider-agnostic contracts for refunds, payouts, and settlement operations."""

import frappe
from frappe import _


class BaseProviderFinancialAdapter:
	def submit_refund(self, refund_request):
		raise NotImplementedError

	def query_refund(self, refund_request):
		raise NotImplementedError

	def submit_payout(self, payout_attempt, escrow_agreement):
		raise NotImplementedError

	def query_payout(self, payout_attempt, escrow_agreement):
		raise NotImplementedError

	def fetch_settlement(self, provider_account, settlement_reference):
		raise NotImplementedError


class SandboxProviderFinancialAdapter(BaseProviderFinancialAdapter):
	"""Deterministic non-live adapter for workflow and failure-path QA."""

	def submit_refund(self, refund_request):
		return {
			"status": "Processing",
			"provider_refund_reference": f"SBX-RFD-{refund_request.name}",
		}

	def query_refund(self, refund_request):
		return {
			"status": "Completed",
			"provider_refund_reference": refund_request.provider_refund_reference,
		}

	def submit_payout(self, payout_attempt, escrow_agreement):
		return {
			"status": "Processing",
			"provider_payout_reference": f"SBX-PAYOUT-{payout_attempt.name}",
			"escrow_reference": escrow_agreement.agreement_reference,
		}

	def query_payout(self, payout_attempt, escrow_agreement):
		return {
			"status": "Completed",
			"provider_payout_reference": payout_attempt.provider_reference,
			"escrow_reference": escrow_agreement.agreement_reference,
		}

	def fetch_settlement(self, provider_account, settlement_reference):
		return {"status": "Settled", "settlement_reference": settlement_reference}


def get_financial_adapter(provider_account_name):
	account = frappe.get_doc("EdgePay Provider Account", provider_account_name)
	adapter_path = getattr(account, "financial_adapter", None)
	if adapter_path:
		adapter_class = frappe.get_attr(adapter_path)
		return adapter_class(account)
	if account.environment == "Sandbox":
		return SandboxProviderFinancialAdapter()
	frappe.throw(_("No live financial adapter is configured for Provider Account {0}").format(account.name))
