<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Search, X } from "lucide-vue-next";
import StatusBadge from "../components/StatusBadge.vue";
import { api } from "../api";
import { toastError } from "../toast";
import { ago, ms, DONE } from "../format";

const route = useRoute();
const router = useRouter();
const runs = ref([]);
const loading = ref(true);
const status = ref("");
const q = ref("");
let timer = null;

async function load() {
	clearTimeout(timer);
	try {
		runs.value = await api.listRuns({ test_case: route.query.test || "", limit: 300 });
	} catch (e) { toastError(e); }
	loading.value = false;
	if (runs.value.some((r) => !DONE.includes(r.status))) timer = setTimeout(load, 2500);
}
onMounted(load);
onBeforeUnmount(() => clearTimeout(timer));
watch(() => route.query.test, load);

const shown = computed(() => {
	const n = q.value.trim().toLowerCase();
	return runs.value.filter((r) => (!status.value || r.status === status.value) && (!n || `${r.title} ${r.suite} ${r.name}`.toLowerCase().includes(n)));
});
const finished = computed(() => shown.value.filter((r) => DONE.includes(r.status)));
const passRate = computed(() => (finished.value.length ? Math.round((100 * finished.value.filter((r) => r.status === "Passed").length) / finished.value.length) : null));
const median = computed(() => {
	const d = finished.value.map((r) => r.duration_ms || 0).sort((a, b) => a - b);
	return d.length ? d[Math.floor(d.length / 2)] : null;
});
const filters = ["", "Passed", "Known Issue", "Failed", "Error", "Running", "Queued"];
const counts = computed(() => Object.fromEntries(filters.map((f) => [f, f ? runs.value.filter((r) => r.status === f).length : runs.value.length])));
</script>

<template>
	<div class="h-full overflow-y-auto">
		<div class="px-8 py-7">
			<div class="flex flex-wrap items-end justify-between gap-4">
				<div>
					<h1 class="page-title">Runs</h1>
					<p class="page-sub">
						<template v-if="route.query.test">Showing runs of {{ runs[0]?.title || route.query.test }}. <router-link class="text-brand hover:underline" :to="{ name: 'runs' }">Show all</router-link></template>
						<template v-else>Every test run, newest first.</template>
					</p>
				</div>
				<dl v-if="finished.length" class="flex gap-6 text-right">
					<div><dt class="text-xs text-muted">Pass rate</dt><dd class="tnum text-lg font-semibold" :class="passRate === 100 ? 'text-pass' : passRate < 80 ? 'text-fail' : ''">{{ passRate }}%</dd></div>
					<div><dt class="text-xs text-muted">Median time</dt><dd class="tnum text-lg font-semibold">{{ ms(median) }}</dd></div>
				</dl>
			</div>

			<div class="mt-5 grid grid-cols-3 overflow-hidden rounded-lg border border-line lg:grid-cols-7" role="tablist" aria-label="Filter by result">
				<button v-for="f in filters" :key="f" role="tab" :aria-selected="status === f"
					class="relative border-line px-4 py-3 text-left transition-colors [&:not(:first-child)]:border-l"
					:class="status === f ? 'bg-sunk/70 after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-brand' : 'hover:bg-sunk/40'" @click="status = f">
					<span class="flex items-center gap-1.5 text-xs text-muted"><span v-if="f" class="h-1.5 w-1.5 rounded-full" :class="{ 'bg-pass': f === 'Passed', 'bg-fail': f === 'Failed', 'bg-warn': f === 'Known Issue', 'bg-warn': f === 'Error', 'bg-run': f === 'Running', 'bg-faint': f === 'Queued' }" />{{ f || 'All runs' }}</span>
					<span class="tnum mt-0.5 block text-lg font-semibold">{{ counts[f] }}</span>
				</button>
			</div>
			<div class="mt-4 flex flex-wrap items-center gap-2">
				<label class="relative w-64">
					<Search class="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-faint" />
					<input v-model="q" type="search" class="field pl-8" placeholder="Filter by test or suite" aria-label="Filter runs" />
				</label>
			</div>

			<div class="mt-4 overflow-hidden rounded-lg border border-line bg-panel">
				<table class="w-full text-sm">
					<thead class="table-head">
						<tr><th class="px-4 py-2.5 font-medium">Result</th><th class="px-4 py-2.5 font-medium">Test</th><th class="px-4 py-2.5 font-medium max-md:hidden">Suite</th>
							<th class="px-4 py-2.5 text-right font-medium">Time</th><th class="px-4 py-2.5 text-right font-medium max-sm:hidden">When</th></tr>
					</thead>
					<tbody>
						<tr v-for="r in shown" :key="r.name" class="cursor-pointer border-b border-line transition-colors last:border-0 hover:bg-sunk/50"
							tabindex="0" @click="router.push({ name: 'run', params: { name: r.name } })" @keydown.enter="router.push({ name: 'run', params: { name: r.name } })">
							<td class="px-4 py-2.5"><StatusBadge :status="r.status" /></td>
							<td class="px-4 py-2.5"><span class="font-medium">{{ r.title }}</span> <span class="ml-1 font-mono text-2xs text-faint">{{ r.name }}</span>
								<span v-if="r.pipeline_run" class="ml-2 rounded bg-sunk px-1.5 py-0.5 text-2xs text-muted">pipeline</span></td>
							<td class="px-4 py-2.5 text-muted max-md:hidden">{{ r.suite }}</td>
							<td class="px-4 py-2.5 text-right tabular-nums text-muted">{{ DONE.includes(r.status) ? ms(r.duration_ms) : '—' }}</td>
							<td class="px-4 py-2.5 text-right text-muted max-sm:hidden" :title="r.creation">{{ ago(r.creation) }}</td>
						</tr>
					</tbody>
				</table>
				<div v-if="loading" class="space-y-2 p-4"><div v-for="i in 6" :key="i" class="h-8 animate-pulse rounded bg-sunk" /></div>
				<p v-else-if="!shown.length" class="px-4 py-12 text-center text-muted">No runs{{ status ? ` with status ${status}` : '' }} yet. Open a test and press Run.</p>
			</div>
		</div>
	</div>
</template>
