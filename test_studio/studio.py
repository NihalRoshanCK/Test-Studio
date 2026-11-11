"""Interactive Studio backend: live browser sessions (recorder / element picker), live run frames, debugger.

Long-lived browser work runs in a detached process (see `spawn`) so it never blocks the RQ workers.
Studio <-> process communication goes through Redis: a command list per session/run plus an
expiring state key and an expiring frame key that the Studio polls.
"""

import base64
import pickle
import json
import os
import subprocess
import sys
import time

import frappe
import redis
from frappe.utils import get_bench_path

from test_studio import engine

TTL = 15 * 60
IDLE_TIMEOUT = 10 * 60
SPAWNABLE = {"test_studio.studio.run_session", "test_studio.runner.execute_run"}
SESSION_CMDS = {
	"click", "type", "press", "goto", "scroll", "back", "forward", "reload", "select",
	"highlight", "mode", "record", "stop",
}
DEBUG_CMDS = {"continue", "step", "stop"}

# Collects selector candidates for the element at (x, y), or the focused element when no point is given.
ELEMENT_INFO_JS = r"""
(pt) => {
	let el = pt ? document.elementFromPoint(pt[0], pt[1]) : document.activeElement;
	if (!el || el === document.body || el === document.documentElement) return null;
	el = el.closest('a,button,input,select,textarea,label,summary,[role],[data-testid],[data-test],[data-cy],[contenteditable]') || el;
	const q = (s) => JSON.stringify(s);
	const clean = (s) => (s || '').trim().replace(/\s+/g, ' ');
	const c = [];
	for (const a of ['data-testid', 'data-test', 'data-cy', 'data-qa'])
		if (el.getAttribute(a)) c.push(`[${a}=${q(el.getAttribute(a))}]`);
	if (el.id && !/\d{3,}|^[a-f0-9-]{8,}$/i.test(el.id)) c.push('#' + CSS.escape(el.id));
	const tag = el.tagName;
	const inputRole = { checkbox: 'checkbox', radio: 'radio', submit: 'button', button: 'button', reset: 'button',
		range: 'slider', number: 'spinbutton', search: 'searchbox' };
	const role = el.getAttribute('role') ||
		({ BUTTON: 'button', SELECT: 'combobox', TEXTAREA: 'textbox', SUMMARY: 'button',
		   H1: 'heading', H2: 'heading', H3: 'heading', H4: 'heading', IMG: 'img' }[tag]) ||
		(tag === 'A' && el.hasAttribute('href') ? 'link' : null) ||
		(tag === 'INPUT' ? inputRole[el.type] || 'textbox' : null);
	const label = el.labels && el.labels[0] ? el.labels[0].innerText : '';
	const name = clean(el.getAttribute('aria-label') || label || el.getAttribute('placeholder') ||
		el.getAttribute('title') || el.getAttribute('alt') ||
		(['button', 'link', 'heading', 'tab', 'menuitem', 'checkbox', 'radio', 'option'].includes(role) ? el.innerText : '') ||
		(tag === 'INPUT' && ['submit', 'button'].includes(el.type) ? el.value : ''));
	if (role && name && name.length <= 60) c.push(`role=${role}[name=${q(name)}]`);
	if (el.getAttribute('name')) c.push(`${tag.toLowerCase()}[name=${q(el.getAttribute('name'))}]`);
	const text = clean(el.innerText);
	if (text && text.length <= 40 && !['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) c.push(`text=${q(text)}`);
	const parts = [];
	for (let e = el; e && e.nodeType === 1 && e !== document.body && parts.length < 6; e = e.parentElement) {
		if (e.id && !/\d{3,}/.test(e.id)) { parts.unshift('#' + CSS.escape(e.id)); break; }
		let s = e.tagName.toLowerCase();
		const sib = e.parentElement ? [...e.parentElement.children].filter((x) => x.tagName === e.tagName) : [];
		if (sib.length > 1) s += `:nth-of-type(${sib.indexOf(e) + 1})`;
		parts.unshift(s);
	}
	c.push(parts.join(' > '));
	return {
		candidates: c, tag, type: el.type || '', text: text.slice(0, 120), value: el.value ?? null,
		options: tag === 'SELECT' ? [...el.options].map((o) => ({ value: o.value, label: clean(o.label) })) : null,
	};
}
"""

