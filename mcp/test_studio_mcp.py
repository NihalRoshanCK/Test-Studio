"""Test Studio MCP server: lets an AI agent read, write and run Frappe browser tests.

Talks to a Test Studio site over its REST API with a Frappe API key, so the agent has exactly the
permissions of that key's user. Configuration (environment, or a KEY=VALUE file at
$TEST_STUDIO_ENV_FILE, default ~/.config/test-studio/mcp.env):

    TEST_STUDIO_URL         e.g. http://qcs.localhost:8000
    TEST_STUDIO_API_KEY     from the user's API Access section in the desk
    TEST_STUDIO_API_SECRET

Run: python test_studio_mcp.py   (stdio transport; register it with your MCP client)
     python test_studio_mcp.py --http [--port 8765]
        Streamable HTTP at http://127.0.0.1:<port>/mcp for MCP clients on other processes (e.g. QCS Flow agents).
        Needs TEST_STUDIO_MCP_TOKEN: clients send it as "Authorization: Bearer <token>".
"""

import json
import os
import re
import time
from pathlib import Path

import httpx
from mcp.server.fastmcp import FastMCP

DONE = ("Passed", "Known Issue", "Failed", "Error")

# The step vocabulary, as the Studio shows it. selector/value say what each column means for the action.
from test_studio.vocab import ACTIONS, _inputs, _steps_text, clean_steps, sentence  # noqa: E402, F401

mcp = FastMCP("test-studio")


# ---------- connection ----------


def _config():
	path = Path(os.environ.get("TEST_STUDIO_ENV_FILE", "~/.config/test-studio/mcp.env")).expanduser()
	conf = {}
	if path.exists():
		for line in path.read_text().splitlines():
			if "=" in line and not line.lstrip().startswith("#"):
				k, v = line.split("=", 1)
				conf[k.strip()] = v.strip()
	conf.update({k: v for k, v in os.environ.items() if k.startswith("TEST_STUDIO_")})
	missing = [k for k in ("TEST_STUDIO_URL", "TEST_STUDIO_API_KEY", "TEST_STUDIO_API_SECRET") if not conf.get(k)]
	if missing:
		raise RuntimeError(f"Test Studio MCP is not configured: set {', '.join(missing)} (env or {path})")
	return conf


_client = None


def _http():
	global _client
	if _client is None:
		c = _config()
		_client = httpx.Client(
			base_url=c["TEST_STUDIO_URL"].rstrip("/"),
			headers={"Authorization": f"token {c['TEST_STUDIO_API_KEY']}:{c['TEST_STUDIO_API_SECRET']}", "Accept": "application/json"},
			timeout=60,
		)
	return _client


def _error_text(resp):
	try:
		data = resp.json()
		msgs = [json.loads(m).get("message", "") for m in json.loads(data.get("_server_messages", "[]"))]
		text = " ".join(re.sub("<[^>]+>", "", m) for m in msgs if m) or str(data.get("exception", ""))
	except ValueError:
		text = resp.text[:300]
	return f"HTTP {resp.status_code}: {text or resp.reason_phrase}"


def call(method, get=False, **args):
	"""Call a whitelisted Frappe method; raise with the server's own message on failure."""
	if get:
		params = {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in args.items() if v is not None}
		resp = _http().get(f"/api/method/{method}", params=params)
	else:
		resp = _http().post(f"/api/method/{method}", json={k: v for k, v in args.items() if v is not None})
	if resp.status_code >= 400:
		raise RuntimeError(_error_text(resp))
	return resp.json().get("message")


# ---------- formatting ----------




