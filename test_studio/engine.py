"""Framework-free test engine: variable substitution, snippet expansion, step execution, codegen.

Kept free of frappe imports so it can be unit-tested and reused outside the desk.
"""

import json
import os
import re
import shutil
import tempfile
import time
from urllib.parse import urljoin, urlparse

VAR_RE = re.compile(r"\{\{\s*([\w.-]+)\s*\}\}")
MAX_SNIPPET_DEPTH = 5
# Opening a page depends on the server (a cold start, a busy dev server), not on the test: page loads get at least
# this long, while clicks and checks keep the suite's shorter limit so a wrong assertion still fails fast.
NAV_MIN_MS = 30000
NAV_ACTIONS = {"goto", "login", "logout", "new_doc"}


class StepError(Exception):
	pass


def substitute(text, variables):
	"""Replace {{key}} with variables[key]; unknown keys raise so typos fail loudly."""
	if not text:
		return ""

	def repl(m):
		key = m.group(1)
		if key not in variables:
			raise StepError(f"Unknown variable {{{{{key}}}}}")
		return str(variables[key])

	return VAR_RE.sub(repl, str(text))


def mask(text, secrets):
	for s in secrets:
		if s:
			text = text.replace(s, "••••")
	return text


# ---------- read-only runs ----------
# shortcut: a Frappe call is treated as a read when its name says so (get_*, load*, search*, run...); a whitelisted
# "get_" method that writes would slip through. For a hard guarantee also log in as a user without write permission.
READ_CALL_RE = re.compile(
	r"(^|\.)(get\w*|load\w*|run|search\w*|validate\w*|check\w*|query\w*|ping|login|logout|can_\w+|has_\w+|is_\w+|count\w*"
	r"|fetch\w*|format\w*|\w*_options|\w*boot\w*)$"
)
# blocked like any write, but not reported: desk housekeeping the user did not ask for
QUIET_CALLS = {
	"frappe.desk.doctype.route_history.route_history.deferred_insert",
	"frappe.model.utils.user_settings.save",
	"frappe.desk.listview.set_list_settings",
}


def blocked_call(method, url, allow=()):
	"""None if a browser request may go out in a read-only run, else a name for the write it would make.
	allow: extra method names the suite treats as reads (a custom app's own read calls)."""
	path = urlparse(url).path
	if "/api/" not in path:
		return None
	rest = re.sub(r"^v\d+/", "", path.split("/api/", 1)[1])
	if rest.startswith("method/"):
		name = rest[len("method/"):].strip("/")
		return None if READ_CALL_RE.search(name) or name in allow else name
	return None if method in ("GET", "HEAD", "OPTIONS") else f"{method} /api/{rest}"


# ---------- self-healing selectors ----------
# Only actions that act on an element; an assertion is never healed (that would hide a real failure).
HEAL_ACTIONS = {"click", "dblclick", "fill", "type", "press", "select", "check", "uncheck", "hover", "upload"}

FINGERPRINT_JS = r"""
e => ({
	tag: e.tagName.toLowerCase(), id: e.id || '', name: e.getAttribute('name') || '', type: e.getAttribute('type') || '',
	text: (e.innerText || e.value || '').replace(/\s+/g, ' ').trim().slice(0, 80),
	aria: e.getAttribute('aria-label') || '', placeholder: e.getAttribute('placeholder') || '', title: e.getAttribute('title') || '',
	label: e.getAttribute('data-label') || '', role: e.getAttribute('role') || '',
	fieldname: e.closest('[data-fieldname]')?.getAttribute('data-fieldname') || '',
	cls: [...e.classList].slice(0, 4),
})
"""

