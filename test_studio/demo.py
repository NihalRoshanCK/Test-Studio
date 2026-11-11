"""Demo data: bench --site <site> execute test_studio.demo.create"""

import frappe


def create():
	if frappe.db.exists("Test Suite", "TodoMVC Demo"):
		return "exists"
	frappe.get_doc({
		"doctype": "Test Snippet", "title": "Add todo",
		"description": "Types {{todo}} into the new-todo box and presses Enter",
		"steps": [
			{"action": "fill", "selector": "role=textbox[name=\"What needs to be done?\"]", "value": "{{todo}}"},
			{"action": "press", "selector": "role=textbox[name=\"What needs to be done?\"]", "value": "Enter"},
		],
	}).insert()
	frappe.get_doc({
		"doctype": "Test Suite", "title": "TodoMVC Demo", "base_url": "https://demo.playwright.dev/todomvc/",
		"variables": [{"key": "todo", "value": "Buy milk"}],
	}).insert()
	cases = [
		("Page loads", "smoke", "High", [
			{"action": "goto", "selector": "/"},
			{"action": "assert_title", "value": "TodoMVC"},
			{"action": "assert_visible", "selector": "role=textbox[name=\"What needs to be done?\"]"},
		]),
		("Add a todo", "regression", "Medium", [
			{"action": "goto", "selector": "/"},
			{"action": "run_snippet", "snippet": "Add todo"},
			{"action": "assert_text", "selector": "[data-testid=todo-title]", "value": "{{todo}}"},
			{"action": "assert_text", "selector": "[data-testid=todo-count]", "value": "1 item left"},
		]),
		("Complete a todo", "regression", "Medium", [
			{"action": "goto", "selector": "/"},
			{"action": "run_snippet", "snippet": "Add todo"},
			{"action": "check", "selector": "[data-testid=todo-item] >> role=checkbox"},
			{"action": "click", "selector": "role=link[name=\"Completed\"]"},
			{"action": "assert_count", "selector": "[data-testid=todo-item]", "value": "1"},
			{"action": "screenshot"},
		]),
	]
	for title, tag, prio, steps in cases:
		frappe.get_doc({"doctype": "Test Case", "title": title, "suite": "TodoMVC Demo", "tags_text": tag,
		                "priority": prio, "steps": steps}).insert()
	frappe.get_doc({
		"doctype": "Test Pipeline", "title": "TodoMVC Release Gate",
		"stages": [
			{"stage_name": "Smoke", "suite": "TodoMVC Demo", "tag": "smoke", "stop_on_failure": 1},
			{"stage_name": "Regression", "suite": "TodoMVC Demo", "tag": "regression", "stop_on_failure": 1},
		],
	}).insert()
	frappe.db.commit()
	return "created"
