# -*- coding: utf-8 -*-
import re

import frappe
from frappe import _
from frappe.utils import flt, get_datetime, now_datetime

from edgepayv1.edgepay.services.checkout import initialize_checkout
from edgepayv1.edgepay.services.payment_requests import create_payment_request_record

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _get_active_link(public_slug):
	name = frappe.db.get_value("EdgePay Payment Link", {"public_slug": public_slug}, "name")
	if not name:
		frappe.throw(_("Payment Link not found"))
	link = frappe.get_doc("EdgePay Payment Link", name)
	if link.status != "Active":
		frappe.throw(_("Payment Link is not active"))
	if link.expires_on and get_datetime(link.expires_on) <= now_datetime():
		link.db_set("status", "Expired", update_modified=False)
		frappe.throw(_("Payment Link has expired"))
	provider_account = frappe.get_doc("EdgePay Provider Account", link.provider_account)
	if not provider_account.enabled or provider_account.status != "Active":
		frappe.throw(_("Payment provider is temporarily unavailable"))
	return link, provider_account


def _resolve_amount(link, customer_amount=None):
	if link.amount_mode == "Fixed":
		return flt(link.amount)
	amount = flt(customer_amount)
	if amount <= 0:
		frappe.throw(_("Enter an amount greater than zero"))
	if link.minimum_amount and amount < flt(link.minimum_amount):
		frappe.throw(_("Amount is below the minimum allowed"))
	if link.maximum_amount and amount > flt(link.maximum_amount):
		frappe.throw(_("Amount exceeds the maximum allowed"))
	return amount


def public_link_context(public_slug):
	link, account = _get_active_link(public_slug)
	merchant = frappe.get_doc("EdgePay Merchant", link.merchant)
	return {
		"public_slug": link.public_slug,
		"title": link.title,
		"description": link.description,
		"merchant_name": merchant.trading_name or merchant.legal_name,
		"amount_mode": link.amount_mode,
		"amount": flt(link.amount) if link.amount_mode == "Fixed" else None,
		"minimum_amount": flt(link.minimum_amount) if link.minimum_amount else None,
		"maximum_amount": flt(link.maximum_amount) if link.maximum_amount else None,
		"currency": link.currency,
		"environment": account.environment,
		"redirect_url": link.redirect_url,
	}


def start_link_checkout(public_slug, customer_name, customer_email, customer_phone=None, amount=None, checkout_session=None):
	link, account = _get_active_link(public_slug)
	customer_name = (customer_name or "").strip()
	customer_email = (customer_email or "").strip().lower()
	if not customer_name or len(customer_name) > 140:
		frappe.throw(_("Customer name is required"))
	if not EMAIL_RE.match(customer_email) or len(customer_email) > 180:
		frappe.throw(_("Enter a valid email address"))
	if customer_phone and len(str(customer_phone)) > 40:
		frappe.throw(_("Phone number is too long"))
	resolved_amount = _resolve_amount(link, amount)
	checkout_session = (checkout_session or frappe.generate_hash(length=20)).strip()[:64]
	result = create_payment_request_record(
		merchant=link.merchant,
		provider=account.provider,
		provider_account=account.name,
		amount=resolved_amount,
		currency=link.currency,
		customer_name=customer_name,
		customer_email=customer_email,
		customer_phone=customer_phone,
		payment_purpose=link.title,
		source_app="EdgePay Hosted Checkout",
		source_doctype="EdgePay Payment Link",
		source_name=link.name,
		external_company_reference=link.merchant_account,
		external_branch_reference=link.merchant_branch,
		metadata_json={"payment_link": link.public_slug, "checkout_session": checkout_session},
		idempotency_key=f"payment-link:{link.public_slug}:{checkout_session}",
		enforce_actor_access=False,
	)
	request_name = result["data"]["payment_request"]
	checkout = initialize_checkout(request_name)
	return {
		"request_reference": result["data"]["request_reference"],
		"payment_attempt": checkout.get("attempt"),
		"checkout_url": checkout.get("checkout_url"),
		"status": checkout.get("status"),
		"amount": resolved_amount,
		"currency": link.currency,
		"redirect_url": link.redirect_url,
	}


def public_payment_status(request_reference):
	name = frappe.db.get_value("EdgePay Payment Request", {"request_reference": request_reference, "source_app": "EdgePay Hosted Checkout"}, "name")
	if not name:
		frappe.throw(_("Payment not found"))
	request = frappe.get_doc("EdgePay Payment Request", name)
	return {
		"request_reference": request.request_reference,
		"status": request.status,
		"amount": flt(request.amount),
		"paid_amount": flt(getattr(request, "paid_amount", 0)),
		"outstanding_amount": flt(getattr(request, "outstanding_amount", request.amount)),
		"currency": request.currency,
	}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_payment_link(public_slug):
	return public_link_context(public_slug)


@frappe.whitelist(allow_guest=True, methods=["POST"])
def start_payment_link(public_slug, customer_name, customer_email, customer_phone=None, amount=None, checkout_session=None):
	return start_link_checkout(public_slug, customer_name, customer_email, customer_phone, amount, checkout_session)


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_payment_status(request_reference):
	return public_payment_status(request_reference)
