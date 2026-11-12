<script setup>
import { computed, ref } from "vue";
import { Search, Plus, Play, Settings2, ChevronRight, Puzzle } from "lucide-vue-next";
import StatusDot from "./StatusDot.vue";
import { store } from "../format";

const props = defineProps({ tree: Object, current: String, currentKind: String });
const emit = defineEmits(["open", "new-test", "new-suite", "run-suite", "edit-suite", "open-snippet", "new-snippet"]);
const q = ref("");
const collapsed = ref(new Set(store.get("collapsed", [])));
function toggle(key) {
	collapsed.value.has(key) ? collapsed.value.delete(key) : collapsed.value.add(key);
	collapsed.value = new Set(collapsed.value);
	store.set("collapsed", [...collapsed.value]);
}
const groups = computed(() => {
	const needle = q.value.trim().toLowerCase();
	return (props.tree.suites || [])
		.map((s) => ({
			...s,
			cases: (props.tree.cases || []).filter((c) => c.suite === s.name && (!needle || `${c.title} ${c.tags_text || ""} ${c.name}`.toLowerCase().includes(needle))),
		}))
		.filter((g) => !needle || g.cases.length);
});
const snippets = computed(() => (props.tree.snippets || []).filter((s) => !q.value || s.toLowerCase().includes(q.value.toLowerCase())));
const passRate = (g) => {
	const run = g.cases.filter((c) => c.last_status);
	return run.length ? Math.round((100 * run.filter((c) => c.last_status === "Passed").length) / run.length) : null;
};
</script>

<template>
	<aside class="flex h-full min-h-0 flex-col border-r border-line bg-panel">
		<div class="p-3">
			<label class="relative block">
				<span class="sr-only">Search tests</span>
				<Search class="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-faint" />
				<input v-model="q" type="search" class="field pl-8" placeholder="Search tests and tags" />
			</label>
		</div>
		<div class="min-h-0 flex-1 overflow-y-auto px-2 pb-3" role="tree" aria-label="Tests">
			<section v-for="g in groups" :key="g.name" class="mb-1">
				<div class="group flex h-8 items-center gap-1 rounded pl-1 pr-1 hover:bg-sunk/60">
					<button class="flex min-w-0 flex-1 items-center gap-1 text-left" :aria-expanded="!collapsed.has(g.name)" @click="toggle(g.name)">
						<ChevronRight class="h-3.5 w-3.5 shrink-0 text-faint transition-transform" :class="!collapsed.has(g.name) && 'rotate-90'" />
						<span class="truncate text-xs font-semibold text-muted">{{ g.name }}</span>
						<span v-if="passRate(g) !== null" class="ml-1 text-2xs tabular-nums" :class="passRate(g) === 100 ? 'text-pass' : 'text-fail'">{{ passRate(g) }}%</span>
					</button>
					<button class="icon-btn h-6 w-6 opacity-0 group-hover:opacity-100 focus:opacity-100" :aria-label="`Suite settings for ${g.name}`" title="Suite settings" @click="emit('edit-suite', g.name)"><Settings2 class="h-3.5 w-3.5" /></button>
					<button class="icon-btn h-6 w-6 opacity-0 group-hover:opacity-100 focus:opacity-100" :aria-label="`Run every test in ${g.name}`" title="Run suite" @click="emit('run-suite', g.name)"><Play class="h-3.5 w-3.5" /></button>
				</div>
				<ul v-show="!collapsed.has(g.name)">
					<li v-for="c in g.cases" :key="c.name">
						<button role="treeitem" :aria-selected="currentKind === 'case' && current === c.name"
							class="flex h-8 w-full items-center gap-2 rounded pl-6 pr-2 text-left text-sm transition-colors"
							:class="currentKind === 'case' && current === c.name ? 'bg-brand/10 text-ink font-medium' : 'text-ink/90 hover:bg-sunk'"
							@click="emit('open', c.name)">
							<StatusDot :status="c.last_status" />
							<span class="min-w-0 flex-1 truncate" :class="!c.enabled && 'text-faint line-through'">{{ c.title }}</span>
							<span class="flex items-end gap-px" :aria-label="`Last ${c.history.length} runs`">
								<span v-for="(h, i) in c.history" :key="i" class="w-[3px] rounded-[1px]" :class="h === 'Passed' ? 'h-2 bg-pass/70' : 'h-3 bg-fail'" />
							</span>
						</button>
					</li>
					<li v-if="!g.cases.length" class="pl-6 text-xs text-faint leading-8">No tests yet</li>
				</ul>
			</section>
			<section v-if="snippets.length || !q" class="mt-3">
				<div class="flex h-8 items-center justify-between pl-2 pr-1">
					<span class="text-xs font-semibold text-muted">Snippets</span>
					<button class="icon-btn h-6 w-6" aria-label="New snippet" title="New snippet" @click="emit('new-snippet')"><Plus class="h-3.5 w-3.5" /></button>
				</div>
				<button v-for="s in snippets" :key="s"
					class="flex h-8 w-full items-center gap-2 rounded pl-3 pr-2 text-left text-sm transition-colors"
					:class="currentKind === 'snippet' && current === s ? 'bg-brand/10 font-medium' : 'hover:bg-sunk'"
					@click="emit('open-snippet', s)">
					<Puzzle class="h-3.5 w-3.5 shrink-0 text-faint" /><span class="truncate">{{ s }}</span>
				</button>
				<p v-if="!snippets.length" class="px-3 text-xs text-faint">Reusable step groups, like a login flow.</p>
			</section>
			<p v-if="!groups.length && q" class="px-3 py-6 text-center text-sm text-muted">Nothing matches “{{ q }}”.</p>
		</div>
		<div class="flex gap-2 border-t border-line p-3">
			<button class="btn-primary flex-1 justify-center" @click="emit('new-test')"><Plus class="h-4 w-4" />New test</button>
			<button class="btn-outline" title="New suite" @click="emit('new-suite')">Suite</button>
		</div>
	</aside>
</template>
