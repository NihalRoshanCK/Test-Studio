"""Install and migrate hooks."""

import frappe

ROLE = "Test Studio User"


def ensure_role():
	"""before_migrate / after_install: the role that writes and runs tests without being a System Manager.
	It must exist before the doctypes that grant it permissions are synced."""
	if not frappe.db.exists("Role", ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": ROLE, "desk_access": 1}).insert(ignore_permissions=True)


def has_app_permission():
	"""Desk apps screen: show Test Studio to the people who can open it."""
	return bool(frappe.has_permission("Test Case", "read"))
