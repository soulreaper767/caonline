# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt
#
# Bridges submitted Timesheet time-logs into billable WIP value, the same
# "read from the one place hours actually get logged" pattern as
# CA Engagement Task.actual_hours (see ca_engagement_task.py). A single
# Timesheet can carry rows against more than one engagement, so this creates
# one CA WIP Entry per (timesheet, engagement) pair, not one per timesheet.

import frappe
from frappe.utils import flt, getdate


def sync_wip_from_timesheet(doc, method=None):
	"""doc_events hook target for Timesheet on_submit / on_update_after_submit
	/ on_cancel (see hooks.py) — mirrors on_timesheet_change()'s reuse across
	all three events in ca_engagement_task.py."""
	engagements = {row.ca_engagement for row in doc.time_logs if row.get("ca_engagement")}

	for engagement in engagements:
		hours = sum(
			flt(row.hours)
			for row in doc.time_logs
			if row.get("ca_engagement") == engagement
		)
		existing = frappe.db.get_value(
			"CA WIP Entry", {"timesheet": doc.name, "engagement": engagement}, "name"
		)

		if doc.docstatus == 2 or hours == 0:
			_remove_or_zero(existing)
			continue

		_upsert_wip_entry(existing, doc, engagement, hours)


def _remove_or_zero(wip_entry_name):
	if not wip_entry_name:
		return
	billed = frappe.db.get_value("CA WIP Entry", wip_entry_name, "billed")
	if billed:
		frappe.throw(
			f"{wip_entry_name} has already been billed and its source Timesheet "
			f"was cancelled or emptied. Resolve this manually (credit note / "
			f"reversal) rather than silently deleting billed WIP."
		)
	frappe.delete_doc("CA WIP Entry", wip_entry_name, ignore_permissions=True)


def _upsert_wip_entry(existing_name, timesheet, engagement, hours):
	grade = timesheet.get("ca_grade_at_entry")
	staff_user = frappe.db.get_value("Employee", timesheet.employee, "user_id") if timesheet.employee else None
	service_line = frappe.db.get_value(
		"CA Engagement Type Template",
		frappe.db.get_value("CA Engagement", engagement, "engagement_type_template"),
		"service_line",
	)
	rate = get_hourly_rate(grade, service_line, timesheet.start_date or frappe.utils.nowdate())
	billable_value = flt(hours) * flt(rate)

	if existing_name:
		wip = frappe.get_doc("CA WIP Entry", existing_name)
		if wip.billed:
			frappe.throw(
				f"{existing_name} has already been billed — its source Timesheet "
				f"was changed after billing. Resolve this manually rather than "
				f"silently revaluing billed WIP."
			)
	else:
		wip = frappe.new_doc("CA WIP Entry")
		wip.timesheet = timesheet.name
		wip.engagement = engagement

	wip.staff_user = staff_user
	wip.grade = grade
	wip.hours = hours
	wip.hourly_rate = rate
	wip.billable_value = billable_value

	if existing_name:
		wip.save(ignore_permissions=True)
	else:
		wip.insert(ignore_permissions=True)


def get_hourly_rate(grade, service_line, on_date):
	"""Prefers a rate card specific to this service_line, falling back to the
	grade's blank-service_line default rate — see CA Billing Rate Card's
	description for that convention."""
	on_date = getdate(on_date)

	for filters in (
		{"grade": grade, "service_line": service_line},
		{"grade": grade, "service_line": ["in", ["", None]]},
	):
		rate = _find_effective_rate(filters, on_date)
		if rate is not None:
			return rate
	return 0.0


def _find_effective_rate(filters, on_date):
	cards = frappe.get_all(
		"CA Billing Rate Card",
		filters=filters,
		fields=["hourly_rate", "effective_from", "effective_to"],
		order_by="effective_from desc",
	)
	for card in cards:
		starts_ok = getdate(card.effective_from) <= on_date
		ends_ok = not card.effective_to or getdate(card.effective_to) >= on_date
		if starts_ok and ends_ok:
			return flt(card.hourly_rate)
	return None
