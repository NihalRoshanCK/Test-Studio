<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter, onBeforeRouteLeave } from "vue-router";
import { Play, Bug, Square, Save, Plus, MoreHorizontal, FileCode2, History, CopyPlus, Trash2, ExternalLink, Disc, ArrowLeft, FlaskConical, Puzzle, ChevronDown, SlidersHorizontal, MonitorPlay, ListChecks, Users, Settings2, Table2, FastForward } from "lucide-vue-next";
import StepInspector from "../components/StepInspector.vue";
import RunPanel from "../components/RunPanel.vue";
import Sentence from "../components/Sentence.vue";
import { ACTIONS, ACTION_GROUPS, GROUP_HINT } from "../actions";
import StepRow from "../components/StepRow.vue";
import BrowserStage from "../components/BrowserStage.vue";
import SuiteDialog from "../components/SuiteDialog.vue";
import NewItemDialog from "../components/NewItemDialog.vue";
import ExportDialog from "../components/ExportDialog.vue";
import Modal from "../components/Modal.vue";
import StatusBadge from "../components/StatusBadge.vue";
import { api } from "../api";
import { useSession } from "../composables/useSession";
import { useRun } from "../composables/useRun";
import { toast, toastError } from "../toast";
import { DONE, store } from "../format";

const route = useRoute();
const router = useRouter();
const tree = ref({ suites: [], cases: [], snippets: [] });
const doc = ref(null);
const kind = ref("case"); // "case" | "snippet"
const dirty = ref(false);
const saving = ref(false);
const activeRow = ref(null);
const bps = ref(new Set());
const wide = ref(store.get("wide", false));
const dialog = ref(null);
const menu = ref(false);
const pickRow = ref(null);
const statusMsg = ref(null);
const selectedStep = ref(null);
const browseSuite = ref(null);
let lastAdded = null;
const tab = ref("step"); // right panel: step | browser | run
const showTree = ref(store.get("tree", true));
watch(showTree, (v) => store.set("tree", v));
const adding = ref(false);
const insertAt = ref(null); // set by the "+" between steps; null = after the selected step
watch(adding, (on) => on && requestAnimationFrame(() => document.getElementById("step-picker")?.scrollIntoView({ block: "end", behavior: "smooth" })));
const expanded = ref(new Set());
const snippetSteps = ref({});
const lastRun = ref(null);
const fieldCache = {};
const fieldList = ref([]);

// stable v-for keys for step objects (new rows have no name yet)
const ids = new WeakMap();
let nextId = 0;
const keyOf = (o) => ids.get(o) ?? (ids.set(o, ++nextId), nextId);

const steps = computed(() => doc.value?.steps || []);
const suiteName = computed(() => (kind.value === "case" ? doc.value?.suite : browseSuite.value));

// ---------- live browser + runs ----------
const { s: session, start: startSession, stop: stopSession, cmd, setMode, setRecording } = useSession({
	onSteps(fresh) {
		if (!doc.value) return;
		for (const step of fresh) {
			const row = { doctype: "Test Step", ...step };
			doc.value.steps.push(row);
			lastAdded = row;
		}
		activeRow.value = doc.value.steps.length - 1;
		markDirty();
		requestAnimationFrame(() => document.querySelector("#steps > li:last-child")?.scrollIntoView({ block: "nearest", behavior: "smooth" }));
	},
	onFillUpdate(value) {
		if (lastAdded && lastAdded.action === "fill" && lastAdded.value !== value) { lastAdded.value = value; markDirty(); }
	},
	onPick(p) {
		const i = pickRow.value ?? activeRow.value;
		const target = i != null ? doc.value?.steps[i] : null;
		if (target) { target.selector = p.selector; markDirty(); }
		else navigator.clipboard?.writeText(p.selector).catch(() => {});
		statusMsg.value = { tone: "pass", lead: target ? `Step ${i + 1} now targets` : "Copied", code: p.selector, alts: p.candidates.filter((c) => c !== p.selector), row: i };
		pickRow.value = null;
	},
	onSelect(prompt) { dialog.value = { type: "select", prompt, value: prompt.options[0]?.value }; },
});
const { r: run, start: startRun, follow: followRun, debug, clear: clearRun } = useRun(() => loadTree());
const runBefore = ref("");
const usage = ref([]);
watch(() => doc.value?.name, async (n) => { usage.value = []; if (n && kind.value === "snippet") try { usage.value = await api.snippetUsage(n); } catch { /* optional */ } });
const defaults = computed(() => { try { return JSON.parse(doc.value?.input_defaults || "{}"); } catch { return {}; } });
function setDefault(k, v) {
	const next = { ...defaults.value, [k]: v };
	if (v === "") delete next[k];
	doc.value.input_defaults = Object.keys(next).length ? JSON.stringify(next) : "";
	markDirty();
}
async function duplicateSnippet() {
	menu.value = false;
	const keep = ["action", "selector", "value", "snippet", "note", "timeout_ms", "continue_on_failure", "known_issue", "fingerprint"];
	try {
		const d = await api.insert({ doctype: "Test Snippet", title: `${doc.value.title} (copy)`, description: doc.value.description, input_defaults: doc.value.input_defaults,
			steps: doc.value.steps.map((st) => Object.fromEntries(keep.filter((k) => st[k] != null && st[k] !== "").map((k) => [k, st[k]]))) });
		await loadTree();
		open(d.name, "snippet");
	} catch (e) { toastError(e); }
}
watch(() => doc.value?.name, (n) => n && kind.value === "snippet" && (runBefore.value = store.get(`before:${n}`, "")));
watch(runBefore, (v) => doc.value && kind.value === "snippet" && store.set(`before:${doc.value.name}`, v));
async function runSnippet() {
	if (!steps.value.length || runActive.value) return;
	await saveFirst();
	if (dirty.value) return; // save failed
	stopSession();
	statusMsg.value = null;
	try { followRun(await api.runSnippet(doc.value.name, browseSuite.value, runBefore.value), doc.value.name); } catch (e) { toastError(e); }
}

