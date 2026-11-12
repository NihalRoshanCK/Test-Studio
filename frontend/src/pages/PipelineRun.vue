<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ArrowLeft, RotateCcw } from "lucide-vue-next";
import StatusBadge from "../components/StatusBadge.vue";
import { api } from "../api";
import { toastError } from "../toast";
import { ago, ms, DONE } from "../format";

const route = useRoute();
const router = useRouter();
const pr = ref(null);
let timer = null;
async function load() {
	clearTimeout(timer);
	try { pr.value = await api.getPipelineRun(route.params.name); } catch (e) { toastError(e); }
	if (pr.value && !DONE.includes(pr.value.status)) timer = setTimeout(load, 1500);
}
onMounted(load);
onBeforeUnmount(() => clearTimeout(timer));
watch(() => route.params.name, load);

// funnel: each stage's band is as wide as its share of the biggest stage; fill shows its pass rate
const max = computed(() => Math.max(1, ...(pr.value?.stages || []).map((s) => s.total || 0)));
async function again() {
	try { router.push({ name: "pipeline-run", params: { name: await api.runPipeline(pr.value.pipeline) } }); } catch (e) { toastError(e); }
}
</script>

<template>
	<div v-if="pr" class="h-full overflow-y-auto">
		<div class="px-8 py-7">
			<router-link :to="{ name: 'pipelines' }" class="inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft class="h-4 w-4" />Pipelines</router-link>
			<div class="mt-2 flex flex-wrap items-center gap-4">
				<h1 class="page-title">{{ pr.pipeline }}</h1>
				<StatusBadge :status="pr.status" />
				<button class="btn-primary ml-auto" :disabled="!DONE.includes(pr.status)" @click="again"><RotateCcw class="h-4 w-4" />Run again</button>
			</div>
			<p class="mt-1 text-sm text-muted">{{ pr.name }}, started {{ ago(pr.started_at || pr.creation) }}<template v-if="DONE.includes(pr.status)">, took {{ ms(pr.duration_ms) }}</template>.</p>

			<section class="mt-8" aria-label="Funnel">
				<div v-for="(s, i) in pr.stages" :key="i" class="grid grid-cols-[180px_1fr_150px] items-center gap-4 py-2 max-sm:grid-cols-1 max-sm:gap-1">
					<div>
						<div class="font-medium" :class="['Skipped', 'Pending'].includes(s.status) && 'text-faint'">{{ s.stage_name }}</div>
						<div class="text-xs text-muted">{{ s.suite }}</div>
					</div>
					<div class="flex justify-center">
						<div class="relative h-10 overflow-hidden rounded-md bg-sunk transition-[width] duration-500"
							:style="{ width: `${Math.max(10, (100 * (s.total || 0)) / max)}%` }" role="img"
							:aria-label="`${s.stage_name}: ${s.passed || 0} of ${s.total || 0} passed`">
							<div class="absolute inset-y-0 left-0 bg-pass transition-[width] duration-500" :style="{ width: `${(100 * (s.passed || 0)) / (s.total || 1)}%` }" />
							<div class="absolute inset-y-0 bg-fail transition-[width] duration-500" :style="{ left: `${(100 * (s.passed || 0)) / (s.total || 1)}%`, width: `${(100 * (s.failed || 0)) / (s.total || 1)}%` }" />
							<div v-if="s.status === 'Running'" class="absolute inset-0 animate-pulse bg-run/15" />
						</div>
					</div>
					<div class="text-sm tabular-nums">
						<template v-if="s.status === 'Skipped'"><span class="text-faint">Skipped</span></template>
						<template v-else-if="s.status === 'Pending'"><span class="text-faint">Waiting</span></template>
						<template v-else><span class="font-medium" :class="s.failed ? 'text-fail' : 'text-pass'">{{ s.passed }}/{{ s.total }}</span> <span class="text-muted">passed</span>
							<span v-if="s.duration_ms" class="ml-1 text-xs text-faint">{{ ms(s.duration_ms) }}</span></template>
					</div>
				</div>
			</section>

			<section class="mt-10">
				<h2 class="mb-3 text-sm font-semibold text-muted">Test runs</h2>
				<div class="table-card">
					<router-link v-for="r in pr.runs" :key="r.name" :to="{ name: 'run', params: { name: r.name } }" class="flex items-center gap-3 border-b border-line px-4 py-2.5 text-sm last:border-0 hover:bg-sunk/50">
						<StatusBadge :status="r.status" /><span class="font-medium">{{ r.title }}</span><span class="text-muted">{{ r.suite }}</span>
						<span class="ml-auto tabular-nums text-muted">{{ DONE.includes(r.status) ? ms(r.duration_ms) : '' }}</span>
					</router-link>
					<p v-if="!pr.runs.length" class="px-4 py-8 text-center text-sm text-muted">Tests appear here as each stage starts.</p>
				</div>
			</section>
		</div>
	</div>
	<div v-else class="grid h-full place-items-center"><div class="h-6 w-6 animate-spin rounded-full border-2 border-brand/25 border-t-brand" /></div>
</template>
