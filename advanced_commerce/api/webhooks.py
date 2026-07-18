"""Thin management API for webhook subscriptions, for integrators who'd
rather call an endpoint than use the Frappe Desk UI or REST doc API
directly. Requires a logged-in user with the Commerce Manager role
(enforced by DocType permissions, not re-checked here).
"""

import frappe


@frappe.whitelist()
def subscribe(event, target_url, secret=None):
	doc = frappe.get_doc(
		{
			"doctype": "Webhook Subscription",
			"event": event,
			"target_url": target_url,
			"secret": secret,
			"enabled": 1,
		}
	)
	doc.insert()
	return {"name": doc.name}


@frappe.whitelist()
def unsubscribe(name):
	frappe.delete_doc("Webhook Subscription", name)
	return {"deleted": name}


@frappe.whitelist()
def list_subscriptions(event=None):
	filters = {"event": event} if event else {}
	return frappe.get_all(
		"Webhook Subscription",
		filters=filters,
		fields=["name", "event", "target_url", "enabled", "last_delivery_status", "last_delivered_at"],
	)
