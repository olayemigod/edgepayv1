# -*- coding: utf-8 -*-
import frappe
from frappe import _

class ConnectorProfile(object):
	def __init__(self, name, label, expected_fields):
		self.name = name
		self.label = label
		self.expected_fields = expected_fields

# Safe definition of connector profiles with validation hints/safe labels
# and expected source_context fields.
CONNECTOR_PROFILES = {
	"erpnext": ConnectorProfile(
		name="erpnext",
		label="ERPNext Integration Link",
		expected_fields=[
			"source_app", "source_doctype", "source_name", "amount", "currency",
			"customer_name", "customer_email", "customer_phone", "payment_purpose",
			"idempotency_key", "metadata"
		]
	),
	"posnext": ConnectorProfile(
		name="posnext",
		label="POSnext Retail Link",
		expected_fields=[
			"source_app", "source_doctype", "source_name", "amount", "currency",
			"customer_name", "customer_email", "customer_phone", "payment_purpose",
			"idempotency_key", "metadata"
		]
	),
	"retailedge": ConnectorProfile(
		name="retailedge",
		label="RetailEdge Store Link",
		expected_fields=[
			"source_app", "source_doctype", "source_name", "amount", "currency",
			"customer_name", "customer_email", "customer_phone", "payment_purpose",
			"idempotency_key", "metadata"
		]
	),
	"vetedge": ConnectorProfile(
		name="vetedge",
		label="VetEdge Clinical Link",
		expected_fields=[
			"source_app", "source_doctype", "source_name", "amount", "currency",
			"customer_name", "customer_email", "customer_phone", "payment_purpose",
			"idempotency_key", "metadata"
		]
	),
	"edgesuite": ConnectorProfile(
		name="edgesuite",
		label="EdgeSuite Suite Link",
		expected_fields=[
			"source_app", "source_doctype", "source_name", "amount", "currency",
			"customer_name", "customer_email", "customer_phone", "payment_purpose",
			"idempotency_key", "metadata"
		]
	)
}

def get_connector_profile(source_app):
	"""
	Retrieves the connector profile for a given source_app name.
	Falls back to a generic fallback profile if not known.
	"""
	app_lower = str(source_app).lower()
	if app_lower in CONNECTOR_PROFILES:
		return CONNECTOR_PROFILES[app_lower]
		
	# Fallback generic profile
	return ConnectorProfile(
		name="generic",
		label="Generic App Link",
		expected_fields=[
			"source_app", "source_doctype", "source_name", "amount", "currency",
			"customer_name", "customer_email"
		]
	)