HIGHLIGHT_JS = r"""
(els) => {
	document.querySelectorAll('[data-ts-hl]').forEach((e) => { e.style.outline = e.dataset.tsHl; delete e.dataset.tsHl; });
	for (const e of els) { e.dataset.tsHl = e.style.outline || ''; e.style.outline = '2px solid #e5484d'; e.style.outlineOffset = '2px'; }
	return els.length;
}
"""


# ---------- redis helpers ----------


def _key(kind, ident, part):
	return f"test_studio:{kind}:{ident}:{part}"


def _get(kind, ident, part="state"):
	return frappe.cache.get_value(_key(kind, ident, part), use_local_cache=False) or {}


def _set(kind, ident, value, part="state"):
	frappe.cache.set_value(_key(kind, ident, part), value, expires_in_sec=TTL)


def push_frame(kind, ident, page, seq):
	try:
		img = page.screenshot(type="jpeg", quality=60)
	except Exception:
		return
	_set(kind, ident, {"seq": seq, "img": base64.b64encode(img).decode(), "url": page.url}, "frame")


def _next_cmd(kind, ident, timeout):
	item = frappe.cache.blpop(_key(kind, ident, "cmd"), timeout=timeout)
	return json.loads(item[1]) if item else None


def send_cmd(kind, ident, cmd):
	frappe.cache.rpush(_key(kind, ident, "cmd"), json.dumps(cmd))
	frappe.cache.expire(frappe.cache.make_key(_key(kind, ident, "cmd")), TTL)


def spawn(method, **kwargs):
	"""Run `method(**kwargs)` in a detached process as the current user."""
	if method not in SPAWNABLE:
		frappe.throw("Not allowed")
	bench = get_bench_path()
	with open(os.path.join(bench, "logs", "test_studio_live.log"), "ab") as log:
		subprocess.Popen(
			[sys.executable, "-m", "test_studio.studio", frappe.local.site, frappe.session.user, method, json.dumps(kwargs)],
			cwd=os.path.join(bench, "sites"),
			stdout=log,
			stderr=subprocess.STDOUT,
			stdin=subprocess.DEVNULL,
			start_new_session=True,
		)


def _safe(fn, default):
	try:
		return fn()
	except Exception:
		return default


# ---------- live run frames + debugger (used by runner.execute_run) ----------


SCREENCAST_EVERY = 0.25  # seconds between frames pushed to the Studio


def _start_screencast(page, run_name, state):
	"""Chromium only: stream frames while a step is running, not just between steps."""
	try:
		cdp = page.context.new_cdp_session(page)
	except Exception:
		return None  # Firefox / WebKit: per-step frames only

	# Playwright calls on_frame in its own greenlet, where frappe.local is empty: resolve the
	# Redis key here and write the same pickled value set_value() would, straight to Redis.
	cache, key = frappe.cache, frappe.cache.make_key(_key("run", run_name, "frame"))

	def on_frame(params):
		try:
			cdp.send("Page.screencastFrameAck", {"sessionId": params["sessionId"]})
		except Exception:
			pass
		now = time.monotonic()
		if now - state["sent"] < SCREENCAST_EVERY:
			return
		state["sent"], state["seq"] = now, state["seq"] + 1
		frame = {"seq": state["seq"], "img": params["data"], "url": params.get("metadata", {}).get("url") or ""}
		try:
			redis.Redis.set(cache, key, pickle.dumps(frame), ex=TTL)
		except Exception:
			pass  # a dropped frame is fine

	cdp.on("Page.screencastFrame", on_frame)
	cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 60, "maxWidth": 1600, "maxHeight": 1000})
	return cdp


def make_run_live(run_name, debug=False, breakpoints=()):
	bps, hit = {str(b) for b in breakpoints or ()}, set()
	state = {"stepping": bool(debug) and not bps, "seq": 0, "sent": 0.0, "cast": None}

	def live(event, no, page):
		if state["cast"] is None:
			state["cast"] = _start_screencast(page, run_name, state) or False
		state["seq"] += 1
		push_frame("run", run_name, page, state["seq"])  # always a sharp frame at each step boundary
		if event != "before" or not debug:
			return None
		top = no.split(".")[0]
		if not (state["stepping"] or (top in bps and top not in hit)):
			return None
		hit.add(top)
		_set("run", run_name, {"paused_at": no})
		cmd = _next_cmd("run", run_name, timeout=IDLE_TIMEOUT)
		_set("run", run_name, {"paused_at": None})
		action = (cmd or {}).get("type", "stop")  # timeout = stop
		state["stepping"] = action == "step"
		return "stop" if action == "stop" else None

	return live


