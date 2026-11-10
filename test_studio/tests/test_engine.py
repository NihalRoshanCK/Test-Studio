"""Engine tests; no site needed: env/bin/python -m pytest apps/test_studio/test_studio/tests"""

import pathlib
import tempfile
import unittest

from test_studio import engine

PAGE = """<html><head><title>Demo Shop</title></head><body>
<input id="user"><input id="pw" type="password">
<button onclick="document.getElementById('msg').textContent='Welcome '+document.getElementById('user').value">Login</button>
<p id="msg"></p><ul><li>a</li><li>b</li></ul></body></html>"""


class TestPure(unittest.TestCase):
	def test_substitute(self):
		self.assertEqual(engine.substitute("hi {{ name }}!", {"name": "Bo"}), "hi Bo!")
		with self.assertRaises(engine.StepError):
			engine.substitute("{{typo}}", {})

	def test_expand_snippets_and_cycle(self):
		snippets = {"login": [{"action": "fill"}, {"action": "click"}], "loop": [{"action": "run_snippet", "snippet": "loop"}]}
		flat = engine.expand_steps([{"action": "goto"}, {"action": "run_snippet", "snippet": "login"}], snippets.get)
		self.assertEqual([n for n, _ in flat], ["1", "2.1", "2.2"])
		with self.assertRaises(engine.StepError):
			engine.expand_steps([{"action": "run_snippet", "snippet": "loop"}], snippets.get)

	def test_frappe_helpers(self):
		m = engine.ROW_FIELD_RE.match("items[2].discount_percentage")
		self.assertEqual(m.groups(), ("items", "2", "discount_percentage"))
		self.assertEqual(engine.ROW_FIELD_RE.match(" Items [1] . Qty ").groups(), ("Items", "1", "Qty"))
		self.assertIsNone(engine.ROW_FIELD_RE.match("Customer"))
		self.assertEqual(engine.slug("Sales Invoice"), "sales-invoice")
		flat = engine.expand_steps([{"action": "run_snippet", "snippet": "Login"}], {"Login": [{"action": "login"}]}.get)
		self.assertEqual(flat[0][1]["_group"], "Login")

	def test_keep_going_covers_snippet_steps(self):
		load = lambda name: [{"action": "click", "selector": "#a"}, {"action": "click", "selector": "#b"}]
		steps = engine.expand_steps([{"action": "run_snippet", "snippet": "S", "continue_on_failure": 1},
			{"action": "run_snippet", "snippet": "S"}], load)
		self.assertEqual([bool(st.get("continue_on_failure")) for _n, st in steps], [True, True, False, False])

	def test_data_rows(self):
		rows = engine.parse_rows('vin,value\nA1,"24,886.42"\n\nB2,7\n')
		self.assertEqual(rows, [{"vin": "A1", "value": "24,886.42"}, {"vin": "B2", "value": "7"}])
		self.assertEqual(engine.parse_rows("  \n"), [])
		with self.assertRaises(engine.StepError):
			engine.parse_rows("vin value\nA1")  # header is not a variable name
		with self.assertRaises(engine.StepError):
			engine.parse_rows("a,b\n1")  # wrong number of values
		steps = engine.expand_rows([("1", {"action": "goto", "selector": "/x/{{vin}}"})], rows)
		self.assertEqual([n for n, _s in steps], ["1:1", "2:1"])
		self.assertEqual(engine.substitute(steps[1][1]["selector"], engine.step_scope(steps[1][1], {"vin": "suite"})), "/x/B2")
		self.assertTrue(steps[0][1]["_group"].startswith("Row 1 (vin=A1"))

	def test_snippet_inputs(self):
		snippets = {
			"Order": [{"action": "fill", "selector": "#d", "value": "{{discount}}"}, {"action": "run_snippet", "snippet": "Inner"}],
			"Inner": [{"action": "fill", "selector": "#c", "value": "{{customer}}"}],
		}
		flat = engine.expand_steps([{"action": "run_snippet", "snippet": "Order", "value": '{"discount": "8", "customer": "{{vip}}"}'}], snippets.get)
		g = {"discount": "5", "vip": "C-1", "customer": "C-0"}
		self.assertEqual(engine.substitute(flat[0][1]["value"], engine.step_scope(flat[0][1], g)), "8")
		self.assertEqual(engine.substitute(flat[1][1]["value"], engine.step_scope(flat[1][1], g)), "C-1")  # inherited by the nested snippet
		self.assertEqual(engine.step_scope({"action": "fill"}, g), g)  # no inputs: run variables
		with self.assertRaises(engine.StepError):
			engine.expand_steps([{"action": "run_snippet", "snippet": "Inner", "value": "discount=8"}], snippets.get)

	def test_snippet_defaults(self):
		step = {"action": "fill", "value": "{{d}}", "_defaults": {"d": "1", "only": "x"}}
		self.assertEqual(engine.step_scope(step, {})["d"], "1")                               # default
		self.assertEqual(engine.step_scope(step, {"d": "5"})["d"], "5")                       # test/suite wins
		self.assertEqual(engine.step_scope({**step, "_params": {"d": "8"}}, {"d": "5"})["d"], "8")  # given at use wins

	def test_resolve_url(self):
		self.assertEqual(engine.resolve_url("https://x.io/app", "/login"), "https://x.io/app/login")
		self.assertEqual(engine.resolve_url("https://x.io", "https://y.io/a"), "https://y.io/a")

	def test_export_hides_secrets(self):
		ts = engine.to_playwright_ts("t", [("1", {"action": "fill", "selector": "#pw", "value": "{{pw}}"})],
		                             {"pw": "hunter2", "u": "bo"}, {"pw"}, "https://x.io")
		self.assertNotIn("hunter2", ts)
		self.assertIn('process.env["pw"]', ts)
		self.assertIn('vars["pw"]', ts)