const results = computed(() => {
	if (!run.name || !doc.value || run.caseName !== doc.value.name) return {};
	const out = {};
	const own = kind.value === "snippet" ? (runBefore.value ? "2" : "1") : null;
	for (const r of run.steps) {
		const parts = String(r.step_no).split(".");
		if (own && parts[0] !== own) continue; // the "first run" snippet
		const top = own ? parts[1] : parts[0];
		const prev = out[top];
		if (!prev) out[top] = { ...r };
		else {
			prev.duration_ms = (prev.duration_ms || 0) + (r.duration_ms || 0);
			if (r.status === "Failed") Object.assign(prev, { status: "Failed", error: r.error }); // a snippet fails if any sub-step fails
			else if (r.status === "Known Issue" && prev.status !== "Failed") Object.assign(prev, { status: "Known Issue", error: r.error });
		}
	}
	return out;
});
const runningIndex = computed(() => {
	if (!run.name || DONE.includes(run.status) || run.pausedAt || run.caseName !== doc.value?.name) return -1;
	return Object.keys(results.value).length;
});
const pausedIndex = computed(() => (run.pausedAt ? parseInt(run.pausedAt, 10) - 1 : -1));
const runActive = computed(() => !!run.name && !DONE.includes(run.status));

// ---------- loading ----------
async function loadTree() {
	try {
		tree.value = await api.tree();
		if (!browseSuite.value) browseSuite.value = tree.value.suites[0]?.name;
	} catch (e) { toastError(e); }
}
async function open(name, k = "case") {
	if (doc.value?.name === name && kind.value === k) return;
	if (!(await confirmDiscard())) return;
	try {
		const d = await api.getDoc(k === "case" ? "Test Case" : "Test Snippet", name);
		d.steps = d.steps || [];
		doc.value = d;
		kind.value = k;
		dirty.value = false;
		activeRow.value = null;
		lastAdded = null;
		statusMsg.value = null;
		bps.value = new Set(store.get(`bps:${name}`, []));
		expanded.value = new Set();
		tab.value = "step";
		loadLastRun().then(() => { if (lastRun.value && activeRow.value == null) tab.value = "run"; });
		if (run.caseName && run.caseName !== name) clearRun();
		const want = k === "case" ? "test" : "snippet";
		if (route.name !== want || route.params.name !== name) router.replace({ name: want, params: { name } });
	} catch (e) { toastError(e); }
}
const routeKind = () => (route.name === "snippet" ? "snippet" : "case");
watch(() => route.params.name, (n) => n && open(n, routeKind()));

