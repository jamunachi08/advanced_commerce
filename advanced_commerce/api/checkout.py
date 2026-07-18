"""Storefront-facing checkout API. Kicks off the 'place_order' saga
(reserve stock -> charge payment -> create sales order), each step running
as a background job with automatic compensation on failure — see
advanced_commerce/workflow_engine/engine.py.

The HTTP response returns immediately with a Workflow Run id; the
storefront polls get_checkout_status (or subscribes to the
'workflow_run.updated' webhook event) to know when the order is finalized,
since payment gateways and stock systems can be slow.
"""

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def start_checkout(cart_name, payment_method_token=None):
	from advanced_commerce.workflow_engine.engine import start_workflow
	from advanced_commerce.workflows import ensure_registered

	ensure_registered()

	cart = frappe.get_doc("Cart", cart_name)
	if cart.status != "Open":
		frappe.throw(_("Cart is not open for checkout"))
	if not cart.items:
		frappe.throw(_("Cart is empty"))

	cart.status = "Checkout In Progress"
	cart.save(ignore_permissions=True)
	frappe.db.commit()

	warehouse = frappe.db.get_value("Sales Channel", cart.sales_channel, "default_warehouse")

	run_name = start_workflow(
		"place_order",
		context={
			"cart": cart.name,
			"warehouse": warehouse,
			"payment_method_token": payment_method_token,
		},
		reference_doctype="Cart",
		reference_name=cart.name,
	)

	return {"workflow_run": run_name, "status": "Processing"}


@frappe.whitelist(allow_guest=True)
def get_checkout_status(workflow_run):
	run_doc = frappe.get_doc("Workflow Run", workflow_run)
	context = run_doc.get_context()
	return {
		"status": run_doc.status,
		"sales_order": context.get("sales_order"),
		"steps": [
			{"step": s.step_name, "status": s.status, "error": s.error if s.status == "Failed" else None}
			for s in run_doc.steps
		],
	}
