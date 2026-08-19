# Copyright (c) 2026, Nabeel Munawar & Co.
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CAClient(Document):
	def validate(self):
		self.validate_unique_contacts()

	def validate_unique_contacts(self):
		"""A Contact should not be attached to this Client more than once,
		and every contact needs exactly one Portal Contact Role so permission
		scoping (see ca_client_contact.json) is unambiguous."""
		seen = set()
		for row in self.contacts:
			if row.contact in seen:
				frappe.throw(
					f"Contact {row.contact} is listed more than once against this client."
				)
			seen.add(row.contact)
			if not row.portal_contact_role:
				frappe.throw(
					f"Contact {row.contact} must have a Portal Contact Role set "
					f"before a portal login can be provisioned."
				)

	def on_update(self):
		# Keep Client-level User Permissions in sync whenever contacts change,
		# so a contact removed from the client immediately loses portal access
		# rather than relying on a separate deprovisioning step.
		self.sync_portal_user_permissions()

	def sync_portal_user_permissions(self):
		from caonline.caonline.api.company_provisioning import (
			ensure_client_user_permission,
			revoke_client_user_permission,
		)

		active_users = {row.portal_user for row in self.contacts if row.is_active and row.portal_user}

		# Grant/confirm access for active, provisioned contacts
		for user in active_users:
			ensure_client_user_permission(user=user, client=self.name)

		# Revoke access for any portal user previously linked to this client
		# that is no longer an active contact (e.g. removed, or marked inactive)
		existing = frappe.get_all(
			"User Permission",
			filters={"allow": "CA Client", "for_value": self.name},
			pluck="user",
		)
		for user in existing:
			if user not in active_users:
				revoke_client_user_permission(user=user, client=self.name)