def _run_summary(run):
	steps = run.get("steps") or []
	counts = {k: sum(s.get("status") == k for s in steps) for k in ("Passed", "Known Issue", "Failed", "Skipped")}
	lines = [f"Run {run.get('name')}: {run.get('status')} ({counts['Passed']} passed, {counts['Known Issue']} known issue, {counts['Failed']} failed, {counts['Skipped']} skipped, {(run.get('duration_ms') or 0) / 1000:.1f}s)"]
	failed = next((s for s in steps if s.get("status") == "Failed"), None) or next((s for s in steps if s.get("status") == "Known Issue"), None)
	if failed:
		where = f" in snippet '{failed['group']}'" if failed.get("group") else ""
		label = "Known issue" if failed.get("status") == "Known Issue" else "Failed"
		lines += [f"{label} at step {failed['step_no']}{where}: {sentence(failed)}", f"Reason: {failed.get('error')}"]
		if failed.get("screenshot"):
			lines.append(f"Screenshot: {_config()['TEST_STUDIO_URL'].rstrip('/')}{failed['screenshot']}")
	if run.get("video"):
		lines.append(f"Video of the run: {_config()['TEST_STUDIO_URL'].rstrip('/')}{run['video']}")
	if run.get("status") == "Error" and run.get("error"):
		lines.append(f"Error: {run['error'][-800:]}")
	return "\n".join(lines)


def _wait(run_name, timeout_s):
	end = time.monotonic() + timeout_s
	while True:
		m = call("test_studio.studio.run_poll", get=True, run=run_name, since=10**9)  # since: skip frames
		if m["status"] in DONE:
			return call("test_studio.studio.get_run", get=True, name=run_name)
		if time.monotonic() > end:
			return {"name": run_name, "status": f"{m['status']} (still going after {timeout_s}s; check get_run later)", "steps": m.get("steps")}
		time.sleep(2)


# ---------- tools ----------


@mcp.tool()
def list_actions() -> str:
	"""The step vocabulary for tests and snippets: each action, what it does, and what selector/value mean."""
	return "\n".join(f"{a}: {desc}. Inputs: {cols}" for a, (desc, cols) in ACTIONS.items())


@mcp.tool()
def list_suites() -> str:
	"""Suites (sites under test) and the variables tests can use as {{name}}."""
	tree = call("test_studio.studio.get_tree", get=True)
	out = []
	for s in tree["suites"]:
		doc = call("frappe.client.get", get=True, doctype="Test Suite", name=s["name"])
		keys = [v["key"] + (" (secret)" if v.get("secret_value") else "") for v in doc.get("variables") or []]
		out.append(f"{s['name']}: {doc.get('base_url') or '(no base URL)'}, browser {doc.get('browser')}; variables: {', '.join(keys) or 'none'}")
	return "\n".join(out) or "No suites yet."


@mcp.tool()
def list_tests(suite: str | None = None) -> str:
	"""Tests with their suite, last result and recent run history (oldest first)."""
	tree = call("test_studio.studio.get_tree", get=True)
	rows = [c for c in tree["cases"] if not suite or c["suite"] == suite]
	return "\n".join(
		f"{c['name']} | {c['title']} | suite {c['suite']} | last: {c.get('last_status') or 'not run'}"
		+ (" | disabled" if not c.get("enabled") else "") + (f" | history: {' '.join(h[0] for h in c.get('history') or [])}" if c.get("history") else "")
		for c in rows
	) or "No tests."


@mcp.tool()
def get_test(name: str) -> str:
	"""A test's steps as readable sentences, plus its variables."""
	doc = call("frappe.client.get", get=True, doctype="Test Case", name=name)
	vars_ = ", ".join(v["key"] + ("=(secret)" if v.get("secret_value") else f"={v.get('value') or ''}") for v in doc.get("variables") or [])
	return f"{doc['name']}: {doc['title']} (suite {doc['suite']}, last {doc.get('last_status') or 'not run'})\nTest variables: {vars_ or 'none'}\nSteps:\n{_steps_text(doc.get('steps') or [])}"


@mcp.tool()
def list_snippets() -> str:
	"""Snippets (reusable building blocks) and the inputs each one needs."""
	tree = call("test_studio.studio.get_tree", get=True)
	inputs = tree.get("snippet_inputs") or {}
	return "\n".join(f"{s}: inputs {', '.join(inputs.get(s, [])) or 'none'}" for s in tree["snippets"]) or "No snippets."


@mcp.tool()
def get_snippet(name: str) -> str:
	"""A snippet's steps as readable sentences."""
	doc = call("frappe.client.get", get=True, doctype="Test Snippet", name=name)
	return f"Snippet {doc['name']}: {doc.get('description') or ''}\nSteps:\n{_steps_text(doc.get('steps') or [])}"


