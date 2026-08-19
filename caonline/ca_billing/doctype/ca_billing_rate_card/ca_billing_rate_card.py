# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class CABillingRateCard(Document):
	def validate(self):
		self.reject_overlapping_period()

	def reject_overlapping_period(self):
		"""A silent overlap between two rate cards for the same (grade,
		service_line) would make WIP valuation ambiguous — which rate applies
		on a given date would depend on record order rather than a clear rule.
		Reject the save outright instead of guessing."""
		other_cards = frappe.get_all(
			"CA Billing Rate Card",
			filters={
				"grade": self.grade,
				"service_line": self.service_line,
				"name": ["!=", self.name or ""],
			},
			fields=["name", "effective_from", "effective_to"],
		)

		this_start = getdate(self.effective_from)
		this_end = getdate(self.effective_to) if self.effective_to else None

		for other in other_cards:
			other_start = getdate(other.effective_from)
			other_end = getdate(other.effective_to) if other.effective_to else None

			starts_before_other_ends = other_end is None or this_start <= other_end
			ends_after_other_starts = this_end is None or this_end >= other_start

			if starts_before_other_ends and ends_after_other_starts:
				frappe.throw(
					f"This rate card's effective period overlaps with {other.name} "
					f"for the same grade/service line combination. Adjust the dates "
					f"so periods don't overlap — WIP valuation depends on exactly "
					f"one rate being in force on any given date."
				)
