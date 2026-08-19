# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CAEngagement(Document):
	def validate(self):
		self.set_engagement_title()
		self.pull_applicable_framework_profile()
		self.recompute_hour_totals()
		self.enforce_breach_gate()
		self.check_bookkeeping_source_availability()

	def check_bookkeeping_source_availability(self):
		"""Every time an Audit / Review / Tax / Compilation engagement is
		saved, check whether this client is also a live bookkeeping client so
		staff see the 'pull from live books' option instead of defaulting to
		a manual upload. Bookkeeping engagements themselves are excluded —
		they ARE the source, not a consumer of it."""
		service_line = frappe.db.get_value(
			"CA Engagement Type Template", self.engagement_type_template, "service_line"
		)
		if service_line == "Bookkeeping":
			self.has_bookkeeping_source_available = 0
			return

		from caonline.caonline.api.fs_integration import has_live_bookkeeping_source
		self.has_bookkeeping_source_available = 1 if has_live_bookkeeping_source(self.client) else 0

	def set_engagement_title(self):
		template = frappe.db.get_value(
			"CA Engagement Type Template", self.engagement_type_template, "service_line"
		)
		self.engagement_title = f"{self.client} - {template} - {self.financial_year}"

	def pull_applicable_framework_profile(self):
		"""Every engagement inherits the client's current Framework Profile at
		creation time. If the client's profile is later re-evaluated (e.g. a
		size-threshold crossing), open engagements are NOT silently rewritten —
		that re-linking is a deliberate, logged action from the standards
		engine, not something that happens on every save."""
		if not self.applicable_framework_profile:
			profile = frappe.db.get_value(
				"CA Client Framework Profile", {"client": self.client, "is_current": 1}, "name"
			)
			if profile:
				self.applicable_framework_profile = profile

	def recompute_hour_totals(self):
		self.budgeted_hours_total = sum(flt(row.budgeted_hours) for row in self.team)
		# Actual hours are aggregated from Timesheet in a scheduled job / report,
		# not recomputed synchronously on every save (kept read-only here).

	def enforce_breach_gate(self):
		"""Mirrors the rule in Section 6.4 of the build spec: an engagement
		cannot progress into Partner Sign-off while a Breach-severity Rule Flag
		is open. This function only recomputes the counter; the actual block
		lives in the Workflow transition condition (see fixtures/workflow.json),
		since the same rule needs to be visible in the UI, not just enforced
		silently server-side."""
		self.open_breach_flags = frappe.db.count(
			"CA Rule Flag",
			filters={"engagement": self.name, "severity": "Breach", "status": "Open"},
		)


def validate_team_independence(doc, method=None):
	"""doc_events hook (see hooks.py). Before saving the team table, cross-
	check every staff member against CA Independence Declaration records for
	this client and its related-party group. A declared, un-waived conflict
	blocks the save outright; a waived conflict is allowed through but stays
	visibly flagged on the row so it shows up in QCR review."""

	related_clients = frappe.get_all(
		"CA Related Client", filters={"parent": doc.client}, pluck="related_client"
	)
	client_group = set([doc.client] + related_clients)

	for row in doc.team:
		declarations = frappe.get_all(
			"CA Independence Declaration",
			filters={
				"staff_user": row.staff_user,
				"related_client": ["in", list(client_group)],
				"status": "Active",
			},
			fields=["name", "waived_by_partner"],
		)

		if not declarations:
			row.independence_check_status = "Clear"
			continue

		if any(d.waived_by_partner for d in declarations):
			row.independence_check_status = "Conflict - Waived by Partner"
			continue

		row.independence_check_status = "Conflict - Blocked"
		frappe.throw(
			f"{row.staff_user} has a declared independence conflict against "
			f"{doc.client} or a related party, and it has not been waived by "
			f"a Partner. Remove this team member or obtain a Partner waiver "
			f"via CA Independence Declaration before saving."
		)


@frappe.whitelist()
def pull_financial_statement_from_bookkeeping(engagement, usage_type="Subject of Audit"):
	"""Single-click action wired to a button on the CA Engagement form,
	shown only when has_bookkeeping_source_available is true. Builds (or
	reuses) the client's Financial Statement straight from their linked
	Company's books and links it to this engagement — this is the concrete
	feature: bookkeeping data flowing into the audit/tax/review module
	without re-entry."""

	eng = frappe.get_doc("CA Engagement", engagement)

	from caonline.caonline.api.fs_integration import (
		build_financial_statement,
		link_fs_to_engagement,
		_period_end_for,
	)

	fs_name = build_financial_statement(
		client=eng.client,
		financial_year=eng.financial_year,
		financial_year_end_date=_period_end_for(eng.financial_year, eng.client),
		prefer_live=1,
	)
	link_fs_to_engagement(fs_name, engagement, usage_type)
	return fs_name


def get_permission_query_conditions(user):
	"""Restricts the Engagement list for non-management grades to only the
	engagements they are actually staffed on, and for CA Client Portal users
	to only their own client's engagements. Management grades (Manager and
	above) see the full portfolio per the Role Permission Manager settings
	in the JSON, so no extra condition is added for them here."""

	if not user:
		user = frappe.session.user

	roles = frappe.get_roles(user)

	if "CA Manager" in roles or "CA Partner" in roles or "System Manager" in roles:
		return ""

	if "CA Client Portal" in roles:
		# Client isolation is additionally enforced by the standard User
		# Permission cascade on the `client` link field (see
		# company_provisioning.py) — this condition is a defence-in-depth
		# layer, not the primary mechanism.
		return f"""exists (
			select 1 from `tabCA Client Contact` cc
			where cc.parent = `tabCA Engagement`.client
			and cc.portal_user = {frappe.db.escape(user)}
			and cc.is_active = 1
		)"""

	# Trainee / Job Incharge / Supervisor grades: only engagements they are
	# staffed on.
	return f"""exists (
		select 1 from `tabCA Engagement Team Member` t
		where t.parent = `tabCA Engagement`.name
		and t.staff_user = {frappe.db.escape(user)}
	)"""
