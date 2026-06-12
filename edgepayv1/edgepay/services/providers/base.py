# -*- coding: utf-8 -*-

class BaseProvider(object):
	def __init__(self, provider_doc):
		self.provider_doc = provider_doc

	def validate_configuration(self):
		raise NotImplementedError

	def get_provider_code(self):
		return self.provider_doc.provider_code

	def get_base_url(self):
		return self.provider_doc.base_url

	def build_checkout_payload(self, payment_request):
		raise NotImplementedError

	def parse_checkout_response(self, response):
		raise NotImplementedError

	def build_verification_payload(self, reference):
		raise NotImplementedError

	def parse_verification_response(self, response):
		raise NotImplementedError

	def verify_webhook_signature(self, payload, headers):
		raise NotImplementedError

	def normalize_transaction_status(self, provider_status):
		raise NotImplementedError

	def parse_webhook_payload(self, payload):
		raise NotImplementedError

	def get_webhook_event_reference(self, payload):
		raise NotImplementedError

	def get_webhook_payment_reference(self, payload):
		raise NotImplementedError

	def get_webhook_transaction_reference(self, payload):
		raise NotImplementedError