# ---------- recorder / picker session ----------


class Session:
	MODES = ("interact", "pick", "assert_visible", "assert_text")

	def __init__(self, sid, page, base_url):
		self.sid, self.page, self.base_url = sid, page, (base_url or "").rstrip("/")
		self.state = {"status": "ready", "mode": "interact", "recording": True, "steps": [], "seq": 0,
		              "picked": None, "select_prompt": None, "highlight": None, "notice": None, "error": None}
		self.frame_seq = 0

	def save(self):
		self.state["url"] = self.page.url
		self.state["title"] = _safe(self.page.title, "")
		_set("session", self.sid, {**_get("session", self.sid), **self.state})

	def frame(self):
		self.frame_seq += 1
		push_frame("session", self.sid, self.page, self.frame_seq)

	def record(self, step):
		if self.state["recording"]:
			self.state["steps"].append(step)

	def info(self, pt=None):
		info = self.page.evaluate(ELEMENT_INFO_JS, pt)
		if info:
			info["unique"] = [c for c in info["candidates"] if _safe(lambda c=c: self.page.locator(c).count(), 0) == 1]
			info["selector"] = (info["unique"] or info["candidates"][-1:] or [None])[0]
		return info

	def settle(self):
		_safe(lambda: self.page.wait_for_load_state("domcontentloaded", timeout=3000), None)
		self.page.wait_for_timeout(250)

	def record_fill(self, info):
		if not info or not info.get("selector"):
			return
		value = info.get("value") or ""
		if info.get("type") == "password":
			value = "{{password}}"
			self.state["notice"] = "Password typed: recorded as {{password}}. Add a 'password' Secret Value to the suite."
		steps = self.state["steps"]
		if self.state["recording"] and steps and steps[-1]["action"] == "fill" and steps[-1]["selector"] == info["selector"]:
			steps[-1]["value"] = value
		else:
			self.record({"action": "fill", "selector": info["selector"], "value": value})

	def highlight(self, selector):
		try:
			if not selector:
				self.page.evaluate(HIGHLIGHT_JS, [])
				return 0
			return self.page.locator(selector).evaluate_all(HIGHLIGHT_JS)
		except Exception as e:
			self.state["error"] = f"Invalid selector: {str(e).splitlines()[0][:200]}"
			return 0

	def handle(self, cmd):
		t, page, st = cmd.get("type"), self.page, self.state
		st["error"] = None
		if t == "click":
			pt = [float(cmd["x"]), float(cmd["y"])]
			info = self.info(pt)
			if not info:
				page.mouse.click(*pt)
				return self.settle()
			sel, mode = info["selector"], st["mode"]
			if mode == "pick":
				st["seq"] += 1
				st["picked"] = {"seq": st["seq"], "selector": sel, "candidates": info["unique"] or [sel], "text": info["text"]}
				self.highlight(sel)
			elif mode == "assert_visible":
				self.record({"action": "assert_visible", "selector": sel})
				self.highlight(sel)
			elif mode == "assert_text":
				self.record({"action": "assert_text", "selector": sel, "value": info["text"][:80]})
				self.highlight(sel)
			elif info["tag"] == "SELECT":
				st["seq"] += 1
				st["select_prompt"] = {"seq": st["seq"], "selector": sel, "options": info["options"]}
			else:
				self.highlight(None)
				page.mouse.click(*pt)
				if info["type"] in ("checkbox", "radio"):
					checked = _safe(lambda: page.locator(sel).is_checked(), True)
					self.record({"action": "check" if checked else "uncheck", "selector": sel})
				else:
					self.record({"action": "click", "selector": sel})
				self.settle()
		elif t == "type":
			page.keyboard.type(str(cmd.get("text", ""))[:2000])
			self.record_fill(self.info())
		elif t == "press":
			key = str(cmd.get("key", ""))[:40]
			focused = self.info() if key in ("Enter", "Tab", "Escape") else None  # before focus moves
			page.keyboard.press(key)
			if key in ("Backspace", "Delete"):
				self.record_fill(self.info())
			elif focused is not None or key in ("Enter", "Tab", "Escape"):
				self.record({"action": "press", "selector": (focused or {}).get("selector") or "", "value": key})
				self.settle()
		elif t == "goto":
			url = engine.resolve_url(self.base_url, str(cmd.get("url") or "/"))
			page.goto(url, timeout=30000)
			rel = url[len(self.base_url):] if self.base_url and url.startswith(self.base_url) else url
			self.record({"action": "goto", "selector": rel or "/"})
		elif t == "scroll":
			page.mouse.wheel(0, max(-5000, min(5000, float(cmd.get("dy", 0)))))
			page.wait_for_timeout(150)
		elif t in ("back", "forward", "reload"):
			getattr(page, {"back": "go_back", "forward": "go_forward", "reload": "reload"}[t])()
			self.settle()
		elif t == "select":
			page.select_option(cmd["selector"], cmd["value"])
			self.record({"action": "select", "selector": cmd["selector"], "value": cmd["value"]})
			st["select_prompt"] = None
		elif t == "highlight":
			st["highlight"] = {"selector": cmd.get("selector"), "count": self.highlight(cmd.get("selector"))}
		elif t == "mode":
			st["mode"] = cmd.get("value") if cmd.get("value") in self.MODES else "interact"
			self.highlight(None)
		elif t == "record":
			st["recording"] = bool(cmd.get("value"))


