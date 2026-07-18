import json

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class WebhookSubscription(Document):
	def log_delivery(self, event_name, status_code, success, error=None):
		log = json.loads(self.delivery_log) if self.delivery_log else []
		log.insert(
			0,
			{
				"event": event_name,
				"status_code": status_code,
				"success": success,
				"error": error,
				"at": str(now_datetime()),
			},
		)
		# keep only the most recent 20 deliveries
		self.delivery_log = json.dumps(log[:20])
		self.last_delivery_status = "Success" if success else "Failed"
		self.last_delivered_at = now_datetime()
		self.db_update()
		frappe.db.commit()
