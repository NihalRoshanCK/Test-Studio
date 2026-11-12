<script setup>
import { computed, ref } from "vue";
import { ChevronRight, Download, FileText, CircleAlert } from "lucide-vue-next";
import Sentence from "./Sentence.vue";
import StatusBadge from "./StatusBadge.vue";
import { DONE, ms } from "../format";

// Run results grouped by snippet; a failure card leads so the reason is the first thing you read.
const props = defineProps({ run: Object, compact: Boolean });
const open = ref(new Set());
const groups = computed(() => {
	const out = [];
	for (const s of props.run.steps || []) {
		const g = s.group || "";
		const last = out[out.length - 1];
		if (g && last && last.group === g && last.top === String(s.step_no).split(".")[0]) last.steps.push(s);
		else out.push({ group: g, top: String(s.step_no).split(".")[0], steps: [s] });
	}
	for (const g of out) {
		g.status = g.steps.some((s) => s.status === "Failed") ? "Failed" : g.steps.some((s) => s.status === "Known Issue") ? "Known Issue" : g.steps.every((s) => s.status === "Skipped") ? "Skipped" : "Passed";
		g.ms = g.steps.reduce((a, s) => a + (s.duration_ms || 0), 0);
	}
	return out;
});
const failed = computed(() => (props.run.steps || []).find((s) => s.status === "Failed") || (props.run.steps || []).find((s) => s.status === "Known Issue"));
const counts = computed(() => ["Passed", "Known Issue", "Failed", "Skipped"].map((k) => [k, (props.run.steps || []).filter((s) => s.status === k).length]));
const toggle = (k) => { open.value.has(k) ? open.value.delete(k) : open.value.add(k); open.value = new Set(open.value); };
const isOpen = (g) => !g.group || g.status === "Failed" || open.value.has(g.top);
</script>

<template>
	<div class="flex h-full flex-col overflow-y-auto">
		<div class="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-5 py-4">
			<StatusBadge :status="run.status" />
			<span class="text-sm text-muted">
				<template v-for="[k, n] in counts" :key="k"><span v-if="n" class="mr-2"><span class="font-medium tabular-nums text-ink">{{ n }}</span> {{ k.toLowerCase() }}</span></template>
				<span v-if="DONE.includes(run.status)" class="tabular-nums">{{ ms(run.duration_ms ?? run.duration) }}</span>
			</span>
			<span class="ml-auto flex gap-1.5">
				<a v-if="run.trace" class="btn-ghost h-7 px-2 text-xs" :href="run.trace" download title="Open with npx playwright show-trace"><Download class="h-3.5 w-3.5" />Trace</a>
				<router-link v-if="!compact && run.name && DONE.includes(run.status)" class="btn-ghost h-7 px-2 text-xs" :to="{ name: 'run', params: { name: run.name } }"><FileText class="h-3.5 w-3.5" />Full report</router-link>
			</span>
		</div>

		<section v-if="failed" class="border-b border-line px-5 py-4" :class="failed.status === 'Known Issue' ? 'bg-warn/[0.06]' : 'bg-fail/[0.05]'" aria-label="Why it failed">
			<p class="flex items-center gap-1.5 text-xs font-medium" :class="failed.status === 'Known Issue' ? 'text-warn' : 'text-fail'"><CircleAlert class="h-3.5 w-3.5" />{{ failed.status === 'Known Issue' ? "Known issue at" : "Failed at" }} step {{ failed.step_no }}<template v-if="failed.group"> in {{ failed.group }}</template></p>
			<p class="mt-1.5 text-sm"><Sentence :step="failed" /></p>
			<pre class="mt-2 whitespace-pre-wrap font-sans text-sm leading-6 text-ink">{{ failed.error }}</pre>
			<a v-if="failed.screenshot" :href="failed.screenshot" target="_blank" rel="noopener" class="mt-3 block">
				<img :src="failed.screenshot" :alt="`Screen when step ${failed.step_no} failed`" class="w-full rounded-md bg-white ring-1 ring-line" />
			</a>
		</section>
		<pre v-else-if="run.status === 'Error' && run.error" class="m-5 max-h-60 overflow-auto rounded-md bg-sunk p-3 font-mono text-xs text-fail">{{ run.error }}</pre>

		<ol class="px-3 py-3" aria-label="Steps">
			<li v-for="g in groups" :key="g.top + g.group">
				<button v-if="g.group" class="flex w-full items-center gap-2 rounded px-2 py-2 text-left text-sm hover:bg-sunk/60" :aria-expanded="isOpen(g)" @click="toggle(g.top)">
					<ChevronRight class="h-4 w-4 text-faint transition-transform" :class="isOpen(g) && 'rotate-90'" />
					<span class="h-2 w-2 shrink-0 rounded-full" :class="{ 'bg-pass': g.status === 'Passed', 'bg-fail': g.status === 'Failed', 'bg-warn': g.status === 'Known Issue', 'bg-line': g.status === 'Skipped' }" />
					<span class="flex-1"><span class="font-medium">{{ g.group }}</span> <span class="text-xs text-faint">{{ g.steps.length }} steps</span></span>
					<span class="text-xs tabular-nums text-faint">{{ ms(g.ms) }}</span>
				</button>
				<ol v-if="isOpen(g)" :class="g.group && 'ml-6 border-l border-line pl-2'">
					<li v-for="s in g.steps" :key="s.step_no" class="flex items-start gap-2 rounded px-2 py-1.5 text-sm" :class="s.status === 'Skipped' && 'opacity-50'">
						<span class="mt-2 h-1.5 w-1.5 shrink-0 rounded-full" :class="{ 'bg-pass': s.status === 'Passed', 'bg-fail': s.status === 'Failed', 'bg-warn': s.status === 'Known Issue', 'bg-line': s.status === 'Skipped' }" />
						<span class="w-8 shrink-0 font-mono text-xs leading-6 text-faint">{{ s.step_no }}</span>
						<span class="min-w-0 flex-1"><Sentence :step="s" /></span>
						<span class="shrink-0 text-xs leading-6 tabular-nums" :class="s.status === 'Failed' ? 'text-fail' : s.status === 'Known Issue' ? 'text-warn' : 'text-faint'">{{ s.status === 'Skipped' ? 'skipped' : ms(s.duration_ms) }}</span>
					</li>
				</ol>
			</li>
			<li v-if="!(run.steps || []).length" class="px-2 py-10 text-center text-sm text-muted">{{ DONE.includes(run.status) ? 'No steps ran.' : 'Waiting for the browser…' }}</li>
		</ol>
	</div>
</template>
