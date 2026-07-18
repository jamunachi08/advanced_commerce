"""Step 3: convert the Cart into a submitted ERPNext Sales Order now that
stock is reserved and payment is captured. Compensating action cancels the
Sales Order (ERPNext's own cancellation cascade releases the stock
reservation tied to it, in addition to the explicit release performed by
reserve_stock.compensate for the pre-order reservation).
"""

import frappe

from advanced_commerce.workflow_engine.engine import Step


def run(context):
	cart = frappe.get_doc("Cart", context["cart"])

	so = frappe.get_doc(
		{
			"doctype": "Sales Order",
			"customer": cart.customer or frappe.db.get_value(
				"Sales Channel", cart.sales_channel, "default_price_list"
			),
			"currency": cart.currency,
			"selling_price_list": frappe.db.get_value(
				"Sales Channel", cart.sales_channel, "default_price_list"
			),
			"items": [
				{"item_code": row.item_code, "qty": row.qty, "rate": row.rate} for row in cart.items
			],
		}
	)
	so.insert(ignore_permissions=True)
	so.submit()

	cart.status = "Converted"
	cart.save(ignore_permissions=True)

	return {"sales_order": so.name}


def compensate(context, result):
	so_name = result.get("sales_order")
	if not so_name:
		return
	so = frappe.get_doc("Sales Order", so_name)
	if so.docstatus == 1:
		so.cancel()


STEP = Step("create_order", run, compensate)
