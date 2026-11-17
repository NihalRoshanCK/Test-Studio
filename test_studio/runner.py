"""Frappe glue: whitelisted API, background jobs, persistence of runs, screenshots and traces."""

import json
import time

import frappe
from frappe import _
from frappe.utils import now_datetime
from frappe.core.doctype.file.exceptions import MaxFileSizeReachedError

from test_studio import engine, studio

JOB_TIMEOUT = 60 * 60


# ---------- helpers ----------


def _collect_vars(*docs):
	"""Later docs override earlier ones. Returns (variables, secret_values, secret_keys)."""
	# built-in: today in the site's date format, as date fields show it; a suite or test can override it
	variables, secrets, secret_keys = {"today": frappe.utils.formatdate(frappe.utils.nowdate())}, [], set()
	for doc in docs:
		for row in doc.get("variables") or []:
			secret = row.get_password("secret_value", raise_exception=False) if row.secret_value else None
			if secret:
				variables[row.key] = secret
				secrets.append(secret)
				secret_keys.add(row.key)
			else:
				variables[row.key] = row.value or ""
				secret_keys.discard(row.key)
	return variables, secrets, secret_keys


def _load_snippet(name):
	doc = frappe.get_doc("Test Snippet", name)
	try:
		defaults = {k: str(v) for k, v in json.loads(doc.input_defaults or "{}").items() if str(v) != ""}
	except ValueError:
		frappe.throw(f"Snippet {name}: Input Defaults is not valid JSON")
	return [{**s.as_dict(), "_defaults": defaults} if defaults else s.as_dict() for s in doc.steps]


def _steps(case):
	steps = engine.expand_steps([s.as_dict() for s in case.steps], _load_snippet)
	rows = engine.parse_rows(case.get("data_rows"))
	return engine.expand_rows(steps, rows) if rows else steps


def _save_file(run_name, filename, content):
	f = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"attached_to_doctype": "Test Run",
			"attached_to_name": run_name,
			"is_private": 1,
		}
	).insert(ignore_permissions=True)
	return f.file_url


def _matches_tag(case, tag):
	if not tag:
		return True
	tags = {t.strip().lower() for t in (case.tags_text or "").split(",")}
	return tag.strip().lower() in tags


PRIORITY_ORDER = {"High": 0, "Medium": 1, "Low": 2}


def _suite_cases(suite, tag=None):
	cases = frappe.get_all(
		"Test Case", {"suite": suite, "enabled": 1}, ["name", "tags_text", "priority"], order_by="creation asc"
	)
	cases = [c for c in cases if _matches_tag(c, tag)]
	return sorted(cases, key=lambda c: PRIORITY_ORDER.get(c.priority, 1))


def _enqueue(method, **kwargs):
	frappe.enqueue(method, queue="long", timeout=JOB_TIMEOUT, enqueue_after_commit=True, **kwargs)


def _remember(case_name, result, fp):
	"""Store the element fingerprint on the step definition (the test's own step, or a snippet's step one level down)."""
	parts = str(result["step_no"]).split(".")
	if len(parts) == 1:
		parent = ("Test Case", case_name)
	elif len(parts) == 2 and result.get("group"):
		parent = ("Test Snippet", result["group"])
	else:
		return
	frappe.db.set_value("Test Step", {"parenttype": parent[0], "parent": parent[1], "idx": int(parts[-1])},
		"fingerprint", json.dumps(fp), update_modified=False)


def _session_for(user):
	"""A desk session for `user`, made server-side (no password); the run deletes it when done."""
	from frappe.sessions import Session, get_expiry_period

	row = frappe.db.get_value("User", {"name": user, "enabled": 1}, ["full_name", "user_type"], as_dict=True)
	if not row:
		frappe.throw(_("User {0} does not exist or is disabled").format(user))
	now, sid = frappe.utils.now(), frappe.generate_hash()
	# Session() would read the web request and switch this worker's own session, so write the record directly
	s = object.__new__(Session)
	s.data = frappe._dict(user=user, sid=sid, data=frappe._dict(user=user, session_ip="127.0.0.1", last_updated=now,
		creation=now, session_expiry=get_expiry_period(), full_name=row.full_name, user_type=row.user_type))
	s.insert_session_record()
	frappe.db.commit()  # the site's web process must find it
	return sid


