# -*- coding: utf-8 -*-
import json

import frappe
from frappe.utils import now_datetime
from frappe.utils.data import cint
from frappe.integrations.utils import make_post_request

from edgepayv1.edgepay.services.deliveries import mark_delivery_result
from edgepayv1.edgepay.services.security import redact_secrets


def deliver_one(delivery_name):
	delivery = frappe.get_doc("EdgePay Delivery", delivery_name)
	if delivery.status not in {"Pending", "Retry Scheduled"}:
		return delivery
	endpoint = frappe.get_doc("EdgePay Delivery Endpoint", delivery.delivery_endpoint)
	if not endpoint.enabled:
		return mark_delivery_result(delivery.name, error_message="Delivery endpoint is disabled")
	if delivery.next_attempt_on and delivery.next_attempt_on > now_datetime():
		return delivery

	delivery.status = "Processing"
	delivery.save(ignore_permissions=True)
	headers = {
		"Content-Type": "application/json",
		"X-EdgePay-Event-Id": delivery.event_id,
		"X-EdgePay-Event-Type": delivery.event_type,
		"X-EdgePay-Signature": delivery.signature,
	}
	try:
		response = make_post_request(
			endpoint.endpoint_url,
			headers=headers,
			data=delivery.payload_json,
			timeout=cint(endpoint.timeout_seconds or 15),
		)
		return mark_delivery_result(delivery.name, http_status=200, response_body=redact_secrets(response))
	except Exception as exc:
		status = getattr(getattr(exc, "response", None), "status_code", None)
		body = getattr(getattr(exc, "response", None), "text", None)
		return mark_delivery_result(delivery.name, http_status=status, response_body=body, error_message=str(exc))


def process_pending_deliveries(limit=50):
	rows = frappe.get_all(
		"EdgePay Delivery",
		filters={
			"status": ["in", ["Pending", "Retry Scheduled"]],
			"next_attempt_on": ["in", [None, ["<=", now_datetime()]]],
		},
		pluck="name",
		order_by="creation asc",
		limit=cint(limit or 50),
	)
	for name in rows:
		try:
			deliver_one(name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"EdgePay delivery worker failed: {name}")
	return len(rows)


def cleanup_expired_api_nonces():
	frappe.db.delete("EdgePay API Request Nonce", {"expires_on": ["<", now_datetime()]})
