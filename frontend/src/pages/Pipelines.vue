<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Play, ChevronRight, Plus } from "lucide-vue-next";
import StatusDot from "../components/StatusDot.vue";
import { api } from "../api";
import { toastError } from "../toast";
import { ago, ms } from "../format";

const router = useRouter();
const pipelines = ref(null);
onMounted(async () => { try { pipelines.value = await api.listPipelines(); } catch (e) { toastError(e); pipelines.value = []; } });
async function run(p) {
	try { router.push({ name: "pipeline-run", params: { name: await api.runPipeline(p.name) } }); } catch (e) { toastError(e); }
}
</script>

<template>
	<div class="h-full overflow-y-auto">
		<div class="px-8 py-7">
			<div class="flex flex-wrap items-end justify-between gap-4">
				<div>
					<h1 class="page-title">Pipelines</h1>
					<p class="page-sub">Run suites in stages, like smoke tests before the full regression. When a stage fails, the stages after it are skipped.</p>
				</div>
				<a href="/desk/test-pipeline/new" class="btn-outline"><Plus class="h-4 w-4" />New pipeline</a>
			</div>
			<div v-if="pipelines === null" class="mt-6 space-y-3"><div v-for="i in 2" :key="i" class="h-36 animate-pulse rounded-lg bg-sunk" /></div>
			<p v-else-if="!pipelines.length" class="mt-10 rounded-lg border border-dashed border-line px-6 py-12 text-center text-muted">No pipelines yet. Create one to chain your suites into a release gate.</p>
			<article v-for="p in pipelines" :key="p.name" class="mt-6 rounded-lg border border-line bg-panel">
				<header class="flex flex-wrap items-center gap-3 px-5 pt-4">
					<h2 class="text-lg font-semibold">{{ p.name }}</h2>
					<p v-if="p.description" class="text-sm text-muted">{{ p.description }}</p>
					<a :href="`/desk/test-pipeline/${encodeURIComponent(p.name)}`" class="btn-ghost ml-auto text-muted">Edit stages</a>
					<button class="btn-primary" @click="run(p)"><Play class="h-4 w-4 fill-current" />Run pipeline</button>
				</header>
				<ol class="flex flex-wrap items-center gap-1.5 px-5 py-4" aria-label="Stages in order">
					<template v-for="(s, i) in p.stages" :key="i">
						<li class="rounded-md border border-line bg-sunk/50 px-3 py-2">
							<div class="text-sm font-medium">{{ s.stage_name }}</div>
							<div class="text-xs text-muted">{{ s.suite }}<template v-if="s.tag">, tagged {{ s.tag }}</template></div>
						</li>
						<ChevronRight v-if="i < p.stages.length - 1" class="h-4 w-4 text-faint" aria-hidden="true" />
					</template>
				</ol>
				<footer class="flex flex-wrap items-center gap-2 border-t border-line px-5 py-3 text-sm">
					<span class="text-muted">Recent runs</span>
					<router-link v-for="r in p.runs" :key="r.name" :to="{ name: 'pipeline-run', params: { name: r.name } }"
						class="inline-flex items-center gap-1.5 rounded-full border border-line px-2 py-0.5 text-xs hover:border-brand" :title="`${r.name}: ${r.status}, ${ms(r.duration_ms)}`">
						<StatusDot :status="r.status" />{{ ago(r.creation) }}
					</router-link>
					<span v-if="!p.runs.length" class="text-faint">None yet</span>
				</footer>
			</article>
		</div>
	</div>
</template>
