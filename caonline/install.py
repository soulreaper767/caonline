# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt
#
# Workspace, Number Card, Dashboard Chart, and Report are shipped here via
# explicit ORM upsert on every migrate, NOT via hooks.fixtures. Reason:
# fixtures/*.json is the right mechanism for plain data records (Role,
# Custom Field, Kanban Board, Print Format all work fine that way — see
# hooks.py), but Workspace's sidebar rendering also depends on Frappe's
# server-side cache, and getting a hand-authored Workspace record to
# actually show up reliably needs an explicit frappe.clear_cache() after
# it's written — generic fixture sync doesn't do that. Keeping the JSON
# under setup_data/ (not fixtures/) means it's processed exactly once, here,
# with no ambiguity about which mechanism owns it.

import json
import os

import frappe

SETUP_DATA_DIR = os.path.join(os.path.dirname(__file__), "setup_data")

FILES_TO_SYNC = [
	"ca_workspace.json",
	"ca_number_cards.json",
	"ca_dashboard_charts.json",
	"ca_reports.json",
]


def after_migrate():
	for filename in FILES_TO_SYNC:
		_upsert_records(filename)
	_ensure_administrator_has_full_access()
	frappe.clear_cache()
	frappe.db.commit()


def _ensure_administrator_has_full_access():
	"""So there's at least one immediately-usable account after install
	without requiring a manual role-assignment step first — Administrator
	always exists on a fresh site and already bypasses permissions, but
	giving it CA Partner explicitly means it also shows up correctly in
	CA-specific role-based UI (e.g. Workflow's allow_edit) rather than
	relying only on the System Manager bypass."""
	if not frappe.db.exists("User", "Administrator"):
		return
	user = frappe.get_doc("User", "Administrator")
	if "CA Partner" not in [r.role for r in user.roles]:
		user.append("roles", {"role": "CA Partner"})
		user.save(ignore_permissions=True)


def _upsert_records(filename):
	path = os.path.join(SETUP_DATA_DIR, filename)
	with open(path, encoding="utf-8") as f:
		records = json.load(f)

	for record in records:
		doctype = record["doctype"]
		name = record.get("name") or record.get("label") or record.get("number_card_name")

		if frappe.db.exists(doctype, name):
			doc = frappe.get_doc(doctype, name)
			doc.update(record)
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc(record)
			doc.insert(ignore_permissions=True)
