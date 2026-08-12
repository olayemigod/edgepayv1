# -*- coding: utf-8 -*-
from edgepayv1.edgepay.services.escrow import sync_from_payment_request


def sync_escrow_funding(doc, method=None):
	"""Frappe doc_event bridge for Payment Request funding changes."""
	sync_from_payment_request(doc.name)
