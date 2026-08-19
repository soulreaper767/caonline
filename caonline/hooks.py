app_name = "caonline"
app_title = "CA Online"
app_publisher = "Nabeel Munawar & Co."
app_description = "Complete CA Firm Management System — clients, multi-engagement delivery, standards compliance, billing, and an isolated client portal."
app_email = "info@nabeelmunawar.co"
app_license = "Proprietary"
required_apps = ["frappe/erpnext"]

# ---------------------------------------------------------------------------
# Fixtures — everything shipped as version-controlled config, not clicked
# together in the UI. Export with:
#   bench --site [site] export-fixtures --app caonline
# ---------------------------------------------------------------------------
fixtures = [
	# Role + Role Profile fixture data itself lives in
	# caonline/fixtures/ca_roles.json (fixture *files* are auto-loaded by
	# `bench migrate` for any doctype not otherwise exported via the filters
	# below — this list controls `bench export-fixtures` re-export scope).
	{"dt": "Role", "filters": [["role_name", "like", "CA %"]]},
	{"dt": "Role Profile", "filters": [["role_profile", "like", "CA %"]]},
	{"dt": "Workspace", "filters": [["module", "=", "CA Core"]]},
	{"dt": "Print Format", "filters": [["module", "in", ["CA Core", "CA Audit", "CA Billing"]]]},
	{"dt": "Number Card", "filters": [["module", "=", "CA Core"]]},
	{"dt": "Custom Field", "filters": [["dt", "in", ["Timesheet", "Timesheet Detail"]]]},
	{"dt": "Kanban Board", "filters": [["reference_doctype", "in", ["CA Engagement Task", "CA Query Point"]]]},
	{"dt": "CA Applicable Standard"},
	{"dt": "CA Report Wording Library"},
	{"dt": "CA Audit Head"},
	{"dt": "Workflow", "filters": [["document_type", "=", "CA Engagement"]]},
]

# ---------------------------------------------------------------------------
# Doc events — server-side only. Rule-break detection, company provisioning,
# and segregation-of-duties checks all live here or in the controller files
# they call into. None of this logic is duplicated in Client Scripts.
# ---------------------------------------------------------------------------
doc_events = {
	"CA Engagement": {
		"validate": "caonline.caonline.doctype.ca_engagement.ca_engagement.validate_team_independence",
		"on_submit": [
			"caonline.caonline.api.company_provisioning.provision_on_engagement_submit",
			"caonline.caonline.api.compliance_engine.on_engagement_submit",
			"caonline.caonline.api.working_paper_manager.on_engagement_submit",
		],
	},
	"CA Query Point": {
		"validate": "caonline.caonline.doctype.ca_query_point.ca_query_point.block_self_approval",
	},
	"Timesheet": {
		"on_submit": [
			"caonline.caonline.doctype.ca_engagement_task.ca_engagement_task.on_timesheet_change",
			"caonline.caonline.api.wip_manager.sync_wip_from_timesheet",
		],
		"on_update_after_submit": [
			"caonline.caonline.doctype.ca_engagement_task.ca_engagement_task.on_timesheet_change",
			"caonline.caonline.api.wip_manager.sync_wip_from_timesheet",
		],
		"on_cancel": [
			"caonline.caonline.doctype.ca_engagement_task.ca_engagement_task.on_timesheet_change",
			"caonline.caonline.api.wip_manager.sync_wip_from_timesheet",
		],
	},
}

# Row-level list/report filtering — see get_permission_query_conditions() in
# each controller for the actual logic and the reasoning behind it.
permission_query_conditions = {
	"CA Engagement": "caonline.caonline.doctype.ca_engagement.ca_engagement.get_permission_query_conditions",
	"CA Uploaded Trial Balance": "caonline.caonline.doctype.ca_uploaded_trial_balance.ca_uploaded_trial_balance.get_permission_query_conditions",
	"CA Engagement Task": "caonline.caonline.doctype.ca_engagement_task.ca_engagement_task.get_permission_query_conditions",
}

# ---------------------------------------------------------------------------
# Portal / permission scaffolding
# ---------------------------------------------------------------------------
website_route_rules = [
	{"from_route": "/ca-portal/<path:app_path>", "to_route": "ca-portal"},
]

# Standard User Permission behaviour relies on ERPNext's default "Apply User
# Permission" cascade on Link fields (Company on accounting doctypes, Client
# on CA doctypes). No override needed here as long as no doctype has
# `ignore_user_permissions` set on those link fields — this is checked in
# the Phase-1 acceptance test (see build prompt, Section 17).
