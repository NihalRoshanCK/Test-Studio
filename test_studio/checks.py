"""Data checks: run existing reports server-side, count their rows, and compare two runs (before / after a change)."""

import json
import time

import frappe
from frappe.utils import cint, now_datetime, nowdate

KEEP_ROWS = 500  # rows stored per check per run, for showing and comparing
NUMERIC = {"Currency", "Float", "Int", "Percent"}


def _column(c):
	"""Report columns come as dicts or as 'Label:Type/Options:Width' strings (query reports)."""
	if isinstance(c, dict):
		label = c.get("label") or c.get("fieldname") or ""
		return {"label": label, "fieldname": c.get("fieldname") or frappe.scrub(label), "fieldtype": c.get("fieldtype") or "Data"}
	parts = str(c).split(":")
	ftype = (parts[1].split("/")[0] if len(parts) > 1 else "") or "Data"
	return {"label": parts[0], "fieldname": frappe.scrub(parts[0]), "fieldtype": ftype}


def report_rows(report, filters):
	from frappe.desk.query_report import run

	out = run(report, filters=filters, ignore_prepared_report=True)
	cols = [_column(c) for c in out.get("columns") or []]
	rows = []
	for r in out.get("result") or []:
		if isinstance(r, dict):
			rows.append([r.get(c["fieldname"]) for c in cols])
		elif isinstance(r, list | tuple):
			rows.append(list(r)[: len(cols)])
	if out.get("add_total_row") and rows:
		rows.pop()
	return cols, rows


def execute_check_run(run_name):
	run = frappe.get_doc("Data Check Run", run_name)
	run.update({"status": "Running", "started_at": now_datetime(), "error": None})
	run.set("results", [])
	run.save(ignore_permissions=True)
	frappe.db.commit()
	t0, seen = time.monotonic(), set()
	try:
		checks = frappe.get_all("Data Check", {"enabled": 1}, ["name", "report", "filters", "max_rows"], order_by="title asc")
		for c in checks:
			s0, row = time.monotonic(), {"data_check": c.name, "max_rows": cint(c.max_rows)}
			try:
				cols, rows = report_rows(c.report, json.loads((c.filters or "{}").replace("{{today}}", nowdate())))
				row.update(row_count=len(rows), status="Passed" if len(rows) <= cint(c.max_rows) else "Failed",
					columns=json.dumps(cols), rows=json.dumps(rows[:KEEP_ROWS], default=str))
			except Exception:
				row.update(status="Error", error=frappe.get_traceback()[-1000:])
			finally:
				frappe.db.rollback()  # a check only reads: drop anything the report wrote
			row["duration_ms"] = int((time.monotonic() - s0) * 1000)
			seen.add(row["status"])
			run.append("results", row)
			run.save(ignore_permissions=True)
			frappe.db.set_value("Data Check", c.name, {"last_status": row["status"], "last_row_count": row.get("row_count") or 0},
				update_modified=False)
			frappe.db.commit()
		run.status = "Error" if "Error" in seen else "Failed" if "Failed" in seen else "Passed"
	except Exception:
		run.update({"status": "Error", "error": frappe.get_traceback()})
	run.duration_ms = int((time.monotonic() - t0) * 1000)
	run.save(ignore_permissions=True)
	frappe.db.commit()
	return run.status


def run_nightly():
	"""scheduler_events daily"""
	if frappe.db.count("Data Check", {"enabled": 1}):
		run = frappe.get_doc({"doctype": "Data Check Run", "label": "Nightly"}).insert(ignore_permissions=True)
		frappe.db.commit()
		execute_check_run(run.name)


def _keyed(cols, rows):
	"""Rows by their non-number columns (warehouse, item, voucher...), so a changed amount reads as 'changed'."""
	idx = [i for i, c in enumerate(cols) if c["fieldtype"] not in NUMERIC] or list(range(len(cols)))
	out = {}
	for r in rows:
		base = " | ".join(str(r[i]) for i in idx if i < len(r))
		k, n = base, 2
		while k in out:  # same key twice: keep both
			k, n = f"{base} #{n}", n + 1
		out[k] = r
	return out


def diff(cols, before, after, limit=100):
	b, a = _keyed(cols, before), _keyed(cols, after)
	return {
		"added": [a[k] for k in a if k not in b][:limit],
		"removed": [b[k] for k in b if k not in a][:limit],
		"changed": [{"before": b[k], "after": a[k]} for k in a if k in b and a[k] != b[k]][:limit],
	}


# ---------- API ----------


@frappe.whitelist()
def run_data_checks(label=None, wait=0):
	"""wait=1 runs the checks in this request (a few seconds) instead of the queue: for a caller that itself holds
	the worker (an automation), which would otherwise wait on its own job."""
	frappe.only_for("System Manager")
	run = frappe.get_doc({"doctype": "Data Check Run", "label": label}).insert()
	if frappe.utils.cint(wait):
		frappe.db.commit()
		execute_check_run(run.name)
	else:
		frappe.enqueue("test_studio.checks.execute_check_run", queue="long", timeout=3600, enqueue_after_commit=True, run_name=run.name)
	return run.name


@frappe.whitelist()
def get_checks():
	frappe.only_for("System Manager")
	return {
		"checks": frappe.get_all("Data Check", fields=["name", "title", "enabled", "report", "filters", "max_rows", "description",
			"last_status", "last_row_count"], order_by="title asc"),
		"runs": frappe.get_all("Data Check Run", fields=["name", "label", "status", "creation", "duration_ms"],
			order_by="creation desc", limit=30),
	}


def _results(run_name):
	run = frappe.get_doc("Data Check Run", run_name)
	return run, {r.data_check: r for r in run.results}


@frappe.whitelist()
def get_check_run(name):
	frappe.only_for("System Manager")
	run, _ = _results(name)
	out = run.as_dict()
	for r in out["results"]:
		r["columns"], r["rows"] = json.loads(r.columns or "[]"), json.loads(r.rows or "[]")
	return out


@frappe.whitelist()
def compare_check_runs(before, after):
	"""Per check: row counts before and after, and the rows added, removed and changed."""
	frappe.only_for("System Manager")
	_b, rb = _results(before)
	_a, ra = _results(after)
	out = []
	for check in dict.fromkeys([*rb, *ra]):
		x, y = rb.get(check), ra.get(check)
		cols = json.loads((y or x).columns or "[]")
		d = diff(cols, json.loads(x.rows or "[]") if x else [], json.loads(y.rows or "[]") if y else [])
		out.append({"check": check, "columns": cols, "before": x.row_count if x else None, "after": y.row_count if y else None,
			"before_status": x.status if x else None, "after_status": y.status if y else None, **d})
	return out
