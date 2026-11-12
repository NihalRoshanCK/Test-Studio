<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ArrowLeft, Download, RotateCcw, PencilLine, ImageOff, Film } from "lucide-vue-next";
import StatusBadge from "../components/StatusBadge.vue";
import RunRibbon from "../components/RunRibbon.vue";
import Sentence from "../components/Sentence.vue";
import { api } from "../api";
import { toastError, toast } from "../toast";
import { ago, ms, DONE } from "../format";

const route = useRoute();
const router = useRouter();
const run = ref(null);
const selected = ref(null);
const live = ref(null); // latest frame while the run is in progress
const showVideo = ref(false);
let seq = 0;
let timer = null;

async function load() {
	clearTimeout(timer);
	try {
		run.value = await api.getRun(route.params.name);
		if (!selected.value) {
			const failed = run.value.steps.find((s) => s.status === "Failed") || run.value.steps.find((s) => s.status === "Known Issue");
			selected.value = String((failed || run.value.steps.find((s) => s.screenshot) || run.value.steps.at(-1) || {}).step_no || "");
		}
	} catch (e) { toastError(e); }
	if (run.value && !DONE.includes(run.value.status)) {
		try {
			const m = await api.runPoll(run.value.name, seq);
			if (m.frame) { seq = m.frame.seq; live.value = m.frame; }
		} catch { /* the report still updates without frames */ }
		timer = setTimeout(load, 600);
	} else live.value = null;
}
onMounted(load);
onBeforeUnmount(() => clearTimeout(timer));
watch(() => route.params.name, () => { run.value = null; selected.value = null; live.value = null; seq = 0; load(); });

const step = computed(() => run.value?.steps.find((s) => String(s.step_no) === selected.value));
const shot = computed(() => step.value?.screenshot || [...(run.value?.steps || [])].reverse().find((s) => s.screenshot && parseFloat(s.step_no) <= parseFloat(selected.value))?.screenshot);
// duration trend over the test's last runs: an SVG polyline, latest point on the right
const timings = ref(null);
watch(() => run.value?.test_case, async (tc) => { if (tc) try { timings.value = await api.stepTimings(tc); } catch (e) { /* trend is optional */ } });
function trend(values) {
	const v = (values || []).map((x) => x ?? 0);
	if (v.filter(Boolean).length < 2) return "";
	const max = Math.max(...v) || 1;
	return v.map((x, i) => `${((i / (v.length - 1)) * 48).toFixed(1)},${(14 - (x / max) * 12).toFixed(1)}`).join(" ");
}
const counts = computed(() => ["Passed", "Known Issue", "Failed", "Skipped"].map((s) => [s, (run.value?.steps || []).filter((x) => x.status === s).length]));
async function rerun() {
	try {
		await api.runCase(run.value.test_case);
		toast("Run queued", "info");
		router.push({ name: "runs", query: { test: run.value.test_case } });
	} catch (e) { toastError(e); }
}
</script>

