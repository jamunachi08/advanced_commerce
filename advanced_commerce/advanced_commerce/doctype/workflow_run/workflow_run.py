import frappe
from frappe.model.document import Document


class WorkflowRun(Document):
	def get_context(self):
		return frappe.parse_json(self.context) if self.context else {}

	def set_context(self, ctx):
		self.context = frappe.as_json(ctx)
