# -*- coding: utf-8 -*-
from pathlib import Path


def test_delivery_worker_and_scheduler_registered():
	root = Path(__file__).resolve().parents[2]
	assert (root / "edgepay/services/delivery_worker.py").exists()
	hooks = (root / "hooks.py").read_text()
	assert "process_pending_deliveries" in hooks
	assert "cleanup_expired_api_nonces" in hooks


def test_payment_and_handoff_events_enqueue_delivery():
	root = Path(__file__).resolve().parents[2]
	payment_state = (root / "edgepay/services/payment_state.py").read_text()
	handoff = (root / "edgepay/services/handoff.py").read_text()
	assert "create_delivery" in payment_state
	assert "create_delivery" in handoff


def test_connector_and_coreedge_contracts_exist():
	root = Path(__file__).resolve().parents[2]
	connector = (root / "edgepay/services/connectors/v2.py").read_text()
	provisioning = (root / "edgepay/services/coreedge_provisioning.py").read_text()
	for name in ["GenericERPNextConnectorV2", "RetailEdgeConnectorV2", "VetEdgeConnectorV2", "EduEdgeConnectorV2"]:
		assert name in connector
	assert "EdgeSuite Free" in provisioning
	assert "external_tenant_reference" in provisioning


def test_endpoint_operations_and_docs_exist():
	root = Path(__file__).resolve().parents[2]
	ops = (root / "edgepay/services/delivery_endpoints.py").read_text()
	assert "rotate_delivery_endpoint_secret" in ops
	assert "test_delivery_endpoint" in ops
	assert (root.parent / "docs/api_v1_and_connectors.md").exists()
