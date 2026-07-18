"""Central place where named workflows are assembled from steps.

Imported lazily (from advanced_commerce.api.checkout) rather than at
hooks.py load time, so step modules can safely import frappe app code
without worrying about import order during bench boot.
"""

from advanced_commerce.workflow_engine.engine import register_workflow
from advanced_commerce.workflow_engine.steps import charge_payment, create_order, reserve_stock

_REGISTERED = False


def ensure_registered():
	global _REGISTERED
	if _REGISTERED:
		return

	register_workflow(
		"place_order",
		[reserve_stock.STEP, charge_payment.STEP, create_order.STEP],
	)
	_REGISTERED = True
