<script setup>
import { computed } from "vue";
import { ms } from "../format";

// One segment per executed step, width by duration: a run read like a signal trace.
const props = defineProps({ results: Array, total: Number, pausedAt: String, selected: String, report: String });
const emit = defineEmits(["select"]);
const segs = computed(() => {
	const done = (props.results || []).map((r) => ({ ...r, w: Math.max(r.status === "Skipped" ? 0.6 : 1, Math.sqrt(r.duration_ms || 0) / 6) }));
	const remaining = Math.max(0, (props.total || 0) - new Set(done.map((r) => String(r.step_no).split(".")[0])).size);
	return [...done, ...Array.from({ length: remaining }, (_, i) => ({ step_no: `pending-${i}`, pending: true, w: 1 }))];
});
const totalMs = computed(() => (props.results || []).reduce((a, r) => a + (r.duration_ms || 0), 0));
</script>

<template>
	<div class="border-t border-line bg-panel px-3 pb-2.5 pt-2">
		<div class="mb-1.5 flex items-center justify-between text-2xs text-muted">
			<span>Timeline</span><span class="flex items-center gap-3"><router-link v-if="report" :to="{ name: 'run', params: { name: report } }" class="font-medium text-brand hover:underline">Open report</router-link><span class="tabular-nums">{{ ms(totalMs) }}</span></span>
		</div>
		<div class="flex h-6 items-stretch gap-[2px]" role="list" aria-label="Run timeline">
			<button v-for="s in segs" :key="s.step_no" role="listitem" :disabled="s.pending"
				class="group relative min-w-[6px] rounded-[3px] transition-[filter,transform] hover:brightness-110 disabled:cursor-default"
				:style="{ flexGrow: s.w, flexBasis: 0 }"
				:class="[
					s.pending ? 'bg-sunk' : s.status === 'Passed' ? 'bg-pass/80' : s.status === 'Failed' ? 'bg-fail' : s.status === 'Known Issue' ? 'bg-warn' : 'bg-line',
					pausedAt && String(s.step_no) === pausedAt && 'ring-2 ring-run ring-offset-1 ring-offset-panel',
					selected === String(s.step_no) && 'ring-2 ring-ink ring-offset-1 ring-offset-panel',
				]"
				:aria-label="s.pending ? 'Not run yet' : `Step ${s.step_no} ${s.action}: ${s.status}, ${ms(s.duration_ms)}`"
				@click="emit('select', String(s.step_no))">
				<span v-if="!s.pending" class="pointer-events-none absolute bottom-full left-1/2 z-10 mb-1.5 hidden -translate-x-1/2 whitespace-nowrap rounded bg-ink px-2 py-1 text-2xs text-paper shadow-pop group-hover:block">
					{{ s.step_no }} · {{ s.action }} · {{ s.status === 'Skipped' ? 'skipped' : ms(s.duration_ms) }}
				</span>
			</button>
		</div>
	</div>
</template>
