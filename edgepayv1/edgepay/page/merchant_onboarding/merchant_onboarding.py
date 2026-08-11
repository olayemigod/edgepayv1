# -*- coding: utf-8 -*-
import frappe

from edgepayv1.edgepay.services.authorization import require_merchant_access
from edgepayv1.edgepay.services.merchant_context import get_default_merchant_context
from edgepayv1.edgepay.services.merchant_onboarding import get_onboarding_readiness


@frappe.whitelist()
def get_onboarding_page_data(merchant=None):
	context = get_default_merchant_context()
	merchant = merchant or context.get("merchant")
	if not merchant:
		return {"merchant": None, "context": context, "readiness": None, "verification": None, "provider_accounts": []}
	require_merchant_access(merchant)
	verification = frappe.db.get_value(
		"EdgePay Merchant Verification", {"merchant": merchant},
		["name", "status", "verification_type", "risk_rating", "modified"], as_dict=True,
		order_by="modified desc",
	)
	provider_accounts = frappe.get_all(
		"EdgePay Provider Account", filters={"merchant": merchant},
		fields=["name", "provider", "environment", "status", "enabled"], order_by="modified desc",
	)
	return {
		"merchant": frappe.get_value("EdgePay Merchant", merchant, ["name", "merchant_name", "onboarding_status", "verification_status", "live_payments_allowed"], as_dict=True),
		"context": context,
		"readiness": get_onboarding_readiness(merchant),
		"verification": verification,
		"provider_accounts": provider_accounts,
	}