# ---------- execution ----------


def create_run(case_name, pipeline_run=None, run_as=None):
	case = frappe.get_doc("Test Case", case_name)
	return frappe.get_doc(
		{"doctype": "Test Run", "test_case": case.name, "suite": case.suite, "pipeline_run": pipeline_run, "run_as": run_as}
	).insert(ignore_permissions=True)


def execute_run(run_name, debug=False, breakpoints=None):
	run = frappe.get_doc("Test Run", run_name)
	case = frappe.get_doc("Test Case", run.test_case)
	suite = frappe.get_doc("Test Suite", case.suite)
	run.update({"status": "Running", "browser": suite.browser, "started_at": now_datetime(), "error": None})
	run.set("steps", [])
	run.save(ignore_permissions=True)
	frappe.db.commit()
	t0, notes = time.monotonic(), []

	def on_step(result, shot):
		fp = result.pop("fingerprint", None)
		result.pop("healed", None)
		if fp:
			_remember(case.name, result, fp)
		if shot:
			result["screenshot"] = _save_file(run.name, f"{run.name}-step-{result['step_no']}.png", shot)
		run.append("steps", result)
		run.save(ignore_permissions=True)
		frappe.db.commit()  # make progress visible to the open form

	try:
		variables, secrets, _keys = _collect_vars(suite, case)
		settings = suite.as_dict()
		settings["keep_going"] = suite.get("keep_going") or case.get("keep_going")
		made = []  # sessions this run made for its login steps; deleted when it ends

		def login_session(user, password):
			name = frappe.db.get_value("User", user) or frappe.db.get_value("User", {"username": user}) or user
			from frappe.utils.password import check_password

			check_password(name, password)  # wrong password: the login step fails, as on the login page
			made.append(_session_for(name))
			return made[-1]

		settings["login_session"] = login_session
		if run.run_as:
			sid = _session_for(run.run_as)
			settings["session"] = {"user": run.run_as, "sid": sid}
			secrets.append(sid)
		live = studio.make_run_live(run.name, debug, breakpoints)
		try:
			status, error, trace, video = engine.run_case(_steps(case), variables, secrets, settings, on_step, live)
		finally:
			if run.run_as:
				frappe.sessions.delete_session(sid, reason="Test Studio run finished")
			for s in made:
				frappe.sessions.delete_session(s, reason="Test Studio run finished")
		# a file too big to keep must not turn a finished run into an Error: keep the result, say what is missing
		for field, data, filename in (("trace", trace, f"{run.name}-trace.zip"), ("video", video, f"{run.name}.webm")):
			if data:
				try:
					run.set(field, _save_file(run.name, filename, data))
				except MaxFileSizeReachedError:
					frappe.clear_messages()
					notes.append(f"Not saved: the {field} ({len(data) / 1048576:.1f} MB) is over the site's file size limit "
						"(System Settings → Max File Size).")
	except Exception:
		status, error = "Error", frappe.get_traceback()
		frappe.log_error(title=f"Test Run {run.name} crashed")

	error = "\n\n".join(x for x in [error, *notes] if x)
	run.update({"status": status, "error": error, "duration_ms": int((time.monotonic() - t0) * 1000)})
	run.save(ignore_permissions=True)
	frappe.db.set_value("Test Case", case.name, "last_status", status, update_modified=False)
	if status in ("Failed", "Error"):
		_notify(suite, case, run)
	frappe.db.commit()
	return status


def _notify(suite, case, run):
	"""Frappe notifications (the bell) for the suite's Notify users; never lets a bad address break the run."""
	for user in dict.fromkeys(u.strip() for u in (suite.get("notify_users") or "").splitlines() if u.strip()):
		try:
			frappe.get_doc({"doctype": "Notification Log", "for_user": user, "type": "Alert",
				"subject": f"Test {run.status.lower()}: {case.title} ({run.name})",
				"email_content": (run.error or "")[:1000], "document_type": "Test Run", "document_name": run.name,
				"from_user": "Administrator"}).insert(ignore_permissions=True)
		except Exception:
			frappe.log_error(title=f"Test Studio could not notify {user}")


