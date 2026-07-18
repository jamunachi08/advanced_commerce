"""Step 1 of the 'place_order' workflow: reserve stock for every cart line
via ERPNext's Stock Reservation Entry. Compensating action cancels the
reservation, freeing the stock back up.
"""

import frappe

from advanced_commerce.workflow_engine.engine import Step


def run(context):
	cart = frappe.get_doc("Cart", context["cart"])
	reservation_names = []

	for row in cart.items:
		sre = frappe.get_doc(
			{
				"doctype": "Stock Reservation Entry",
				"item_code": row.item_code,
				"warehouse": context.get("warehouse"),
				"voucher_type": "Cart",
				"voucher_no": cart.name,
				"qty_to_reserve": row.qty,
			}
		)
		sre.insert(ignore_permissions=True)
		sre.submit()
		reservation_names.append(sre.name)

	return {"stock_reservations": reservation_names}


def compensate(context, result):
	for name in result.get("stock_reservations", []):
		try:
			doc = frappe.get_doc("Stock Reservation Entry", name)
			if doc.docstatus == 1:
				doc.cancel()
		except frappe.DoesNotExistError:
			pass


STEP = Step("reserve_stock", run, compensate)
