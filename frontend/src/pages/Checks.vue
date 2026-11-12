<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { ChevronRight, ExternalLink, GitCompare, Play, Plus } from "lucide-vue-next";
import StatusBadge from "../components/StatusBadge.vue";
import StatusDot from "../components/StatusDot.vue";
import { api } from "../api";
import { toast, toastError } from "../toast";
import { ago, ms } from "../format";

const checks = ref([]);
const runs = ref([]);
const runName = ref("");
const run = ref(null);
const open = ref(new Set());
const label = ref("");
const before = ref("");
const after = ref("");
const comparison = ref(null);
let timer;

const busy = (s) => ["Queued", "Running"].includes(s);
const cell = (v) => (v === null || v === undefined ? "" : typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : String(v));

async function load() {
	try {
		const d = await api.getChecks();
		checks.value = d.checks;
		runs.value = d.runs;
		if (!runName.value && d.runs.length) runName.value = d.runs[0].name;
		if (!after.value && d.runs[0]) after.value = d.runs[0].name;
		if (!before.value && d.runs[1]) before.value = d.runs[1].name;
	} catch (e) { toastError(e); }
}
async function loadRun() {
	clearTimeout(timer);
	if (!runName.value) return;
	try { run.value = await api.getCheckRun(runName.value); } catch (e) { toastError(e); }
	if (run.value && busy(run.value.status)) timer = setTimeout(async () => { await loadRun(); if (!busy(run.value?.status)) load(); }, 1500);
}
async function runNow() {
	try {
		runName.value = await api.runChecks(label.value.trim() || null);
		label.value = "";
		toast(`Started ${runName.value}`, "success");
		await load();
		after.value = runName.value;
	} catch (e) { toastError(e); }
}
async function compare() {
	if (!before.value || !after.value) return;
	try { comparison.value = await api.compareChecks(before.value, after.value); } catch (e) { toastError(e); }
}
const toggle = (k) => { open.value.has(k) ? open.value.delete(k) : open.value.add(k); open.value = new Set(open.value); };
const runLabel = (r) => `${r.name}${r.label ? ` · ${r.label}` : ""} · ${ago(r.creation)}`;
const results = computed(() => run.value?.results || []);
const changes = computed(() => (comparison.value || []).filter((c) => c.added.length || c.removed.length || c.changed.length || c.before !== c.after));

watch(runName, loadRun);
onMounted(async () => { await load(); loadRun(); });
onBeforeUnmount(() => clearTimeout(timer));
</script>