# ---------- schedule ----------

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def is_due(schedule, hour, weekday, last, now):
	"""Whether a suite with this schedule should run at `now` (called hourly)."""
	if not schedule:
		return False
	if schedule == "Hourly":
		return last is None or (now - last).total_seconds() >= 55 * 60
	if now.hour != (hour or 0) or (last is not None and last.date() == now.date()):
		return False
	return schedule == "Daily" or (schedule == "Weekly" and WEEKDAYS[now.weekday()] == (weekday or "Monday"))


def run_scheduled_suites():
	"""scheduler_events hourly: run every suite whose schedule is due (its enabled tests, as a suite run does)."""
	now = frappe.utils.now_datetime()
	for s in frappe.get_all("Test Suite", {"schedule": ["is", "set"]},
			["name", "schedule", "schedule_hour", "schedule_weekday", "last_scheduled_at"]):
		last = frappe.utils.get_datetime(s.last_scheduled_at) if s.last_scheduled_at else None
		if not is_due(s.schedule, s.schedule_hour, s.schedule_weekday, last, now):
			continue
		frappe.db.set_value("Test Suite", s.name, "last_scheduled_at", now, update_modified=False)
		for c in _suite_cases(s.name):
			_enqueue("test_studio.runner.execute_run", run_name=create_run(c.name).name)
		frappe.db.commit()


def execute_pipeline(pipeline_run_name):
	prun = frappe.get_doc("Test Pipeline Run", pipeline_run_name)
	prun.update({"status": "Running", "started_at": now_datetime()})
	prun.save(ignore_permissions=True)
	frappe.db.commit()
	t0, overall, halted = time.monotonic(), "Passed", False

	try:
		definition = frappe.get_doc("Test Pipeline", prun.pipeline).stages
		for stage, spec in zip(prun.stages, definition, strict=False):
			if halted:
				stage.status = "Skipped"
				continue
			s0 = time.monotonic()
			cases = _suite_cases(stage.suite, spec.tag)
			stage.update({"status": "Running", "total": len(cases), "passed": 0, "failed": 0})
			prun.save(ignore_permissions=True)
			frappe.db.commit()

			for c in cases:
				ok = execute_run(create_run(c.name, prun.name).name) in ("Passed", "Known Issue")
				stage.passed += ok
				stage.failed += not ok
				prun.save(ignore_permissions=True)
				frappe.db.commit()

			stage.duration_ms = int((time.monotonic() - s0) * 1000)
			stage.status = "Failed" if stage.failed else "Passed"
			if stage.failed:
				overall = "Failed"
				halted = bool(spec.stop_on_failure)
		prun.status = overall
	except Exception:
		prun.update({"status": "Error", "error": frappe.get_traceback()})
		frappe.log_error(title=f"Pipeline Run {prun.name} crashed")

	prun.duration_ms = int((time.monotonic() - t0) * 1000)
	prun.save(ignore_permissions=True)
	frappe.db.commit()


# ---------- API ----------


def _check_capacity():
	"""Each run outside the queue is a browser of its own: refuse more than Settings allows at once.
	Runs 'Running' for over an hour (a crashed process) do not count."""
	limit = frappe.utils.cint(frappe.db.get_single_value("Test Studio Settings", "max_parallel_runs")) or 3
	since = frappe.utils.add_to_date(now_datetime(), hours=-1)
	busy = frappe.db.count("Test Run", {"status": "Running", "started_at": [">", since]})
	if busy >= limit:
		frappe.throw(_("{0} runs are already in progress (the most at once is {1}). Try again when one finishes.").format(busy, limit),
			title=_("Too many runs at once"))


@frappe.whitelist()
def run_test_case(name, debug=0, breakpoints=None, detached=0):
	"""debug=1 runs in a detached process (it may sit paused) instead of occupying a worker.
	detached=1 also runs outside the worker queue, without pausing: for a caller that itself holds a worker
	(an automation waiting on the result) and would otherwise wait for its own run."""
	frappe.has_permission("Test Case", "read", name, throw=True)
	frappe.has_permission("Test Run", "create", throw=True)
	if frappe.utils.cint(detached) or frappe.utils.cint(debug):
		_check_capacity()
	run = create_run(name)
	if frappe.utils.cint(detached) and not frappe.utils.cint(debug):
		frappe.db.commit()  # the detached process must see the new run
		studio.spawn("test_studio.runner.execute_run", run_name=run.name)
	elif frappe.utils.cint(debug):
		bps = frappe.parse_json(breakpoints) if breakpoints else []
		frappe.db.commit()  # the detached process must see the new run
		studio.spawn("test_studio.runner.execute_run", run_name=run.name, debug=True, breakpoints=[str(b) for b in bps])
	else:
		_enqueue("test_studio.runner.execute_run", run_name=run.name)
	return run.name