# Finds the visible element most like the fingerprint; marks it data-ts-heal and returns a stable selector for it.
HEAL_JS = r"""
fp => {
	document.querySelectorAll('[data-ts-heal]').forEach(e => e.removeAttribute('data-ts-heal'));
	const txt = e => (e.innerText || e.value || '').replace(/\s+/g, ' ').trim().slice(0, 80);
	const score = e => {
		let s = 0;
		const a = (k, v, w) => { if (v && e.getAttribute(k) === v) s += w; };
		if (fp.id && e.id === fp.id) s += 5;
		a('name', fp.name, 3); a('aria-label', fp.aria, 3); a('placeholder', fp.placeholder, 3); a('data-label', fp.label, 3);
		a('title', fp.title, 2); a('role', fp.role, 1); a('type', fp.type, 1);
		if (fp.fieldname && e.closest('[data-fieldname]')?.getAttribute('data-fieldname') === fp.fieldname) s += 3;
		if (fp.text) s += txt(e) === fp.text ? 5 : (txt(e).includes(fp.text) || fp.text.includes(txt(e)) && txt(e)) ? 1 : 0;
		s += fp.cls.filter(c => e.classList.contains(c)).length * 0.5;
		return s;
	};
	const seen = [...document.querySelectorAll(fp.tag)].filter(e => e.getClientRects().length).map(e => [score(e), e]).sort((x, y) => y[0] - x[0]);
	if (!seen.length || seen[0][0] < 5 || (seen[1] && seen[1][0] === seen[0][0])) return null;
	const e = seen[0][1];
	e.setAttribute('data-ts-heal', '1');
	const q = v => JSON.stringify(v);
	const one = s => { try { return document.querySelectorAll(s).length === 1 && s; } catch (x) { return false; } };
	const fn = e.closest('[data-fieldname]')?.getAttribute('data-fieldname');
	return {
		selector: (e.id && one('#' + CSS.escape(e.id))) || (e.name && one(`${fp.tag}[name=${q(e.name)}]`))
			|| (e.getAttribute('aria-label') && one(`${fp.tag}[aria-label=${q(e.getAttribute('aria-label'))}]`))
			|| (fn && one(`[data-fieldname=${q(fn)}] ${fp.tag}`))
			|| (txt(e) && `${fp.tag}:visible:has-text(${q(txt(e))})`) || '',
		score: seen[0][0],
	};
}
"""


def snippet_inputs(step):
	"""A run_snippet step's per-use inputs: its value holds a JSON object like {"discount": "8"}."""
	raw = (step.get("value") or "").strip()
	if not raw:
		return {}
	try:
		data = json.loads(raw)
	except ValueError:
		raise StepError(f"Snippet inputs must be JSON, got {raw[:60]}") from None
	return {str(k): str(v) for k, v in data.items() if str(v) != ""} if isinstance(data, dict) else {}


def expand_steps(steps, load_snippet, _depth=0, _prefix="", _inputs=None):
	"""Flatten run_snippet steps into [(step_no, step_dict)]. load_snippet(name) -> list of step dicts.

	Sub-steps carry `_params`: the inputs given where the snippet is used (inner uses win)."""
	if _depth > MAX_SNIPPET_DEPTH:
		raise StepError("Snippets nested too deep (possible cycle)")
	out = []
	for i, step in enumerate(steps, 1):
		no = f"{_prefix}{i}"
		if step.get("action") == "run_snippet":
			if not step.get("snippet"):
				raise StepError(f"Step {no}: run_snippet needs a snippet")
			inputs = {**(_inputs or {}), **snippet_inputs(step)}
			sub = expand_steps(load_snippet(step["snippet"]), load_snippet, _depth + 1, f"{no}.", inputs)
			keep = {"continue_on_failure": 1} if step.get("continue_on_failure") else {}  # "keep going" covers its steps
			out.extend((n, {**st, "_group": st.get("_group") or step["snippet"], **keep}) for n, st in sub)
		else:
			out.append((no, {**step, "_params": _inputs} if _inputs else step))
	return out


def resolve_url(base_url, url):
	if base_url and not re.match(r"^\w+://", url or ""):
		return urljoin(base_url.rstrip("/") + "/", (url or "").lstrip("/"))
	return url


def _var_name(name):
	name = (name or "").strip().strip("{}").strip()
	if not re.fullmatch(r"[\w.-]+", name):
		raise StepError("store_url / store_text need a variable name in Value, e.g. invoice_url")
	return name


def parse_rows(text):
	"""Data rows from CSV text: a header of variable names, then one row per pass. [] when empty."""
	import csv
	import io

	lines = [ln for ln in (text or "").splitlines() if ln.strip()]
	if not lines:
		return []
	reader = csv.reader(io.StringIO("\n".join(lines)))
	header = [h.strip() for h in next(reader)]
	bad = [h for h in header if not re.fullmatch(r"[\w.-]+", h)]
	if bad:
		raise StepError(f"Data rows: column names must be variable names, not {', '.join(map(repr, bad))}")
	rows = []
	for n, values in enumerate(reader, 2):
		if len(values) != len(header):
			raise StepError(f"Data rows, line {n}: {len(values)} values for {len(header)} columns (quote values with commas)")
		rows.append({h: v.strip() for h, v in zip(header, values, strict=True)})
	return rows


