# -*- coding: utf-8 -*-
"""Central authorization helpers for EdgePay service and API operations.

Phase 1A intentionally uses Frappe roles and document permissions. Merchant-aware
scope checks will extend this module when the EdgePay Merchant foundation lands.
"""

import frappe
from frappe import _


PLATFORM_CONFIGURATION_ROLES = {"System Manager", "EdgePay Admin"}
PLATFORM_OPERATIONS_ROLES = {
    "System Manager",
    "EdgePay Admin",
    "EdgePay Manager",
}


def require_authenticated_user():
    """Reject Guest access and return the current user."""
    user = frappe.session.user
    if not user or user == "Guest":
        frappe.throw(
            _("Authentication required to access this API"),
            frappe.PermissionError,
        )
    return user


def require_any_role(roles, message=None):
    """Require at least one role from ``roles`` for the current user."""
    user = require_authenticated_user()
    user_roles = set(frappe.get_roles(user))
    required_roles = set(roles)
    if not user_roles.intersection(required_roles):
        frappe.throw(
            message or _("You are not permitted to perform this EdgePay operation"),
            frappe.PermissionError,
        )
    return user


def require_platform_configuration_access():
    return require_any_role(
        PLATFORM_CONFIGURATION_ROLES,
        _("Only an EdgePay Administrator may manage or inspect provider configuration"),
    )


def require_platform_operations_access():
    return require_any_role(
        PLATFORM_OPERATIONS_ROLES,
        _("You are not permitted to manage EdgePay operational handoffs"),
    )


def require_doctype_permission(doctype, ptype="read"):
    """Require a DocType-level permission before creating a new document."""
    require_authenticated_user()
    if not frappe.has_permission(doctype, ptype=ptype):
        frappe.throw(
            _("Not permitted to {0} {1}").format(ptype, doctype),
            frappe.PermissionError,
        )


def require_document_permission(doctype, name, ptype="read"):
    """Load a document and enforce Frappe object-level permission."""
    require_authenticated_user()
    if not name or not frappe.db.exists(doctype, name):
        frappe.throw(_("{0} {1} was not found").format(doctype, name))

    doc = frappe.get_doc(doctype, name)
    if not doc.has_permission(ptype=ptype):
        frappe.throw(
            _("Not permitted to {0} {1} {2}").format(ptype, doctype, name),
            frappe.PermissionError,
        )
    return doc


def require_provider_access(provider_name, ptype="read"):
    return require_document_permission("EdgePay Provider", provider_name, ptype=ptype)


def require_payment_request_access(payment_request_name, ptype="read"):
    return require_document_permission(
        "EdgePay Payment Request", payment_request_name, ptype=ptype
    )


def require_payment_transaction_access(transaction_name, ptype="read"):
    return require_document_permission(
        "EdgePay Payment Transaction", transaction_name, ptype=ptype
    )
