import frappe
from frappe.tests.utils import FrappeTestCase

from edgepayv1.edgepay.services.escrow_adapters import normalize_escrow_payload


class TestEscrowAdapters(FrappeTestCase):
	def test_agricedge_contract_is_normalized_without_losing_source_fields(self):
		payload = {
			"trade_id": "AGT-0001",
			"buyer_id": "BUY-1",
			"buyer_name": "Buyer One",
			"buyer_email": "buyer@example.com",
			"buyer_phone": "+2348000000000",
			"seller_id": "SELL-1",
			"seller_name": "Farm One",
			"amount": "125000",
			"provider": "Monnify",
			"currency": "ngn",
			"commodity": "Maize",
			"quantity": 50,
			"transport_reference": "TRN-9",
			"delivery_evidence_required": True,
		}
		normalized = normalize_escrow_payload("AgricEdge", payload)
		self.assertEqual(normalized["source_app"], "AgricEdge")
		self.assertEqual(normalized["external_trade_reference"], "AGT-0001")
		self.assertEqual(normalized["beneficiary_reference"], "SELL-1")
		self.assertEqual(normalized["currency"], "NGN")
		self.assertEqual(normalized["source_payload"]["commodity"], "Maize")
		self.assertEqual(normalized["source_payload"]["transport_reference"], "TRN-9")
		self.assertTrue(normalized["source_payload"]["delivery_evidence_required"])

	def test_agricedge_defaults_to_buyer_acceptance_release(self):
		normalized = normalize_escrow_payload(
			"AgricEdge",
			{
				"trade_id": "AGT-0002",
				"buyer_id": "BUY-2",
				"buyer_name": "Buyer Two",
				"buyer_email": "buyer2@example.com",
				"seller_id": "SELL-2",
				"amount": 5000,
				"provider": "Monnify",
			},
		)
		self.assertEqual(normalized["release_policy"], "Buyer Acceptance")
		self.assertEqual(normalized["idempotency_key"], "AgricEdge:Trade:AGT-0002:escrow")

	def test_same_buyer_and_seller_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			normalize_escrow_payload(
				"AgricEdge",
				{
					"trade_id": "AGT-0003",
					"buyer_id": "PARTY-1",
					"buyer_name": "Party",
					"buyer_email": "party@example.com",
					"seller_id": "PARTY-1",
					"amount": 5000,
					"provider": "Monnify",
				},
			)

	def test_generic_adapter_supports_non_agricedge_clients(self):
		normalized = normalize_escrow_payload(
			"generic",
			{
				"source_app": "Partner Marketplace",
				"source_name": "ORDER-77",
				"buyer_reference": "CUSTOMER-1",
				"buyer_name": "Customer One",
				"buyer_email": "customer@example.com",
				"beneficiary_reference": "VENDOR-9",
				"amount": 25000,
				"provider": "Monnify",
			},
		)
		self.assertEqual(normalized["source_app"], "Partner Marketplace")
		self.assertEqual(normalized["release_policy"], "Manual Approval")