<template>
	<div class="h-full overflow-y-auto">
		<div class="px-8 py-7 max-sm:px-4">
			<div class="flex flex-wrap items-end justify-between gap-4">
				<div>
					<h1 class="page-title">Data checks</h1>
					<p class="page-sub">Reports that should stay empty (or under a limit), run on the server every night or on demand. They only read: anything a report writes is rolled back.</p>
				</div>
				<div class="flex items-center gap-2">
					<input v-model="label" class="field h-9 w-48" placeholder="Label, e.g. before repost" aria-label="Label for this run" @keydown.enter="runNow" />
					<button class="btn-primary h-9" @click="runNow"><Play class="h-4 w-4" />Run checks</button>
				</div>
			</div>

			<section class="mt-6 table-card" aria-label="Checks">
				<div class="table-head flex items-center justify-between px-4 py-2">
					<span>Checks</span>
					<a class="btn-ghost h-7 px-2 text-xs" href="/desk/data-check/new" target="_blank" rel="noopener"><Plus class="h-3.5 w-3.5" />Add check</a>
				</div>
				<ul class="divide-y divide-line">
					<li v-for="c in checks" :key="c.name" class="flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-3 sm:flex-nowrap" :class="!c.enabled && 'opacity-50'">
						<StatusDot :status="c.last_status" class="mt-2" />
						<div class="min-w-0 flex-1">
							<p class="text-sm font-medium">{{ c.title }}</p>
							<p class="text-xs text-muted">{{ c.description }}</p>
						</div>
						<span class="shrink-0 text-xs text-muted max-sm:order-last max-sm:w-full max-sm:pl-5 sm:text-right">
							<span class="tnum text-sm font-semibold text-ink">{{ c.last_row_count ?? '–' }}</span> rows, at most {{ c.max_rows }}<br />{{ c.report }}
						</span>
						<a class="icon-btn h-7 w-7" :href="`/desk/data-check/${encodeURIComponent(c.name)}`" target="_blank" rel="noopener" :aria-label="`Edit ${c.title}`"><ExternalLink class="h-3.5 w-3.5" /></a>
					</li>
					<li v-if="!checks.length" class="px-4 py-6 text-sm text-muted">No checks yet. Add one: pick a report, its filters and how many rows are acceptable.</li>
				</ul>
			</section>

			<section v-if="runs.length" class="mt-6 table-card" aria-label="Results">
				<div class="table-head flex flex-wrap items-center justify-between gap-2 px-4 py-2">
					<span>Results</span>
					<select v-model="runName" class="field h-8 !w-auto max-w-full text-xs sm:max-w-sm" aria-label="Run">
						<option v-for="r in runs" :key="r.name" :value="r.name">{{ runLabel(r) }} · {{ r.status }}</option>
					</select>
				</div>
				<p v-if="run" class="px-4 pt-3 text-xs text-muted"><StatusBadge :status="run.status" /> <span v-if="run.duration_ms" class="ml-2">took {{ ms(run.duration_ms) }}</span></p>
				<ul class="divide-y divide-line">
					<li v-for="r in results" :key="r.data_check">
						<button class="flex w-full items-center gap-3 px-4 py-2.5 text-left text-sm hover:bg-sunk/50" :aria-expanded="open.has(r.data_check)" @click="toggle(r.data_check)">
							<ChevronRight class="h-4 w-4 text-faint transition-transform" :class="open.has(r.data_check) && 'rotate-90'" />
							<StatusDot :status="r.status" />
							<span class="flex-1">{{ r.data_check }}</span>
							<span class="tnum shrink-0 text-xs text-muted">{{ r.row_count }} / {{ r.max_rows }} rows<span class="max-sm:hidden"> · {{ ms(r.duration_ms) }}</span></span>
						</button>
						<div v-if="open.has(r.data_check)" class="overflow-x-auto px-4 pb-4">
							<pre v-if="r.error" class="whitespace-pre-wrap text-xs text-fail">{{ r.error }}</pre>
							<table v-else-if="r.rows.length" class="w-full text-xs">
								<thead><tr><th v-for="c in r.columns" :key="c.fieldname" class="border-b border-line px-2 py-1.5 text-left font-medium text-muted">{{ c.label }}</th></tr></thead>
								<tbody><tr v-for="(row, i) in r.rows.slice(0, 50)" :key="i"><td v-for="(v, j) in row" :key="j" class="tnum border-b border-line/60 px-2 py-1">{{ cell(v) }}</td></tr></tbody>
							</table>
							<p v-else class="text-xs text-muted">No rows.</p>
							<p v-if="r.rows.length > 50" class="mt-1 text-xs text-muted">First 50 of {{ r.row_count }} rows.</p>
						</div>
					</li>
				</ul>
			</section>

			<section v-if="runs.length > 1" class="mt-6 table-card" aria-label="Compare runs">
				<div class="table-head px-4 py-2.5">Before and after</div>
				<div class="flex flex-wrap items-end gap-3 px-4 py-3">
					<label class="block"><span class="label">Before</span>
						<select v-model="before" class="field h-9 !w-auto max-w-full"><option v-for="r in runs" :key="r.name" :value="r.name">{{ runLabel(r) }}</option></select></label>
					<label class="block"><span class="label">After</span>
						<select v-model="after" class="field h-9 !w-auto max-w-full"><option v-for="r in runs" :key="r.name" :value="r.name">{{ runLabel(r) }}</option></select></label>
					<button class="btn-outline h-9" :disabled="!before || !after || before === after" @click="compare"><GitCompare class="h-4 w-4" />Compare</button>
				</div>
				<p class="px-4 pb-3 text-xs text-muted">Rehearse a fix: run the checks, make the change (patch, repost...), run them again, compare. Rows match on their text columns, so a changed amount shows as changed.</p>
				<template v-if="comparison">
					<p v-if="!changes.length" class="px-4 pb-4 text-sm text-pass">No differences.</p>
					<div v-for="c in changes" :key="c.check" class="border-t border-line px-4 py-3">
						<p class="text-sm font-medium">{{ c.check }} <span class="tnum ml-2 text-xs font-normal text-muted">{{ c.before ?? '–' }} → {{ c.after ?? '–' }} rows</span></p>
						<div class="mt-2 overflow-x-auto">
							<table class="w-full text-xs">
								<thead><tr><th class="w-20 px-2 py-1 text-left font-medium text-muted"></th><th v-for="col in c.columns" :key="col.fieldname" class="px-2 py-1 text-left font-medium text-muted">{{ col.label }}</th></tr></thead>
								<tbody>
									<tr v-for="(row, i) in c.added" :key="'a' + i" class="bg-pass/[0.06]"><td class="px-2 py-1 text-pass">added</td><td v-for="(v, j) in row" :key="j" class="tnum px-2 py-1">{{ cell(v) }}</td></tr>
									<tr v-for="(row, i) in c.removed" :key="'r' + i" class="bg-fail/[0.06]"><td class="px-2 py-1 text-fail">removed</td><td v-for="(v, j) in row" :key="j" class="tnum px-2 py-1 line-through decoration-fail/40">{{ cell(v) }}</td></tr>
									<tr v-for="(ch, i) in c.changed" :key="'c' + i" class="bg-warn/[0.06]"><td class="px-2 py-1 text-warn">changed</td>
										<td v-for="(v, j) in ch.after" :key="j" class="tnum px-2 py-1"><template v-if="String(ch.before[j]) !== String(v)"><span class="text-muted line-through">{{ cell(ch.before[j]) }}</span> {{ cell(v) }}</template><template v-else>{{ cell(v) }}</template></td></tr>
								</tbody>
							</table>
						</div>
					</div>
				</template>
			</section>
		</div>
	</div>
</template>
