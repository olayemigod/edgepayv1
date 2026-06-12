# -*- coding: utf-8 -*-

class BaseSourceConnector(object):
	def validate_source_context(self, source_context):
		"""
		Validates the structure and content of a source context payload.
		Must throw frappe.ValidationError (or raise Exception) if invalid.
		"""
		raise NotImplementedError

	def build_payment_request_payload(self, source_context):
		"""
		Maps the source context payload to standard fields required for creating a Payment Request.
		Returns a dict.
		"""
		raise NotImplementedError

	def handle_payment_status_update(self, payment_request, transaction=None):
		"""
		Invoked when a Payment Request or Transaction status changes.
		Handles propagation/notification (e.g. via background tasks).
		"""
		raise NotImplementedError

	def get_safe_source_summary(self, source_context):
		"""
		Returns a safe/sanitized dictionary summary of the source for logging/public status.
		"""
		raise NotImplementedError
