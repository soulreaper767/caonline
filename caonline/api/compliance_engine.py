# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt
#
# The one shared entry point for the Standards Compliance Engine's mechanical
# side: opening/closing CA Rule Flag records, and instantiating a per-
# engagement checklist from its template. Every controller that needs to
# raise a flag calls through raise_or_clear_rule_flag() instead of writing
# its own frappe.get_doc("CA Rule Flag", ...) — so "is there already an open
# flag for this exact condition" and "auto-resolve it once the condition
# clears" only has one implementation to get right, not one per caller.
#
# Standard-linked flags (the "Applicable Standard Requirement" rule_source)
# are deliberately NOT auto-raised here yet — CA Applicable Standard ships
# with no requirement content by design (see its doctype description), so
# there is nothing machine-checkable to test against until the firm's
# technical team populates real standards. This module only automates the
# mechanical checks that don't depend on that content: balance-sheet
# tie-out today, more as they're added.

import frappe
from frappe.utils import flt


def on_engagement_submit(doc, method=None):
	"""doc_events hook target for CA Engagement.on_submit (see hooks.py) —
	thin adapter so the whitelisted, name-based API below can also be called
	directly from the desk UI (a manual re-run button) without needing two
	separate implementations."""
	instantiate_checklist_for_engagement(doc.name)


@frappe.whitelist()
def instantiate_checklist_for_engagement(engagement):
	"""Copies the engagement type template's Compliance Checklist Template
	items onto a new CA Engagement Checklist for this engagement. Safe to
	call more than once — a no-op if a checklist already exists, since
	re-instantiating would silently wipe any items already ticked off."""
	existing = frappe.db.exists("CA Engagement Checklist", {"engagement": engagement})
	if existing:
		return existing

	eng = frappe.get_doc("CA Engagement", engagement)
	template_name = frappe.db.get_value(
		"CA Engagement Type Template", eng.engagement_type_template, "checklist_template"
	)
	if not template_name:
		return None

	template = frappe.get_doc("CA Compliance Checklist Template", template_name)
	if not template.items:
		return None

	checklist = frappe.new_doc("CA Engagement Checklist")
	checklist.engagement = engagement
	checklist.checklist_template = template_name
	for row in template.items:
		checklist.append(
			"items",
			{
				"item_text": row.item_text,
				"category": row.category,
				"reference": row.reference,
				"is_mandatory": row.is_mandatory,
			},
		)
	checklist.insert(ignore_permissions=True)
	return checklist.name


def raise_or_clear_rule_flag(
	condition, key, rule_source, severity, description, engagement=None, financial_statement=None
):
	"""If `condition` is true, ensures exactly one Open CA Rule Flag exists
	for this (engagement/financial_statement, key) pair, creating it only if
	one doesn't already exist — so re-saving a document that still has the
	same problem doesn't pile up duplicate flags. If `condition` is false,
	auto-resolves any Open flag previously raised under this key, since the
	underlying issue no longer holds.

	`key` is a short stable string (e.g. "balance_sheet_tie_out") stamped as
	a "[key] " prefix on the flag's description, so this function can find
	its own previously-raised flags again without needing a dedicated field
	just for that — and so a manually-raised flag on the same document
	(which won't carry the prefix) is never mistaken for one of these and
	auto-resolved out from under a reviewer."""

	filters = {"status": "Open", "rule_source": rule_source}
	if engagement:
		filters["engagement"] = engagement
	if financial_statement:
		filters["financial_statement"] = financial_statement

	open_flags = frappe.get_all("CA Rule Flag", filters=filters, fields=["name", "description"])
	prefix = f"[{key}] "
	own_open_flags = [r for r in open_flags if (r.description or "").startswith(prefix)]

	if condition:
		if own_open_flags:
			return own_open_flags[0].name
		flag = frappe.new_doc("CA Rule Flag")
		flag.engagement = engagement
		flag.financial_statement = financial_statement
		flag.rule_source = rule_source
		flag.severity = severity
		flag.status = "Open"
		flag.description = f"{prefix}{description}"
		flag.insert(ignore_permissions=True)
		return flag.name

	for row in own_open_flags:
		frappe.db.set_value(
			"CA Rule Flag",
			row.name,
			{
				"status": "Resolved",
				"resolved_by": frappe.session.user,
				"resolution_note": "Auto-resolved: underlying condition no longer holds.",
			},
		)
	return None