@frappe.whitelist()
def run_as_users(name, users=None):
	"""Run the test once signed in as each user (saved on the test as Run As Users). Signing in as someone
	else needs no password, so only a System Manager may do it."""
	frappe.only_for("System Manager")
	case = frappe.get_doc("Test Case", name)
	if users is not None:
		case.run_as = users
		case.save()
	people = [u.strip() for u in (case.run_as or "").splitlines() if u.strip()]
	if not people:
		frappe.throw(_("Add at least one user to Run As Users"))
	runs = []
	for user in dict.fromkeys(people):
		run = create_run(case.name, run_as=user)
		_enqueue("test_studio.runner.execute_run", run_name=run.name)
		runs.append({"user": user, "run": run.name})
	return runs


@frappe.whitelist()
def role_matrix(name):
	"""Latest run per user for a test (the Run As grid)."""
	frappe.has_permission("Test Case", "read", name, throw=True)
	people = [u.strip() for u in (frappe.db.get_value("Test Case", name, "run_as") or "").splitlines() if u.strip()]
	out = []
	for user in dict.fromkeys(people):
		last = frappe.get_all("Test Run", {"test_case": name, "run_as": user}, ["name", "status", "creation", "error"],
			order_by="creation desc", limit=1)
		out.append({"user": user, **(last[0] if last else {})})
	return out


SNIPPET_TAG = "snippet-run"


@frappe.whitelist()
def run_snippet(name, suite, before=None):
	"""Run a snippet on its own, optionally after another one (e.g. a login).

	Runs need a Test Case, so each snippet gets one hidden, disabled case per suite
	(tagged snippet-run: kept out of the Tests list and out of suite runs).
	"""
	frappe.has_permission("Test Snippet", "read", name, throw=True)
	frappe.has_permission("Test Run", "create", throw=True)
	title = f"Snippet: {name}"
	existing = frappe.db.get_value("Test Case", {"title": title, "suite": suite})
	case = frappe.get_doc("Test Case", existing) if existing else frappe.new_doc("Test Case")
	case.update({"title": title, "suite": suite, "enabled": 0, "tags_text": SNIPPET_TAG})
	case.set("steps", ([{"action": "run_snippet", "snippet": before}] if before else []) + [{"action": "run_snippet", "snippet": name}])
	case.save(ignore_permissions=True)
	return run_test_case(case.name)


@frappe.whitelist()
def run_test_suite(name, tag=None):
	frappe.has_permission("Test Suite", "read", name, throw=True)
	frappe.has_permission("Test Run", "create", throw=True)
	runs = []
	for c in _suite_cases(name, tag):
		run = create_run(c.name)
		_enqueue("test_studio.runner.execute_run", run_name=run.name)
		runs.append(run.name)
	if not runs:
		frappe.throw(_("No enabled test cases in this suite"))
	return runs


@frappe.whitelist()
def run_pipeline(name):
	frappe.has_permission("Test Pipeline", "read", name, throw=True)
	frappe.has_permission("Test Pipeline Run", "create", throw=True)
	pipeline = frappe.get_doc("Test Pipeline", name)
	prun = frappe.get_doc(
		{
			"doctype": "Test Pipeline Run",
			"pipeline": name,
			"stages": [
				{"stage_name": s.stage_name, "suite": s.suite, "status": "Pending"} for s in pipeline.stages
			],
		}
	).insert(ignore_permissions=True)
	_enqueue("test_studio.runner.execute_pipeline", pipeline_run_name=prun.name)
	return prun.name


@frappe.whitelist()
def export_playwright(name):
	frappe.has_permission("Test Case", "read", name, throw=True)
	case = frappe.get_doc("Test Case", name)
	suite = frappe.get_doc("Test Suite", case.suite)
	variables, _secrets, secret_keys = _collect_vars(suite, case)
	return engine.to_playwright_ts(case.title, _steps(case), variables, secret_keys, suite.base_url)