def expand_rows(steps, rows):
	"""The flattened steps once per data row: step numbers "<row>:<no>", grouped "Row n", the row's values in scope."""
	out = []
	for i, row in enumerate(rows, 1):
		label = f"Row {i} ({', '.join(f'{k}={v}' for k, v in row.items())})"[:120]
		for no, st in steps:
			out.append((f"{i}:{no}", {**st, "_row": row, "_row_no": i,
				"_group": f"{label} · {st['_group']}" if st.get("_group") else label}))
	return out


def step_scope(step, variables):
	"""Variables a step sees: the run's, with its data row's values and its snippet inputs (themselves {{var}}-able) in front."""
	params, defaults, row = step.get("_params"), step.get("_defaults"), step.get("_row")
	if not (params or defaults or row):
		return variables
	# snippet defaults < test/suite variables < the data row < inputs given where a snippet is used
	base = {**(defaults or {}), **variables, **(row or {})}
	return {**base, **{k: substitute(v, base) for k, v in (params or {}).items()}}


def step_timeout(step, default_timeout):
	timeout = step.get("timeout_ms") or default_timeout
	return max(timeout, NAV_MIN_MS) if step.get("action") in NAV_ACTIONS else timeout


def run_step(page, step, variables, base_url, default_timeout, login=None):
	"""Execute one step against a Playwright sync Page. Raises on failure."""
	from playwright.sync_api import expect

	action = step["action"]
	scope = step_scope(step, variables)
	sel = substitute(step.get("selector"), scope)
	val = step.get("value") if action.startswith("store_") else substitute(step.get("value"), scope)
	timeout = step_timeout(step, default_timeout)
	loc = page.locator(sel) if sel else None

	def need_sel():
		if not loc:
			raise StepError(f"{action} needs a selector")
		return loc

	match action:
		case "goto":
			page.goto(resolve_url(base_url, sel or val), timeout=timeout)
		case "click":
			need_sel().click(timeout=timeout)
		case "dblclick":
			need_sel().dblclick(timeout=timeout)
		case "fill":
			need_sel().fill(val, timeout=timeout)
		case "type":
			need_sel().press_sequentially(val, timeout=timeout)
		case "press":
			if loc:
				loc.press(val, timeout=timeout)
			else:
				page.keyboard.press(val)
		case "select":
			need_sel().select_option(val, timeout=timeout)
		case "check":
			need_sel().check(timeout=timeout)
		case "uncheck":
			need_sel().uncheck(timeout=timeout)
		case "hover":
			need_sel().hover(timeout=timeout)
		case "upload":
			need_sel().set_input_files(val, timeout=timeout)
		case "wait":
			page.wait_for_timeout(int(val or 1000))
		case "wait_for":
			need_sel().first.wait_for(timeout=timeout)
		case "assert_visible":
			expect(need_sel().first).to_be_visible(timeout=timeout)
		case "assert_hidden":
			expect(need_sel().first).to_be_hidden(timeout=timeout)
		case "assert_text":
			expect(need_sel().first).to_contain_text(val, timeout=timeout)
		case "assert_value":
			expect(need_sel().first).to_have_value(val, timeout=timeout)
		case "assert_count":
			expect(need_sel()).to_have_count(int(val), timeout=timeout)
		case "assert_url":
			expect(page).to_have_url(re.compile(re.escape(val or sel)), timeout=timeout)
		case "assert_title":
			expect(page).to_have_title(re.compile(re.escape(val or sel)), timeout=timeout)
		case "store_url":
			variables[_var_name(val)] = page.url
		case "store_text":
			el = need_sel().first
			tag = el.evaluate("e => e.tagName")
			variables[_var_name(val)] = (el.input_value(timeout=timeout) if tag in ("INPUT", "TEXTAREA", "SELECT") else el.inner_text(timeout=timeout)).strip()
		case "screenshot":
			pass  # the caller captures a screenshot for this action
		case "login":
			frappe_login(page, base_url, sel, val, timeout, login)
		case "logout":
			page.context.clear_cookies()  # a test-run logout; the UI logout needs a confirm dialog
			page.goto(resolve_url(base_url, "/login"), timeout=timeout)
		case "new_doc":
			page.goto(resolve_url(base_url, f"/desk/{slug(val or sel)}/new"), timeout=timeout)
			_wait_form(page, timeout)
		case "set_field":
			frappe_set_field(page, sel, val, timeout)
		case "save":
			frappe_save(page, timeout)
		case "workflow":
			frappe_workflow(page, val or sel, timeout)
		case "expect_status":
			expect(page.locator(STATUS)).to_contain_text(val or sel, timeout=timeout)
		case "create_from":
			frappe_create_from(page, val or sel, timeout)
		case _:
			raise StepError(f"Unknown action {action}")


