# -*- coding: utf-8 -*-
import frappe
from edgepayv1.edgepay.services.security import redact_secrets

def log(msg, title="EdgePay", level="info"):
	"""
	Logs a message after safely redacting sensitive data.
	"""
	try:
		settings = frappe.get_doc("EdgePay Settings")
		enable_debug_logging = settings.enable_debug_logging
	except Exception:
		# Fallback if settings are not initialized yet
		enable_debug_logging = True

	if level == "debug" and not enable_debug_logging:
		return

	# Redact secrets recursively
	redacted_msg = redact_secrets(msg)
	
	if level == "error":
		frappe.log_error(message=str(redacted_msg), title=title)
	else:
		frappe.logger().info(f"{title}: {redacted_msg}")
