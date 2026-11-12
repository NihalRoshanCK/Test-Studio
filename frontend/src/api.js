// Thin Frappe RPC client. Errors carry the server's message so the UI can show it.
export class ApiError extends Error {}

function serverMessage(data) {
	try {
		const msgs = JSON.parse(data._server_messages || "[]").map((m) => JSON.parse(m).message);
		if (msgs.length) return msgs.join("\n").replace(/<[^>]+>/g, "");
	} catch (e) { /* fall through */ }
	return data.exception ? String(data.exception).split(":").slice(1).join(":").trim() : null;
}

export async function call(method, args = {}, { get = false } = {}) {
	const url = `/api/method/${method}`;
	const opts = { headers: { Accept: "application/json", "X-Frappe-CSRF-Token": window.csrf_token || "" }, credentials: "same-origin" };
	let res;
	if (get) {
		const q = new URLSearchParams(Object.entries(args).map(([k, v]) => [k, typeof v === "object" ? JSON.stringify(v) : v]));
		res = await fetch(`${url}?${q}`, opts);
	} else {
		opts.method = "POST";
		opts.headers["Content-Type"] = "application/json";
		opts.body = JSON.stringify(args);
		res = await fetch(url, opts);
	}
	if (res.status === 401 || res.status === 403) {
		const data = await res.json().catch(() => ({}));
		if (data.session_expired || res.status === 401) {
			window.location.href = "/login?redirect-to=" + encodeURIComponent(location.pathname);
		}
		throw new ApiError(serverMessage(data) || "You don't have permission to do that.");
	}
	const data = await res.json().catch(() => ({}));
	if (!res.ok) throw new ApiError(serverMessage(data) || `Request failed (${res.status})`);
	return data.message;
}

const S = "test_studio.studio.";
const R = "test_studio.runner.";
const C = "test_studio.checks.";
export const api = {
	tree: () => call(S + "get_tree", {}, { get: true }),
	getDoc: (doctype, name) => call("frappe.client.get", { doctype, name }, { get: true }),
	save: (doc) => call("frappe.client.save", { doc }),
	insert: (doc) => call("frappe.client.insert", { doc }),
	remove: (doctype, name) => call("frappe.client.delete", { doctype, name }),
	runCase: (name, debug = false, breakpoints = []) => call(R + "run_test_case", { name, debug: debug ? 1 : 0, breakpoints: JSON.stringify(breakpoints) }),
	runSnippet: (name, suite, before) => call(R + "run_snippet", { name, suite, before: before || null }),
	runSuite: (name, tag) => call(R + "run_test_suite", { name, tag }),
	runPipeline: (name) => call(R + "run_pipeline", { name }),
	exportTs: (name) => call(R + "export_playwright", { name }),
	runPoll: (run, since) => call(S + "run_poll", { run, since }, { get: true }),
	debug: (run, command) => call(S + "debug_cmd", { run, command }),
	startSession: (suite, url) => call(S + "start_session", { suite, url }),
	sessionCmd: (session, command) => call(S + "session_cmd", { session, command }),
	sessionPoll: (session, since) => call(S + "session_poll", { session, since }, { get: true }),
	listSnippets: () => call("frappe.client.get_list", { doctype: "Test Snippet", fields: ["name", "description", "modified"], order_by: "name asc", limit_page_length: 500 }, { get: true }),
	snippetUsage: (name) => call(S + "snippet_usage", { name }, { get: true }),
	renameSnippet: (name, new_name) => call(S + "rename_snippet", { name, new_name }),
	getFields: (doctype) => call(S + "get_fields", { doctype }, { get: true }),
	listRuns: (filters = {}) => call(S + "list_runs", filters, { get: true }),
	getRun: (name) => call(S + "get_run", { name }, { get: true }),
	listPipelines: () => call(S + "list_pipelines", {}, { get: true }),
	getPipelineRun: (name) => call(S + "get_pipeline_run", { name }, { get: true }),
	getChecks: () => call(C + "get_checks", {}, { get: true }),
	runChecks: (label) => call(C + "run_data_checks", { label }),
	getCheckRun: (name) => call(C + "get_check_run", { name }, { get: true }),
	compareChecks: (before, after) => call(C + "compare_check_runs", { before, after }, { get: true }),
	runAsUsers: (name, users) => call(R + "run_as_users", { name, users }),
	roleMatrix: (name) => call(R + "role_matrix", { name }, { get: true }),
	stepTimings: (test_case) => call(S + "step_timings", { test_case }, { get: true }),
	getSettings: () => call(S + "get_settings", {}, { get: true }),
	pruneNow: () => call(S + "prune_now", {}),
};