# ---------- Frappe desk helpers ----------
# Frappe keeps previous pages in the DOM (hidden), so every lookup is scoped to what is visible.
STATUS = ".page-head:visible .page-indicator-pill, .page-head:visible .indicator-pill >> nth=0"
ROW_FIELD_RE = re.compile(r"^\s*(.+?)\s*\[\s*(\d+)\s*\]\s*\.\s*(.+?)\s*$")

# Marks the control for `key` (fieldname or label) with data-ts-target, opening its tab / collapsed section.
FIND_FIELD_JS = r"""
([key, scopeSel]) => {
	document.querySelectorAll('[data-ts-target]').forEach(e => e.removeAttribute('data-ts-target'));
	const shown = e => { const pc = e.closest('.page-container'); return !pc || getComputedStyle(pc).display !== 'none'; };
	const scope = scopeSel ? [...document.querySelectorAll(scopeSel)].find(e => e.getClientRects().length) : document;  // fixed-position panels have no offsetParent
	if (!scope) return null;
	const norm = t => (t || '').replace(/\*/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
	const all = [...scope.querySelectorAll('.frappe-control[data-fieldname]')].filter(e => shown(e) && (scopeSel || !e.closest('.form-in-grid, .grid-row')));
	const c = all.find(e => e.dataset.fieldname === key)
		|| all.find(e => norm(e.querySelector('.control-label, label, .grid-heading-row')?.innerText) === norm(key));
	if (!c) return null;
	const pane = c.closest('.tab-pane');
	if (pane && !pane.classList.contains('active')) document.querySelector(`[data-bs-target="#${pane.id}"], [href="#${pane.id}"], [aria-controls="${pane.id}"]`)?.click();
	const head = c.closest('.form-section')?.querySelector('.section-head.collapsed');
	if (head) head.click();
	c.setAttribute('data-ts-target', '1');
	return { fieldname: c.dataset.fieldname, fieldtype: c.dataset.fieldtype, label: (c.querySelector('.control-label, label')?.innerText || '').trim() };
}
"""


def slug(doctype):
	return (doctype or "").strip().lower().replace(" ", "-")


def screen_message(page):
	"""Text of a visible Frappe dialog (validation error, permission error...), if any."""
	try:
		box = page.locator(".modal.show .modal-body:visible").first
		return box.inner_text(timeout=300).strip() if box.count() else ""
	except Exception:
		return ""


def _wait_form(page, timeout):
	page.locator(".page-head:visible").first.wait_for(timeout=timeout)
	page.locator(".frappe-control[data-fieldname]:visible").first.wait_for(timeout=timeout)


def frappe_login(page, base_url, user, password, timeout, login=None):
	"""login(user, password) -> sid, when given, checks the password on the server and returns a session: the
	password never goes through the browser, so it cannot end up in a trace or a video. Without it the login page
	is filled in (outside a Frappe site, e.g. unit tests)."""
	page.context.clear_cookies()
	if login:
		try:
			sid = login(user, password)
		except Exception as e:
			raise StepError(f"Login failed for {user}: {str(e) or type(e).__name__}") from None
		page.context.add_cookies([{"name": "sid", "value": sid, "url": resolve_url(base_url, "/")}])
		page.goto(resolve_url(base_url, "/desk"), timeout=timeout)
		return
	page.goto(resolve_url(base_url, "/login"), timeout=timeout)
	page.locator("#login_email").fill(user, timeout=timeout)
	page.locator("#login_password").fill(password, timeout=timeout)
	page.locator("#login_password").press("Enter")
	try:
		page.wait_for_url(lambda u: "/login" not in u, timeout=timeout)
	except Exception:
		msg = page.locator(".login-content .page-card-body .text-danger, .invalid-login, .indicator.red").all_inner_texts()
		raise StepError(f"Login failed for {user}" + (f": {' '.join(msg).strip()}" if any(msg) else "")) from None


