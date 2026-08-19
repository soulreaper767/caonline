# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt
#
# The "Assignment Manager" surface: lets a Job Incharge/Manager/Partner see,
# in one place, every audit head that actually has a balance in this
# engagement's Financial Statement (e.g. "Other Income", "Loans & Advances -
# Non-Performing"), which ones already have a task + assignee, which don't,
# and staff them against the engagement team with a budgeted-hours estimate
# — all before anyone opens a spreadsheet to plan the fieldwork.

import frappe
from frappe.utils import flt


# ---------------------------------------------------------------------------
# Step 1 — derive the audit-head worklist from the Financial Statement
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_audit_heads_from_engagement(engagement):
	"""Groups the linked Financial Statement's line items by CA Audit Head
	and returns each head's combined balance plus whether a task already
	exists and who (if anyone) it's assigned to. This is the primary data
	the Assignment Manager screen is built around."""

	eng = frappe.db.get_value(
		"CA Engagement", engagement, ["source_financial_statement", "client"], as_dict=True
	)
	if not eng or not eng.source_financial_statement:
		frappe.throw(
			"This engagement has no Source Financial Statement linked yet. "
			"Build or pull one first (see CA Engagement > Pull Financial "
			"Statement from Bookkeeping, or link an uploaded trial balance)."
		)

	fs_lines = frappe.get_all(
		"CA FS Line Item",
		filters={"parent": eng.source_financial_statement},
		fields=["fs_line_item", "closing_balance"],
	)

	head_totals = {}
	for row in fs_lines:
		if not row.fs_line_item:
			continue
		head = frappe.db.get_value("CA Standard FS Line", row.fs_line_item, "audit_head")
		if not head:
			continue
		head_totals[head] = head_totals.get(head, 0.0) + flt(row.closing_balance)

	existing_tasks = {
		t.audit_head: t
		for t in frappe.get_all(
			"CA Engagement Task",
			filters={"engagement": engagement, "task_type": "Audit Head"},
			fields=["name", "audit_head", "assigned_to", "status", "budgeted_hours", "actual_hours"],
		)
	}

	result = []
	for head, balance in head_totals.items():
		task = existing_tasks.get(head)
		head_meta = frappe.db.get_value(
			"CA Audit Head",
			head,
			["default_risk_rating", "typical_min_grade"],
			as_dict=True,
		)
		result.append(
			{
				"audit_head": head,
				"combined_balance": balance,
				"risk_rating": head_meta.default_risk_rating if head_meta else None,
				"typical_min_grade": head_meta.typical_min_grade if head_meta else None,
				"has_task": bool(task),
				"task": task.name if task else None,
				"assigned_to": task.assigned_to if task else None,
				"status": task.status if task else "Not Yet Created",
				"budgeted_hours": task.budgeted_hours if task else None,
				"actual_hours": task.actual_hours if task else None,
			}
		)

	# Sort so the biggest, unassigned balances surface first — that's the
	# Assignment Manager's actual triage priority.
	result.sort(key=lambda r: (r["has_task"], -abs(r["combined_balance"])))
	return result


# ---------------------------------------------------------------------------
# Step 2 — bulk-create unassigned task stubs for every head with a balance
# ---------------------------------------------------------------------------
@frappe.whitelist()
def bulk_create_tasks_from_fs(engagement):
	"""One click on the Assignment Manager screen: create an unassigned
	CA Engagement Task for every Audit Head present in the FS that doesn't
	already have one. Returns the list of newly created task names."""

	heads = get_audit_heads_from_engagement(engagement)
	created = []

	for row in heads:
		if row["has_task"]:
			continue
		task = frappe.get_doc(
			{
				"doctype": "CA Engagement Task",
				"engagement": engagement,
				"task_type": "Audit Head",
				"audit_head": row["audit_head"],
				"task_title": row["audit_head"],
				"fs_balance_at_assignment": row["combined_balance"],
				"status": "Unassigned",
			}
		).insert()
		created.append(task.name)

	return created


# ---------------------------------------------------------------------------
# Step 3 — assign a task to a specific team member with a time budget
# ---------------------------------------------------------------------------
@frappe.whitelist()
def assign_task(task, assigned_to, budgeted_hours=None, reviewer=None, due_date=None):
	"""The actual assignment action — deliberately a single call so the
	Assignment Manager UI can do this inline (e.g. a table with an
	'Assign' dropdown per row) without opening the full task form. All the
	real validation (team membership, independence, reviewer != assignee)
	still runs through CAEngagementTask.validate() since this just sets
	fields and saves."""

	doc = frappe.get_doc("CA Engagement Task", task)
	doc.assigned_to = assigned_to
	if budgeted_hours is not None:
		doc.budgeted_hours = flt(budgeted_hours)
	if reviewer:
		doc.reviewer = reviewer
	if due_date:
		doc.due_date = due_date
	doc.save()
	return doc.name


@frappe.whitelist()
def get_assignable_team(engagement):
	"""Feeds the assignee dropdown on the Assignment Manager screen — only
	people actually on the engagement's team, with their grade and current
	total workload across all of THIS engagement's tasks, so a Job Incharge
	can see at a glance who's already stretched thin before piling on
	another head."""

	team = frappe.get_all(
		"CA Engagement Team Member",
		filters={"parent": engagement},
		fields=["staff_user", "grade", "independence_check_status"],
	)

	for member in team:
		member["current_task_count"] = frappe.db.count(
			"CA Engagement Task",
			filters={
				"engagement": engagement,
				"assigned_to": member.staff_user,
				"status": ["!=", "Cleared"],
			},
		)
		member["current_budgeted_hours"] = flt(
			frappe.db.sql(
				"""
				select coalesce(sum(budgeted_hours), 0) from `tabCA Engagement Task`
				where engagement = %s and assigned_to = %s and status != 'Cleared'
				""",
				(engagement, member.staff_user),
			)[0][0]
		)

	return team


# ---------------------------------------------------------------------------
# Portfolio-level view — every task across every engagement a given
# Job Incharge / Manager / Supervisor is responsible for, for the
# "My Job Task Board" / "Department Job Board" Kanban boards.
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_my_assignment_queue(user=None):
	user = user or frappe.session.user
	return frappe.get_all(
		"CA Engagement Task",
		filters={"assigned_to": user, "status": ["!=", "Cleared"]},
		fields=[
			"name", "engagement", "task_title", "audit_head", "status",
			"priority", "due_date", "budgeted_hours", "actual_hours", "over_budget",
		],
		order_by="due_date asc",
	)
