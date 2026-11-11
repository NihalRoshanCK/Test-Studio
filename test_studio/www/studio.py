import json
import os

import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=" + frappe.utils.quote(frappe.request.path)
		raise frappe.Redirect
	if not frappe.has_permission("Test Case", "read"):
		raise frappe.PermissionError
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.boot = (
		{
			"user": frappe.session.user,
			"full_name": frappe.utils.get_fullname(frappe.session.user),
			"site": frappe.local.site,
		}
	)
	manifest = os.path.join(os.path.dirname(__file__), "..", "public", "studio", ".vite", "manifest.json")
	with open(manifest) as f:
		entry = json.load(f)["src/main.js"]
	context.script = entry["file"]
	context.styles = entry.get("css", [])
	frappe.db.commit()  # persist a freshly generated csrf token
