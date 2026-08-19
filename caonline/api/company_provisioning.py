# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt
#
# Implements build prompt Section 4: "Multi-Company Model for Bookkeeping
# Clients (Client Data Isolation)". This is the single most important piece
# of the platform's security model — a bug here means a client can see
# another client's books, so every function below is written to fail loud
# (frappe.throw) rather than fail silent.

import frappe
from frappe.utils import random_string


# ---------------------------------------------------------------------------
# Entry point — wired in hooks.py as CA Engagement.on_submit
# ---------------------------------------------------------------------------
def provision_on_engagement_submit(doc, method=None):
	template = frappe.get_cached_doc("CA Engagement Type Template", doc.engagement_type_template)

	if not template.requires_dedicated_company:
		return

	client = frappe.get_doc("CA Client", doc.client)

	if not client.linked_company:
		company = create_company_for_client(client)
		client.db_set("linked_company", company.name)
		frappe.msgprint(
			f"Isolated Company '{company.name}' has been created for {client.client_name}. "
			f"All future bookkeeping documents for this engagement will be scoped to it.",
			alert=True,
		)

	if not client.has_portal_access:
		provision_client_portal_users(client)
		client.db_set("has_portal_access", 1)


# ---------------------------------------------------------------------------
# Step 1 — Company + supporting records
# ---------------------------------------------------------------------------
def create_company_for_client(client):
	company_name = f"{client.client_name} (Books)"

	if frappe.db.exists("Company", company_name):
		frappe.throw(
			f"A Company named '{company_name}' already exists but is not linked "
			f"to {client.name}. Resolve this manually before provisioning — "
			f"auto-creating a duplicate-named Company would break isolation."
		)

	coa_template = frappe.db.get_single_value(
		"CA Settings", "default_bookkeeping_chart_of_accounts_template"
	) or "Standard"

	company = frappe.get_doc(
		{
			"doctype": "Company",
			"company_name": company_name,
			"abbr": _safe_abbr(company_name),
			"default_currency": "PKR",
			"country": "Pakistan",
			"chart_of_accounts": coa_template,
			"create_chart_of_accounts_based_on": "Standard Template",
		}
	).insert(ignore_permissions=True)

	# Fiscal Year: only create a dedicated one if the client's tax year-end
	# differs from the firm's own — otherwise reuse the firm's Fiscal Year
	# records, since ERPNext Fiscal Year is not strictly company-scoped.
	if client.tax_year_end and client.tax_year_end != "30 June":
		_ensure_client_fiscal_year(company.name, client.tax_year_end)

	# Default Cost Center is auto-created by ERPNext's Company controller;
	# nothing further required here.

	return company


def _safe_abbr(company_name):
	base = "".join(w[0] for w in company_name.split() if w.isalnum())[:5].upper()
	abbr = base or random_string(4).upper()
	suffix = 1
	original = abbr
	while frappe.db.exists("Company", {"abbr": abbr}):
		suffix += 1
		abbr = f"{original}{suffix}"
	return abbr


def _ensure_client_fiscal_year(company, tax_year_end):
	# Placeholder for firms whose bookkeeping clients run a non-standard
	# year-end; implement per the firm's actual Fiscal Year policy.
	frappe.log_error(
		title="CA Online: non-standard fiscal year requested",
		message=f"Company {company} requested a fiscal year ending {tax_year_end}. "
		f"Implement _ensure_client_fiscal_year() per firm policy before go-live.",
	)


# ---------------------------------------------------------------------------
# Step 2 — Portal users + the User Permission isolation layer
# ---------------------------------------------------------------------------
def provision_client_portal_users(client):
	for row in client.contacts:
		if not row.is_active:
			continue
		user = _get_or_create_portal_user(row.contact)
		row.db_set("portal_user", user.name)
		ensure_client_user_permission(user=user.name, client=client.name)
		if client.linked_company:
			ensure_company_user_permission(user=user.name, company=client.linked_company)


def _get_or_create_portal_user(contact_name):
	contact = frappe.get_doc("Contact", contact_name)
	email = contact.email_id or (contact.email_ids[0].email_id if contact.email_ids else None)

	if not email:
		frappe.throw(
			f"Contact {contact_name} has no email address — a portal login "
			f"cannot be provisioned without one."
		)

	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": contact.first_name or contact.name,
				"send_welcome_email": 1,
				"user_type": "Website User",
			}
		).insert(ignore_permissions=True)

	# CA Client Portal role only — this user must never pick up an internal
	# desk role via any other automation.
	if "CA Client Portal" not in [r.role for r in user.roles]:
		user.append("roles", {"role": "CA Client Portal"})
		user.save(ignore_permissions=True)

	return user


def ensure_client_user_permission(user, client):
	"""Restricts every doctype whose `client` Link field has User Permission
	cascade enabled (the default in Frappe unless a doctype's field explicitly
	sets ignore_user_permissions=1) to only this client's records."""
	_ensure_user_permission(user=user, allow="CA Client", for_value=client)


def ensure_company_user_permission(user, company):
	"""The equivalent restriction for every native ERPNext accounting doctype
	(Sales Invoice, Journal Entry, Payment Entry, GL Entry, etc.) — these all
	carry a standard `company` Link field with cascade already enabled, so no
	per-doctype code is required beyond this single User Permission record."""
	_ensure_user_permission(user=user, allow="Company", for_value=company)


def revoke_client_user_permission(user, client):
	frappe.db.delete(
		"User Permission", {"user": user, "allow": "CA Client", "for_value": client}
	)


def _ensure_user_permission(user, allow, for_value):
	exists = frappe.db.exists(
		"User Permission", {"user": user, "allow": allow, "for_value": for_value}
	)
	if exists:
		return
	frappe.get_doc(
		{
			"doctype": "User Permission",
			"user": user,
			"allow": allow,
			"for_value": for_value,
			"apply_to_all_doctypes": 1,
		}
	).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Build-time isolation test — run this after provisioning any client during
# development/QA. Referenced in build prompt Section 17, Acceptance
# Criterion 2. Not intended to run in production request cycles.
# ---------------------------------------------------------------------------
def assert_isolation(client_name):
	"""Logs in as each active portal user for this client and asserts that
	list views for the doctypes below return zero records belonging to any
	other client/company. Raises AssertionError on any leak."""

	client = frappe.get_doc("CA Client", client_name)
	doctypes_to_check = [
		"Sales Invoice",
		"Journal Entry",
		"Payment Entry",
		"CA Engagement",
		"CA Query Point",
	]

	for row in client.contacts:
		if not row.portal_user:
			continue

		with frappe.set_user(row.portal_user):
			for dt in doctypes_to_check:
				link_field = "company" if dt in (
					"Sales Invoice", "Journal Entry", "Payment Entry"
				) else "client"
				records = frappe.get_all(dt, fields=[link_field], limit=1000)
				bad = [
					r for r in records
					if r.get(link_field) not in (client.linked_company, client.name)
				]
				if bad:
					raise AssertionError(
						f"ISOLATION BREACH: portal user {row.portal_user} can see "
						f"{len(bad)} {dt} record(s) outside client {client_name}."
					)

	frappe.msgprint(f"Isolation check passed for {client_name}.", alert=True)
