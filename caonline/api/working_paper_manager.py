# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt
#
# Turns an Engagement Type Template's Working Paper Skeleton (CA Working
# Paper Template Item rows — "kinds of working papers this service line
# always needs", e.g. Planning Memo, Materiality Calculation) into real,
# empty CA Working Paper records the team then fills in and attaches files
# to, the same "define once, instantiate per engagement" pattern already
# used for the Compliance Checklist (see api/compliance_engine.py).

import frappe


def on_engagement_submit(doc, method=None):
	"""doc_events hook target for CA Engagement.on_submit (see hooks.py)."""
	instantiate_working_papers_from_template(doc.name)


@frappe.whitelist()
def instantiate_working_papers_from_template(engagement):
	"""Creates one skeleton CA Working Paper per template item that doesn't
	already have a working paper of the same title on this engagement — safe
	to call more than once (e.g. if the template is expanded mid-engagement)
	without duplicating papers staff have already started work on."""
	eng = frappe.get_doc("CA Engagement", engagement)
	template_name = eng.engagement_type_template
	if not template_name:
		return []

	template = frappe.get_doc("CA Engagement Type Template", template_name)
	if not template.working_paper_set:
		return []

	existing_titles = set(
		frappe.get_all(
			"CA Working Paper", filters={"engagement": engagement}, pluck="title"
		)
	)

	created = []
	for row in sorted(template.working_paper_set, key=lambda r: r.sort_order or 0):
		if row.item_name in existing_titles:
			continue
		wp = frappe.new_doc("CA Working Paper")
		wp.engagement = engagement
		wp.title = row.item_name
		wp.wp_type = row.default_wp_type
		wp.audit_head = row.default_audit_head
		wp.insert(ignore_permissions=True)
		created.append(wp.name)

	return created
