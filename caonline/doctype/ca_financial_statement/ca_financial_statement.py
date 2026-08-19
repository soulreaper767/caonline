# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CAFinancialStatement(Document):
	def validate(self):
		self.title = f"{self.client} - {self.financial_year}"
		self.compute_control_totals()
		self.roll_up_rule_flags()

	def compute_control_totals(self):
		"""Mechanical check per the Standards Compliance Engine (build prompt
		Section 15/6.4): assets must equal liabilities + equity. This is the
		first Rule Flag category and is checked directly here so it's visible
		on the FS itself, not only in the separate Rule Flag log."""
		assets, liab_equity = 0.0, 0.0
		for row in self.line_items:
			category = frappe.db.get_value("CA Standard FS Line", row.fs_line_item, "category")
			if category == "Asset":
				assets += flt(row.closing_balance)
			elif category in ("Liability", "Equity"):
				liab_equity += flt(row.closing_balance)

		self.total_assets = assets
		self.total_liabilities_equity = liab_equity
		self.balances = 1 if abs(assets - liab_equity) < 1 else 0

		if not self.balances:
			frappe.msgprint(
				f"Balance sheet does not balance: Assets {assets:,.0f} vs "
				f"Liabilities+Equity {liab_equity:,.0f}. This will raise a "
				f"Breach-severity Rule Flag on save.",
				indicator="orange",
				alert=True,
			)

		from caonline.caonline.api.compliance_engine import raise_or_clear_rule_flag

		raise_or_clear_rule_flag(
			condition=not self.balances,
			key="balance_sheet_tie_out",
			rule_source="Mechanical Check (Casting/Balancing)",
			severity="Breach",
			description=(
				f"Balance sheet does not tie out: Assets {assets:,.0f} vs "
				f"Liabilities+Equity {liab_equity:,.0f}."
			),
			financial_statement=self.name,
		)

	def roll_up_rule_flags(self):
		self.open_rule_flags = frappe.db.count(
			"CA Rule Flag", filters={"financial_statement": self.name, "status": "Open"}
		)

	def on_submit(self):
		if not self.balances:
			frappe.throw(
				"This Financial Statement cannot be submitted while the balance "
				"sheet does not balance. Fix the underlying trial balance or "
				"mapping and re-import before submitting."
			)


@frappe.whitelist()
def refresh_from_source(financial_statement):
	"""Re-pulls line items from whichever source is configured (live company
	books or the uploaded trial balance) without losing the existing FS
	line-item-to-standard-line mapping, so re-running this after the client
	uploads a corrected TB doesn't force re-mapping every account again."""
	from caonline.caonline.api.fs_integration import rebuild_financial_statement

	return rebuild_financial_statement(financial_statement)
