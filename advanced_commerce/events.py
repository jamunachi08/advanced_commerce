"""
Lightweight event bus for Advanced Commerce.

Inspired by Saleor's plugin manager / webhook dispatcher and Medusa's event
bus: every meaningful change (order placed, payment captured, shipment
created...) is turned into a named event and fanned out to:

  1. Internal Python "plugins" registered in PLUGIN_REGISTRY (e.g. loyalty
     points, tax recalculation, search index updates).
  2. External subscribers stored in the `Webhook Subscription` doctype,
     delivered asynchronously via background jobs so a slow/broken
     third-party endpoint never blocks the triggering transaction.

Nothing here talks to the database transaction directly except to read
subscriptions and enqueue jobs, so a failure in a subscriber can never roll
back the document that triggered it.
"""

import json

import frappe
from frappe.utils import now_datetime

# Map of event_name -> list of callables(doc, event_name)
PLUGIN_REGISTRY = {}


def register_plugin(event_name, handler):
	"""Register an internal plugin handler for a given event name.

	Example:
		from advanced_commerce.events import register_plugin
		register_plugin("order.confirmed", my_loyalty_points_handler)
	"""
	PLUGIN_REGISTRY.setdefault(event_name, []).append(handler)


def _event_name_for(doc, method):
	doctype_slug = frappe.scrub(doc.doctype)
	action = {
		"on_submit": "confirmed",
		"on_cancel": "cancelled",
		"on_update_after_submit": "updated",
		"on_update": "updated",
	}.get(method, method)
	return f"{doctype_slug}.{action}"


def dispatch_doc_event(doc, method):
	"""Hook target used from hooks.py doc_events.

	Builds an event name like "sales_order.confirmed" and fans it out to
	internal plugins (synchronously, since they're expected to be fast and
	transactional) and to external webhook subscribers (asynchronously).
	"""
	event_name = _event_name_for(doc, method)
	emit(event_name, doc)


def emit(event_name, doc=None, payload=None):
	"""Emit an arbitrary named event, e.g. from workflow steps or the API."""
	payload = payload or (doc.as_dict() if doc else {})

	for handler in PLUGIN_REGISTRY.get(event_name, []):
		try:
			handler(doc, event_name)
		except Exception:
			frappe.log_error(
				title=f"Advanced Commerce plugin failed for {event_name}",
				message=frappe.get_traceback(),
			)

	_notify_webhook_subscribers(event_name, payload)


def _notify_webhook_subscribers(event_name, payload):
	subscriptions = frappe.get_all(
		"Webhook Subscription",
		filters={"event": event_name, "enabled": 1},
		fields=["name", "target_url", "secret"],
	)
	if not subscriptions:
		return

	for sub in subscriptions:
		frappe.enqueue(
			"advanced_commerce.events.deliver_webhook",
			queue="short",
			enqueue_after_commit=True,
			subscription=sub.name,
			event_name=event_name,
			payload=payload,
			fired_at=str(now_datetime()),
		)


def deliver_webhook(subscription, event_name, payload, fired_at):
	"""Background job: POST the event payload to the subscriber's target_url.

	Retries are handled by re-enqueuing with an incrementing attempt count
	stored on the Webhook Subscription's delivery log (see
	webhook_subscription.py for the log/backoff logic).
	"""
	import requests

	sub_doc = frappe.get_doc("Webhook Subscription", subscription)
	body = json.dumps({"event": event_name, "payload": payload, "fired_at": fired_at}, default=str)
	headers = {"Content-Type": "application/json"}

	if sub_doc.secret:
		import hashlib
		import hmac

		signature = hmac.new(sub_doc.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
		headers["X-Commerce-Signature"] = signature

	try:
		response = requests.post(sub_doc.target_url, data=body, headers=headers, timeout=10)
		sub_doc.log_delivery(event_name, response.status_code, success=response.ok)
	except Exception as e:
		sub_doc.log_delivery(event_name, None, success=False, error=str(e))
