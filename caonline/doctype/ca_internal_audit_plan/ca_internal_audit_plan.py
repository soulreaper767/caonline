# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CAInternalAuditPlan(Document):
	def validate(self):
		self.check_statutory_audit_overlap()

	def check_statutory_audit_overlap(self):
		"""build prompt Section 12: 'internal audit engagements for a
		statutory-audit client are tracked as a distinct engagement type to
		preserve independence documentation.' This flags the overlap and, if
		found, requires that no team member on this Internal Audit Plan's
		engagement also sits on the client's Statutory Audit engagement team
		for the same year."""
		client = frappe.db.get_value("CA Engagement", self.engagement, "client")

		statutory_engagements = frappe.get_all(
			"CA Engagement",
			filters={"client": client, "docstatus": ["!=", 2]},
			fields=["name", "engagement_type_template"],
		)
		statutory_names = [
			e.name for e in statutory_engagements
			if frappe.db.get_value(
				"CA Engagement Type Template", e.engagement_type_template, "service_line"
			) == "Statutory Audit"
		]

		self.client_also_audit_client = 1 if statutory_names else 0

		if not statutory_names:
			return

		ia_team = {
			r.staff_user for r in frappe.get_all(
				"CA Engagement Team Member", filters={"parent": self.engagement}, fields=["staff_user"]
			)
		}
		for stat_eng in statutory_names:
			sa_team = {
				r.staff_user for r in frappe.get_all(
					"CA Engagement Team Member", filters={"parent": stat_eng}, fields=["staff_user"]
				)
			}
			overlap = ia_team & sa_team
			if overlap:
				frappe.throw(
					f"{', '.join(overlap)} are on both the Internal Audit team and "
					f"the Statutory Audit team ({stat_eng}) for the same client. "
					f"This threatens auditor independence — reassign one of the "
					f"two roles before saving."
				)
