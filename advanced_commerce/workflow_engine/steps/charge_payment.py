"""Step 2 of the 'place_order' workflow: capture payment through whichever
Payment Provider is configured for the cart's Sales Channel. Providers are
resolved dynamically (a Frappe-native version of Saleor/Medusa's payment
plugin registry) via advanced_commerce.api.payments.get_provider so adding
Stripe/Razorpay/PayPal support means writing one small adapter, not
touching the workflow.
"""

import frappe

from advanced_commerce.workflow_engine.engine import Step


def run(context):
	from advanced_commerce.api.payments import get_provider

	cart = frappe.get_doc("Cart", context["cart"])
	provider = get_provider(cart.sales_channel)

	charge_id = provider.charge(
		amount=cart.grand_total,
		currency=cart.currency,
		payment_method_token=context.get("payment_method_token"),
		reference=cart.name,
	)
	return {"charge_id": charge_id, "provider": provider.name}


def compensate(context, result):
	from advanced_commerce.api.payments import get_provider_by_name

	if not result.get("charge_id"):
		return
	provider = get_provider_by_name(result["provider"])
	provider.refund(result["charge_id"])


STEP = Step("charge_payment", run, compensate)
