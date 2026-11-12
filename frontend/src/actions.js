// One vocabulary for steps: what each action is called, which inputs it needs, and how it reads as a sentence.
// `fields` drive the step inspector: key is the Test Step column it writes to.

const F = {
	selector: (label, placeholder, extra = {}) => ({ key: "selector", label, placeholder, ...extra }),
	value: (label, placeholder, extra = {}) => ({ key: "value", label, placeholder, ...extra }),
};

export const ACTIONS = {
	// Frappe: what most tests need
	login: { group: "Frappe", label: "Log in as", help: "Log in with a user and password. Use variables, e.g. {{exec_user}}.", fields: [F.selector("User", "{{exec_user}}"), F.value("Password", "{{exec_password}}", { secret: true })] },
	logout: { group: "Frappe", label: "Log out", help: "End the current user's session.", fields: [] },
	new_doc: { group: "Frappe", label: "New document", help: "Open a new, empty form.", fields: [F.value("Document type", "Sales Order")] },
	set_field: { group: "Frappe", label: "Set field", help: "Fill a field by its label. Handles links, selects, checkboxes and dates. For a table row use items[1].discount_percentage.", fields: [F.selector("Field", "Customer", { suggest: "fields" }), F.value("Value", "{{customer}}")] },
	save: { group: "Frappe", label: "Save", help: "Save the form. Fails with the message Frappe shows if validation stops it.", fields: [] },
	workflow: { group: "Frappe", label: "Workflow action", help: "Run an action from the Actions menu, like Send for Approval or Approve.", fields: [F.value("Action", "Approve")] },
	expect_status: { group: "Frappe", label: "Expect status", help: "Check the status shown next to the title (workflow state or document status).", fields: [F.value("Status", "Approved")] },
	create_from: { group: "Frappe", label: "Create from this", help: "Use the Create menu, e.g. make a Sales Invoice from a Sales Order.", fields: [F.value("Create", "Sales Invoice")] },
	// Pages & elements
	goto: { group: "Page", label: "Open page", help: "Go to a URL or a path on the suite's site.", fields: [F.selector("URL or path", "/desk/sales-order")] },
	click: { group: "Page", label: "Click", help: "Click an element.", fields: [F.selector("Element", 'text="Submit"', { pick: true })] },
	fill: { group: "Page", label: "Type into", help: "Replace an input's text.", fields: [F.selector("Element", "#email", { pick: true }), F.value("Text", "")] },
	press: { group: "Page", label: "Press key", help: "Press a key, optionally on an element.", fields: [F.value("Key", "Enter"), F.selector("On element (optional)", "", { pick: true })] },
	select: { group: "Page", label: "Choose option", help: "Choose an option in a dropdown.", fields: [F.selector("Dropdown", "", { pick: true }), F.value("Option", "")] },
	check: { group: "Page", label: "Tick", help: "Tick a checkbox.", fields: [F.selector("Checkbox", "", { pick: true })] },
	uncheck: { group: "Page", label: "Untick", help: "Untick a checkbox.", fields: [F.selector("Checkbox", "", { pick: true })] },
	hover: { group: "Page", label: "Hover", help: "Move the mouse over an element.", fields: [F.selector("Element", "", { pick: true })] },
	dblclick: { group: "Page", label: "Double-click", help: "Double-click an element.", fields: [F.selector("Element", "", { pick: true })] },
	type: { group: "Page", label: "Type slowly", help: "Type key by key, firing key events.", fields: [F.selector("Element", "", { pick: true }), F.value("Text", "")] },
	upload: { group: "Page", label: "Upload file", help: "Attach a file from the server.", fields: [F.selector("File input", "", { pick: true }), F.value("File path", "")] },
	// Checks
	assert_text: { group: "Check", label: "Expect text", help: "An element must contain this text.", fields: [F.selector("Element", "", { pick: true }), F.value("Text", "")] },
	assert_visible: { group: "Check", label: "Expect visible", help: "An element must be visible.", fields: [F.selector("Element", "", { pick: true })] },
	assert_hidden: { group: "Check", label: "Expect hidden", help: "An element must be hidden or gone.", fields: [F.selector("Element", "", { pick: true })] },
	assert_value: { group: "Check", label: "Expect value", help: "An input must have this value.", fields: [F.selector("Input", "", { pick: true }), F.value("Value", "")] },
	assert_count: { group: "Check", label: "Expect count", help: "Exactly this many elements must match.", fields: [F.selector("Elements", "", { pick: true }), F.value("Count", "1")] },
	assert_url: { group: "Check", label: "Expect URL", help: "The page URL must contain this.", fields: [F.value("URL contains", "/desk/")] },
	assert_title: { group: "Check", label: "Expect title", help: "The page title must contain this.", fields: [F.value("Title contains", "")] },
	// Flow
	run_snippet: { group: "Flow", label: "Run snippet", help: "Use a snippet as a building block. Give it inputs for this use, or leave them blank to use the test's and suite's variables.", fields: [{ key: "snippet", label: "Snippet", suggest: "snippets" }] },
	store_url: { group: "Flow", label: "Remember page", help: "Save this page's address; open it later with Open page {{name}}.", fields: [F.value("Save as", "invoice_url")] },
	store_text: { group: "Flow", label: "Remember text", help: "Save an element's text or a field's value as a variable.", fields: [F.selector("Element", "", { pick: true }), F.value("Save as", "invoice_no")] },
	wait: { group: "Flow", label: "Wait", help: "Pause for a fixed time. Prefer Wait for.", fields: [F.value("Milliseconds", "1000")] },
	wait_for: { group: "Flow", label: "Wait for", help: "Wait until an element appears.", fields: [F.selector("Element", "", { pick: true })] },
	screenshot: { group: "Flow", label: "Screenshot", help: "Add a screenshot to the report.", fields: [] },
};