def _find(page, key, scope, timeout):
	end = time.monotonic() + timeout / 1000
	while time.monotonic() < end:
		info = page.evaluate(FIND_FIELD_JS, [key, scope])
		if info:
			page.wait_for_timeout(150)  # let a just-opened section / tab render
			return info, page.locator("[data-ts-target]")
		page.wait_for_timeout(200)
	raise StepError(f"No field '{key}' on this form")


def _set_control(page, ctrl, info, value, timeout):
	ftype, label = info["fieldtype"], info["label"] or info["fieldname"]
	if ftype in ("Link", "Dynamic Link", "Table MultiSelect"):
		inp = ctrl.locator("input").first
		inp.fill(value, timeout=timeout)
		option = ctrl.locator("[role=option], .awesomplete li").filter(has_text=value).first
		try:
			option.click(timeout=timeout)
		except Exception:
			raise StepError(f"'{value}' is not offered for {label}: it doesn't exist, is filtered out, or this user can't see it") from None
	elif ftype == "Select":
		ctrl.locator("select").first.select_option(label=value, timeout=timeout)
	elif ftype == "Check":
		box = ctrl.locator("input[type=checkbox]").first
		box.set_checked(str(value).strip().lower() in ("1", "true", "yes", "on", "y"), timeout=timeout)
	elif ftype in ("Text Editor", "HTML Editor"):
		ed = ctrl.locator(".ql-editor, textarea").first
		ed.click(timeout=timeout)
		ed.fill(value, timeout=timeout)
	elif ftype in ("Small Text", "Text", "Long Text", "Code"):
		ctrl.locator("textarea").first.fill(value, timeout=timeout)
	else:  # Data, Int, Float, Currency, Percent, Date, Datetime, ...
		inp = ctrl.locator("input").first
		inp.fill(value, timeout=timeout)
		inp.press("Escape" if ftype in ("Date", "Datetime", "Time") else "Tab")
	page.wait_for_timeout(300)  # client scripts react to the change


def frappe_set_field(page, key, value, timeout):
	"""key: field label or fieldname, or `items[1].discount_percentage` for a child-table row."""
	m = ROW_FIELD_RE.match(key or "")
	if not m:
		info, ctrl = _find(page, key, None, timeout)
		return _set_control(page, ctrl, info, value, timeout)
	table, idx, field = m.group(1), int(m.group(2)), m.group(3)
	_info, grid = _find(page, table, None, timeout)
	rows = grid.locator(".grid-body .grid-row")
	while rows.count() < idx:
		grid.locator(".grid-add-row").first.click(timeout=timeout)
		page.wait_for_timeout(300)
	rows.nth(idx - 1).locator(".btn-open-row").first.click(timeout=timeout)
	page.locator(".form-in-grid:visible").first.wait_for(timeout=timeout)
	info, ctrl = _find(page, field, ".form-in-grid", timeout)
	_set_control(page, ctrl, info, value, timeout)
	page.keyboard.press("Escape")
	page.locator(".form-in-grid:visible").first.wait_for(state="hidden", timeout=timeout)


def _status(page):
	try:
		return page.locator(STATUS).inner_text(timeout=500).strip()
	except Exception:
		return ""


def _wait_until(page, done, what, timeout):
	end = time.monotonic() + timeout / 1000
	while time.monotonic() < end:
		msg = screen_message(page)
		if msg and "are you sure" not in msg.lower():
			raise StepError(f"{what} failed: {msg}")
		if done():
			return
		page.wait_for_timeout(200)
	raise StepError(f"{what} did not finish in {timeout} ms")


def frappe_save(page, timeout):
	page.keyboard.press("Control+s")
	_wait_until(page, lambda: "/new-" not in page.url and "Not Saved" not in _status(page), "Save", timeout)


