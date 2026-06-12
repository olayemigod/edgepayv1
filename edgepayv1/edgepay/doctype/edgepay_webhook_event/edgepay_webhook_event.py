# -*- coding: utf-8 -*-
# Copyright (c) 2026, ProcessEdge Solutions Limited and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

from frappe import _

class EdgePayWebhookEvent(Document):
	def validate(self):
		self.validate_provider()
		self.validate_status()
		self.validate_idempotency_key()
		self.validate_event_reference()

	def validate_idempotency_key(self):
		if self.idempotency_key:
			duplicate = frappe.db.get_value(
				"EdgePay Webhook Event",
				{
					"idempotency_key": self.idempotency_key,
					"processing_status": ["!=", "Failed"],
					"name": ["!=", self.name]
				},
				"name"
			)
			if duplicate:
				frappe.throw(_("An active Webhook Event with this Idempotency Key ({0}) already exists: {1}").format(self.idempotency_key, duplicate))

	def validate_event_reference(self):
		if self.event_reference:
			duplicate = frappe.db.get_value(
				"EdgePay Webhook Event",
				{
					"event_reference": self.event_reference,
					"processing_status": ["!=", "Failed"],
					"name": ["!=", self.name]
				},
				"name"
			)
			if duplicate:
				frappe.throw(_("An active Webhook Event with this Event Reference ({0}) already exists: {1}").format(self.event_reference, duplicate))

	def validate_provider(self):
		if not self.provider:
			frappe.throw(_("Provider is required"))

	def validate_status(self):
		allowed_statuses = ["Pending", "Processed", "Failed", "Ignored"]
		if self.processing_status not in allowed_statuses:
			frappe.throw(_("Processing Status must be one of: {0}").format(", ".join(allowed_statuses)))
