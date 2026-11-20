app_name = "test_studio"
app_title = "Test Studio"
app_publisher = "Quark Cyber"
app_description = "Visual browser test automation"
app_email = "vivek@quarkcyber.systems"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "test_studio",
# 		"logo": "/assets/test_studio/logo.png",
# 		"title": "Test Studio",
# 		"route": "/test_studio",
# 		"has_permission": "test_studio.api.permission.has_app_permission",
# 	}
# ]

# The dock, the rail down the left of the desk, is a document rather than a hook. Author it in
# Manage Dock on a developer-mode site and press Export to App, and it is written to
# `test_studio/dock/test_studio/test_studio.json` for git to carry. An app that ships none has no
# rail: its sidebar gets a switcher in the header instead.
#
# A companion app, one that extends a host app rather than standing on its own, says so with
# `mount_on` on that same record, and its entries are appended to the host's rail. Mounting keeps
# the companion off the apps screen, so it takes precedence over any add_to_apps_screen above.

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/test_studio/css/test_studio.css"
# app_include_js = "/assets/test_studio/js/test_studio.js"

# include js, css files in header of web template
# web_include_css = "/assets/test_studio/css/test_studio.css"
# web_include_js = "/assets/test_studio/js/test_studio.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "test_studio/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_kanban_js = {"doctype" : "public/js/doctype_kanban.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "test_studio/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "test_studio.utils.jinja_methods",
# 	"filters": "test_studio.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "test_studio.install.before_install"
# after_install = "test_studio.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "test_studio.uninstall.before_uninstall"
# after_uninstall = "test_studio.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "test_studio.utils.before_app_install"
# after_app_install = "test_studio.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "test_studio.utils.before_app_uninstall"
# after_app_uninstall = "test_studio.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "test_studio.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "test_studio.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "test_studio.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["test_studio.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"test_studio.tasks.all"
# 	],
# 	"daily": [
# 		"test_studio.tasks.daily"
# 	],
# 	"hourly": [
# 		"test_studio.tasks.hourly"
# 	],
# 	"weekly": [
# 		"test_studio.tasks.weekly"
# 	],
# 	"monthly": [
# 		"test_studio.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "test_studio.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "test_studio.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "test_studio.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "test_studio.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["test_studio.utils.before_request"]
# after_request = ["test_studio.utils.after_request"]

# Job Events
# ----------
# before_job = ["test_studio.utils.before_job"]
# after_job = ["test_studio.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"test_studio.auth.validate"
# ]

# on_social_login = "test_studio.auth.on_social_login"

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# Test Studio
app_include_js = "/assets/test_studio/js/test_studio.js"
app_include_css = "/assets/test_studio/css/test_studio.css"
app_include_icons = ["/assets/test_studio/icons/test-studio-icons.svg"]

add_to_apps_screen = [
	{
		"name": "test_studio",
		"logo": "/assets/test_studio/images/test-studio-logo.svg",
		"title": "Test Studio",
		"route": "/studio",
		"has_permission": "test_studio.install.has_app_permission",
	}
]

# the role has to exist before the doctypes that grant it permissions are synced
before_migrate = ["test_studio.install.ensure_role"]
before_install = ["test_studio.install.ensure_role"]
after_install = ["test_studio.install.ensure_role"]

website_route_rules = [{"from_route": "/studio/<path:app_path>", "to_route": "studio"}]

# Test-system safety: block all outgoing email and SMS (see test_studio/blocker.py)
before_request = ["test_studio.blocker.mute_emails"]
before_job = ["test_studio.blocker.mute_emails"]
send_sms = ["test_studio.blocker.block_sms"]

# nightly data checks (Data Check doctype)
scheduler_events = {
	"hourly": ["test_studio.runner.run_scheduled_suites"],
	"daily": ["test_studio.checks.run_nightly", "test_studio.studio.prune_runs"],
}