def frappe_workflow(page, action_name, timeout):
	before = _status(page)
	page.locator('.page-head:visible button:has-text("Actions")').first.click(timeout=timeout)
	item = page.locator(f'role=menuitem[name="{action_name}"]')
	try:
		item.first.click(timeout=min(timeout, 5000))
	except Exception:
		offered = [t.strip() for t in page.locator("[role=menuitem]").all_inner_texts() if t.strip()]
		page.keyboard.press("Escape")
		raise StepError(f"Workflow action '{action_name}' is not available here. Offered: {', '.join(offered) or 'none'}") from None
	yes = page.locator('.modal.show button:has-text("Yes")')
	page.wait_for_timeout(300)
	if yes.count() and yes.first.is_visible():
		yes.first.click()
	_wait_until(page, lambda: _status(page) not in ("", before), f"Workflow '{action_name}'", timeout)


def frappe_create_from(page, target, timeout):
	page.reload(timeout=timeout)  # the Create menu is built on load, not after a workflow change
	_wait_form(page, timeout)
	page.locator('.page-head:visible button:has-text("Create")').first.click(timeout=timeout)
	item = page.locator(f'role=menuitem[name="{target}"]')
	try:
		item.first.click(timeout=min(timeout, 5000))
	except Exception:
		offered = [t.strip() for t in page.locator("[role=menuitem]").all_inner_texts() if t.strip()]
		raise StepError(f"'{target}' is not in the Create menu. Offered: {', '.join(offered) or 'none'}") from None
	page.wait_for_url(re.compile(r"/new-"), timeout=timeout)
	_wait_form(page, timeout)


def _fingerprint(page, step, variables, timeout):
	"""What the step's element looks like (waits for it like the action would). None: not an element action;
	False: the element never showed up."""
	if step["action"] not in HEAL_ACTIONS or not step.get("selector"):
		return None
	try:
		return page.locator(substitute(step["selector"], step_scope(step, variables))).first.evaluate(FINGERPRINT_JS, timeout=timeout)
	except Exception:
		return False


def _heal(page, step, variables, base_url, default_timeout):
	"""Retry an element action on the element most like the one it last worked on; returns the new selector or None."""
	fp = step.get("fingerprint")
	if step["action"] not in HEAL_ACTIONS or not fp:
		return None
	try:
		found = page.evaluate(HEAL_JS, json.loads(fp) if isinstance(fp, str) else fp)
		if not found:
			return None
		run_step(page, {**step, "selector": "[data-ts-heal]", "timeout_ms": 3000}, variables, base_url, default_timeout)
		return found["selector"] or "[an element with no stable selector]"
	except Exception:
		return None


