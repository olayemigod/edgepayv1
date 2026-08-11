# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod

import frappe
from frappe import _


class EdgePayConnectorV2(ABC):
	connector_code = "generic"
	schema_version = "1.0"

	@abstractmethod
	def build_payment_request_payload(self, source_doc):
		raise NotImplementedError

	@abstractmethod
	def apply_payment_event(self, payload):
		"""Apply a normalized EdgePay event in the consuming product.

		Implementations must preserve ERPNext accounting truth and must never mutate
		submitted accounting documents. They should create or allocate safe accounting
		documents inside the consuming product only.
		"""
		raise NotImplementedError

	def validate_payload(self, payload):
		required = {"schema_version", "event_id", "event_type", "data"}
		missing = required.difference(payload or {})
		if missing:
			frappe.throw(_("Connector payload is missing: {0}").format(", ".join(sorted(missing))))
		return True


class GenericERPNextConnectorV2(EdgePayConnectorV2):
	connector_code = "erpnext"

	def build_payment_request_payload(self, source_doc):
		return {
			"source_app": "ERPNext",
			"source_doctype": source_doc.doctype,
			"source_name": source_doc.name,
			"amount": source_doc.outstanding_amount,
			"currency": source_doc.currency,
			"customer_name": source_doc.customer_name,
			"customer_email": getattr(source_doc, "contact_email", None),
			"payment_purpose": f"Payment for {source_doc.doctype} {source_doc.name}",
		}

	def apply_payment_event(self, payload):
		self.validate_payload(payload)
		return {"accepted": True, "action": "consumer_accounting_required", "connector": self.connector_code}


class RetailEdgeConnectorV2(GenericERPNextConnectorV2):
	connector_code = "retailedge"


class VetEdgeConnectorV2(GenericERPNextConnectorV2):
	connector_code = "vetedge"


class EduEdgeConnectorV2(GenericERPNextConnectorV2):
	connector_code = "eduedge"


CONNECTORS = {
	"erpnext": GenericERPNextConnectorV2,
	"retailedge": RetailEdgeConnectorV2,
	"vetedge": VetEdgeConnectorV2,
	"eduedge": EduEdgeConnectorV2,
}


def get_connector_v2(code):
	cls = CONNECTORS.get(str(code or "").lower())
	if not cls:
		frappe.throw(_("Unsupported EdgePay connector: {0}").format(code))
	return cls()
