# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CAUploadedTrialBalance(Document):
	def validate(self):
		self.auto_suggest_mapping()
		self.compute_control_totals()

	def auto_suggest_mapping(self):
		"""Reuses the mapping the firm built for this client in a prior period
		(build prompt Section 8: 'auto-mapping engine ... learning and reusing
		the mapping every subsequent period') instead of asking staff to
		re-map the same client account names every year."""
		for row in self.lines:
			if row.mapped_fs_line:
				continue
			prior = frappe.db.get_value(
				"CA TB Mapped Line",
				{"client_account_name": row.client_account_name, "mapped_fs_line": ["is", "set"]},
				"mapped_fs_line",
				order_by="modified desc",
			)
			if prior:
				row.mapped_fs_line = prior

	def compute_control_totals(self):
		self.total_debit = sum(flt(r.debit) for r in self.lines)
		self.total_credit = sum(flt(r.credit) for r in self.lines)
		self.ties_out = 1 if abs(self.total_debit - self.total_credit) < 1 else 0


def get_permission_query_conditions(user):
	"""Client portal users may only see/upload trial balances for their own
	client, mirroring the CA Engagement scoping."""
	if not user:
		user = frappe.session.user
	roles = frappe.get_roles(user)
	if "CA Client Portal" not in roles:
		return ""
	return f"""exists (
		select 1 from `tabCA Client Contact` cc
		where cc.parent = `tabCA Uploaded Trial Balance`.client
		and cc.portal_user = {frappe.db.escape(user)}
		and cc.is_active = 1
	)"""
