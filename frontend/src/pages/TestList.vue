<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Plus, Search, Play, Settings2, RefreshCw, Inbox, ChevronDown, Puzzle } from "lucide-vue-next";
import StatusBadge from "../components/StatusBadge.vue";
import NewItemDialog from "../components/NewItemDialog.vue";
import SuiteDialog from "../components/SuiteDialog.vue";
import { api } from "../api";
import { toast, toastError } from "../toast";
import { ago } from "../format";

// One page for both lists, like QCS Flow's Flows: title, what it is for, filters, a bordered table.
const route = useRoute();
const router = useRouter();
const isSnippets = computed(() => route.name === "snippets");
const tree = ref({ suites: [], cases: [], snippets: [] });
const snippets = ref([]);
const loading = ref(true);
const q = ref("");
const suite = ref("");
const status = ref("");
const dialog = ref(null);

async function load() {
	loading.value = true;
	try {
		tree.value = await api.tree();
		if (isSnippets.value) snippets.value = await api.listSnippets();
	} catch (e) { toastError(e); }
	loading.value = false;
}
onMounted(load);
watch(isSnippets, load);

const result = (c) => (!c.enabled ? "Disabled" : c.last_status || "Not run");
const matches = (c, k) => (k === "Failed" ? ["Failed", "Error"].includes(result(c)) : result(c) === k);
const strip = computed(() => {
	const cs = tree.value.cases.filter((c) => !suite.value || c.suite === suite.value);
	return [["", "All tests"], ["Passed", "Passed"], ["Known Issue", "Known issue"], ["Failed", "Failed"], ["Not run", "Not run"]].map(([k, label]) => ({ k, label, n: k ? cs.filter((c) => matches(c, k)).length : cs.length }));
});
const tests = computed(() => {
	const n = q.value.trim().toLowerCase();
	return tree.value.cases.filter((c) => (!suite.value || c.suite === suite.value) && (!status.value || matches(c, status.value))
		&& (!n || `${c.title} ${c.tags_text || ""} ${c.name}`.toLowerCase().includes(n)));
});
const shownSnippets = computed(() => {
	const n = q.value.trim().toLowerCase();
	return snippets.value.filter((s) => !n || `${s.name} ${s.description || ""}`.toLowerCase().includes(n));
});
const tags = (c) => (c.tags_text || "").split(",").map((x) => x.trim()).filter(Boolean);
const filtered = computed(() => q.value || suite.value || status.value);

async function create({ title, suite: s, description }) {
	try {
		const d = await api.insert(isSnippets.value ? { doctype: "Test Snippet", title, description, steps: [] } : { doctype: "Test Case", title, suite: s, steps: [] });
		router.push({ name: isSnippets.value ? "snippet" : "test", params: { name: d.name } });
	} catch (e) { toastError(e); }
}
async function run(c) {
	try { const r = await api.runCase(c.name); toast(`${c.title}: queued`, "info"); router.push({ name: "run", params: { name: r } }); } catch (e) { toastError(e); }
}
async function runSuite() {
	try { const runs = await api.runSuite(suite.value); toast(`${runs.length} tests queued`, "info"); router.push({ name: "runs" }); } catch (e) { toastError(e); }
}
async function editSuite() {
	try { dialog.value = { type: "suite", suite: await api.getDoc("Test Suite", suite.value) }; } catch (e) { toastError(e); }
}
</script>