class TestBrowser(unittest.TestCase):
	def run_steps(self, steps, variables, settings=None):
		with tempfile.TemporaryDirectory() as d:
			page = pathlib.Path(d, "index.html")
			page.write_text(PAGE)
			results = []
			status, error, trace, video = engine.run_case(
				[(str(i), s) for i, s in enumerate(steps, 1)], variables, [variables.get("pw", "")],
				{"base_url": page.parent.as_uri(), "default_timeout_ms": 2000, "record_trace": 1, **(settings or {})},
				lambda r, shot: results.append(r),
			)
		self.video = video
		return status, error, trace, results

	def test_pass(self):
		status, error, trace, results = self.run_steps([
			{"action": "goto", "selector": "index.html"},
			{"action": "assert_title", "value": "Demo"},
			{"action": "fill", "selector": "#user", "value": "{{user}}"},
			{"action": "fill", "selector": "#pw", "value": "{{pw}}"},
			{"action": "click", "selector": "text=Login"},
			{"action": "assert_text", "selector": "#msg", "value": "Welcome bo"},
			{"action": "assert_count", "selector": "li", "value": "2"},
		], {"user": "bo", "pw": "s3cret"})
		self.assertEqual(status, "Passed", error)
		self.assertTrue(trace and trace[:2] == b"PK")
		self.assertTrue(all(r["status"] == "Passed" for r in results))

	def test_store_and_reuse(self):
		variables = {"user": "bo"}
		status, error, _t, _r = self.run_steps([
			{"action": "goto", "selector": "index.html"},
			{"action": "store_url", "value": "page_url"},
			{"action": "fill", "selector": "#user", "value": "{{user}}"},
			{"action": "click", "selector": "text=Login"},
			{"action": "store_text", "selector": "#msg", "value": "greeting"},
			{"action": "store_text", "selector": "#user", "value": "{{typed}}"},
			{"action": "goto", "selector": "{{page_url}}"},
			{"action": "assert_title", "value": "Demo"},
		], variables)
		self.assertEqual(status, "Passed", error)
		self.assertEqual(variables["greeting"], "Welcome bo")
		self.assertEqual(variables["typed"], "bo")
		self.assertTrue(variables["page_url"].endswith("index.html"))

	def test_fail_stops_and_masks(self):
		status, error, _t, results = self.run_steps([
			{"action": "goto", "selector": "index.html"},
			{"action": "assert_text", "selector": "#msg", "value": "{{pw}}"},
			{"action": "click", "selector": "text=Login"},
		], {"pw": "s3cret"})
		self.assertEqual(status, "Failed")
		self.assertEqual([r["status"] for r in results], ["Passed", "Failed", "Skipped"])
		self.assertNotIn("s3cret", error + results[1]["error"])

	def test_video(self):
		self.run_steps([{"action": "goto", "selector": "index.html"}, {"action": "click", "selector": "text=Login"}], {},
			{"record_video": 1})
		self.assertTrue(self.video and self.video[:4] == b"\x1aE\xdf\xa3", "a WebM file")  # EBML header
		self.run_steps([{"action": "goto", "selector": "index.html"}], {})
		self.assertIsNone(self.video)

	def test_heal_click(self):
		# a passing run remembers what the button looked like...
		_s, _e, _t, results = self.run_steps([
			{"action": "goto", "selector": "index.html"}, {"action": "click", "selector": "text=Login"},
		], {})
		fp = results[1]["fingerprint"]
		self.assertEqual((fp["tag"], fp["text"]), ("button", "Login"))
		# ...so when its selector breaks, the step still clicks it and suggests the fix
		status, error, _t, results = self.run_steps([
			{"action": "goto", "selector": "index.html"},
			{"action": "fill", "selector": "#user", "value": "bo"},
			{"action": "click", "selector": "#login-btn", "fingerprint": fp, "timeout_ms": 500},
			{"action": "assert_text", "selector": "#msg", "value": "Welcome bo"},
		], {})
		self.assertEqual(status, "Passed", error)
		self.assertEqual(results[2]["healed"], 'button:visible:has-text("Login")')
		# assertions are never healed
		status, _e, _t, results = self.run_steps([
			{"action": "goto", "selector": "index.html"},
			{"action": "assert_visible", "selector": "#login-btn", "fingerprint": fp, "timeout_ms": 500},
		], {})
		self.assertEqual(status, "Failed")

	def test_blocked_call(self):
		b = engine.blocked_call
		self.assertIsNone(b("POST", "http://x/api/method/frappe.desk.form.load.getdoc"))
		self.assertIsNone(b("POST", "http://x/api/method/frappe.desk.query_report.run"))
		self.assertIsNone(b("POST", "http://x/api/method/login"))
		self.assertIsNone(b("GET", "http://x/api/resource/Item/A"))
		self.assertIsNone(b("POST", "http://x/assets/frappe/x.js"))
		self.assertEqual(b("POST", "http://x/api/method/frappe.desk.form.save.savedocs"), "frappe.desk.form.save.savedocs")
		self.assertEqual(b("POST", "http://x/api/method/frappe.client.set_value"), "frappe.client.set_value")
		self.assertEqual(b("POST", "http://x/api/v2/method/run_doc_method"), "run_doc_method")
		self.assertEqual(b("DELETE", "http://x/api/resource/Item/A"), "DELETE /api/resource/Item/A")
		self.assertIsNone(b("POST", "http://x/api/method/frappe.client.validate_link_and_fetch"))
		self.assertIsNone(b("GET", "http://x/api/method/helpdesk.api.doc.sort_options"))
		self.assertEqual(b("POST", "http://x/api/method/my_app.api.lookup"), "my_app.api.lookup")
		self.assertIsNone(b("POST", "http://x/api/method/my_app.api.lookup", {"my_app.api.lookup"}))

	def test_failed_row_skips_only_that_row(self):
		rows = engine.parse_rows("name\nnobody\nbo")
		base = [("1", {"action": "goto", "selector": "index.html"}), ("2", {"action": "fill", "selector": "#user", "value": "{{name}}"}),
			("3", {"action": "click", "selector": "text=Login"}),
			("4", {"action": "assert_text", "selector": "#msg", "value": "Welcome bo", "timeout_ms": 500}),
			("5", {"action": "assert_title", "value": "Demo"})]
		with tempfile.TemporaryDirectory() as d:
			pathlib.Path(d, "index.html").write_text(PAGE)
			results = []
			status, _e, _t, _v = engine.run_case(engine.expand_rows(base, rows), {}, [], {"base_url": pathlib.Path(d).as_uri(),
				"default_timeout_ms": 2000}, lambda r, shot: results.append(r))
		self.assertEqual(status, "Failed")
		self.assertEqual([(r["step_no"], r["status"]) for r in results if r["step_no"].endswith((":4", ":5"))],
			[("1:4", "Failed"), ("1:5", "Skipped"), ("2:4", "Passed"), ("2:5", "Passed")])

	def test_keep_going(self):
		steps = [{"action": "goto", "selector": "index.html"}, {"action": "assert_title", "value": "Nope", "timeout_ms": 300},
			{"action": "assert_title", "value": "Demo"}]
		status, _e, _t, results = self.run_steps(steps, {}, {"keep_going": 1})
		self.assertEqual((status, [r["status"] for r in results]), ("Failed", ["Passed", "Failed", "Passed"]))

	def test_known_issue(self):
		known = {"action": "assert_count", "selector": "li", "value": "0", "known_issue": "Actual value: 2"}
		# the expected failure is recorded and the run carries on
		status, error, _t, results = self.run_steps([
			{"action": "goto", "selector": "index.html"}, known, {"action": "assert_title", "value": "Demo"},
		], {})
		self.assertEqual((status, error), ("Known Issue", ""))
		self.assertEqual([r["status"] for r in results], ["Passed", "Known Issue", "Passed"])
		# a different failure is a real failure
		status, _e, _t, results = self.run_steps([
			{"action": "goto", "selector": "index.html"}, {**known, "known_issue": "Actual value: 9"},
		], {})
		self.assertEqual((status, results[1]["status"]), ("Failed", "Failed"))
		# once fixed the step passes and says so
		status, _e, _t, results = self.run_steps([
			{"action": "goto", "selector": "index.html"}, {**known, "value": "2"},
		], {})
		self.assertEqual((status, results[1]["status"]), ("Passed", "Passed"))
		self.assertIn("no longer happens", results[1]["error"])


if __name__ == "__main__":
	unittest.main()
