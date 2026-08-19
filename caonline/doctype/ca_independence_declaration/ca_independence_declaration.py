# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CAIndependenceDeclaration(Document):
	def validate(self):
		if self.waived_by_partner:
			if "CA Partner" not in frappe.get_roles(self.waived_by_partner):
				frappe.throw(
					f"{self.waived_by_partner} does not hold the CA Partner role and "
					f"cannot waive an independence conflict. Only a Partner-level "
					f"user may waive this."
				)
			if not self.waiver_note:
				frappe.throw("A waiver rationale is required whenever a conflict is waived.")
