"""Storefront-facing cart API. Works for both logged-in customers and guest
sessions (identified by a client-generated session_id), matching how
Saleor/Medusa storefronts keep a cart alive across a browsing session
before the customer authenticates.
"""

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def get_or_create_cart(channel, session_id=None):
	customer = _current_customer()
	filters = {"sales_channel": channel, "status": "Open"}

	if customer:
		filters["customer"] = customer
	elif session_id:
		filters["session_id"] = session_id
	else:
		frappe.throw(_("session_id is required for guest carts"))

	existing = frappe.get_all("Cart", filters=filters, limit_page_length=1, pluck="name")
	if existing:
		return frappe.get_doc("Cart", existing[0])

	cart = frappe.get_doc(
		{
			"doctype": "Cart",
			"sales_channel": channel,
			"customer": customer,
			"session_id": None if customer else session_id,
			"currency": frappe.db.get_value("Sales Channel", channel, "currency"),
		}
	)
	cart.insert(ignore_permissions=True)
	return cart


@frappe.whitelist(allow_guest=True)
def add_item(cart_name, item_code, qty=1):
	cart = _load_cart(cart_name)
	price_list = frappe.db.get_value("Sales Channel", cart.sales_channel, "default_price_list")
	rate = frappe.db.get_value(
		"Item Price", {"item_code": item_code, "price_list": price_list}, "price_list_rate"
	) or 0

	for row in cart.items:
		if row.item_code == item_code:
			row.qty = (row.qty or 0) + float(qty)
			break
	else:
		cart.append("items", {"item_code": item_code, "qty": qty, "rate": rate})

	cart.save(ignore_permissions=True)
	return cart


@frappe.whitelist(allow_guest=True)
def update_item_qty(cart_name, item_code, qty):
	cart = _load_cart(cart_name)
	qty = float(qty)
	cart.items = [row for row in cart.items if not (row.item_code == item_code and qty <= 0)]
	for row in cart.items:
		if row.item_code == item_code:
			row.qty = qty
	cart.save(ignore_permissions=True)
	return cart


@frappe.whitelist(allow_guest=True)
def remove_item(cart_name, item_code):
	return update_item_qty(cart_name, item_code, 0)


@frappe.whitelist(allow_guest=True)
def apply_coupon(cart_name, coupon_code):
	cart = _load_cart(cart_name)
	rule_name = frappe.db.get_value(
		"Promotion Rule", {"coupon_code": coupon_code, "is_active": 1}, "name"
	)
	if not rule_name:
		frappe.throw(_("Invalid or expired coupon code"))

	cart.promotion_rule = rule_name
	cart.save(ignore_permissions=True)
	return cart


def _load_cart(cart_name):
	cart = frappe.get_doc("Cart", cart_name)
	customer = _current_customer()
	if cart.customer and cart.customer != customer:
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	if cart.status != "Open":
		frappe.throw(_("This cart is no longer open"))
	return cart


def _current_customer():
	if frappe.session.user == "Guest":
		return None
	return frappe.db.get_value("Customer", {"user": frappe.session.user}, "name")
