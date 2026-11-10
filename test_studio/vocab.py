"""The step vocabulary and step helpers shared by the MCP server and the QCS Flow agent tools (no frappe import)."""

import json

ACTIONS = {
	"login": ("Log in as a user", "selector = user, value = password (use {{vars}}, e.g. {{exec_user}} / {{exec_password}})"),
	"logout": ("Log out", "no inputs"),
	"new_doc": ("Open a new, empty form", "value = doctype, e.g. Sales Order"),
	"set_field": ("Fill a field by its label", "selector = field label or fieldname, or items[1].qty for a table row; value = value"),
	"save": ("Save the form; fails with Frappe's on-screen message", "no inputs"),
	"workflow": ("Run a workflow action from the Actions menu", "value = action, e.g. Approve"),
	"expect_status": ("Check the status/workflow state next to the title", "value = expected status"),
	"create_from": ("Use the Create menu (e.g. Sales Invoice from a Sales Order)", "value = target doctype"),
	"run_snippet": ("Run a snippet (building block)", "snippet = snippet name; inputs = {var: value} for this use only"),
	"store_url": ("Remember the current page URL", "value = variable name; use later as {{name}}"),
	"store_text": ("Remember an element's text / input value", "selector = element; value = variable name"),
	"goto": ("Open a URL or path", "selector = URL or /path"),
	"click": ("Click an element", "selector = Playwright selector"),
	"fill": ("Replace an input's text", "selector, value"),
	"press": ("Press a key", "value = key, optional selector"),
	"select": ("Choose a dropdown option", "selector, value"),
	"check": ("Tick a checkbox", "selector"),
	"uncheck": ("Untick a checkbox", "selector"),
	"hover": ("Hover an element", "selector"),
	"wait": ("Pause", "value = milliseconds"),
	"wait_for": ("Wait until an element appears", "selector"),
	"assert_text": ("An element must contain text", "selector, value"),
	"assert_visible": ("An element must be visible", "selector"),
	"assert_hidden": ("An element must be hidden", "selector"),
	"assert_value": ("An input must have a value", "selector, value"),
	"assert_count": ("Exactly N elements must match", "selector, value = N"),
	"assert_url": ("The URL must contain text", "value"),
	"assert_title": ("The page title must contain text", "value"),
	"screenshot": ("Add a screenshot to the report", "no inputs"),
}


def _inputs(step):
	if step.get("action") != "run_snippet" or not step.get("value"):
		return {}
	try:
		data = json.loads(step["value"])
		return data if isinstance(data, dict) else {}
	except ValueError:
		return {}


def sentence(step):
	"""A step as the Studio reads it, e.g. 'Set Customer to {{customer}}'."""
	a, sel, val = step.get("action"), step.get("selector") or step.get("target") or "", step.get("value") or ""
	match a:
		case "login": return f"Log in as {sel}"
		case "logout": return "Log out"
		case "new_doc": return f"New {val or sel}"
		case "set_field": return f"Set {sel} to {val}"
		case "save": return "Save"
		case "workflow": return f"Workflow: {val or sel}"
		case "expect_status": return f"Status should be {val or sel}"
		case "create_from": return f"Create {val or sel} from this document"
		case "run_snippet":
			given = ", ".join(f"{k}={v}" for k, v in _inputs(step).items())
			return f"Run snippet '{step.get('snippet') or step.get('group') or sel}'" + (f" with {given}" if given else "")
		case "store_url": return f"Remember this page as {{{{{val}}}}}"
		case "goto": return f"Open {sel or val}"
		case _: return " ".join(x for x in (a, sel, f"= {val}" if val else "") if x)


def _steps_text(steps):
	return "\n".join(f"{i}. {sentence(s)}" + (f"   ({s['note']})" if s.get("note") else "") for i, s in enumerate(steps, 1)) or "(no steps)"


def clean_steps(steps):
	"""Accept steps from the agent: validate actions; inputs={...} on run_snippet becomes the value JSON."""
	out = []
	for i, s in enumerate(steps, 1):
		a = (s.get("action") or "").strip()
		if a not in ACTIONS:
			raise ValueError(f"Step {i}: unknown action '{a}'. Call list_actions for the vocabulary.")
		row = {"action": a}
		for k in ("selector", "value", "snippet", "note", "timeout_ms", "continue_on_failure", "known_issue"):
			if s.get(k) not in (None, ""):
				row[k] = s[k]
		if a == "run_snippet":
			if not s.get("snippet"):
				raise ValueError(f"Step {i}: run_snippet needs a snippet name")
			if s.get("inputs"):
				row["value"] = json.dumps({k: str(v) for k, v in s["inputs"].items()})
		out.append(row)
	return out
