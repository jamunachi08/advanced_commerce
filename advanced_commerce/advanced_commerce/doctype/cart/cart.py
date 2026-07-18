import frappe
from frappe.model.document import Document
from frappe.utils import add_days, now_datetime


class Cart(Document):
	def validate(self):
		self.recalculate_totals()

	def recalculate_totals(self):
		"""Recompute item amounts and grand total, applying the linked
		promotion rule (if any) before saving. Kept intentionally simple —
		real tax/shipping calculation is delegated to ERPNext's pricing
		engine at checkout time via advanced_commerce.api.checkout.
		"""
		subtotal = 0.0
		for row in self.items:
			row.amount = (row.rate or 0) * (row.qty or 0)
			subtotal += row.amount

		discount = 0.0
		if self.promotion_rule:
			from advanced_commerce.advanced_commerce.doctype.promotion_rule.promotion_rule import (
				calculate_discount,
			)

			discount = calculate_discount(self.promotion_rule, self)

		self.discount_total = discount
		self.grand_total = max(subtotal - discount, 0)


def expire_stale_carts():
	"""Daily scheduled job: mark carts untouched for 14+ days as Abandoned,
	and hard-expire guest carts untouched for 60+ days. Keeps the Cart table
	from growing unbounded with dead storefront sessions.
	"""
	cutoff_abandon = add_days(now_datetime(), -14)
	cutoff_expire = add_days(now_datetime(), -60)

	frappe.db.set_value(
		"Cart",
		{"status": "Open", "modified": ["<", cutoff_abandon]},
		"status",
		"Abandoned",
	)
	frappe.db.set_value(
		"Cart",
		{"status": "Abandoned", "modified": ["<", cutoff_expire]},
		"status",
		"Expired",
	)
	frappe.db.commit()
