# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CAInternalAuditFinding(Document):
	def validate(self):
		if self.status == "Re-tested - Closed" and not self.retest_note:
			frappe.throw(
				"An Internal Audit finding cannot be closed without a re-test "
				"note — mandatory follow-up re-testing is required before an "
				"issue is closed (build prompt Section 12)."
			)
