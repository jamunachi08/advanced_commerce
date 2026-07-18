app_name = "advanced_commerce"
app_title = "Advanced Commerce"
app_publisher = "Your Company"
app_description = "Multi-channel headless commerce engine for Frappe: channel/attribute catalog (Saleor-style) + saga workflow orchestration (Medusa-style)."
app_email = "dev@example.com"
app_license = "MIT"
required_apps = ["frappe/erpnext"]

after_install = "advanced_commerce.install.after_install"

# Includes in <head>
# ------------------
app_include_css = "/assets/advanced_commerce/css/advanced_commerce.css"
app_include_js = "/assets/advanced_commerce/js/advanced_commerce.js"

# Fixtures exported with the app (roles, custom fields, property setters)
# ------------------------------------------------------------------
fixtures = [
	{"dt": "Role", "filters": [["name", "in", ["Commerce Manager", "Commerce API"]]]},
]

# Document Events
# ---------------
# Fires the internal event bus (advanced_commerce.events) whenever these
# doctypes change, which in turn notifies webhook subscribers and any
# registered internal plugins. This mirrors Saleor's plugin manager /
# webhook dispatch pattern.
doc_events = {
	"Sales Order": {
		"on_submit": "advanced_commerce.events.dispatch_doc_event",
		"on_update_after_submit": "advanced_commerce.events.dispatch_doc_event",
		"on_cancel": "advanced_commerce.events.dispatch_doc_event",
	},
	"Payment Entry": {
		"on_submit": "advanced_commerce.events.dispatch_doc_event",
	},
	"Delivery Note": {
		"on_submit": "advanced_commerce.events.dispatch_doc_event",
	},
	"Cart": {
		"on_update": "advanced_commerce.events.dispatch_doc_event",
	},
	"Workflow Run": {
		"on_update": "advanced_commerce.events.dispatch_doc_event",
	},
}

# Scheduled Tasks
# ---------------
scheduler_events = {
	"cron": {
		# every 5 minutes: resume any workflow runs stuck in a retry-able state
		"*/5 * * * *": [
			"advanced_commerce.workflow_engine.engine.process_pending_runs",
		],
	},
	"daily": [
		"advanced_commerce.advanced_commerce.doctype.cart.cart.expire_stale_carts",
	],
}

# Whitelisted API modules are just regular python modules under advanced_commerce/api/*
# exposed via @frappe.whitelist(); no extra wiring needed here.

# Website route rules (optional storefront preview pages)
website_route_rules = [
	{"from_route": "/commerce/<path:app_path>", "to_route": "commerce"},
]
