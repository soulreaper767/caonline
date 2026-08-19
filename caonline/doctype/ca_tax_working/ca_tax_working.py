# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CATaxWorking(Document):
	def validate(self):
		self.compute()

	def compute(self):
		self.total_addbacks = sum(
			flt(r.amount) for r in self.adjustments if r.adjustment_type == "Add-back (Inadmissible Expense)"
		)
		self.total_allowances = sum(
			flt(r.amount) for r in self.adjustments if r.adjustment_type == "Allowance / Deduction"
		)
		self.total_credits = sum(
			flt(r.amount) for r in self.adjustments if r.adjustment_type == "Tax Credit"
		)

		self.taxable_income = (
			flt(self.accounting_profit) + self.total_addbacks - self.total_allowances
		)
		self.net_tax_payable = flt(self.tax_liability) - self.total_credits


@frappe.whitelist()
def pull_accounting_profit(tax_working):
	"""Wired to a form button. This is the tax-side half of the cross-module
	feature: rather than the tax preparer re-deriving accounting profit from
	scratch, it is read straight from the same CA Financial Statement the
	audit/bookkeeping side already built and (ideally) had reviewed."""

	doc = frappe.get_doc("CA Tax Working", tax_working)
	if not doc.source_financial_statement:
		frappe.throw(
			"No Source Financial Statement is linked to this Tax Working's "
			"Engagement. Link or build one first (CA Engagement > Pull "
			"Financial Statement from Bookkeeping, or build from an uploaded "
			"trial balance)."
		)

	from caonline.caonline.api.fs_integration import get_accounting_profit

	profit = get_accounting_profit(doc.source_financial_statement)
	doc.db_set("accounting_profit", profit)
	return profit
