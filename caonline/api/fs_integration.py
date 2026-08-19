# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt
#
# Implements the cross-module data bridge: if a client is BOTH a bookkeeping
# client (has an isolated Company per company_provisioning.py) AND an audit
# / tax / review client, this module pulls the client's own books straight
# into the Financial Statement used by those other engagements — instead of
# the firm re-typing a trial balance the firm itself already booked.
#
# Design rule: this module only ever READS from the client's Company books.
# It never writes back into the client's accounting ledgers from the audit
# or tax side — audit adjustments live in CA Financial Statement / CA Rule
# Flag / CA Tax Working, never as posted Journal Entries in the client's
# own Company, so the client's books stay exactly what the client's
# bookkeeper actually recorded.

import frappe
from frappe.utils import flt, getdate


# ---------------------------------------------------------------------------
# Discovery — is this client also a bookkeeping client with live books?
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_related_engagements(client, financial_year=None):
	"""Returns every other engagement for this client (optionally scoped to
	one financial year) grouped by service line, so the UI can show 'This
	client also has an active Bookkeeping engagement — pull live data?'
	prompts wherever an Audit, Review, Compilation or Tax engagement is
	opened."""
	filters = {"client": client}
	if financial_year:
		filters["financial_year"] = financial_year

	engagements = frappe.get_all(
		"CA Engagement",
		filters=filters,
		fields=[
			"name", "engagement_title", "engagement_type_template",
			"financial_year", "status",
		],
	)
	for e in engagements:
		e["service_line"] = frappe.db.get_value(
			"CA Engagement Type Template", e.engagement_type_template, "service_line"
		)
	return engagements


def has_live_bookkeeping_source(client):
	"""True only if the client has a linked_company AND at least one active
	(non-cancelled) Bookkeeping engagement against it — a client that once
	had bookkeeping but has since terminated that engagement should fall
	back to uploaded trial balances, not silently keep reading stale books."""
	client_doc = frappe.db.get_value("CA Client", client, ["linked_company"], as_dict=True)
	if not client_doc or not client_doc.linked_company:
		return False

	active_bk = frappe.get_all(
		"CA Engagement",
		filters={
			"client": client,
			"docstatus": ["!=", 2],
			"status": ["!=", "Closed"],
		},
		fields=["name", "engagement_type_template"],
	)
	for e in active_bk:
		service_line = frappe.db.get_value(
			"CA Engagement Type Template", e.engagement_type_template, "service_line"
		)
		if service_line == "Bookkeeping":
			return True
	return False


# ---------------------------------------------------------------------------
# Pulling the trial balance from live books
# ---------------------------------------------------------------------------
def get_source_trial_balance(client, financial_year_end_date):
	"""Pulls a period-end trial balance directly from GL Entry for the
	client's linked_company. This runs under the FIRM staff member's own
	permissions (Manager/Job Incharge etc, who have normal company access
	via their own Role Permissions) — it is never called in a request
	context belonging to the client's own restricted portal user, so the
	isolation model in company_provisioning.py is not bypassed by this
	function; it is a separate, firm-side read path into the same data."""

	company = frappe.db.get_value("CA Client", client, "linked_company")
	if not company:
		frappe.throw(f"Client {client} has no linked_company — cannot pull a live trial balance.")

	rows = frappe.db.sql(
		"""
		select account, sum(debit) as debit, sum(credit) as credit
		from `tabGL Entry`
		where company = %s
		and posting_date <= %s
		and is_cancelled = 0
		group by account
		having sum(debit) != 0 or sum(credit) != 0
		order by account
		""",
		(company, getdate(financial_year_end_date)),
		as_dict=True,
	)
	return rows


# ---------------------------------------------------------------------------
# Building / refreshing a CA Financial Statement from whichever source
# applies
# ---------------------------------------------------------------------------
@frappe.whitelist()
def build_financial_statement(client, financial_year, financial_year_end_date, prefer_live=1):
	"""Central entry point. Called when creating an Audit, Review,
	Compilation, or Tax engagement's Financial Statement. Decides the data
	source, builds the CA Financial Statement, and returns it unsubmitted
	for staff review — nothing here auto-submits, since a human must always
	review the mapping and control totals before the FS is relied on."""

	use_live = bool(int(prefer_live)) and has_live_bookkeeping_source(client)

	fs = frappe.new_doc("CA Financial Statement")
	fs.client = client
	fs.financial_year = financial_year

	if use_live:
		fs.data_source = "Live from Linked Bookkeeping Company"
		bk_engagement = _get_active_bookkeeping_engagement(client)
		fs.source_bookkeeping_engagement = bk_engagement
		_populate_lines_from_gl(fs, client, financial_year_end_date)
	else:
		fs.data_source = "Uploaded Trial Balance"
		uploaded = frappe.db.get_value(
			"CA Uploaded Trial Balance",
			{"client": client, "financial_year": financial_year},
			"name",
			order_by="creation desc",
		)
		if not uploaded:
			frappe.throw(
				f"No live bookkeeping source and no CA Uploaded Trial Balance found "
				f"for {client} / {financial_year}. Upload a trial balance first, or "
				f"ask the client to upload one via the portal."
			)
		fs.source_uploaded_trial_balance = uploaded
		_populate_lines_from_uploaded_tb(fs, uploaded)

	fs.insert()
	return fs.name


