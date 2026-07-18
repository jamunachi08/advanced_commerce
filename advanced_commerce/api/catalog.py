"""Storefront-facing catalog API. Every endpoint is channel-aware: pass a
`channel` (Sales Channel code) and get back only what's priced/stocked for
that channel, the same shape Saleor's channel-scoped GraphQL queries give
you, just as plain REST/JSON.
"""

import frappe
from frappe import _


@frappe.whitelist(allow_guest=True)
def list_products(channel, item_group=None, attribute_filters=None, start=0, page_length=20):
	"""List items available on a channel, optionally filtered by attribute
	values (e.g. {"color": "red", "size": "m"}). attribute_filters can be a
	JSON string (as it will be when called over HTTP) or a dict.
	"""
	channel_doc = _get_channel(channel)

	filters = {"disabled": 0}
	if item_group:
		filters["item_group"] = item_group

	items = frappe.get_all(
		"Item",
		filters=filters,
		fields=["name", "item_name", "item_group", "image", "description"],
		start=start,
		page_length=page_length,
	)

	attribute_filters = frappe.parse_json(attribute_filters) if isinstance(attribute_filters, str) else (attribute_filters or {})

	result = []
	for item in items:
		price = _get_price(item.name, channel_doc.default_price_list)
		if attribute_filters and not _matches_attributes(item.name, attribute_filters):
			continue
		result.append(
			{
				**item,
				"price": price,
				"currency": channel_doc.currency,
			}
		)

	return {"channel": channel, "count": len(result), "items": result}


@frappe.whitelist(allow_guest=True)
def get_product(channel, item_code):
	channel_doc = _get_channel(channel)

	if not frappe.db.exists("Item", item_code):
		frappe.throw(_("Product not found"), frappe.DoesNotExistError)

	item = frappe.get_doc("Item", item_code)
	variants = []
	if item.has_variants:
		variants = frappe.get_all(
			"Item",
			filters={"variant_of": item.name, "disabled": 0},
			fields=["name", "item_name"],
		)
		for v in variants:
			v["price"] = _get_price(v.name, channel_doc.default_price_list)
			v["attributes"] = _get_item_attributes(v.name)

	return {
		"item_code": item.name,
		"item_name": item.item_name,
		"description": item.description,
		"image": item.image,
		"price": _get_price(item.name, channel_doc.default_price_list),
		"currency": channel_doc.currency,
		"has_variants": item.has_variants,
		"variants": variants,
		"attributes": _get_item_attributes(item.name),
	}


@frappe.whitelist(allow_guest=True)
def list_facets(channel, item_group=None):
	"""Return the filterable Commerce Attributes + their values, so a
	storefront can render a filter sidebar without hardcoding anything.
	"""
	_get_channel(channel)
	attrs = frappe.get_all(
		"Commerce Attribute",
		filters={"is_filterable": 1},
		fields=["name", "attribute_name", "attribute_code"],
	)
	for a in attrs:
		a["values"] = frappe.get_all(
			"Commerce Attribute Value",
			filters={"parent": a.name},
			fields=["value_label", "value_code", "swatch_color"],
			order_by="sort_order asc",
		)
	return attrs


def _get_channel(channel_code):
	channel_doc = frappe.get_cached_doc("Sales Channel", channel_code)
	if not channel_doc.is_active:
		frappe.throw(_("This sales channel is not active"))
	return channel_doc


def _get_price(item_code, price_list):
	if not price_list:
		return None
	return frappe.db.get_value(
		"Item Price", {"item_code": item_code, "price_list": price_list}, "price_list_rate"
	)


def _get_item_attributes(item_code):
	rows = frappe.get_all(
		"Item Variant Attribute",
		filters={"parent": item_code},
		fields=["attribute", "attribute_value"],
	)
	return {r.attribute: r.attribute_value for r in rows}


def _matches_attributes(item_code, attribute_filters):
	current = _get_item_attributes(item_code)
	return all(current.get(k) == v for k, v in attribute_filters.items())
