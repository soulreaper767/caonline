# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today


class CAReviewSignoff(Document):
	def validate(self):
		self.validate_reviewer_on_team()
		self.stamp_signed_on()

	def validate_reviewer_on_team(self):
		"""A review sign-off only means something if the reviewer is actually
		staffed on this engagement in a matching role — otherwise anyone
		could sign off any engagement they've never looked at."""
		team_row = frappe.db.get_value(
			"CA Engagement Team Member",
			{"parent": self.engagement, "staff_user": self.reviewer},
			"role_on_engagement",
		)
		if not team_row:
			frappe.throw(
				f"{self.reviewer} is not on the engagement team for "
				f"{self.engagement} and cannot record a review sign-off on it."
			)
		if team_row != self.review_level:
			frappe.msgprint(
				f"{self.reviewer} is staffed as '{team_row}' on this engagement, "
				f"not '{self.review_level}'. Confirm this is intentional before "
				f"relying on this sign-off.",
				indicator="orange",
				alert=True,
			)

	def stamp_signed_on(self):
		if self.status == "Signed Off" and not self.signed_on:
			self.signed_on = today()
		if self.status != "Signed Off":
			self.signed_on = None
