# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, today


class CAEngagementChecklist(Document):
	def validate(self):
		self.stamp_checked_metadata()
		self.recompute_completion()

	def stamp_checked_metadata(self):
		"""Records who ticked an item and when, without requiring the UI to
		set those fields itself — this keeps the audit trail honest even if
		the checklist is updated via the API rather than the desk grid."""
		for row in self.items:
			if row.checked and not row.checked_by:
				row.checked_by = frappe.session.user
				row.checked_on = today()
			if not row.checked:
				row.checked_by = None
				row.checked_on = None

	def recompute_completion(self):
		self.total_items = len(self.items)
		self.completed_items = len([r for r in self.items if r.checked])
		self.percent_complete = (
			flt(self.completed_items) / self.total_items * 100 if self.total_items else 0
		)
