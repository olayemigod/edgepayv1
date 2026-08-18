import frappe
from frappe import _

from edgepayv1.edgepay.services.authorization import require_merchant_access
from edgepayv1.edgepay.services.merchant_context import can_bootstrap_merchant, get_default_merchant_context
from edgepayv1.edgepay.services.merchant_onboarding import get_onboarding_readiness


def _require_bootstrap_access():
	if not can_bootstrap_merchant():
		frappe.throw(
			_("Only an EdgePay platform administrator can create a merchant from first-run onboarding."),
			frappe.PermissionError,
		)


def _bootstrap_state(context):
	return {
		"can_bootstrap": bool(context.get("can_bootstrap")),
		"has_context": bool(context.get("merchant")),
		"merchant_count": int(frappe.db.count("EdgePay Merchant") or 0)
		if context.get("can_bootstrap")
		else None,
	}


@frappe.whitelist()
def create_first_merchant(
	merchant_name: str,
	legal_name: str | None = None,
	email: str | None = None,
	phone: str | None = None,
	country: str = "Nigeria",
	default_currency: str = "NGN",
) -> dict:
	_require_bootstrap_access()
	merchant_name = (merchant_name or "").strip()
	legal_name = (legal_name or merchant_name).strip()
	if not merchant_name:
		frappe.throw(_("Merchant name is required."))
	if not legal_name:
		frappe.throw(_("Legal business name is required."))
	if not country:
		frappe.throw(_("Country is required."))
	if not default_currency:
		frappe.throw(_("Default currency is required."))

	if frappe.db.exists("EdgePay Merchant", {"merchant_name": merchant_name}):
		frappe.throw(_("A merchant with this name already exists."))

	user = frappe.session.user
	merchant = frappe.get_doc(
		{
			"doctype": "EdgePay Merchant",
			"merchant_name": merchant_name,
			"legal_name": legal_name,
			"trading_name": merchant_name,
			"email": email,
			"phone": phone,
			"country": country,
			"default_currency": default_currency,
			"status": "Draft",
			"onboarding_status": "In Progress",
		}
	).insert(ignore_permissions=True)

	account = frappe.get_doc(
		{
			"doctype": "EdgePay Merchant Account",
			"merchant": merchant.name,
			"account_name": "Primary Business",
			"account_type": "Primary Business",
			"status": "Active",
			"legal_name": legal_name,
			"default_currency": default_currency,
		}
	).insert(ignore_permissions=True)

	frappe.db.set_value("EdgePay Merchant User", {"user": user, "is_default": 1}, "is_default", 0)
	membership = frappe.get_doc(
		{
			"doctype": "EdgePay Merchant User",
			"merchant": merchant.name,
			"user": user,
			"merchant_role": "Owner",
			"active": 1,
			"is_default": 1,
		}
	).insert(ignore_permissions=True)

	return {
		"merchant": merchant.name,
		"merchant_account": account.name,
		"membership": membership.name,
		"status": merchant.status,
		"onboarding_status": merchant.onboarding_status,
	}


@frappe.whitelist()
def get_onboarding_page_data(merchant: str | None = None) -> dict:
	context = get_default_merchant_context()
	merchant = merchant or context.get("merchant")
	if not merchant:
		return {
			"merchant": None,
			"context": context,
			"bootstrap": _bootstrap_state(context),
			"readiness": None,
			"verification": None,
			"provider_accounts": [],
		}
	require_merchant_access(merchant)
	verification = frappe.db.get_value(
		"EdgePay Merchant Verification",
		{"merchant": merchant},
		["name", "status", "verification_type", "risk_rating", "modified"],
		as_dict=True,
		order_by="modified desc",
	)
	provider_accounts = frappe.get_all(
		"EdgePay Provider Account",
		filters={"merchant": merchant},
		fields=["name", "provider", "environment", "status", "enabled"],
		order_by="modified desc",
	)
	return {
		"merchant": frappe.get_value(
			"EdgePay Merchant",
			merchant,
			[
				"name",
				"merchant_name",
				"onboarding_status",
				"verification_status",
				"live_payments_allowed",
			],
			as_dict=True,
		),
		"context": context,
		"bootstrap": _bootstrap_state(context),
		"readiness": get_onboarding_readiness(merchant),
		"verification": verification,
		"provider_accounts": provider_accounts,
	}
