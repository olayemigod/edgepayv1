# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
from datetime import timedelta

import frappe
from frappe.utils import now_datetime

from edgepayv1.edgepay.services.security import redact_secrets


def _sign(secret, payload):
	return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_delivery(merchant, event_type, payload, payment_request=None, payment_transaction=None):
	created = []
	for endpoint_name in frappe.get_all("EdgePay Delivery Endpoint", filters={"merchant": merchant, "enabled": 1}, pluck="name"):
		endpoint = frappe.get_doc("EdgePay Delivery Endpoint", endpoint_name)
		allowed = {x.strip() for x in (endpoint.event_types or "").split(",") if x.strip()}
		if allowed and event_type not in allowed:
			continue
		event_id = f"evt_{frappe.generate_hash(length=24)}"
		body = json.dumps({"schema_version": "1.0", "event_id": event_id, "event_type": event_type, "occurred_at": str(now_datetime()), "data": redact_secrets(payload)}, separators=(",", ":"), sort_keys=True)
		doc = frappe.new_doc("EdgePay Delivery")
		doc.merchant = merchant
		doc.delivery_endpoint = endpoint.name
		doc.event_id = event_id
		doc.event_type = event_type
		doc.payment_request = payment_request
		doc.payment_transaction = payment_transaction
		doc.status = "Pending"
		doc.payload_json = body
		doc.signature = _sign(endpoint.get_password("secret"), body)
		doc.created_on = now_datetime()
		doc.insert(ignore_permissions=True)
		created.append(doc.name)
	return created


def mark_delivery_result(delivery_name, http_status=None, response_body=None, error_message=None):
	delivery = frappe.get_doc("EdgePay Delivery", delivery_name)
	endpoint = frappe.get_doc("EdgePay Delivery Endpoint", delivery.delivery_endpoint)
	attempt_no = int(delivery.attempt_count or 0) + 1
	attempt = frappe.new_doc("EdgePay Delivery Attempt")
	attempt.merchant = delivery.merchant
	attempt.delivery = delivery.name
	attempt.attempt_number = attempt_no
	attempt.started_on = now_datetime()
	attempt.completed_on = now_datetime()
	attempt.http_status = http_status
	attempt.request_signature = delivery.signature
	attempt.response_body = json.dumps(redact_secrets(response_body or {})) if response_body is not None else None
	attempt.error_message = redact_secrets(error_message) if error_message else None
	attempt.insert(ignore_permissions=True)
	delivery.attempt_count = attempt_no
	delivery.last_http_status = http_status
	delivery.last_error = redact_secrets(error_message) if error_message else None
	if http_status and 200 <= int(http_status) < 300:
		delivery.status = "Delivered"
		delivery.delivered_on = now_datetime()
	elif attempt_no >= int(endpoint.max_attempts or 8):
		delivery.status = "Dead Letter"
	else:
		delivery.status = "Retry Scheduled"
		delivery.next_attempt_on = now_datetime() + timedelta(minutes=min(60, 2 ** attempt_no))
	delivery.save(ignore_permissions=True)
	return delivery
