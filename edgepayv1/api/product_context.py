from __future__ import annotations

from edgepayv1.api.permission import has_app_permission

PRODUCT_DESCRIPTOR = {
	"key": "edgepay",
	"product_key": "edgepay",
	"label": "EdgePay",
	"product": "EdgePay",
	"icon": "wallet",
	"home_route": "/app/edgepay-home",
	"route_patterns": [
		"/app/edgepay*",
		"/app/merchant-onboarding*",
		"/app/query-report/EdgePay*",
	],
	"order": 40,
}


def get_product_availability() -> dict | None:
	"""Expose EdgePay only when the current user has final EdgePay access."""
	if not has_app_permission():
		return None
	return dict(PRODUCT_DESCRIPTOR)