<template>
	<div v-if="run" class="flex h-full min-h-0 flex-col">
		<header class="border-b border-line bg-panel px-8 pb-4 pt-5">
			<router-link :to="{ name: 'runs' }" class="inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft class="h-4 w-4" />Runs</router-link>
			<div class="mt-2 flex items-start gap-4">
				<div class="flex min-w-0 flex-1 flex-wrap items-center gap-x-3 gap-y-1"><h1 class="page-title">{{ run.title }}</h1><StatusBadge :status="run.status" /><span v-if="run.run_as" class="pill">as {{ run.run_as }}</span><span v-if="trend(timings?.totals)" class="flex items-center gap-1.5 text-xs text-muted" :title="`Total time of the last ${timings.totals.length} runs`"><svg class="h-4 w-12 text-brand" viewBox="0 0 48 16" aria-hidden="true"><polyline :points="trend(timings.totals)" fill="none" stroke="currentColor" stroke-width="1.5" /></svg>last {{ timings.totals.length }} runs</span></div>
				<div class="flex shrink-0 flex-wrap justify-end gap-1.5">
					<button v-if="run.video" class="btn-outline" :aria-pressed="showVideo" @click="showVideo = !showVideo"><Film class="h-4 w-4" />{{ showVideo ? "Screenshots" : "Video" }}</button>
					<a v-if="run.trace" class="btn-outline" :href="run.trace" download title="Open with npx playwright show-trace, or drop it on trace.playwright.dev"><Download class="h-4 w-4" />Trace</a>
					<router-link class="btn-outline" :to="{ name: 'test', params: { name: run.test_case } }"><PencilLine class="h-4 w-4" />Edit test</router-link>
					<button class="btn-primary" @click="rerun"><RotateCcw class="h-4 w-4" />Run again</button>
				</div>
			</div>
			<p class="mt-1 text-sm text-muted">
				{{ run.name }} in {{ run.suite }}, {{ run.browser }}, {{ ago(run.started_at || run.creation) }}<template v-if="DONE.includes(run.status)">, took {{ ms(run.duration_ms) }}</template>.
				<span v-for="[k, n] in counts" :key="k" class="ml-3"><span class="font-medium tabular-nums" :class="{ 'text-pass': k === 'Passed' && n, 'text-fail': k === 'Failed' && n, 'text-warn': k === 'Known Issue' && n }">{{ n }}</span> {{ k.toLowerCase() }}</span>
			</p>
		</header>
		<RunRibbon :results="run.steps" :total="0" :selected="selected" @select="selected = $event" />
		<div class="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(340px,440px)_1fr]">
			<ol class="min-h-0 overflow-y-auto border-r border-line bg-panel py-2" aria-label="Steps">
				<li v-for="(s, i) in run.steps" :key="s.step_no">
					<p v-if="s.group && s.group !== run.steps[i - 1]?.group" class="px-5 pb-1 pt-3 text-xs font-semibold text-muted">{{ s.group }}</p>
					<button class="flex w-full items-start gap-3 px-5 py-2 text-left transition-colors"
						:class="selected === String(s.step_no) ? 'bg-brand/[0.08]' : 'hover:bg-sunk/60'" :aria-current="selected === String(s.step_no)" @click="selected = String(s.step_no)">
						<span class="mt-1.5 h-2 w-2 shrink-0 rounded-full" :class="s.status === 'Passed' ? 'bg-pass' : s.status === 'Failed' ? 'bg-fail' : s.status === 'Known Issue' ? 'bg-warn' : 'bg-line'" />
						<span class="w-8 shrink-0 font-mono text-xs leading-6 text-faint">{{ s.step_no }}</span>
						<span class="min-w-0 flex-1">
							<span class="block text-sm"><Sentence :step="s" /></span>
							<span v-if="s.error" class="mt-1 block whitespace-pre-wrap font-mono text-xs" :class="s.status === 'Failed' ? 'text-fail' : 'text-warn'">{{ s.error }}</span>
						</span>
						<svg v-if="trend(timings?.steps[s.step_no])" class="mt-1.5 h-4 w-12 shrink-0 text-faint" viewBox="0 0 48 16" aria-hidden="true"><polyline :points="trend(timings.steps[s.step_no])" fill="none" stroke="currentColor" stroke-width="1.25" /></svg>
						<span class="shrink-0 text-xs leading-6 tabular-nums text-faint" :title="timings?.steps[s.step_no] ? `Last runs: ${timings.steps[s.step_no].map((x) => ms(x)).join(', ')}` : ''">{{ s.status === 'Skipped' ? 'skipped' : ms(s.duration_ms) }}</span>
					</button>
				</li>
				<li v-if="!run.steps.length" class="px-5 py-10 text-center text-sm text-muted">{{ DONE.includes(run.status) ? 'No steps ran.' : 'Waiting for the browser…' }}</li>
			</ol>
			<div class="min-h-0 overflow-auto bg-sunk/60 p-6">
				<p v-if="run.status !== 'Error' && (run.error || '').includes('Not saved:')" class="mb-4 rounded-md bg-panel p-3 text-xs text-warn ring-1 ring-warn/30">{{ run.error.slice(run.error.indexOf('Not saved:')) }}</p>
				<pre v-if="run.status === 'Error' && run.error" class="mb-4 max-h-60 overflow-auto rounded-md bg-panel p-4 font-mono text-xs text-fail ring-1 ring-fail/20">{{ run.error }}</pre>
				<figure v-if="showVideo && run.video" class="mx-auto max-w-4xl">
					<video :src="run.video" controls autoplay class="w-full rounded-md bg-black shadow-pop ring-1 ring-line" :aria-label="`Video of ${run.name}`" />
					<figcaption class="mt-2 text-xs text-muted">The whole run, as the browser saw it. <a :href="run.video" download class="text-brand hover:underline">Download</a></figcaption>
				</figure>
				<figure v-else-if="live" class="mx-auto max-w-4xl">
					<div class="relative">
						<img :src="'data:image/jpeg;base64,' + live.img" alt="Live view of the running test" class="w-full rounded-md bg-white shadow-pop ring-1 ring-line" />
						<span class="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-ink/80 px-2.5 py-1 text-2xs font-medium text-paper"><span class="h-1.5 w-1.5 animate-pulse rounded-full bg-run" />Live</span>
					</div>
					<figcaption class="mt-2 truncate text-xs text-muted">{{ live.url }}</figcaption>
				</figure>
				<figure v-else-if="shot" class="mx-auto max-w-4xl">
					<a :href="shot" target="_blank" rel="noopener"><img :src="shot" :alt="`Screenshot at step ${selected}`" class="w-full rounded-md bg-white shadow-pop ring-1 ring-line" /></a>
					<figcaption class="mt-2 text-xs text-muted">Screenshot {{ step?.screenshot ? `after step ${selected}` : 'from an earlier step' }}. Click to open full size.</figcaption>
				</figure>
				<div v-else class="grid h-full place-items-center text-center text-sm text-muted">
					<div><ImageOff class="mx-auto mb-2 h-8 w-8 text-faint" />No screenshot for this step.<br />Failures are captured automatically. Turn on “Screenshot after every step” in the suite settings for more.</div>
				</div>
			</div>
		</div>
	</div>
	<div v-else class="grid h-full place-items-center"><div class="h-6 w-6 animate-spin rounded-full border-2 border-brand/25 border-t-brand" /></div>
</template>