<template>
	<div class="px-8 py-7">
		<div class="mb-5 flex items-start justify-between gap-4">
			<div class="min-w-0">
				<h1 class="page-title">{{ isSnippets ? "Snippets" : "Tests" }}</h1>
				<p class="page-sub">{{ isSnippets ? "Reusable groups of steps, like logging in or creating an approved Sales Order. Any test can run them." : "Browser tests that use your Frappe site like a person would: log in, fill forms, move documents through workflows." }}</p>
			</div>
			<div class="flex shrink-0 items-center gap-2">
				<button v-if="!isSnippets" class="btn-outline" @click="dialog = { type: 'suite', suite: null }">New Suite</button>
				<button class="btn-primary" :disabled="!isSnippets && !tree.suites.length" @click="dialog = { type: 'new' }"><Plus class="h-4 w-4" />{{ isSnippets ? "New Snippet" : "New Test" }}</button>
			</div>
		</div>

		<!-- status strip, like QCS Flow's Runs -->
		<div v-if="!isSnippets" class="mb-4 grid grid-cols-2 overflow-hidden rounded-lg border border-line sm:grid-cols-5" role="tablist" aria-label="Filter by result">
			<button v-for="s in strip" :key="s.k" role="tab" :aria-selected="status === s.k"
				class="relative border-line px-4 py-3 text-left transition-colors [&:not(:first-child)]:border-l"
				:class="status === s.k ? 'bg-sunk/70 after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-brand' : 'hover:bg-sunk/40'" @click="status = s.k">
				<span class="flex items-center gap-1.5 text-xs text-muted">
					<span v-if="s.k" class="h-1.5 w-1.5 rounded-full" :class="{ 'bg-pass': s.k === 'Passed', 'bg-fail': s.k === 'Failed', 'bg-warn': s.k === 'Known Issue', 'bg-faint': s.k === 'Not run' }" />{{ s.label }}
				</span>
				<span class="tnum mt-0.5 block text-lg font-semibold">{{ s.n }}</span>
			</button>
		</div>

		<div class="mb-3 flex flex-wrap items-center gap-2">
			<label class="relative w-64">
				<span class="sr-only">Search</span>
				<Search class="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-faint" />
				<input v-model="q" type="search" class="field pl-8" :placeholder="isSnippets ? 'Search snippets…' : 'Search tests or tags…'" />
			</label>
			<label v-if="!isSnippets" class="pill relative cursor-pointer">
				Suite <span class="font-medium text-ink">{{ suite || "Any" }}</span><ChevronDown class="h-3.5 w-3.5" />
				<select v-model="suite" class="absolute inset-0 cursor-pointer opacity-0" aria-label="Suite">
					<option value="">Any</option><option v-for="s in tree.suites" :key="s.name" :value="s.name">{{ s.name }}</option>
				</select>
			</label>
			<template v-if="suite">
				<button class="btn-ghost px-2.5 text-muted" @click="editSuite"><Settings2 class="h-4 w-4" />Suite settings</button>
				<button class="btn-ghost px-2.5 text-muted" @click="runSuite"><Play class="h-4 w-4" />Run suite</button>
			</template>
			<button class="icon-btn ml-auto" aria-label="Refresh" title="Refresh" @click="load"><RefreshCw class="h-4 w-4" :class="loading && 'animate-spin'" /></button>
		</div>

		<div class="table-card">
			<table v-if="!isSnippets" class="w-full text-sm">
				<thead class="table-head"><tr>
					<th class="px-4 py-2.5 font-medium">Test</th><th class="px-4 py-2.5 font-medium max-md:hidden">Suite</th>
					<th class="px-4 py-2.5 font-medium max-lg:hidden">Last 10 runs</th><th class="px-4 py-2.5 font-medium">Result</th><th class="w-12" />
				</tr></thead>
				<tbody>
					<tr v-for="c in tests" :key="c.name" class="group cursor-pointer border-b border-line last:border-0 hover:bg-sunk/40" @click="router.push({ name: 'test', params: { name: c.name } })">
						<td class="px-4 py-3">
							<router-link :to="{ name: 'test', params: { name: c.name } }" class="font-medium text-ink" @click.stop>{{ c.title }}</router-link>
							<div class="mt-0.5 flex flex-wrap gap-1 text-xs text-faint"><span>{{ c.name }}</span><span v-for="t in tags(c)" :key="t" class="rounded bg-sunk px-1.5 text-muted">{{ t }}</span></div>
						</td>
						<td class="px-4 py-3 text-muted max-md:hidden">{{ c.suite }}</td>
						<td class="px-4 py-3 max-lg:hidden">
							<span class="flex h-4 items-end gap-[3px]" :aria-label="`Last ${c.history.length} runs`">
								<span v-for="(h, i) in c.history" :key="i" class="w-1.5 rounded-sm" :class="h === 'Passed' ? 'h-2.5 bg-pass/70' : 'h-4 bg-fail'" :title="h" />
								<span v-if="!c.history.length" class="text-xs text-faint">No runs yet</span>
							</span>
						</td>
						<td class="px-4 py-3"><StatusBadge :status="result(c)" /></td>
						<td class="px-2 py-3 text-right"><button class="icon-btn opacity-0 group-hover:opacity-100 focus:opacity-100" :aria-label="`Run ${c.title}`" title="Run" @click.stop="run(c)"><Play class="h-4 w-4" /></button></td>
					</tr>
				</tbody>
			</table>
			<table v-else class="w-full text-sm">
				<thead class="table-head"><tr><th class="px-4 py-2.5 font-medium">Snippet</th><th class="px-4 py-2.5 font-medium max-md:hidden">What it does</th><th class="px-4 py-2.5 font-medium max-lg:hidden">Inputs</th><th class="px-4 py-2.5 text-right font-medium">Updated</th></tr></thead>
				<tbody>
					<tr v-for="s in shownSnippets" :key="s.name" class="cursor-pointer border-b border-line last:border-0 hover:bg-sunk/40" @click="router.push({ name: 'snippet', params: { name: s.name } })">
						<td class="px-4 py-3"><router-link :to="{ name: 'snippet', params: { name: s.name } }" class="flex items-center gap-2 font-medium" @click.stop><Puzzle class="h-4 w-4 text-faint" />{{ s.name }}</router-link></td>
						<td class="max-w-md px-4 py-3 text-muted max-md:hidden"><span class="line-clamp-2">{{ s.description || "—" }}</span></td>
						<td class="px-4 py-3 max-lg:hidden"><span class="flex flex-wrap gap-1"><code v-for="v in tree.snippet_inputs?.[s.name] || []" :key="v" class="rounded bg-sunk px-1.5 py-0.5 font-mono text-xs text-muted">{{ v }}</code><span v-if="!(tree.snippet_inputs?.[s.name] || []).length" class="text-xs text-faint">none</span></span></td>
						<td class="px-4 py-3 text-right text-muted" :title="s.modified">{{ ago(s.modified) }}</td>
					</tr>
				</tbody>
			</table>
			<div v-if="loading && !(isSnippets ? snippets.length : tree.cases.length)" class="space-y-2 p-4"><div v-for="i in 5" :key="i" class="h-9 animate-pulse rounded bg-sunk" /></div>
			<div v-else-if="!(isSnippets ? shownSnippets.length : tests.length)" class="grid place-items-center px-6 py-20 text-center">
				<Inbox class="mb-2 h-6 w-6 text-faint" />
				<p class="font-medium">{{ filtered ? "Nothing matches" : isSnippets ? "No snippets yet" : "No tests yet" }}</p>
				<p class="mt-1 text-sm text-muted">{{ filtered ? "Try another search or filter." : isSnippets ? "Make one for steps you repeat, like logging in." : tree.suites.length ? "Create one, then add steps or record them." : "Create a suite with your site's address first." }}</p>
				<button v-if="!filtered" class="btn-primary mt-4" @click="dialog = { type: tree.suites.length || isSnippets ? 'new' : 'suite', suite: null }">{{ isSnippets ? "New Snippet" : tree.suites.length ? "New Test" : "New Suite" }}</button>
			</div>
		</div>

		<NewItemDialog v-if="dialog?.type === 'new'" :title="isSnippets ? 'New snippet' : 'New test'" :confirm-label="isSnippets ? 'Create snippet' : 'Create test'"
			:needs-suite="!isSnippets" :snippet="isSnippets" :suites="tree.suites" :default-suite="suite" @close="dialog = null" @create="create" />
		<SuiteDialog v-if="dialog?.type === 'suite'" :suite="dialog.suite" @close="dialog = null" @saved="dialog = null; load()" />
	</div>
</template>