@mcp.tool()
def get_fields(doctype: str) -> str:
	"""Field labels you can use in set_field for a doctype, including items[1].field rows of its tables."""
	fields = call("test_studio.studio.get_fields", get=True, doctype=doctype) or []
	return "\n".join(f"{f['key']}  ({f['fieldtype']}{', required' if f.get('reqd') else ''})" for f in fields) or "No fields (unknown doctype?)."


@mcp.tool()
def create_test(title: str, suite: str, steps: list[dict], tags: str | None = None) -> str:
	"""Create a test. steps: [{"action": "login", "selector": "{{exec_user}}", "value": "{{exec_password}}"},
	{"action": "run_snippet", "snippet": "Create approved service Sales Order", "inputs": {"discount": "8"}}, ...]."""
	doc = call("frappe.client.insert", doc={"doctype": "Test Case", "title": title, "suite": suite, "tags_text": tags, "steps": clean_steps(steps)})
	return f"Created {doc['name']}: {doc['title']}\n{_steps_text(doc.get('steps') or [])}"


@mcp.tool()
def update_test(name: str, steps: list[dict] | None = None, title: str | None = None, tags: str | None = None) -> str:
	"""Replace a test's steps (same format as create_test) and/or rename or retag it."""
	doc = call("frappe.client.get", get=True, doctype="Test Case", name=name)
	if steps is not None:
		doc["steps"] = clean_steps(steps)
	if title:
		doc["title"] = title
	if tags is not None:
		doc["tags_text"] = tags
	doc = call("frappe.client.save", doc=doc)
	return f"Saved {doc['name']}: {doc['title']}\n{_steps_text(doc.get('steps') or [])}"


@mcp.tool()
def create_snippet(title: str, steps: list[dict], description: str | None = None) -> str:
	"""Create a reusable snippet. Use {{variables}} for its inputs; tests give values per use."""
	doc = call("frappe.client.insert", doc={"doctype": "Test Snippet", "title": title, "description": description, "steps": clean_steps(steps)})
	return f"Created snippet {doc['name']}\n{_steps_text(doc.get('steps') or [])}"


@mcp.tool()
def run_test(name: str, wait: bool = True, timeout_s: int = 600) -> str:
	"""Run a test in a real browser. With wait=True, returns the result: status, and for a failure the step,
	the reason (including Frappe's on-screen message) and a screenshot URL."""
	# detached: runs outside the worker queue, so a caller that holds a worker (an automation) never waits on itself
	run = call("test_studio.runner.run_test_case", name=name, detached=1)
	return _run_summary(_wait(run, timeout_s)) if wait else f"Started {run}. Check it with get_run."


@mcp.tool()
def run_snippet(name: str, suite: str, before: str | None = None, wait: bool = True, timeout_s: int = 600) -> str:
	"""Run one snippet on a suite's site, optionally after another snippet (e.g. a login)."""
	run = call("test_studio.runner.run_snippet", name=name, suite=suite, before=before)
	return _run_summary(_wait(run, timeout_s)) if wait else f"Started {run}. Check it with get_run."


@mcp.tool()
def get_run(name: str, all_steps: bool = False) -> str:
	"""A run's result. all_steps=True lists every executed step with its time."""
	run = call("test_studio.studio.get_run", get=True, name=name)
	text = _run_summary(run)
	if all_steps:
		text += "\n" + "\n".join(f"{s['step_no']} [{s['status']}] {sentence(s)} ({s.get('duration_ms') or 0} ms)" for s in run.get("steps") or [])
	return text


@mcp.tool()
def create_suite(title: str, copy_from: str, description: str | None = None, settings: dict | None = None) -> str:
	"""A new suite with copy_from's site, browser and logins as {{variables}} (secret values are copied on the server
	and never shown). settings changes the copy, e.g. {"record_video": 1, "screenshot_each_step": 1, "read_only": 1,
	"default_timeout_ms": 20000}. Asking again with the same title returns the existing suite."""
	name = call("test_studio.studio.copy_suite", source=copy_from, title=title, description=description,
		settings=json.dumps(settings or {}))
	return f"Suite '{name}' is ready (copied from {copy_from}). Pass suite='{name}' to create_test."


