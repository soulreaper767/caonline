# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CAQCRReview(Document):
	def validate(self):
		self.enforce_reviewer_independence()

	def enforce_reviewer_independence(self):
		"""A QCR review only means something if the reviewer stood outside
		the engagement being reviewed. This is a distinct, simpler check from
		validate_team_independence() in ca_engagement.py (which handles
		client-relationship conflicts) — here the conflict is simply having
		done the work that's now being graded."""
		was_on_team = frappe.db.exists(
			"CA Engagement Team Member",
			{"parent": self.engagement, "staff_user": self.qcr_reviewer},
		)
		if was_on_team:
			frappe.throw(
				f"{self.qcr_reviewer} was a member of the engagement team for "
				f"{self.engagement} and cannot perform its Quality Control "
				f"Review. Assign a reviewer who was not on the original team."
			)
