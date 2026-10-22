# -*- coding: utf-8 -*-
import secrets

import frappe
from frappe import _
from frappe.utils import now_datetime

from edgepayv1.edgepay.services.authorization import require_merchant_access
from edgepayv1.edgepay.services.deliveries import create_delivery


def rotate_endpoint_secret(endpoint_name):
	endpoint = frappe.get_doc("EdgePay Delivery Endpoint", endpoint_name)
	require_merchant_access(endpoint.merchant)
	secret = secrets.token_urlsafe(48)
	endpoint.secret = secret
	endpoint.save(ignore_permissions=True)
	return {"delivery_endpoint": endpoint.name, "secret": secret, "show_once": True, "rotated_on": now_datetime()}


def send_test_delivery(endpoint_name):
	endpoint = frappe.get_doc("EdgePay Delivery Endpoint", endpoint_name)
	require_merchant_access(endpoint.merchant)
	if not endpoint.enabled:
		frappe.throw(_("Delivery Endpoint is disabled"))
	created = create_delivery(endpoint.merchant, "endpoint.test", {"message": "EdgePay test delivery", "endpoint": endpoint.name})
	for delivery_name in created:
		delivery = frappe.get_doc("EdgePay Delivery", delivery_name)
		if delivery.delivery_endpoint == endpoint.name:
			frappe.enqueue("edgepayv1.edgepay.services.delivery_worker.deliver_one", queue="short", delivery_name=delivery.name)
			return {"delivery": delivery.name, "status": delivery.status}
	frappe.throw(_("Endpoint is not subscribed to endpoint.test; add it to Event Types or leave Event Types blank"))


@frappe.whitelist()
def rotate_delivery_endpoint_secret(endpoint_name):
	return rotate_endpoint_secret(endpoint_name)


@frappe.whitelist()
def test_delivery_endpoint(endpoint_name):
	return send_test_delivery(endpoint_name)
