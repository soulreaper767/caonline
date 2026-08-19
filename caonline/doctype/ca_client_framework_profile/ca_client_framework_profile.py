# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CAClientFrameworkProfile(Document):
	def validate(self):
		self.enforce_single_current_profile()

	def enforce_single_current_profile(self):
		"""CA Engagement.pull_applicable_framework_profile() resolves a client's
		framework via frappe.db.get_value(..., {"client": ..., "is_current": 1},
		"name") — a get_value with no order_by picks an arbitrary row if more
		than one is current, so this invariant has to be enforced here, not
		left to convention."""
		if not self.is_current:
			return
		frappe.db.set_value(
			"CA Client Framework Profile",
			{"client": self.client, "is_current": 1, "name": ["!=", self.name]},
			"is_current",
			0,
		)