def run_session(sid, url=None, base_url=None, width=1280, height=720, browser="chromium"):
	from playwright.sync_api import sync_playwright

	with sync_playwright() as pw:
		b = getattr(pw, browser if browser in ("chromium", "firefox", "webkit") else "chromium").launch()
		page = b.new_context(viewport={"width": int(width), "height": int(height)}).new_page()
		s = Session(sid, page, base_url)
		try:
			if url:
				try:
					s.handle({"type": "goto", "url": url})
				except Exception as e:
					s.state["error"] = str(e).split("Call log:")[0].strip()[:300]
			s.save()
			s.frame()
			last = time.monotonic()
			while time.monotonic() - last < IDLE_TIMEOUT:
				cmd = _next_cmd("session", sid, timeout=1)
				if cmd:
					last = time.monotonic()
					if cmd.get("type") == "stop":
						break
					try:
						s.handle(cmd)
					except Exception as e:
						s.state["error"] = str(e).split("Call log:")[0].strip()[:300]
					s.save()
				s.frame()  # idle frames keep animations / async UI visible
		finally:
			s.state["status"] = "closed"
			_safe(s.save, None)
			b.close()


# ---------- whitelisted API ----------


def _check_session(sid):
	state = _get("session", sid)
	if not state or state.get("owner") != frappe.session.user:
		frappe.throw("Session not found or expired", frappe.PermissionError)
	return state


@frappe.whitelist()
def start_session(suite=None, url=None):
	frappe.has_permission("Test Case", "write", throw=True)
	s = frappe.get_doc("Test Suite", suite) if suite else None
	sid = frappe.generate_hash(length=16)
	_set("session", sid, {"owner": frappe.session.user, "status": "starting"})
	spawn(
		"test_studio.studio.run_session",
		sid=sid,
		url=url or ("/" if s and s.base_url else None),
		base_url=s.base_url if s else None,
		width=(s and s.viewport_width) or 1280,
		height=(s and s.viewport_height) or 720,
		browser=(s and s.browser) or "chromium",
	)
	return sid


@frappe.whitelist()
def session_cmd(session, command):
	# params avoid "sid" and "cmd": Frappe reserves both (login session id / method name)
	sid = session
	_check_session(sid)
	cmd = json.loads(command) if isinstance(command, str) else command
	if cmd.get("type") not in SESSION_CMDS:
		frappe.throw("Unknown command")
	send_cmd("session", sid, cmd)


@frappe.whitelist()
def session_poll(session, since=0):
	sid = session
	state = _check_session(sid)
	frame = _get("session", sid, "frame")
	return {"state": state, "frame": frame if frame.get("seq", 0) > int(since or 0) else None}