def run_case(steps, variables, secrets, settings, on_step, live=None):
	"""Run flattened steps in a fresh browser context.

	settings keys: browser, headless, base_url, default_timeout_ms, viewport_width,
	viewport_height, record_trace, screenshot_each_step, read_only (block writes from the browser),
	session ({"user", "sid"}: start signed in as that user; login steps are then skipped),
	keep_going (do not stop at a failure), record_video, login_session (fn(user, password) -> sid: log in
	without typing the password in the browser).
	on_step(result: dict, screenshot: bytes | None) is called after every step; a passing step on an element
	carries result["fingerprint"], and a healed one result["healed"] (the selector that worked).
	live(event, step_no, page) is called with "before"/"after" around each step and "done" at the end;
	it may block (debugger pause) and may return "stop" to skip the remaining steps.
	Returns (status, error_text, trace_bytes | None, video_bytes | None); video when settings["record_video"].
	"""
	from playwright.sync_api import sync_playwright

	status, error, trace, video = "Passed", "", None, None
	with sync_playwright() as pw:
		browser = getattr(pw, settings.get("browser") or "chromium").launch(headless=bool(settings.get("headless", 1)))
		size = {"width": settings.get("viewport_width") or 1280, "height": settings.get("viewport_height") or 720}
		video_dir = tempfile.mkdtemp(prefix="ts-video-") if settings.get("record_video") else None
		ctx = browser.new_context(viewport=size, **({"record_video_dir": video_dir, "record_video_size": size} if video_dir else {}))
		tracing = settings.get("record_trace")
		if tracing:
			# with a video, the trace's own screen recording only doubles it (and it is most of a trace's size)
			ctx.tracing.start(screenshots=not video_dir, snapshots=True)
		blocked = []
		if settings.get("read_only"):

			allow = {a.strip() for a in (settings.get("read_only_allow") or "").splitlines() if a.strip()}

			def guard(route):
				name = blocked_call(route.request.method, route.request.url, allow)
				if name is None:
					return route.continue_()
				if name not in QUIET_CALLS:
					blocked.append(name)
				return route.abort("blockedbyclient")

			ctx.route("**/api/**", guard)
		session = settings.get("session")
		if session:
			ctx.add_cookies([{"name": "sid", "value": session["sid"], "url": resolve_url(settings.get("base_url"), "/")}])
		page = ctx.new_page()
		stop, skip_row = False, None  # a failed data row skips the rest of that row only
		default_timeout = settings.get("default_timeout_ms") or 10000
		try:
			for no, step in steps:
				result = {"step_no": no, "action": step["action"], "group": step.get("_group") or ""}
				try:
					result["target"] = mask(substitute(step.get("selector"), step_scope(step, variables)), secrets)[:140]
				except StepError:
					result["target"] = step.get("selector") or ""
				if step["action"] != "login":  # login's value is the password
					try:
						result["value"] = mask(substitute(step.get("value"), step_scope(step, variables)), secrets)[:140]
					except StepError:
						result["value"] = step.get("value") or ""
				if not stop and live and live("before", no, page) == "stop":
					stop = True
				if stop or (skip_row is not None and step.get("_row_no") == skip_row):
					on_step({**result, "status": "Skipped", "duration_ms": 0}, None)
					continue
				if session and step["action"] in ("login", "logout"):
					on_step({**result, "status": "Skipped", "duration_ms": 0, "error": f"Running as {session['user']}"}, None)
					continue
				t0, shot = time.monotonic(), None
				timeout = step_timeout(step, default_timeout)
				try:
					fp = _fingerprint(page, step, variables, timeout)
					if fp is False:  # already waited the full timeout; don't wait again in run_step
						raise StepError(f"Timed out after {timeout / 1000:.0f}s waiting for {result['target']}")
					run_step(page, step, variables, settings.get("base_url"), default_timeout, settings.get("login_session"))
					result["status"] = "Passed"
					if fp:
						result["fingerprint"] = fp
					took = time.monotonic() - t0
					if step.get("known_issue"):
						result["error"] = "Known failure no longer happens: clear Known Failure on this step"
					elif step["action"] != "wait" and took > 0.7 * timeout / 1000:
						result["error"] = f"Slow: took {took:.1f}s of its {timeout / 1000:.0f}s timeout"
					if settings.get("screenshot_each_step") or step["action"] == "screenshot":
						shot = page.screenshot()
				except Exception as e:
					healed = _heal(page, step, variables, settings.get("base_url"), default_timeout)
					msg = str(e).split("Call log:")[0].strip()
					shown = screen_message(page)
					if shown and shown not in msg:
						msg += f"\nOn screen: {shown}"
					msg = mask(msg, secrets)
					shot = _safe_screenshot(page)
					known = (step.get("known_issue") or "").strip()
					if healed:
						result.update(status="Passed", healed=healed, error=f"Healed: '{result['target']}' was not found; "
							f"used {healed} instead. Update the step's selector.")
						shot = None
					elif known and known in msg:  # the expected failure: record it, keep going
						result.update(status="Known Issue", error=msg[:1000])
						if status == "Passed":
							status = "Known Issue"
					else:
						result.update(status="Failed", error=msg[:1000])
						status = "Failed"
						error = error or f"Step {no} ({step['action']}): {msg}"
						if not (step.get("continue_on_failure") or settings.get("keep_going")):
							if step.get("_row_no") is not None:
								skip_row = step["_row_no"]
							else:
								stop = True
				result["duration_ms"] = int((time.monotonic() - t0) * 1000)
				if blocked:
					note = "Blocked (read-only run): " + ", ".join(dict.fromkeys(blocked))
					result["error"] = f"{result['error']}\n{note}" if result.get("error") else note
					blocked.clear()
				on_step(result, shot)
				if live:
					live("after", no, page)
			if live:
				live("done", None, page)
		finally:
			if tracing:
				fd, path = tempfile.mkstemp(suffix=".zip")
				os.close(fd)
				try:
					ctx.tracing.stop(path=path)
					with open(path, "rb") as fh:
						trace = fh.read()
				finally:
					os.unlink(path)
			if video_dir:
				try:
					ctx.close()  # the video file is complete only once its context closes
					clips = sorted((os.path.join(video_dir, f) for f in os.listdir(video_dir) if f.endswith(".webm")),
						key=os.path.getsize, reverse=True)
					if clips:  # one per page; the main page's is the longest
						with open(clips[0], "rb") as fh:
							video = fh.read()
				finally:
					shutil.rmtree(video_dir, ignore_errors=True)
			browser.close()
	return status, error, trace, video