def _label(c):
	return c.get("label") or c.get("fieldname") if isinstance(c, dict) else str(c).split(":")[0]


@mcp.tool()
def run_report(report: str, filters: dict | None = None, limit: int = 50) -> str:
	"""Run any report the API user may open, with its filters as {fieldname: value}, e.g. "General Ledger"
	{"company": "...", "voucher_no": "..."}. Returns its columns and first rows."""
	out = call("frappe.desk.query_report.run", report_name=report, filters=json.dumps(filters or {}), ignore_prepared_report=1) or {}
	cols = out.get("columns") or []
	keys = [c.get("fieldname") if isinstance(c, dict) else None for c in cols]
	rows = [[r.get(k) for k in keys] if isinstance(r, dict) else r for r in out.get("result") or []]
	lines = [" | ".join(_label(c) for c in cols)] + [" | ".join("" if v is None else str(v) for v in r) for r in rows[: min(limit, 200)]]
	return f"{report}: {len(rows)} rows\n" + "\n".join(lines)


@mcp.tool()
def run_data_checks(label: str | None = None, timeout_s: int = 300) -> str:
	"""Run every enabled data check now (each is a report that should stay empty or under a row limit) and wait.
	Returns each check's result, with the rows of the ones that fail."""
	name = call("test_studio.checks.run_data_checks", label=label, wait=1)  # inline: never queued behind the caller
	end = time.monotonic() + timeout_s
	while True:
		run = call("test_studio.checks.get_check_run", get=True, name=name)
		if run["status"] not in ("Queued", "Running") or time.monotonic() > end:
			break
		time.sleep(2)
	lines = [f"Data checks {name}: {run['status']}"]
	for r in run.get("results") or []:
		lines.append(f"- {r['data_check']}: {r['status']}, {r.get('row_count') or 0} rows (allowed {r.get('max_rows') or 0})"
			+ (f" error: {(r.get('error') or '')[-200:]}" if r["status"] == "Error" else ""))
		if r["row_count"]:
			lines.append("  " + " | ".join(c["label"] for c in r["columns"]))
			lines += ["  " + " | ".join("" if v is None else str(v) for v in row) for row in r["rows"][:15]]
	return "\n".join(lines)


@mcp.tool()
def add_comment(doctype: str, name: str, text: str) -> str:
	"""Add a comment (Markdown) to any document's timeline, e.g. to report test results on the record they are
	about. Internal: no email is sent and portals do not show it."""
	c = call("test_studio.studio.add_comment", doctype=doctype, name=name, text=text)
	return f"Comment {c} added to {doctype} {name}."


@mcp.tool()
def list_runs(test: str | None = None, status: str | None = None, limit: int = 20) -> str:
	"""Recent runs, newest first. status: Passed, Known Issue, Failed, Error, Running or Queued."""
	runs = call("test_studio.studio.list_runs", get=True, test_case=test, status=status, limit=limit)
	return "\n".join(f"{r['name']} | {r['status']} | {r['title']} | {(r.get('duration_ms') or 0) / 1000:.1f}s | {r['creation']}" for r in runs) or "No runs."


def serve_http(port):
	"""Streamable HTTP on 127.0.0.1, every request checked against TEST_STUDIO_MCP_TOKEN."""
	import hmac

	import uvicorn

	token = os.environ.get("TEST_STUDIO_MCP_TOKEN") or _config().get("TEST_STUDIO_MCP_TOKEN")
	if not token or len(token) < 24:
		raise SystemExit("Set TEST_STUDIO_MCP_TOKEN (24+ characters) before serving over HTTP")
	inner = mcp.streamable_http_app()

	async def app(scope, receive, send):
		if scope["type"] == "http":
			sent = dict(scope.get("headers") or []).get(b"authorization", b"").decode()
			if not hmac.compare_digest(sent, f"Bearer {token}"):
				await send({"type": "http.response.start", "status": 401, "headers": [(b"content-type", b"text/plain")]})
				await send({"type": "http.response.body", "body": b"unauthorized"})
				return
		await inner(scope, receive, send)

	uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
	import sys

	if "--http" in sys.argv:
		port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8765
		serve_http(port)
	else:
		mcp.run()
