"""Payment provider plugin registry — a Frappe-native equivalent of Saleor's
plugin manager for payments. Each provider is a small adapter class;
registering a new gateway (Stripe, Razorpay, PayPal...) means writing one
adapter and one line of registration, never touching the checkout workflow.
"""

import frappe

PROVIDER_REGISTRY = {}


class PaymentProvider:
	name = "base"

	def charge(self, amount, currency, payment_method_token, reference):
		raise NotImplementedError

	def refund(self, charge_id):
		raise NotImplementedError


class ManualPaymentProvider(PaymentProvider):
	"""Default fallback used when no real gateway is configured yet — marks
	the order for manual reconciliation instead of failing checkout outright.
	Replace with a real adapter (Stripe/Razorpay/etc.) per channel.
	"""

	name = "manual"

	def charge(self, amount, currency, payment_method_token, reference):
		return f"manual-{reference}"

	def refund(self, charge_id):
		frappe.logger("advanced_commerce").info(f"Manual refund requested for {charge_id}")


def register_provider(name, provider_cls):
	PROVIDER_REGISTRY[name] = provider_cls


def get_provider_by_name(name):
	provider_cls = PROVIDER_REGISTRY.get(name, ManualPaymentProvider)
	return provider_cls()


def get_provider(sales_channel):
	"""Resolve which provider a Sales Channel should use. Reads from
	Commerce Settings' channel-provider map; falls back to manual so
	checkout never hard-fails just because a gateway isn't wired up yet.
	"""
	provider_name = (
		frappe.db.get_value("Sales Channel", sales_channel, "payment_provider") or "manual"
	)
	return get_provider_by_name(provider_name)


# Built-in fallback is always available.
register_provider("manual", ManualPaymentProvider)
