import frappe
from frappe.model.document import Document


class SalesChannel(Document):
	def validate(self):
		self.channel_code = (self.channel_code or "").strip().lower().replace(" ", "-")

		if not self.channel_code:
			frappe.throw("Channel Code is required")