def rebuild_financial_statement(financial_statement):
	"""Re-pull from the same configured source without disturbing engagement
	linkages already recorded in used_by_engagements."""
	fs = frappe.get_doc("CA Financial Statement", financial_statement)
	if fs.docstatus == 1:
		frappe.throw("Cannot refresh a submitted Financial Statement. Amend it first.")

	fs.line_items = []
	if fs.data_source == "Live from Linked Bookkeeping Company":
		_populate_lines_from_gl(fs, fs.client, _period_end_for(fs.financial_year, fs.client))
	else:
		_populate_lines_from_uploaded_tb(fs, fs.source_uploaded_trial_balance)

	fs.save()
	return fs.name


def _get_active_bookkeeping_engagement(client):
	return frappe.db.get_value(
		"CA Engagement",
		{
			"client": client,
			"status": ["!=", "Closed"],
			"docstatus": ["!=", 2],
		},
		"name",
		order_by="creation desc",
	)


def _period_end_for(financial_year, client):
	# Placeholder resolution — in the full build this reads the client's
	# Fiscal Year record; kept simple here since financial_year is currently
	# a free-text field on CA Engagement / CA Financial Statement.
	return frappe.utils.nowdate()


def _populate_lines_from_gl(fs, client, period_end_date):
	gl_rows = get_source_trial_balance(client, period_end_date)
	mapping_cache = _get_client_account_mapping_cache(client)

	for row in gl_rows:
		closing = flt(row.debit) - flt(row.credit)
		mapped_line = mapping_cache.get(row.account)
		fs.append(
			"line_items",
			{
				"source_account": row.account,
				"fs_line_item": mapped_line,
				"closing_balance": closing,
			},
		)


def _populate_lines_from_uploaded_tb(fs, uploaded_tb_name):
	tb = frappe.get_doc("CA Uploaded Trial Balance", uploaded_tb_name)
	if not tb.ties_out:
		frappe.msgprint(
			f"Warning: source trial balance {uploaded_tb_name} does not tie out "
			f"(debit != credit). The Financial Statement built from it will "
			f"almost certainly fail the balance check.",
			indicator="orange",
			alert=True,
		)
	for row in tb.lines:
		closing = flt(row.debit) - flt(row.credit)
		fs.append(
			"line_items",
			{
				"source_account": row.client_account_name,
				"fs_line_item": row.mapped_fs_line,
				"closing_balance": closing,
			},
		)


def _get_client_account_mapping_cache(client):
	"""Reuses whatever GL-account -> Standard FS Line mapping was confirmed
	on this client's most recent Financial Statement, exactly the same
	'learn once, reuse every period' behaviour as the uploaded-TB path."""
	prior_fs = frappe.db.get_value(
		"CA Financial Statement",
		{"client": client, "docstatus": 1},
		"name",
		order_by="creation desc",
	)
	if not prior_fs:
		return {}
	rows = frappe.get_all(
		"CA FS Line Item",
		filters={"parent": prior_fs},
		fields=["source_account", "fs_line_item"],
	)
	return {r.source_account: r.fs_line_item for r in rows if r.fs_line_item}


# ---------------------------------------------------------------------------
# Linking a Financial Statement to whichever engagement(s) rely on it
# ---------------------------------------------------------------------------
@frappe.whitelist()
def link_fs_to_engagement(financial_statement, engagement, usage_type):
	"""Attaches one CA Financial Statement to an Engagement (Audit, Review,
	Tax, Compilation, etc). This is what makes 'the audit module' actually
	see the bookkeeping-derived numbers: the Audit engagement's working
	papers, checklist, and Rule Flag engine all key off
	CA Engagement.source_financial_statement, set here."""

	fs = frappe.get_doc("CA Financial Statement", financial_statement)
	already_linked = any(row.engagement == engagement for row in fs.used_by_engagements)
	if not already_linked:
		fs.append("used_by_engagements", {"engagement": engagement, "usage_type": usage_type})
		fs.save()

	frappe.db.set_value("CA Engagement", engagement, "source_financial_statement", financial_statement)


@frappe.whitelist()
def get_accounting_profit(financial_statement):
	"""Used by the Tax Working module (ca_tax_working.py) to pull the
	starting 'accounting profit' figure straight from the FS instead of
	the tax preparer re-summing income/expense lines by hand."""
	income, expense = 0.0, 0.0
	fs = frappe.get_doc("CA Financial Statement", financial_statement)
	for row in fs.line_items:
		category = frappe.db.get_value("CA Standard FS Line", row.fs_line_item, "category")
		if category == "Income":
			income += flt(row.closing_balance)
		elif category == "Expense":
			expense += flt(row.closing_balance)
	return income - expense
