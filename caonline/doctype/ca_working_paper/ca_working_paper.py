# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CAWorkingPaper(Document):
	def validate(self):
		self.check_ties_to_fs()

	def check_ties_to_fs(self):
		"""The casting/posting check: if this schedule claims to support a
		specific FS line, its schedule_total must actually agree with that
		line's closing balance on the engagement's Source Financial Statement
		— this is what makes a lead schedule a real tie-out, not just a label."""
		if not self.fs_line_item:
			self.ties_to_fs = 0
			return

		source_fs = frappe.db.get_value("CA Engagement", self.engagement, "source_financial_statement")
		if not source_fs:
			self.ties_to_fs = 0
			return

		fs_balance = frappe.db.get_value(
			"CA FS Line Item",
			{"parent": source_fs, "fs_line_item": self.fs_line_item},
			"closing_balance",
		)
		if fs_balance is None:
			self.ties_to_fs = 0
			return

		self.ties_to_fs = 1 if abs(flt(self.schedule_total) - flt(fs_balance)) < 1 else 0