@frappe.whitelist()
def run_poll(run, since=0):
	frappe.has_permission("Test Run", "read", run, throw=True)
	doc = frappe.get_doc("Test Run", run)
	frame = _get("run", run, "frame")
	return {
		"status": doc.status,
		"error": doc.error,
		"duration_ms": doc.duration_ms,
		"trace": doc.trace,
		"steps": [s.as_dict() for s in doc.steps],
		"paused_at": _get("run", run).get("paused_at"),
		"frame": frame if frame.get("seq", 0) > int(since or 0) else None,
	}


@frappe.whitelist()
def debug_cmd(run, command):
	cmd = command
	frappe.has_permission("Test Run", "write", run, throw=True)
	if cmd not in DEBUG_CMDS:
		frappe.throw("Unknown command")
	send_cmd("run", run, {"type": cmd})


@frappe.whitelist()
def get_tree():
	frappe.has_permission("Test Case", "read", throw=True)
	suites = frappe.get_all("Test Suite", fields=["name", "base_url", "browser"], order_by="name asc")
	cases = frappe.get_all(
		"Test Case", fields=["name", "title", "suite", "enabled", "last_status", "tags_text", "priority"],
		order_by="title asc",
	)
	runs = frappe.get_all(
		"Test Run", fields=["test_case", "status"], filters={"status": ["in", ["Passed", "Known Issue", "Failed", "Error"]]},
		order_by="creation desc", limit=2000,
	)
	history = {}
	for r in runs:
		h = history.setdefault(r.test_case, [])
		if len(h) < 10:
			h.append(r.status)
	cases = [c for c in cases if "snippet-run" not in (c.tags_text or "")]  # hidden cases behind "Run snippet"
	for c in cases:
		c["history"] = list(reversed(history.get(c.name, [])))
	snippets = frappe.get_all("Test Snippet", pluck="name", order_by="name asc")
	return {"suites": suites, "cases": cases, "snippets": snippets, "snippet_inputs": snippet_inputs(snippets)}


@frappe.whitelist()
def snippet_usage(name):
	"""Tests and snippets that run this snippet."""
	frappe.has_permission("Test Snippet", "read", name, throw=True)
	rows = frappe.get_all("Test Step", filters={"action": "run_snippet", "snippet": name}, fields=["parent", "parenttype"], distinct=True)
	titles = dict(frappe.get_all("Test Case", fields=["name", "title"], as_list=True))
	return [{"doctype": r.parenttype, "name": r.parent, "title": titles.get(r.parent, r.parent)} for r in rows
		if "snippet-run" not in (frappe.db.get_value("Test Case", r.parent, "tags_text") or "")]


@frappe.whitelist()
def rename_snippet(name, new_name):
	"""Rename a snippet; every Run snippet step that uses it follows (Frappe updates the links)."""
	frappe.has_permission("Test Snippet", "write", name, throw=True)
	new_name = (new_name or "").strip()
	if not new_name or new_name == name:
		return name
	frappe.rename_doc("Test Snippet", name, new_name)
	frappe.db.set_value("Test Snippet", new_name, "title", new_name)
	return new_name


def snippet_inputs(names):
	"""{snippet: [variables its steps use]}, following nested snippets: what a block needs to be given."""
	rows = frappe.get_all("Test Step", filters={"parenttype": "Test Snippet", "parent": ["in", names]},
		fields=["parent", "selector", "value", "snippet", "action"], order_by="idx asc") if names else []
	direct, calls = {n: [] for n in names}, {n: [] for n in names}
	for r in rows:
		if r.action == "run_snippet" and r.snippet:
			calls[r.parent].append(r.snippet)
		for text in (r.selector, r.value):
			for var in engine.VAR_RE.findall(text or ""):
				if var not in direct[r.parent]:
					direct[r.parent].append(var)

	def collect(name, seen):
		out = list(direct.get(name, []))
		for child in calls.get(name, []):
			if child not in seen:
				out += [v for v in collect(child, seen | {child}) if v not in out]
		return out

	return {n: collect(n, {n}) for n in names}