// ---------- editing ----------
function markDirty() { dirty.value = true; }
function select(i) { activeRow.value = i; tab.value = "step"; }
async function toggleExpand(i) {
	const name = doc.value.steps[i].snippet;
	const next = new Set(expanded.value);
	if (next.has(i)) next.delete(i);
	else {
		next.add(i);
		if (name && !snippetSteps.value[name]) {
			try { snippetSteps.value = { ...snippetSteps.value, [name]: (await api.getDoc("Test Snippet", name)).steps || [] }; } catch (e) { toastError(e); }
		}
	}
	expanded.value = next;
}
// doctype the selected step works on: the nearest New document / Create from above it
const ctxDoctype = computed(() => {
	for (let i = activeRow.value ?? -1; i >= 0; i--) {
		const st = steps.value[i];
		if (st && ["new_doc", "create_from"].includes(st.action) && st.value && !/\{\{/.test(st.value)) return st.value;
	}
	return null;
});
watch(ctxDoctype, async (dt) => {
	if (!dt) return (fieldList.value = []);
	try { fieldList.value = fieldCache[dt] ||= await api.getFields(dt); } catch { fieldList.value = []; }
});
async function loadLastRun() {
	lastRun.value = null;
	if (kind.value !== "case" || !doc.value) return;
	try {
		const [r] = await api.listRuns({ test_case: doc.value.name, limit: 1 });
		if (r) lastRun.value = await api.getRun(r.name);
	} catch { /* history is optional */ }
}
function patch(i, change) {
	Object.assign(doc.value.steps[i], change);
	if ("action" in change && change.action !== "run_snippet") doc.value.steps[i].snippet = null;
	markDirty();
}
function focusRow(i) { requestAnimationFrame(() => document.querySelector(`#steps > li:nth-child(${i + 1}) select`)?.focus()); }
function addStep(action = "set_field", extra = {}) {
	const at = insertAt.value ?? (activeRow.value != null ? activeRow.value + 1 : steps.value.length);
	insertAt.value = null;
	doc.value.steps.splice(at, 0, { doctype: "Test Step", action, selector: "", value: "", ...extra });
	adding.value = false;
	select(at);
	markDirty();
	requestAnimationFrame(() => document.querySelector("#insp-selector, #insp-value, #insp-snippet")?.focus());
}
function duplicate(i) {
	const { name, idx, ...copy } = doc.value.steps[i];
	doc.value.steps.splice(i + 1, 0, copy);
	activeRow.value = i + 1;
	markDirty();
}
function remove(i) {
	doc.value.steps.splice(i, 1);
	activeRow.value = steps.value.length ? Math.min(i, steps.value.length - 1) : null;
	markDirty();
}
function move(i, delta) {
	const j = i + delta;
	if (j < 0 || j >= steps.value.length) return;
	const [row] = doc.value.steps.splice(i, 1);
	doc.value.steps.splice(j, 0, row);
	activeRow.value = j;
	markDirty();
	focusRow(j);
}
let dragFrom = null;
function drop(i) {
	if (dragFrom == null || dragFrom === i) return;
	const [row] = doc.value.steps.splice(dragFrom, 1);
	doc.value.steps.splice(i, 0, row);
	activeRow.value = i;
	dragFrom = null;
	markDirty();
}
function toggleBp(i) {
	const k = String(i + 1);
	const next = new Set(bps.value);
	next.has(k) ? next.delete(k) : next.add(k);
	bps.value = next;
	store.set(`bps:${doc.value.name}`, [...next]);
}

async function save() {
	if (!doc.value || saving.value || !dirty.value) return;
	const wanted = (doc.value.title || "").trim();
	const rename = kind.value === "snippet" && wanted && wanted !== doc.value.name;
	if (rename) doc.value.title = doc.value.name; // save under the current ID first, then rename
	saving.value = true;
	try {
		doc.value.steps.forEach((s, i) => (s.idx = i + 1));
		const saved = await api.save(doc.value);
		saved.steps = saved.steps || [];
		doc.value = saved;
		lastAdded = null;
		dirty.value = false;
		if (rename) {
			const old = doc.value.name;
			const newName = await api.renameSnippet(old, wanted);
			dirty.value = false;
			doc.value = null;
			await loadTree();
			await open(newName, "snippet");
			toast(`Renamed to ${newName}; tests using it were updated`, "success");
			return;
		}
		toast("Saved", "success", 1800);
		loadTree();
	} catch (e) { toastError(e); } finally { saving.value = false; }
}
const saveFirst = () => (dirty.value ? save() : Promise.resolve());

// ---------- actions ----------
async function runTest(withDebug) {
	if (kind.value !== "case" || !steps.value.length || runActive.value) return;
	await saveFirst();
	if (dirty.value) return; // save failed
	stopSession();
	statusMsg.value = null;
	selectedStep.value = null;
	await startRun(doc.value.name, { debug: withDebug, breakpoints: [...bps.value] });
}
async function toggleRecord() {
	if (session.id && session.recording) return setRecording(false);
	if (session.id) { await setRecording(true); return setMode("interact"); }
	clearRun();
	await startSession(suiteName.value, { recording: true, existingSteps: steps.value.length });
}
async function openBrowser() {
	clearRun();
	await startSession(suiteName.value, { recording: false, existingSteps: steps.value.length });
}
async function pickFor(i) {
	activeRow.value = i;
	if (!session.id) await openBrowser();
	if (!session.id) return;
	pickRow.value = i;
	await setMode("pick");
	statusMsg.value = { tone: "warn", lead: `Click an element in the page to target it from step ${i + 1}.` };
}
async function testSelector(sel) {
	if (!session.id) await openBrowser();
	if (!session.id) return;
	statusMsg.value = null;
	cmd({ type: "highlight", selector: sel });
}
function useAlt(sel, row) {
	if (row == null || !doc.value.steps[row]) return;
	doc.value.steps[row].selector = sel;
	markDirty();
	statusMsg.value = { tone: "pass", lead: `Step ${row + 1} now targets`, code: sel, alts: [], row };
}
// data rows: the steps run once per row, the row's columns as {{variables}}
const rowCount = computed(() => Math.max(0, (doc.value?.data_rows || "").split("\n").filter((l) => l.trim()).length - 1));
function openRows() {
	menu.value = false;
	dialog.value = { type: "rows", text: doc.value.data_rows || "" };
}
function saveRows() {
	const lines = dialog.value.text.split("\n").filter((l) => l.trim());
	if (lines.length === 1) return toast("Add at least one row under the header line", "error");
	doc.value.data_rows = lines.length ? dialog.value.text.trim() : "";
	markDirty();
	dialog.value = null;
}
function toggleKeepGoing() {
	menu.value = false;
	doc.value.keep_going = doc.value.keep_going ? 0 : 1;
	markDirty();
}

// run the test signed in as each user (a role matrix); the users are saved on the test
let matrixTimer;
async function openRunAs() {
	menu.value = false;
	await saveFirst();
	dialog.value = { type: "runas", users: doc.value.run_as || "", rows: [] };
	loadMatrix();
}
async function loadMatrix() {
	clearTimeout(matrixTimer);
	if (dialog.value?.type !== "runas") return;
	try { dialog.value.rows = await api.roleMatrix(doc.value.name); } catch (e) { toastError(e); }
	if (dialog.value?.rows?.some((r) => ["Queued", "Running"].includes(r.status))) matrixTimer = setTimeout(loadMatrix, 2000);
}
async function runAs() {
	try {
		await api.runAsUsers(doc.value.name, dialog.value.users);
		doc.value.run_as = dialog.value.users;
		toast("Runs queued, one per user", "info");
		loadMatrix();
	} catch (e) { toastError(e); }
}
async function exportTs() {
	menu.value = false;
	await saveFirst();
	try { dialog.value = { type: "export", code: await api.exportTs(doc.value.name) }; } catch (e) { toastError(e); }
}
async function duplicateTest() {
	menu.value = false;
	const strip = (rows) => (rows || []).map(({ name, parent, parenttype, parentfield, creation, modified, owner, modified_by, ...rest }) => rest);
	const { name, creation, modified, owner, modified_by, last_status, ...rest } = doc.value;
	try {
		const copy = await api.insert({ ...rest, title: `${doc.value.title} (copy)`, steps: strip(doc.value.steps), variables: strip(doc.value.variables) });
		dirty.value = false;
		await loadTree();
		open(copy.name);
	} catch (e) { toastError(e); }
}
function openExtract() {
	menu.value = false;
	const at = (activeRow.value ?? 0) + 1;
	dialog.value = { type: "extract", from: at, to: Math.min(steps.value.length, at + 2), title: "", description: "" };
}
const extractRange = computed(() => {
	const d = dialog.value;
	if (d?.type !== "extract") return [];
	const a = Math.max(1, Math.min(d.from, d.to)), b = Math.min(steps.value.length, Math.max(d.from, d.to));
	return steps.value.slice(a - 1, b);
});
const extractInputs = computed(() => [...new Set(extractRange.value.flatMap((st) => [st.selector, st.value].join(" ").match(/\{\{\s*[\w.-]+\s*\}\}/g) || []).map((v) => v.replace(/[{}\s]/g, "")))]);
async function extractSnippet() {
	const d = dialog.value, title = d.title.trim();
	if (!title || !extractRange.value.length) return;
	await saveFirst();
	if (dirty.value) return;
	const keep = ["action", "selector", "value", "snippet", "note", "timeout_ms", "continue_on_failure", "known_issue", "fingerprint"];
	try {
		await api.insert({ doctype: "Test Snippet", title, description: d.description.trim(),
			steps: extractRange.value.map((st) => Object.fromEntries(keep.filter((k) => st[k] != null && st[k] !== "").map((k) => [k, st[k]]))) });
		const a = Math.min(d.from, d.to);
		doc.value.steps.splice(a - 1, extractRange.value.length, { doctype: "Test Step", action: "run_snippet", snippet: title, selector: "", value: "" });
		markDirty();
		dialog.value = null;
		await save();
		select(a - 1);
		toast(`Saved ${title} as a snippet; step ${a} now runs it`, "success");
	} catch (e) { toastError(e); }
}
async function deleteItem() {
	dialog.value = null;
	try {
		await api.remove(kind.value === "case" ? "Test Case" : "Test Snippet", doc.value.name);
		toast(`Deleted ${doc.value.title || doc.value.name}`, "success");
		dirty.value = false;
		doc.value = null;
		router.replace({ name: kind.value === "case" ? "tests" : "snippets" });
		loadTree();
	} catch (e) { toastError(e); }
}
async function create({ title, suite, description }) {
	const type = dialog.value.type;
	try {
		if (type === "new-snippet") {
			const d = await api.insert({ doctype: "Test Snippet", title, description, steps: [] });
			dialog.value = null;
			await loadTree();
			return open(d.name, "snippet");
		}
		const d = await api.insert({ doctype: "Test Case", title, suite, steps: [] });
		dialog.value = null;
		dirty.value = false;
		await loadTree();
		await open(d.name);
		if (type === "record") toggleRecord();
	} catch (e) { toastError(e); }
}
async function editSuite(name) {
	try { dialog.value = { type: "suite", suite: await api.getDoc("Test Suite", name) }; } catch (e) { toastError(e); }
}
async function runSuite(name) {
	try {
		const runs = await api.runSuite(name);
		toast(`${runs.length} tests queued from ${name}`, "info");
		router.push({ name: "runs" });
	} catch (e) { toastError(e); }
}

// ---------- unsaved changes ----------
let discardResolve = null;
function confirmDiscard() {
	if (!dirty.value) return Promise.resolve(true);
	return new Promise((resolve) => { discardResolve = resolve; dialog.value = { type: "discard" }; });
}
function resolveDiscard(ok) { dialog.value = null; if (ok) dirty.value = false; discardResolve?.(ok); discardResolve = null; }
onBeforeRouteLeave(async (to) => {
	if (to.name === "test" || to.name === "snippet") return true;
	if (!(await confirmDiscard())) return false;
	stopSession();
	return true;
});
const beforeUnload = (e) => { if (dirty.value) { e.preventDefault(); e.returnValue = ""; } };

// ---------- shortcuts ----------
function onKey(e) {
	const mod = e.ctrlKey || e.metaKey;
	const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) || e.target.isContentEditable;
	if (doc.value && !typing && !dialog.value && activeRow.value != null) {
		const i = activeRow.value;
		if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) { e.preventDefault(); return move(i, e.key === "ArrowUp" ? -1 : 1); }
		if (e.key === "ArrowUp" && i > 0) { e.preventDefault(); return select(i - 1); }
		if (e.key === "ArrowDown" && i < steps.value.length - 1) { e.preventDefault(); return select(i + 1); }
		if (e.key === "Delete") { e.preventDefault(); return remove(i); }
		if (mod && e.key.toLowerCase() === "d") { e.preventDefault(); return duplicate(i); }
	}
	if (mod && e.key.toLowerCase() === "s") { e.preventDefault(); save(); }
	else if (mod && e.key === "Enter") { e.preventDefault(); kind.value === "snippet" ? runSnippet() : runTest(false); }
	else if (e.key === "F8" && run.pausedAt) { e.preventDefault(); debug("continue"); }
	else if (e.key === "F10" && run.pausedAt) { e.preventDefault(); debug("step"); }
}
onMounted(async () => {
	window.addEventListener("keydown", onKey);
	window.addEventListener("beforeunload", beforeUnload);
	await loadTree();
	if (route.params.name) open(route.params.name, routeKind());
});
onBeforeUnmount(() => {
	clearTimeout(matrixTimer);
	window.removeEventListener("keydown", onKey);
	window.removeEventListener("beforeunload", beforeUnload);
	stopSession();
	clearRun();
});
watch(wide, (v) => store.set("wide", v));
watch(() => run.name, (n) => n && (tab.value = "browser"));
watch(() => run.status, (st) => { if (DONE.includes(st) && run.caseName === doc.value?.name) { tab.value = "run"; loadLastRun(); } });
watch(() => session.id || session.starting, (on) => on && (tab.value = "browser"));
const panelRun = computed(() => (run.name && run.caseName === doc.value?.name ? { ...run, duration_ms: run.duration } : lastRun.value));
const grouped = ACTION_GROUPS.map((g) => [g, Object.entries(ACTIONS).filter(([, m]) => m.group === g)]);
const hl = computed(() => session.state?.highlight);
watch(hl, (h) => h && (statusMsg.value = null));
const modeHint = {
	interact: "Use the page normally.",
	pick: "Click an element to copy its selector.",
	assert_visible: "Click an element that must be visible.",
	assert_text: "Click an element whose text must match.",
};
</script>

