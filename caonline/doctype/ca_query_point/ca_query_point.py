# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CAQueryPoint(Document):
	def validate(self):
		if self.assigned_to == self.raised_by:
			frappe.throw("A query point cannot be assigned to the person who raised it.")


def block_self_approval(doc, method=None):
	"""Segregation-of-duties enforcement (build prompt Section 3.2): a
	preparer cannot clear/close their own query point. This fires on every
	save so a status change slipped in via the API is caught too, not just
	changes made through the desk UI."""

	if doc.has_value_changed("status") and doc.status in ("Cleared", "Closed"):
		if doc.cleared_by == doc.raised_by:
			frappe.throw(
				"The person who raised this query point cannot also clear it. "
				"Route clearance through the assigned reviewer/preparer chain."
			)
		if not doc.cleared_by:
			doc.cleared_by = frappe.session.user
