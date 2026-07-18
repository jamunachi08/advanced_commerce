import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class PromotionRule(Document):
	def validate(self):
		if self.valid_from and self.valid_upto and getdate(self.valid_from) > getdate(self.valid_upto):
			frappe.throw("Valid From must be before Valid Upto")


def calculate_discount(rule_name, cart):
	"""Pure function: given a Promotion Rule name and a Cart document (not
	yet saved), return the discount amount in cart currency. Kept outside
	the controller so it can be unit tested and reused by the checkout
	workflow step without instantiating a full Cart.
	"""
	rule = frappe.get_cached_doc("Promotion Rule", rule_name)

	if not rule.is_active:
		return 0.0

	today_date = getdate(today())
	if rule.valid_from and today_date < getdate(rule.valid_from):
		return 0.0
	if rule.valid_upto and today_date > getdate(rule.valid_upto):
		return 0.0

	if rule.usage_limit and rule.times_used >= rule.usage_limit:
		return 0.0

	subtotal = sum((row.rate or 0) * (row.qty or 0) for row in cart.items)

	if rule.min_cart_value and subtotal < rule.min_cart_value:
		return 0.0

	if rule.discount_type == "Percentage":
		return round(subtotal * (rule.discount_value or 0) / 100, 2)
	elif rule.discount_type == "Flat Amount":
		return min(rule.discount_value or 0, subtotal)
	# "Free Shipping" affects the shipping line at checkout time, not the
	# cart subtotal — handled separately in advanced_commerce.api.checkout.
	return 0.0


def register_usage(rule_name):
	frappe.db.set_value("Promotion Rule", rule_name, "times_used", frappe.db.get_value(
		"Promotion Rule", rule_name, "times_used") + 1)