<template>
	<div class="flex h-full flex-col bg-paper">
		<!-- the top of every editor, as in QCS Flow: the way back, what this is, whether it is saved, the actions -->
		<header v-if="doc" class="flex h-[60px] shrink-0 items-center justify-between gap-3 border-b border-line bg-panel px-3 sm:px-5">
			<div class="flex min-w-0 items-center gap-3">
				<router-link :to="{ name: kind === 'case' ? 'tests' : 'snippets' }" class="icon-btn shrink-0" :title="`Back to ${kind === 'case' ? 'Tests' : 'Snippets'}`" :aria-label="`Back to ${kind === 'case' ? 'Tests' : 'Snippets'}`"><ArrowLeft class="h-4 w-4" /></router-link>
				<span class="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-brand/10 text-brand max-sm:hidden" aria-hidden="true"><FlaskConical v-if="kind === 'case'" class="h-4 w-4" /><Puzzle v-else class="h-4 w-4" /></span>
				<div class="min-w-0">
					<input v-model="doc.title" class="-ml-1 w-[min(46vw,560px)] truncate rounded bg-transparent px-1 text-[15px] font-semibold outline-none enabled:hover:bg-sunk enabled:focus:bg-sunk"
						aria-label="Title" @input="markDirty" />
					<div class="flex min-w-0 items-center gap-1.5 overflow-hidden whitespace-nowrap text-xs text-muted">
						<router-link :to="{ name: kind === 'case' ? 'tests' : 'snippets' }" class="hover:text-ink max-sm:hidden">{{ kind === 'case' ? 'Tests' : 'Snippets' }}</router-link>
						<span aria-hidden="true">/</span>
						<button v-if="kind === 'case'" class="inline-flex items-center gap-1 hover:text-ink" :title="`Settings of suite ${doc.suite} (video, screenshots, timeout, logins)`" @click="editSuite(doc.suite)">{{ doc.suite }}<Settings2 class="h-3 w-3" /></button>
						<span v-else class="inline-flex items-center gap-1">browse on <select v-model="browseSuite" class="h-5 rounded bg-sunk px-1 text-xs" aria-label="Suite to browse"><option v-for="s in tree.suites" :key="s.name">{{ s.name }}</option></select></span>
						<span aria-hidden="true">·</span>
						<span v-if="dirty" class="flex items-center gap-1 text-warn"><span class="h-1.5 w-1.5 rounded-full bg-warn" />Not saved</span>
						<span v-else>Saved</span>
					</div>
				</div>
			</div>
			<div class="flex shrink-0 items-center gap-1 sm:gap-1.5">
				<button class="btn-ghost px-2.5" :disabled="!dirty || saving" title="Save (Ctrl+S)" @click="save"><Save class="h-4 w-4" /><span class="max-md:sr-only">Save</span></button>
				<button class="btn-ghost px-2.5" :class="session.recording && 'text-rec'" :title="session.recording ? 'Stop recording' : 'Record steps by using the site'" @click="toggleRecord">
					<Square v-if="session.recording" class="h-3.5 w-3.5 fill-current" /><Disc v-else class="h-4 w-4 text-rec" /><span class="max-md:sr-only">{{ session.recording ? 'Stop' : 'Record' }}</span>
				</button>
				<template v-if="kind === 'snippet'">
					<button class="btn-ghost px-2.5" title="This snippet's inputs and their defaults" @click="dialog = { type: 'inputs' }">
						<SlidersHorizontal class="h-4 w-4" /><span class="max-md:sr-only">Inputs</span>
						<span class="rounded-full bg-sunk px-1.5 text-xs tabular-nums text-muted">{{ (tree.snippet_inputs?.[doc.name] || []).length }}</span>
					</button>
					<label class="pill relative max-lg:hidden" title="Run another snippet first, like a login">
						First run <span class="max-w-[160px] truncate font-medium text-ink">{{ runBefore || "nothing" }}</span><ChevronDown class="h-3.5 w-3.5" />
						<select v-model="runBefore" class="absolute inset-0 cursor-pointer opacity-0" aria-label="Run this snippet first">
							<option value="">Nothing</option>
							<option v-for="sn in tree.snippets.filter((x) => x !== doc.name)" :key="sn" :value="sn">{{ sn }}</option>
						</select>
					</label>
					<button class="btn-primary" :disabled="!steps.length || runActive" :title="`Run on ${browseSuite}`" @click="runSnippet"><Play class="h-4 w-4 fill-current" /><span class="max-md:sr-only">Run</span></button>
				</template>
				<template v-if="kind === 'case'">
					<button class="btn-outline" :disabled="!steps.length || runActive" :title="bps.size ? `Debug: pause at ${bps.size} breakpoint(s)` : 'Debug: pause before every step'" @click="runTest(true)"><Bug class="h-4 w-4" /><span class="max-md:sr-only">Debug</span></button>
					<button class="btn-primary" :disabled="!steps.length || runActive" title="Run (Ctrl+Enter)" @click="runTest(false)"><Play class="h-4 w-4 fill-current" /><span class="max-md:sr-only">Run</span></button>
				</template>
				<div class="relative">
					<button class="icon-btn" aria-label="More actions" :aria-expanded="menu" @click="menu = !menu"><MoreHorizontal class="h-4 w-4" /></button>
					<div v-if="menu" class="fixed inset-0 z-20" @click="menu = false" />
					<div v-if="menu" class="absolute right-0 top-9 z-30 w-56 rounded-lg border border-line bg-panel p-1 shadow-xl">
						<template v-if="kind === 'case'">
							<button class="flex h-8 w-full items-center gap-2 rounded px-2 text-left hover:bg-sunk" @click="menu = false; editSuite(doc.suite)"><Settings2 class="h-4 w-4 text-muted" />Suite settings (video…)</button>
							<button class="flex h-8 w-full items-center gap-2 rounded px-2 text-left hover:bg-sunk" @click="openRows"><Table2 class="h-4 w-4 text-muted" />Test data rows…<span v-if="rowCount" class="ml-auto text-xs text-muted">{{ rowCount }}</span></button>
							<button class="flex h-8 w-full items-center gap-2 rounded px-2 text-left hover:bg-sunk" role="menuitemcheckbox" :aria-checked="!!doc.keep_going" @click="toggleKeepGoing"><FastForward class="h-4 w-4 text-muted" />Keep going after a failure<span v-if="doc.keep_going" class="ml-auto text-xs text-brand">On</span></button>
							<button class="flex h-8 w-full items-center gap-2 rounded px-2 text-left hover:bg-sunk" :disabled="!steps.length" @click="openRunAs"><Users class="h-4 w-4 text-muted" />Run as each user…</button>
							<button class="flex h-8 w-full items-center gap-2 rounded px-2 text-left hover:bg-sunk" @click="exportTs"><FileCode2 class="h-4 w-4 text-muted" />Export to Playwright</button>
							<router-link class="flex h-8 items-center gap-2 rounded px-2 hover:bg-sunk" :to="{ name: 'runs', query: { test: doc.name } }"><History class="h-4 w-4 text-muted" />Run history</router-link>
							<button class="flex h-8 w-full items-center gap-2 rounded px-2 text-left hover:bg-sunk" :disabled="!steps.length" @click="openExtract"><Puzzle class="h-4 w-4 text-muted" />Save steps as snippet</button>
							<button class="flex h-8 w-full items-center gap-2 rounded px-2 text-left hover:bg-sunk" @click="duplicateTest"><CopyPlus class="h-4 w-4 text-muted" />Duplicate test</button>
							<a class="flex h-8 items-center gap-2 rounded px-2 hover:bg-sunk" :href="`/desk/test-case/${encodeURIComponent(doc.name)}`"><ExternalLink class="h-4 w-4 text-muted" />Open in desk</a>
							<div class="my-1 h-px bg-line" />
						</template>
						<template v-if="kind === 'snippet'">
							<button class="flex h-8 w-full items-center gap-2 rounded px-2 text-left hover:bg-sunk" @click="duplicateSnippet"><CopyPlus class="h-4 w-4 text-muted" />Duplicate snippet</button>
							<div class="my-1 h-px bg-line" />
						</template>
						<button class="flex h-8 w-full items-center gap-2 rounded px-2 text-left text-fail hover:bg-fail/10" @click="menu = false; dialog = { type: 'delete' }"><Trash2 class="h-4 w-4" />Delete {{ kind === 'case' ? 'test' : 'snippet' }}</button>
					</div>
				</div>
			</div>
		</header>
	<div class="grid min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(0,1fr)_minmax(0,42vh)] lg:grid-rows-1"
		:class="wide ? 'lg:grid-cols-[minmax(360px,1fr)_minmax(460px,56%)]' : 'lg:grid-cols-[minmax(0,1fr)_minmax(340px,380px)] xl:grid-cols-[minmax(0,1fr)_minmax(400px,460px)]'">
		<!-- steps -->
		<section class="flex min-h-0 min-w-0 flex-col bg-panel lg:border-r lg:border-line" aria-label="Steps">
			<template v-if="doc">
				<div class="min-h-0 flex-1 overflow-y-auto px-6 pb-16 pt-5">
					<div v-if="kind === 'snippet'" class="mb-3 rounded-lg border border-line bg-sunk/40 px-4 py-3 text-sm">
						<input v-model="doc.description" class="-mx-1 w-full rounded bg-transparent px-1 font-medium outline-none placeholder:text-faint hover:bg-panel focus:bg-panel" placeholder="Describe what this block does…" aria-label="What this snippet does" @input="markDirty" />
						<p class="mt-0.5 text-muted">Add it to any test with Add step → Building blocks.
							<template v-if="(tree.snippet_inputs?.[doc.name] || []).length"> Each use can set its inputs.</template>
							<template v-else> It needs no inputs.</template></p>
						<p class="mt-3 text-xs text-muted">Used by:
							<template v-if="usage.length"><router-link v-for="u in usage" :key="u.doctype + u.name" :to="{ name: u.doctype === 'Test Case' ? 'test' : 'snippet', params: { name: u.name } }" class="ml-1.5 inline-block rounded bg-panel px-1.5 py-0.5 text-ink ring-1 ring-line hover:ring-brand">{{ u.title }}</router-link></template>
							<span v-else class="ml-1 text-faint">nothing yet</span></p>
					</div>
					<p class="mb-3 flex items-center justify-between px-3 text-xs text-muted"><span>{{ steps.length }} steps<template v-if="kind === 'case' && rowCount"> · <button class="text-brand hover:underline" @click="openRows">runs once per data row ({{ rowCount }})</button></template><template v-if="kind === 'case' && doc.keep_going"> · keeps going after a failure</template><template v-if="bps.size"> · {{ bps.size }} breakpoint{{ bps.size > 1 ? 's' : '' }}</template></span><span class="max-md:hidden">↑↓ move · Alt+↑↓ reorder · Del delete · Ctrl+D duplicate · click a number to set a breakpoint</span></p>
					<ol id="steps" class="space-y-1.5">
						<StepRow v-for="(st, i) in steps" :key="keyOf(st)" :step="st" :index="i" :selected="activeRow === i"
							:breakpoint="bps.has(String(i + 1))" :result="results[String(i + 1)]" :running="runningIndex === i" :paused="pausedIndex === i"
							:expanded="expanded.has(i)" @select="select(i)" @toggle-bp="toggleBp(i)" @duplicate="duplicate(i)" @remove="remove(i)"
							@dragstart="dragFrom = i" @drop="drop(i)" @toggle-expand="toggleExpand(i)" @insert-before="activeRow = i - 1 < 0 ? null : i - 1; insertAt = i; adding = true">
							<ol v-if="expanded.has(i)" class="mb-2 ml-[88px] mt-1 space-y-0.5 border-l-2 border-brand/20 pl-4">
								<li v-for="(sub, j) in snippetSteps[st.snippet] || []" :key="j" class="flex gap-3 py-1.5 text-[14px]">
									<span class="w-8 shrink-0 font-mono text-xs leading-6 text-faint">{{ i + 1 }}.{{ j + 1 }}</span><Sentence :step="sub" />
								</li>
								<li class="py-1"><button class="text-xs font-medium text-brand hover:underline" @click="open(st.snippet, 'snippet')">Edit this snippet</button></li>
							</ol>
						</StepRow>
					</ol>

					<div v-if="!steps.length" class="mx-2 mt-6 rounded-lg border border-dashed border-line px-6 py-12 text-center">
						<p class="font-medium">No steps yet</p>
						<p class="mx-auto mt-1 max-w-sm text-sm text-muted">Add Frappe steps like Log in, New document and Set field, or press Record and use the site.</p>
						<div class="mt-5 flex justify-center gap-2">
							<button class="btn-primary" @click="adding = true"><Plus class="h-4 w-4" />Add a step</button>
							<button class="btn-outline" @click="toggleRecord"><Disc class="h-4 w-4 text-rec" />Record</button>
						</div>
					</div>

					<div class="relative mt-1 px-1">
						<button v-if="steps.length" class="btn-ghost h-9 w-full justify-start border border-dashed border-line text-muted hover:border-brand hover:text-ink" @click="adding = !adding">
							<Plus class="h-4 w-4" />Add step{{ activeRow != null ? ` after ${activeRow + 1}` : '' }}
						</button>
						<div v-if="adding && tree.snippets.filter((x) => x !== doc.name).length" class="mt-1 rounded-lg border border-line bg-panel p-4 shadow-pop">
							<p class="mb-2 text-xs font-semibold text-muted">Building blocks <span class="font-normal text-faint">snippets you've already made</span></p>
							<div class="grid gap-1.5 sm:grid-cols-2">
								<button v-for="sn in tree.snippets.filter((x) => x !== doc.name)" :key="sn" class="flex items-start gap-2 rounded-md border border-line px-3 py-2 text-left transition-colors hover:border-brand hover:bg-brand/5"
									@click="addStep('run_snippet', { snippet: sn })">
									<Puzzle class="mt-0.5 h-4 w-4 shrink-0 text-brand" />
									<span class="min-w-0"><span class="block truncate text-sm font-medium">{{ sn }}</span>
										<span class="block truncate text-xs text-faint">{{ (tree.snippet_inputs?.[sn] || []).length ? 'needs ' + tree.snippet_inputs[sn].join(', ') : 'no inputs' }}</span></span>
								</button>
							</div>
						</div>
						<div v-if="adding" id="step-picker" class="relative z-20 mt-1 grid gap-x-6 gap-y-4 rounded-lg border border-line bg-panel p-4 shadow-pop sm:grid-cols-2" @keydown.escape="adding = false">
							<div v-for="[g, items] in grouped" :key="g">
								<p class="mb-1.5 text-xs font-semibold text-muted">{{ g }} <span class="font-normal text-faint">{{ GROUP_HINT[g] }}</span></p>
								<div class="flex flex-wrap gap-1">
									<button v-for="[a, m] in items" :key="a" class="rounded-md border border-line px-2 py-1 text-sm transition-colors hover:border-brand hover:bg-brand/5" :title="m.help" @click="addStep(a)">{{ m.label }}</button>
								</div>
							</div>
						</div>
					</div>
				</div>
			</template>

			<!-- nothing open -->
			<div v-else class="grid h-full place-items-center px-8">
				<div class="max-w-md">
					<h1 class="text-2xl font-semibold tracking-tight">Test your site by using it</h1>
					<p class="mt-2 text-muted">Write steps the way you'd explain them: log in, open a new Sales Order, set Customer, save, approve. Or record them by using the site.</p>
					<div class="mt-6 flex flex-wrap gap-2">
						<button class="btn-primary h-9 px-4" :disabled="!tree.suites.length" @click="dialog = { type: 'new-test' }"><Plus class="h-4 w-4" />New test</button>
						<button class="btn-outline h-9 px-4" :disabled="!tree.suites.length" @click="dialog = { type: 'record' }"><Disc class="h-4 w-4 text-rec" />Record a test</button>
					</div>
					<p v-if="!tree.suites.length" class="mt-4 text-sm text-muted">First, <button class="font-medium text-brand underline-offset-2 hover:underline" @click="dialog = { type: 'suite', suite: null }">create a suite</button> with your site's address.</p>
				</div>
			</div>
		</section>

		<!-- context panel: the selected step, the live browser, or the latest run -->
		<section class="flex min-h-0 min-w-0 flex-col bg-panel max-lg:border-t max-lg:border-line" aria-label="Details">
			<nav class="flex h-11 shrink-0 items-end gap-1 border-b border-line px-3" role="tablist">
				<button v-for="t in [{ k: 'step', l: 'Step', i: SlidersHorizontal }, { k: 'browser', l: session.id ? 'Browser · live' : run.name && !DONE.includes(run.status) ? 'Browser · running' : 'Browser', i: MonitorPlay }, { k: 'run', l: 'Last run', i: ListChecks }]"
					:key="t.k" role="tab" :aria-selected="tab === t.k"
					class="relative flex h-full items-center gap-1.5 px-2.5 text-sm transition-colors"
					:class="tab === t.k ? 'font-medium text-ink after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full after:bg-brand' : 'text-muted hover:text-ink'"
					@click="tab = t.k">
					<component :is="t.i" class="h-4 w-4" />{{ t.l }}
					<span v-if="t.k === 'run' && panelRun" class="h-1.5 w-1.5 rounded-full" :class="{ 'bg-pass': panelRun.status === 'Passed', 'bg-warn': panelRun.status === 'Known Issue', 'bg-fail': ['Failed', 'Error'].includes(panelRun.status), 'bg-run animate-pulse': !DONE.includes(panelRun.status) }" />
				</button>
			</nav>
			<div class="min-h-0 flex-1">
				<template v-if="tab === 'step'">
					<StepInspector v-if="doc && activeRow != null && steps[activeRow]" :step="steps[activeRow]" :index="activeRow"
						:snippets="tree.snippets" :snippet-inputs="tree.snippet_inputs" :fields="fieldList" :doctype="ctxDoctype" :picking="pickRow === activeRow"
						@change="patch(activeRow, $event)" @pick="pickFor(activeRow); tab = 'browser'" @test="testSelector($event); tab = 'browser'" @open-snippet="open($event, 'snippet')" />
					<div v-else class="grid h-full place-items-center px-8 text-center text-sm text-muted">
						<div><SlidersHorizontal class="mx-auto mb-3 h-6 w-6 text-faint" />{{ doc ? 'Select a step to edit it here.' : 'Open a test to start.' }}</div>
					</div>
				</template>
				<BrowserStage v-show="tab === 'browser'" class="h-full" :session="session" :run="run" :total="steps.length" :wide="wide" :has-test="!!doc" :selected="selectedStep"
					@start="openBrowser" @stop="stopSession" @cmd="cmd" @mode="setMode" @debug="debug" @wide="wide = !wide"
					@select-step="selectedStep = $event; activeRow = parseInt($event, 10) - 1">
					<template #status>
						<div v-if="statusMsg" :class="{ 'text-pass': statusMsg.tone === 'pass', 'text-warn': statusMsg.tone === 'warn' }">
							{{ statusMsg.lead }} <code v-if="statusMsg.code" class="rounded bg-sunk px-1.5 py-0.5 font-mono text-ink">{{ statusMsg.code }}</code>
							<div v-if="statusMsg.alts?.length" class="mt-1.5 flex flex-wrap items-center gap-1.5 text-muted">
								Other unique selectors:
								<button v-for="a in statusMsg.alts" :key="a" class="max-w-full truncate rounded-full border border-line px-2 py-0.5 font-mono text-2xs text-ink hover:border-brand" @click="useAlt(a, statusMsg.row)">{{ a }}</button>
							</div>
						</div>
						<p v-else-if="hl" :class="hl.count === 1 ? 'text-pass' : 'text-warn'">
							<code class="rounded bg-sunk px-1.5 py-0.5 font-mono text-ink">{{ hl.selector }}</code>
							matches {{ hl.count === 1 ? 'exactly one element' : `${hl.count} elements` }}{{ hl.count === 1 ? '.' : hl.count ? '. Make it more specific.' : '. Check the selector.' }}
						</p>
						<p v-else class="text-muted">{{ modeHint[session.mode] }}<span v-if="session.state.title"> Page: <span class="text-ink">{{ session.state.title }}</span></span></p>
					</template>
				</BrowserStage>
				<template v-if="tab === 'run'">
					<RunPanel v-if="panelRun" :run="panelRun" />
					<div v-else class="grid h-full place-items-center px-8 text-center text-sm text-muted">
						<div><ListChecks class="mx-auto mb-3 h-6 w-6 text-faint" />This test hasn't run yet. Press Run.</div>
					</div>
				</template>
			</div>
		</section>

	</div>
		<!-- dialogs -->
		<NewItemDialog v-if="['new-test', 'record'].includes(dialog?.type)" :title="dialog.type === 'record' ? 'Record a new test' : 'New test'"
			:confirm-label="dialog.type === 'record' ? 'Create and record' : 'Create test'" needs-suite :suites="tree.suites" :default-suite="doc?.suite"
			@close="dialog = null" @create="create" />
		<NewItemDialog v-if="dialog?.type === 'new-snippet'" title="New snippet" confirm-label="Create snippet" snippet @close="dialog = null" @create="create" />
		<Modal v-if="dialog?.type === 'inputs'" title="Snippet inputs" @close="dialog = null">
			<p class="mb-3 text-sm text-muted">The <code v-pre class="font-mono">{{variables}}</code> this snippet's steps use. A default applies when neither the step that uses it nor the test or suite sets the input.</p>
			<div class="divide-y divide-line overflow-hidden rounded-md border border-line">
				<label v-for="v in tree.snippet_inputs?.[doc.name] || []" :key="v" class="flex items-center gap-3 px-3 py-1.5">
					<code class="w-40 shrink-0 truncate font-mono text-xs text-ink" :title="v">{{ v }}</code>
					<input class="field h-8" :value="defaults[v] || ''" placeholder="No default" @input="setDefault(v, $event.target.value)" />
				</label>
			</div>
			<p class="mt-3 text-xs text-muted">Order used: value set where it's used → test or suite variable → default here.</p>
			<template #footer>
				<button class="btn-primary" @click="dialog = null">Done</button>
			</template>
		</Modal>
		<Modal v-if="dialog?.type === 'extract'" title="Save steps as a snippet" wide @close="dialog = null">
			<form id="extract-form" class="grid gap-4" @submit.prevent="extractSnippet">
				<div class="flex flex-wrap items-end gap-3">
					<label><span class="label">From step</span><input v-model.number="dialog.from" type="number" min="1" :max="steps.length" class="field w-24" /></label>
					<label><span class="label">To step</span><input v-model.number="dialog.to" type="number" min="1" :max="steps.length" class="field w-24" /></label>
					<p class="pb-1.5 text-xs text-muted">These {{ extractRange.length }} steps move into the snippet; the test runs the snippet in their place.</p>
				</div>
				<ol class="max-h-48 overflow-y-auto rounded-md border border-line bg-sunk/40 px-3 py-2 text-sm">
					<li v-for="(st, j) in extractRange" :key="j" class="flex gap-2 py-0.5"><span class="w-6 shrink-0 text-right text-xs leading-6 text-faint">{{ Math.min(dialog.from, dialog.to) + j }}</span><Sentence :step="st" /></li>
				</ol>
				<p v-if="extractInputs.length" class="text-xs text-muted">Inputs this block will have:
					<code v-for="v in extractInputs" :key="v" class="ml-1 rounded bg-sunk px-1.5 py-0.5 font-mono text-ink">{{ v }}</code></p>
				<label><span class="label">Name</span><input v-model="dialog.title" class="field" required autofocus placeholder="e.g. Approve as Sales Manager" /></label>
				<label><span class="label">What it does</span><input v-model="dialog.description" class="field" placeholder="One line, shown wherever it's used" /></label>
			</form>
			<template #footer>
				<button class="btn-ghost" @click="dialog = null">Cancel</button>
				<button class="btn-primary" form="extract-form" type="submit" :disabled="!dialog.title.trim() || !extractRange.length">Save as snippet</button>
			</template>
		</Modal>
		<SuiteDialog v-if="dialog?.type === 'suite'" :suite="dialog.suite" @close="dialog = null" @saved="dialog = null; loadTree()" />
		<Modal v-if="dialog?.type === 'rows'" title="Test data rows" wide @close="dialog = null">
			<p class="text-sm text-muted">The steps run once per row. The first line names the columns; use them in steps as <code v-pre class="font-mono">{{column}}</code>. A failing row is reported and the next row still runs. Leave empty to run the steps once.</p>
			<textarea v-model="dialog.text" rows="10" class="field field-mono mt-3 py-2" spellcheck="false" placeholder="customer,item,price&#10;Acme Ltd,Widget A,&quot;1,250.00&quot;&#10;Globex,Widget B,99.50" />
			<p class="mt-1 text-xs text-muted">CSV: put a value in quotes when it has a comma, like "24,886.42".</p>
			<template #footer>
				<button class="btn-ghost" @click="dialog = null">Cancel</button>
				<button class="btn-primary" @click="saveRows">Use these rows</button>
			</template>
		</Modal>
		<Modal v-if="dialog?.type === 'runas'" title="Run as each user" wide @close="dialog = null">
			<p class="text-sm text-muted">Runs this test once signed in as each user, without their password; login steps are skipped. Use it to see which roles can do what. Only a System Manager can start these runs.</p>
			<label class="mt-4 block"><span class="label">Users, one per line</span>
				<textarea v-model="dialog.users" rows="4" class="field field-mono py-2" placeholder="sales.user@example.com&#10;stock.manager@example.com" /></label>
			<table v-if="dialog.rows.length" class="mt-4 w-full text-sm">
				<thead><tr class="text-left text-xs text-muted"><th class="py-1.5 font-medium">User</th><th class="py-1.5 font-medium">Last result</th><th class="py-1.5 font-medium">Why</th></tr></thead>
				<tbody>
					<tr v-for="r in dialog.rows" :key="r.user" class="border-t border-line align-top">
						<td class="py-2 pr-3 font-mono text-xs">{{ r.user }}</td>
						<td class="py-2 pr-3"><router-link v-if="r.name" :to="{ name: 'run', params: { name: r.name } }"><StatusBadge :status="r.status" /></router-link><span v-else class="text-xs text-faint">not run</span></td>
						<td class="py-2 text-xs text-muted">{{ (r.error || '').split('\n')[0].slice(0, 140) }}</td>
					</tr>
				</tbody>
			</table>
			<template #footer>
				<button class="btn-ghost" @click="dialog = null">Close</button>
				<button class="btn-primary" :disabled="!dialog.users.trim()" @click="runAs"><Play class="h-4 w-4 fill-current" />Run as each</button>
			</template>
		</Modal>
		<ExportDialog v-if="dialog?.type === 'export'" :name="doc.name" :code="dialog.code" @close="dialog = null" />
		<Modal v-if="dialog?.type === 'select'" title="Choose an option" @close="dialog = null">
			<select v-model="dialog.value" class="field h-auto py-1" size="6" aria-label="Option" autofocus>
				<option v-for="o in dialog.prompt.options" :key="o.value" :value="o.value">{{ o.label || o.value }}</option>
			</select>
			<template #footer>
				<button class="btn-ghost" @click="dialog = null">Cancel</button>
				<button class="btn-primary" @click="cmd({ type: 'select', selector: dialog.prompt.selector, value: dialog.value }); dialog = null">Select option</button>
			</template>
		</Modal>
		<Modal v-if="dialog?.type === 'discard'" title="Discard unsaved changes?" @close="resolveDiscard(false)">
			<p class="text-sm text-muted">Your edits to “{{ doc?.title }}” haven't been saved.</p>
			<template #footer>
				<button class="btn-ghost" @click="resolveDiscard(false)">Keep editing</button>
				<button class="btn-danger" @click="resolveDiscard(true)">Discard changes</button>
			</template>
		</Modal>
		<Modal v-if="dialog?.type === 'delete'" :title="`Delete ${kind === 'case' ? 'test' : 'snippet'}?`" @close="dialog = null">
			<p v-if="kind === 'snippet' && usage.length" class="mb-2 text-sm text-fail">It's used by {{ usage.length }} {{ usage.length === 1 ? 'test' : 'tests' }} ({{ usage.map((u) => u.title).join(', ') }}). Those steps will stop working.</p>
			<p class="text-sm text-muted">“{{ doc.title || doc.name }}” will be permanently deleted.<template v-if="kind === 'case'"> Tests that already have runs can't be deleted; disable them in the desk instead.</template></p>
			<template #footer>
				<button class="btn-ghost" @click="dialog = null">Cancel</button>
				<button class="btn-danger" @click="deleteItem">Delete</button>
			</template>
		</Modal>
	</div>
</template>
