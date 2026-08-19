# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class CAEngagementTask(Document):
	def validate(self):
		self.validate_assignee_is_on_engagement_team()
		self.validate_reviewer_differs_from_assignee()
		self.recompute_hours()
		self.set_status_on_assignment()

	def validate_assignee_is_on_engagement_team(self):
		"""A task can only be handed to someone actually staffed on this
		engagement — prevents the Assignment Manager accidentally routing
		'Non-Performing Loans' to a person who was never independence-cleared
		or budgeted for this client in the first place."""
		if not self.assigned_to:
			return

		team_row = frappe.db.get_value(
			"CA Engagement Team Member",
			{"parent": self.engagement, "staff_user": self.assigned_to},
			["grade", "independence_check_status"],
			as_dict=True,
		)
		if not team_row:
			frappe.throw(
				f"{self.assigned_to} is not on the engagement team for "
				f"{self.engagement}. Add them to CA Engagement.team first, "
				f"then assign this task."
			)
		if team_row.independence_check_status == "Conflict - Blocked":
			frappe.throw(
				f"{self.assigned_to} has a blocked independence conflict on "
				f"this engagement and cannot be assigned any task on it."
			)
		self.assigned_grade = team_row.grade

	def validate_reviewer_differs_from_assignee(self):
		if self.reviewer and self.reviewer == self.assigned_to:
			frappe.throw("The reviewer of a task cannot be the same person it is assigned to.")

	def recompute_hours(self):
		self.hours_variance = flt(self.actual_hours) - flt(self.budgeted_hours)
		self.over_budget = 1 if self.hours_variance > 0 else 0

	def set_status_on_assignment(self):
		if self.assigned_to and self.status == "Unassigned":
			self.status = "Not Started"
		if not self.assigned_to:
			self.status = "Unassigned"


def recompute_actual_hours(task_name):
	"""Called from the Timesheet doc_events (see hooks.py) whenever a
	Timesheet is submitted/updated/cancelled, so CA Engagement Task.actual_hours
	always reflects real logged time rather than staff self-reporting a
	status without the hours to back it up."""
	total = frappe.db.sql(
		"""
		select coalesce(sum(td.hours), 0)
		from `tabTimesheet Detail` td
		inner join `tabTimesheet` ts on ts.name = td.parent
		where td.ca_engagement_task = %s
		and ts.docstatus = 1
		""",
		(task_name,),
	)[0][0]

	frappe.db.set_value("CA Engagement Task", task_name, "actual_hours", flt(total))
	task = frappe.get_doc("CA Engagement Task", task_name)
	task.recompute_hours()
	task.db_update()


def on_timesheet_change(doc, method=None):
	"""doc_events hook target for Timesheet — recomputes every distinct
	CA Engagement Task referenced in this timesheet's rows."""
	task_names = {row.ca_engagement_task for row in doc.time_logs if row.get("ca_engagement_task")}
	for task_name in task_names:
		recompute_actual_hours(task_name)


def get_permission_query_conditions(user):
	"""Trainees and Job Incharges see only tasks assigned to them or tasks
	on engagements they're staffed on as a reviewer/incharge; Manager and
	above see everything (per the Role Permission Manager settings in the
	JSON). This keeps a Junior Trainee's task list from showing every other
	trainee's assignments across the whole firm."""

	if not user:
		user = frappe.session.user

	roles = frappe.get_roles(user)
	if "CA Manager" in roles or "CA Partner" in roles or "System Manager" in roles:
		return ""

	return f"""(
		`tabCA Engagement Task`.assigned_to = {frappe.db.escape(user)}
		or `tabCA Engagement Task`.reviewer = {frappe.db.escape(user)}
		or exists (
			select 1 from `tabCA Engagement Team Member` t
			where t.parent = `tabCA Engagement Task`.engagement
			and t.staff_user = {frappe.db.escape(user)}
			and t.role_on_engagement in ('First Reviewer', 'Second Reviewer', 'Final Sign-off')
		)
	)"""
