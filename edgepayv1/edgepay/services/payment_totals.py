import frappe
from frappe.utils import flt


def get_payment_totals(payment_request_name):
	request = frappe.get_doc("EdgePay Payment Request", payment_request_name)
	paid = frappe.db.sql(
		"""select coalesce(sum(amount), 0) from `tabEdgePay Payment Transaction`
		where payment_request=%s and status='Success'""",
		(payment_request_name,),
	)[0][0]
	refunded = frappe.db.sql(
		"""select coalesce(sum(amount), 0) from `tabEdgePay Refund Request`
		where payment_request=%s and status='Completed'""",
		(payment_request_name,),
	)[0][0]
	net_paid = max(flt(paid) - flt(refunded), 0)
	outstanding = max(flt(request.amount) - net_paid, 0)
	overpaid = max(net_paid - flt(request.amount), 0)
	if net_paid <= 0:
		derived_status = "Unpaid"
	elif outstanding > 0:
		derived_status = "Partly Paid"
	elif overpaid > 0:
		derived_status = "Overpaid"
	else:
		derived_status = "Paid"
	return {
		"payment_request": request.name,
		"requested_amount": flt(request.amount),
		"successful_amount": flt(paid),
		"refunded_amount": flt(refunded),
		"net_paid_amount": net_paid,
		"outstanding_amount": outstanding,
		"overpaid_amount": overpaid,
		"currency": request.currency,
		"derived_status": derived_status,
	}


def sync_payment_totals(payment_request_name):
	request = frappe.get_doc("EdgePay Payment Request", payment_request_name)
	totals = get_payment_totals(payment_request_name)
	request.paid_amount = totals["net_paid_amount"]
	request.outstanding_amount = totals["outstanding_amount"]
	request.refunded_amount = totals["refunded_amount"]
	if totals["derived_status"] == "Partly Paid" and request.status not in {"Cancelled", "Expired"}:
		request.status = "Partly Paid"
	elif totals["derived_status"] in {"Paid", "Overpaid"} and request.status not in {"Cancelled", "Expired"}:
		request.status = totals["derived_status"]
	request.save(ignore_permissions=True)
	return totals


# Compatibility alias for callers that adopted the earlier descriptive name.
sync_payment_request_totals = sync_payment_totals