export const ACTION_GROUPS = ["Frappe", "Page", "Check", "Flow"];
export const GROUP_HINT = { Frappe: "Forms, fields and workflows", Page: "Pages and elements", Check: "Assertions", Flow: "Snippets, variables, waits" };
export const pickable = (action) => !!ACTIONS[action]?.fields.some((f) => f.pick);

// a Run snippet step's per-use inputs live in its value as JSON: {"discount": "8"}
export function snippetInputs(step) {
	if (step.action !== "run_snippet" || !step.value) return {};
	try { const o = JSON.parse(step.value); return o && typeof o === "object" ? Object.fromEntries(Object.entries(o).filter(([, v]) => v !== "")) : {}; } catch { return {}; }
}

// "items[1].discount_percentage" -> "Items row 1 › Discount Percentage"
export function prettyField(key) {
	const m = /^\s*(.+?)\s*\[\s*(\d+)\s*\]\s*\.\s*(.+?)\s*$/.exec(key || "");
	const title = (t) => t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
	return m ? `${title(m[1])} row ${m[2]} › ${title(m[3])}` : key || "";
}

// A step as sentence parts: [{ text, kind: "verb" | "target" | "value" | "plain" }]
export function sentence(step) {
	const a = step.action, sel = step.selector || step.target || "", val = step.value || "";
	const V = (text) => ({ text, kind: "verb" }), T = (text) => ({ text, kind: "target" }), X = (text) => ({ text, kind: "value" }), P = (text) => ({ text, kind: "plain" });
	const varName = (v) => `{{${(v || "").replace(/[{}]/g, "")}}}`;
	switch (a) {
		case "login": return [V("Log in as"), T(sel)];
		case "logout": return [V("Log out")];
		case "new_doc": return [V("New"), T(val || sel)];
		case "set_field": return [V("Set"), T(prettyField(sel)), P("to"), X(val)];
		case "save": return [V("Save")];
		case "workflow": return [V("Workflow"), T(val || sel)];
		case "expect_status": return [V("Status should be"), X(val || sel)];
		case "create_from": return [V("Create"), T(val || sel), P("from this document")];
		case "goto": return [V("Open"), T(sel || val)];
		case "run_snippet": {
			const given = Object.entries(snippetInputs(step)).map(([k, v]) => `${k} ${v}`);
			return given.length ? [V("Run"), T(step.snippet || step.group || sel), P("with"), X(given.join(", "))] : [V("Run"), T(step.snippet || step.group || sel)];
		}
		case "store_url": return [V("Remember this page as"), X(varName(val))];
		case "store_text": return [V("Remember"), T(sel), P("as"), X(varName(val))];
		case "wait": return [V("Wait"), X(`${val || 1000} ms`)];
		case "screenshot": return [V("Take a screenshot")];
		case "press": return sel ? [V("Press"), X(val), P("on"), T(sel)] : [V("Press"), X(val)];
		case "assert_text": return [V("Expect"), T(sel), P("to contain"), X(val)];
		case "assert_url": case "assert_title": return [V(ACTIONS[a].label), X(val || sel)];
		default: {
			const label = ACTIONS[a]?.label || a;
			return val ? [V(label), T(sel), P("with"), X(val)] : [V(label), T(sel)];
		}
	}
}
export const sentenceText = (step) => sentence(step).map((p) => p.text).filter(Boolean).join(" ");
