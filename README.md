# CA Online — Frappe v16 App

Complete CA firm automation: clients, multi-service-line engagement delivery,
staffing/timesheets/assignments, standards compliance (user-defined,
period-scoped), working papers with casting/tie-out checks, review hierarchy
and QCR, engagement workflow with a breach gate, billing/WIP, and a starter
corporate report library.

Started as a Phase-1 skeleton (Role hierarchy, `CA Client`/`CA Engagement`
core, segregation-of-duties, independence checking, Company
auto-provisioning/client data isolation) and has since been built out through
nine phases:

- **Phase 0** — closed every broken Link/Table reference from the original
  skeleton (`CA Client Sector`, `CA Applicable Standard`,
  `CA Client Framework Profile`, `CA Compliance Checklist Template/Item`,
  `CA Rule Flag`, `CA Working Paper(/Template Item)`, `CA Required Grade`,
  `CA Settings`, `CA Billing Rate Card`, `CA Report Wording Library`).
- **Phase 1** — Compliance engine: `CA Engagement Checklist`, and
  `api/compliance_engine.py`'s `raise_or_clear_rule_flag()` — the one shared
  place a mechanical check opens/auto-resolves a `CA Rule Flag` (wired today
  to `CA Financial Statement`'s balance-tie check).
- **Phase 2** — `api/working_paper_manager.py` instantiates
  `CA Working Paper` skeletons from an Engagement Type Template's Working
  Paper Skeleton on engagement submit.
- **Phase 3** — Review hierarchy (`CA Review Sign-off`, one doctype for every
  level) and the QCR module (`CA QCR Review`/`CA QCR Finding`, reviewer
  independence enforced).
- **Phase 4** — `fixtures/ca_engagement_workflow.json`: a real Workflow for
  `CA Engagement` gating the Review → Partner Sign-off transition on
  `open_breach_flags == 0`.
- **Phase 5** — Billing/WIP: `CA Billing Rate Card` + `CA WIP Entry`,
  computed automatically off submitted Timesheets via
  `api/wip_manager.py`.
- **Phase 6** — Added the missing "Merger / Restructuring Advisory" service
  line. Due Diligence/Valuation/Merger deliberately reuse
  `CA Engagement` + `CA Working Paper` rather than bespoke doctypes.
- **Phase 7** — Data import: no new doctype: `CA Uploaded Trial Balance` +
  Frappe's native Data Import tool already cover this.
- **Phase 8** — `fixtures/ca_print_formats.json`: three starter Print
  Formats (Engagement Letter, Financial Statement, Draft Audit Report)
  pulling firm identity from `CA Settings` and boilerplate wording from
  `CA Report Wording Library`.
- **Phase 9** — Portal API hardening: verified none of the above leak to
  `CA Client Portal` by omission. Actual `www/` portal pages are still not
  built — this remains backend/API surface only (see Known gaps).
- **Desk UI layer** — a single "CA Online" Workspace (sidebar entry,
  shortcuts, Kanban boards, cards grouping every doctype by area, charts and
  number cards), 5 Number Cards, 3 Dashboard Charts, 6 Query Reports, and 2
  more Kanban boards (Query Point review queue, Rule Flag triage), plus
  `Company.ca_client`, `Sales Invoice.ca_engagement`, and `Employee.ca_grade`
  custom fields (the last one auto-feeding `Timesheet.ca_grade_at_entry` via
  `fetch_from`). Roles, Custom Fields, Kanban Boards, Print Formats, and the
  Workflow ship as standard `hooks.fixtures` (`caonline/fixtures/*.json`).
  Workspace, Number Cards, Dashboard Charts, and Reports ship differently —
  via `caonline/setup_data/*.json` synced by an explicit `after_migrate`
  hook (`install.py`) that also clears the server cache — see that file's
  docstring for why generic fixture sync isn't reliable enough for the
  Workspace sidebar specifically. `after_migrate` also grants the
  `Administrator` account the `CA Partner` role so there's at least one
  fully-set-up login immediately after install, with no manual role
  assignment step required first.

  This repo does **not** create real `User` accounts on install (that would
  mean fabricating email addresses/passwords for people who don't exist) —
  "users" here means the role hierarchy is fully installed and ready to
  assign to whichever real accounts the firm creates.

## What's included

```
caonline/
  hooks.py                                — doc_events, fixtures, permission_query_conditions wiring
  modules.txt                             — the 7 app modules
  fixtures/ca_roles.json                  — full Role + Role Profile hierarchy
  doctype/ca_client/                      — Client master + isolation fields
  doctype/ca_client_contact/               — contact child table w/ Portal Contact Role
  doctype/ca_related_client/               — related-party link table
  doctype/ca_engagement/                  — core Engagement doctype + controller
  doctype/ca_engagement_team_member/       — team child table w/ independence status
  doctype/ca_engagement_type_template/     — per-service-line template incl. requires_dedicated_company
  doctype/ca_independence_declaration/     — conflict declarations + Partner-only waiver
  doctype/ca_query_point/                 — review notes w/ self-approval block
  api/company_provisioning.py             — THE isolation engine (Section 4 of the build prompt)

  # Cross-module data bridge (bookkeeping -> audit -> tax -> internal audit)
  doctype/ca_standard_fs_line/            — standardised FS line-item taxonomy (master data)
  doctype/ca_financial_statement/         — the ONE shared FS artifact, used by audit/review/compilation/tax
  doctype/ca_fs_line_item/                 — FS line child table, mapped from client's own CoA
  doctype/ca_fs_used_by_engagement/        — link table: which engagements rely on this FS, and how
  doctype/ca_uploaded_trial_balance/      — fallback path for clients with no live bookkeeping source
  doctype/ca_tb_mapped_line/               — uploaded TB child table w/ learned auto-mapping
  api/fs_integration.py                   — pulls GL data from a bookkeeping client's isolated Company
                                             straight into the FS used by their Audit/Review/Tax engagement

  # Tax Working module
  doctype/ca_tax_working/                 — computation sheet (accounting profit -> taxable income)
  doctype/ca_tax_adjustment/               — add-back/allowance/credit child table w/ ITO 2001 references

  # Internal Audit module
  doctype/ca_internal_audit_plan/          — risk-based auditable universe per client, w/ SA-overlap check
  doctype/ca_internal_audit_area/          — child table of auditable areas/processes
  doctype/ca_internal_audit_finding/       — findings w/ mandatory re-test-before-close enforcement

  # Assignment Manager (task-level staffing, e.g. one person on "Other
  # Income", another on "Non-Performing Loans")
  doctype/ca_audit_head/                  — master list of assignable audit work areas
  doctype/ca_engagement_task/             — the actual assignment record, w/ timesheet-driven actual_hours
  api/assignment_manager.py               — derives the head worklist from the FS, bulk-creates tasks,
                                             assigns them, and reports workload per team member
  fixtures/ca_timesheet_custom_fields.json — links ERPNext's native Timesheet back to CA Engagement Task
  fixtures/ca_kanban_boards.json           — the Assignment Manager Kanban board fixture

  # Standards Compliance Engine (Phase 0 + Phase 1)
  doctype/ca_client_sector/                — sector/industry master (CA Client.sector target)
  doctype/ca_applicable_standard/          — generic, period-scoped standard/law/regulation master — ships empty
  doctype/ca_client_framework_profile/     — which standards apply to a client for a period, w/ single-current enforcement
  doctype/ca_compliance_checklist_template/ — per-service-line checklist template (+ ca_compliance_checklist_item child)
  doctype/ca_engagement_checklist/         — per-engagement instantiated checklist (+ ca_engagement_checklist_item child)
  doctype/ca_rule_flag/                    — mechanical/standard/independence flag log, severity incl. Breach
  api/compliance_engine.py                 — raise_or_clear_rule_flag() + checklist instantiation, the one shared
                                              entry point every mechanical check should call through

  # Working Papers (Phase 0 + Phase 2)
  doctype/ca_working_paper/                — casting/tie-out-checked schedules; review notes live on CA Query Point
  doctype/ca_working_paper_template_item/  — firm-wide library of "kinds of working papers" (child table)
  api/working_paper_manager.py             — instantiates working papers from a template on engagement submit

  # Review Hierarchy / QCR (Phase 3)
  doctype/ca_review_sign_off/              — one generic sign-off doctype for every review level
  doctype/ca_qcr_review/                   — independent post-issuance quality review (+ ca_qcr_finding child)

  # Engagement Workflow (Phase 4)
  fixtures/ca_workflow_states.json         — the 10 CA Engagement status states as Workflow State masters
  fixtures/ca_workflow_actions.json        — the transition action labels as Workflow Action Master records
  fixtures/ca_engagement_workflow.json     — the Workflow itself; Review -> Partner Sign-off gated on open_breach_flags

  # Billing / WIP (Phase 5)
  doctype/ca_billing_rate_card/            — grade x service_line hourly rates, overlapping-period validated
  doctype/ca_wip_entry/                    — one row per (Timesheet, Engagement), computed off submitted timesheets
  api/wip_manager.py                       — sync_wip_from_timesheet() + rate-card lookup

  # Settings & Reports (Phase 0 + Phase 8)
  doctype/ca_settings/                     — firm-wide Single: bookkeeping defaults, fiscal year policy, report identity
  doctype/ca_report_wording_library/       — reusable opinion/disclaimer/boilerplate wording — ships empty
  fixtures/ca_print_formats.json           — Engagement Letter, Financial Statement, Draft Audit Report
```

## How task-level assignment works (e.g. one person on "Other Income", another on NPLs)

`CA Standard FS Line` now carries an `audit_head` field — a grouping layer
between raw GL accounts and assignable work. Multiple FS lines (e.g.
"Trade Receivables — Related Party", "Trade Receivables — Third Party") can
roll into one `CA Audit Head` like *"Loans & Advances - Non-Performing"*, or
each FS line can be its own head if that's finer than the firm wants.

1. **Derive the worklist**: `assignment_manager.get_audit_heads_from_engagement()`
   groups the engagement's linked `CA Financial Statement` line items by
   `audit_head` and returns each head's combined balance, its default risk
   rating, and whether a task already exists for it — biggest unassigned
   balances sort to the top.
2. **Bulk-create task stubs**: `bulk_create_tasks_from_fs()` creates an
   *Unassigned* `CA Engagement Task` for every head with a balance and no
   task yet, snapshotting the balance at that moment
   (`fs_balance_at_assignment`) so the Assignment Manager can see materiality
   at a glance when deciding who to staff.
3. **Assign**: `assign_task(task, assigned_to, budgeted_hours, reviewer,
   due_date)` is a single call an inline "Assign" dropdown can hit directly.
   `CAEngagementTask.validate()` then enforces:
   - the assignee must actually be on `CA Engagement.team` (not just any
     firm staff member),
   - a blocked independence conflict on that engagement blocks the
     assignment outright,
   - the reviewer can never be the same person as the assignee.
4. **Timesheets roll up automatically**: two Custom Fields
   (`ca_engagement` and `ca_engagement_task`) are added to `Timesheet
   Detail` via fixture, so staff log time against a specific task the same
   way they'd log time against anything else in ERPNext. `on_timesheet_change`
   (wired in `hooks.py` against `Timesheet.on_submit` /
   `on_update_after_submit` / `on_cancel`) recomputes
   `CA Engagement Task.actual_hours` and its budget variance every time.
5. **Workload visibility**: `get_assignable_team(engagement)` shows a Job
   Incharge each team member's current task count and total budgeted hours
   on this engagement before they assign one more thing to them.
6. **The board**: `CA Assignment Manager - Task Board` (a fixture-shipped
   Kanban Board on `CA Engagement Task`, columns Unassigned → Not Started →
   In Progress → Under Review → Query Raised → Cleared) is the day-to-day
   view — filterable to one engagement to plan a job's fieldwork, or to one
   assignee to see a single person's queue across every engagement they're
   on.

## How the bookkeeping -> audit/tax/internal-audit bridge works

If a client has **both** a Bookkeeping engagement (with an isolated Company,
per Section 4) **and** an Audit, Review, Compilation, or Tax engagement in
the same period, the firm should never have to re-key the same numbers
twice. The bridge works like this:

1. `fs_integration.has_live_bookkeeping_source(client)` checks whether the
   client has an active Bookkeeping engagement with a `linked_company`.
   `CA Engagement.has_bookkeeping_source_available` surfaces this as a
   read-only flag on every non-bookkeeping engagement for that client.
2. When true, staff can click **"Pull Financial Statement from Bookkeeping"**
   on the Audit/Review/Tax engagement (wired to
   `ca_engagement.pull_financial_statement_from_bookkeeping`), which:
   - Reads a period-end trial balance directly from `GL Entry` for the
     client's own `Company` (`fs_integration.get_source_trial_balance`) —
     this is a firm-staff-side read, entirely separate from the client
     portal user's restricted access, so it does not weaken isolation.
   - Maps each GL account to a `CA Standard FS Line` using whatever mapping
     was confirmed on the client's last submitted Financial Statement
     (learn-once-reuse-every-period, same pattern as the manual-upload path).
   - Builds a `CA Financial Statement` and links it to the engagement via
     `CA FS Used By Engagement` (`usage_type` records *why* — e.g. "Subject
     of Audit" vs "Feeds Tax Computation").
3. If no live bookkeeping source exists, the same `CA Financial Statement`
   is instead built from a `CA Uploaded Trial Balance` (client- or
   staff-uploaded), with its own learned account mapping.
4. **Tax Working** (`CA Tax Working`) then pulls `accounting_profit`
   straight from whichever `CA Financial Statement` is linked to its
   Engagement, via the **"Pull Accounting Profit from FS"** button
   (`ca_tax_working.pull_accounting_profit`) — so the tax computation's
   starting point is provably the same number the audit/bookkeeping side
   already produced, not a second manual summation.
5. **Internal Audit** (`CA Internal Audit Plan`) is deliberately kept on a
   *separate* engagement/team from Statutory Audit for the same client —
   `check_statutory_audit_overlap()` blocks saving if any staff member is on
   both teams, to protect independence — but shares the same Client/
   Engagement backbone and can equally reference the client's Financial
   Statement as background context for risk assessment.

**Important boundary, by design**: this bridge only ever *reads* the
client's bookkeeping data into the audit/tax side. It never posts audit
adjustments back into the client's own accounting ledgers — those live in
`CA Financial Statement`, `CA Rule Flag`, and `CA Tax Working` only, so the
client's own books remain exactly what their bookkeeper recorded.

## Install (against an existing Frappe v16 bench with ERPNext installed)

```bash
cd ~/frappe-bench
bench get-app caonline /path/to/this/folder   # or your git remote once pushed
bench --site [sitename] install-app caonline
bench --site [sitename] migrate
```

This loads the DocTypes and the Role/Role Profile fixtures. Nothing else is
auto-created — Engagement Type Templates, the `CA Settings` singleton (for
`default_bookkeeping_chart_of_accounts_template`), and Sector master data
still need to be entered once, either manually or via a data-import script
for the firm's actual service-line list (Section 3 of the build prompt).

## Verifying the isolation mechanism (do this before trusting it with real data)

1. Create a `CA Client` with `entity_type = Company - Private`, one contact
   with a real email and `Portal Contact Role = Primary / Authorized Signatory`.
2. Create a `CA Engagement Type Template` with `service_line = Bookkeeping`
   and `requires_dedicated_company = 1`.
3. Create and **submit** a `CA Engagement` against that client and template.
   - This should auto-create a Company named `"<Client Name> (Books)"`,
     set `CA Client.linked_company`, create/attach a portal User, and
     insert two `User Permission` records (`CA Client` and `Company`).
4. From the Python console:
   ```python
   from caonline.caonline.api.company_provisioning import assert_isolation
   assert_isolation("<the client name>")
   ```
   This should print "Isolation check passed" — if it raises
   `AssertionError`, **do not proceed to production** until fixed. Repeat
   with a second client and confirm neither portal user can see the other's
   Sales Invoices, Journal Entries, or Engagements.

## Known gaps to close before this is production-ready

- `_ensure_client_fiscal_year()` is still a stub — implement per the firm's
  actual policy for clients with a non-June year-end (`CA Settings.
  firm_default_fiscal_year_end` is now available for it to read).
- `_period_end_for()` in `fs_integration.py` is still a stub returning
  today's date — `financial_year` is a free-text field, not a structured
  date range, so proper Fiscal-Year-based period-end resolution is still
  outstanding.
- `CA Applicable Standard` and `CA Report Wording Library` ship with **zero
  content by design** — the doctypes/structure exist, but the firm's real
  standards catalogue and opinion/disclaimer wording still need to be
  entered. Standard-linked Rule Flags (the "Applicable Standard Requirement"
  `rule_source`) are not auto-raised anywhere yet because there's no
  requirement content to check against — only the mechanical balance-tie
  check is automated so far.
- Tax Working's `tax_liability` field is entered manually — progressive
  tax-slab computation logic (per ITO 2001 rates) is not yet implemented;
  only the add-back/allowance/credit netting is automated.
- No desk Page/UI wraps `assignment_manager.py`'s functions, or the new
  `compliance_engine.py` / `working_paper_manager.py` / `wip_manager.py`
  functions, into a single screen — everything is callable (e.g. from a
  custom Page or a Vite/React panel) but no such UI is built. The Workspace
  gives shortcuts/Kanban/reports access to the underlying doctypes, not a
  purpose-built Assignment Manager screen.
- No `www/` client portal pages exist behind the `/ca-portal` route stub —
  deliberately out of scope for this pass (backend/API surface only); a
  real frontend still needs to be built to consume it.
- The three shipped Print Formats are unverified against a live bench —
  Jinja fails at render time, not at `bench migrate`, so smoke-test them
  after install.
- New doctypes from Phases 0-5 use role-based permissions only, not
  row-level `permission_query_conditions` scoping trainees/incharges to
  their own engagements (the pattern `CA Engagement`/`CA Engagement Task`
  use) — worth adding if a Junior Trainee seeing e.g. every open Rule Flag
  firm-wide (not just their own engagements') turns out to be too broad.
