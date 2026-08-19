# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CAWIPEntry(Document):
	def validate(self):
		if self.billed and not self.sales_invoice:
			frappe.throw(
				"A WIP Entry cannot be marked Billed without a linked Sales "
				"Invoice — set sales_invoice first, or leave billed unchecked "
				"until the invoice actually exists."
			)