def _safe_screenshot(page):
	try:
		return page.screenshot()
	except Exception:
		return None


# ---------- Export to Playwright TypeScript ----------

_TS = {
	"goto": "await page.goto({u});",
	"click": "await page.locator({s}).click();",
	"dblclick": "await page.locator({s}).dblclick();",
	"fill": "await page.locator({s}).fill({v});",
	"type": "await page.locator({s}).pressSequentially({v});",
	"select": "await page.locator({s}).selectOption({v});",
	"check": "await page.locator({s}).check();",
	"uncheck": "await page.locator({s}).uncheck();",
	"hover": "await page.locator({s}).hover();",
	"upload": "await page.locator({s}).setInputFiles({v});",
	"wait": "await page.waitForTimeout({n});",
	"wait_for": "await page.locator({s}).first().waitFor();",
	"assert_visible": "await expect(page.locator({s}).first()).toBeVisible();",
	"assert_hidden": "await expect(page.locator({s}).first()).toBeHidden();",
	"assert_text": "await expect(page.locator({s}).first()).toContainText({v});",
	"assert_value": "await expect(page.locator({s}).first()).toHaveValue({v});",
	"assert_count": "await expect(page.locator({s})).toHaveCount({n});",
	"assert_url": "await expect(page).toHaveURL(new RegExp(escapeRe({t})));",
	"assert_title": "await expect(page).toHaveTitle(new RegExp(escapeRe({t})));",
	"screenshot": "await page.screenshot({{ path: 'step-{no}.png' }});",
	"store_url": "vars[{vn}] = page.url();",
	"store_text": "vars[{vn}] = ((await page.locator({s}).first().inputValue().catch(() => null)) ?? (await page.locator({s}).first().innerText())).trim();",
}


def _ts_str(text):
	"""JS template literal; {{var}} becomes ${vars["var"]}."""
	esc = str(text or "").replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
	return "`" + VAR_RE.sub(lambda m: "${vars[" + json.dumps(m.group(1)) + "]}", esc) + "`"


def to_playwright_ts(title, steps, variables, secret_keys, base_url):
	"""steps: flattened [(no, step)]. Secret values are read from process.env, never inlined."""
	var_lines = [f"  {json.dumps(k)}: {json.dumps(v)}," for k, v in variables.items() if k not in secret_keys]
	var_lines += [f"  {json.dumps(k)}: process.env[{json.dumps(k)}] ?? ''," for k in secret_keys]
	lines = ["import { test, expect } from '@playwright/test';", ""]
	if base_url:
		lines += [f"test.use({{ baseURL: {json.dumps(base_url)} }});", ""]
	lines += [
		"const vars: Record<string, string> = {", *var_lines, "};",
		"const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');",
		"",
		f"test({json.dumps(title)}, async ({{ page }}) => {{",
	]
	for no, st in steps:
		a, sel, val = st["action"], st.get("selector"), st.get("value")
		if a == "press":
			line = (
				f"await page.locator({_ts_str(sel)}).press({_ts_str(val)});"
				if sel
				else f"await page.keyboard.press({_ts_str(val)});"
			)
		else:
			url = sel or val or ""
			if base_url and not re.match(r"^\w+://", url):
				url = url.lstrip("/")  # Playwright resolves "/x" to the origin; engine resolves it under base_url
			line = _TS.get(a, f"// unsupported action: {a}").format(
				s=_ts_str(sel), v=_ts_str(val), u=_ts_str(url), t=_ts_str(val or sel),
				n=int(val) if str(val or "").strip().isdigit() else 1000, no=no.replace(".", "_"),
				vn=json.dumps(str(val or "").strip().strip("{}").strip()),
			)
		note = f"  // {st['note']}" if st.get("note") else ""
		lines.append(f"  {line}{note}  // step {no}")
	lines.append("});")
	return "\n".join(lines) + "\n"