@frappe.whitelist()
def list_runs(test_case=None, suite=None, status=None, limit=100):
	filters = {k: v for k, v in {"test_case": test_case, "suite": suite, "status": status}.items() if v}
	runs = frappe.get_list(
		"Test Run",
		filters=filters,
		fields=["name", "test_case", "suite", "status", "browser", "started_at", "duration_ms", "pipeline_run", "creation"],
		order_by="creation desc",
		limit_page_length=min(int(limit), 500),
	)
	titles = dict(frappe.get_all("Test Case", fields=["name", "title"], as_list=True))
	for r in runs:
		r["title"] = titles.get(r.test_case, r.test_case)
	return runs


@frappe.whitelist()
def get_run(name):
	frappe.has_permission("Test Run", "read", name, throw=True)
	doc = frappe.get_doc("Test Run", name).as_dict()
	doc["title"] = frappe.db.get_value("Test Case", doc.test_case, "title")
	return doc


# what copy_suite may change on the copy; anything else in `settings` is ignored
SUITE_SETTINGS = ("base_url", "browser", "headless", "default_timeout_ms", "viewport_width", "viewport_height",
	"record_trace", "record_video", "screenshot_each_step", "read_only")


@frappe.whitelist(methods=["POST"])
def copy_suite(source, title, description=None, settings=None):
	"""A new suite with `source`'s site, browser and variables (secret values copied server-side, never returned),
	then `settings` ({"record_video": 1, ...}, see SUITE_SETTINGS) on top. Asking again for the same title returns it."""
	frappe.has_permission("Test Suite", "read", source, throw=True)
	frappe.has_permission("Test Suite", "create", throw=True)
	src = frappe.get_doc("Test Suite", source)
	title = (title or "").strip()[:140]
	if not title:
		frappe.throw("A title is needed")
	if frappe.db.exists("Test Suite", title):
		return title  # a retried call gets the same suite
	new = frappe.copy_doc(src)
	new.title = title
	new.description = description or f"Copy of {source}"
	new.update({k: v for k, v in (frappe.parse_json(settings) or {}).items() if k in SUITE_SETTINGS})
	new.set("variables", [])
	for row in src.variables:
		r = {"key": row.key, "value": row.value}
		if row.secret_value:
			r["secret_value"] = row.get_password("secret_value", raise_exception=False)
		new.append("variables", r)
	new.insert()
	return new.name


@frappe.whitelist(methods=["POST"])
def add_comment(doctype, name, text):
	"""A comment (Markdown) on any document the caller can read, in its timeline/activity. Internal: Frappe does not
	email it, and portal (customer-facing) views do not show it."""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	c = doc.add_comment("Comment", text=frappe.utils.md_to_html(text), comment_email=frappe.session.user)
	return c.name


@frappe.whitelist()
def step_timings(test_case, limit=15):
	"""Duration of each step over the test's last runs, oldest first: {step_no: [ms, ...]} plus run totals."""
	frappe.has_permission("Test Case", "read", test_case, throw=True)
	runs = frappe.get_all("Test Run", {"test_case": test_case, "status": ["not in", ["Queued", "Running"]]},
		["name", "duration_ms"], order_by="creation desc", limit=int(limit))[::-1]
	steps = {}
	if runs:
		order = {r.name: i for i, r in enumerate(runs)}
		for s in frappe.get_all("Test Run Step", {"parent": ["in", list(order)], "parenttype": "Test Run",
				"status": ["not in", ["Skipped"]]}, ["parent", "step_no", "duration_ms"]):
			steps.setdefault(s.step_no, [None] * len(runs))[order[s.parent]] = s.duration_ms
	return {"runs": [r.name for r in runs], "totals": [r.duration_ms for r in runs], "steps": steps}


@frappe.whitelist()
def list_pipelines():
	frappe.has_permission("Test Pipeline", "read", throw=True)
	out = []
	for p in frappe.get_list("Test Pipeline", fields=["name", "description"], order_by="name asc"):
		doc = frappe.get_doc("Test Pipeline", p.name)
		p["stages"] = [{"stage_name": s.stage_name, "suite": s.suite, "tag": s.tag, "stop_on_failure": s.stop_on_failure} for s in doc.stages]
		p["runs"] = frappe.get_list(
			"Test Pipeline Run", filters={"pipeline": p.name},
			fields=["name", "status", "duration_ms", "creation"], order_by="creation desc", limit_page_length=12,
		)
		out.append(p)
	return out


@frappe.whitelist()
def get_pipeline_run(name):
	frappe.has_permission("Test Pipeline Run", "read", name, throw=True)
	doc = frappe.get_doc("Test Pipeline Run", name).as_dict()
	doc["runs"] = frappe.get_list(
		"Test Run", filters={"pipeline_run": name},
		fields=["name", "test_case", "suite", "status", "duration_ms"], order_by="creation asc",
	)
	titles = dict(frappe.get_all("Test Case", fields=["name", "title"], as_list=True))
	for r in doc["runs"]:
		r["title"] = titles.get(r.test_case, r.test_case)
	return doc


@frappe.whitelist()
def get_fields(doctype):
	"""Field suggestions for Set field: labels of the doctype plus `table[1].field` for child tables."""
	frappe.has_permission("Test Case", "read", throw=True)
	if not frappe.db.exists("DocType", doctype):
		return []
	skip = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Fold", "Heading", "Image", "Read Only"}
	out = []
	for f in frappe.get_meta(doctype).fields:
		if f.fieldtype in skip or f.hidden:
			continue
		if f.fieldtype == "Table":
			for cf in frappe.get_meta(f.options).fields:
				if cf.fieldtype not in skip and not cf.hidden and not cf.read_only:
					out.append({"key": f"{f.fieldname}[1].{cf.fieldname}", "label": f"{f.label} row 1 › {cf.label}", "fieldtype": cf.fieldtype})
			continue
		if not f.read_only:
			out.append({"key": f.label or f.fieldname, "label": f.label or f.fieldname, "fieldtype": f.fieldtype, "reqd": f.reqd})
	return out


# ---------- detached process entry point ----------

if __name__ == "__main__":
	site, user, method, kwargs = sys.argv[1:5]
	if method not in SPAWNABLE:
		raise SystemExit("not allowed")
	frappe.init(site=site, sites_path=".")
	frappe.connect()
	try:
		frappe.set_user(user)
		frappe.get_attr(method)(**json.loads(kwargs))
		frappe.db.commit()
	finally:
		frappe.destroy()


# ---------- settings and retention ----------

SETTINGS = "Test Studio Settings"


def _mcp_status(url):
	"""running / not reachable: any HTTP answer (401 without its token is expected) means the server is up."""
	import urllib.error
	import urllib.request

	if not url:
		return "not set"
	try:
		urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=2)
		return "running"
	except urllib.error.HTTPError:
		return "running"
	except Exception:
		return "not reachable"


@frappe.whitelist()
def get_settings():
	"""The settings, plus whether the MCP server answers; defaults for new suites are read by the suite dialog."""
	doc = frappe.get_single(SETTINGS)
	out = doc.as_dict()
	if "System Manager" in frappe.get_roles():
		out["mcp_status"] = _mcp_status(doc.mcp_url)
		out["run_count"] = frappe.db.count("Test Run")
	return out


def runs_to_prune(runs, keep, days, now):
	"""Names of finished runs to delete: beyond the newest `keep` of their test, or older than `days` (0: no limit).
	runs: newest first, each {name, test_case, status, creation}."""
	seen, out = {}, []
	for r in runs:
		if r["status"] in ("Queued", "Running"):
			continue
		seen[r["test_case"]] = seen.get(r["test_case"], 0) + 1
		too_many = keep and seen[r["test_case"]] > keep
		too_old = days and (now - r["creation"]).days > days
		if too_many or too_old:
			out.append(r["name"])
	return out


def prune_runs():
	"""scheduler_events daily, and the Settings page's Clean up now: delete old runs (their files go with them)."""
	s = frappe.get_single(SETTINGS)
	keep, days = frappe.utils.cint(s.keep_runs_per_test), frappe.utils.cint(s.delete_runs_after_days)
	if not keep and not days:
		return 0
	runs = frappe.get_all("Test Run", fields=["name", "test_case", "status", "creation"], order_by="creation desc")
	names = runs_to_prune(runs, keep, days, frappe.utils.now_datetime())
	for name in names:
		frappe.delete_doc("Test Run", name, force=True, ignore_permissions=True, delete_permanently=True)
		frappe.db.commit()
	return len(names)


@frappe.whitelist(methods=["POST"])
def prune_now():
	frappe.only_for("System Manager")
	return prune_runs()
