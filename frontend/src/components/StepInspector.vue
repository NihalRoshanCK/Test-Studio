<script setup>
import { computed, ref, watch } from "vue";
import { Crosshair, ScanEye, ExternalLink } from "lucide-vue-next";
import { ACTIONS, ACTION_GROUPS, GROUP_HINT, snippetInputs as givenInputs } from "../actions";
import Sentence from "./Sentence.vue";

const props = defineProps({ step: Object, index: Number, snippets: Array, fields: Array, doctype: String, picking: Boolean, snippetInputs: Object });
const emit = defineEmits(["change", "pick", "test", "open-snippet"]);
const meta = computed(() => ACTIONS[props.step.action] || { fields: [], help: "" });
const grouped = ACTION_GROUPS.map((g) => [g, Object.entries(ACTIONS).filter(([, m]) => m.group === g)]);
const set = (key, value) => emit("change", { [key]: value });
const listId = `fields-${Math.random().toString(36).slice(2, 8)}`;
const showAdvanced = ref(false);
// a building block's inputs: the {{variables}} its steps use; what you type here applies to this use only
const inputs = computed(() => (props.step.action === "run_snippet" && props.step.snippet ? props.snippetInputs?.[props.step.snippet] || [] : []));
const given = computed(() => givenInputs(props.step));
function setInput(k, v) {
	const next = { ...given.value, [k]: v };
	if (v === "") delete next[k];
	set("value", Object.keys(next).length ? JSON.stringify(next) : "");
}
watch(() => props.index, () => (showAdvanced.value = !!(props.step.timeout_ms || props.step.continue_on_failure || props.step.known_issue)));
</script>

<template>
	<div class="flex h-full flex-col overflow-y-auto">
		<div class="border-b border-line px-5 pb-4 pt-4">
			<p class="text-xs text-muted">Step {{ index + 1 }}</p>
			<p class="mt-1 text-[15px] leading-6"><Sentence :step="step" /></p>
		</div>

		<div class="space-y-5 px-5 py-5">
			<label class="block">
				<span class="label">What should this step do?</span>
				<select class="field h-9" :value="step.action" @change="set('action', $event.target.value)">
					<optgroup v-for="[g, items] in grouped" :key="g" :label="`${g}: ${GROUP_HINT[g]}`">
						<option v-for="[a, m] in items" :key="a" :value="a">{{ m.label }}</option>
					</optgroup>
				</select>
				<span class="mt-1.5 block text-xs leading-5 text-muted">{{ meta.help }}</span>
			</label>

			<div v-for="f in meta.fields" :key="f.key">
				<label :for="`insp-${f.key}`" class="label">{{ f.label }}</label>
				<template v-if="f.suggest === 'snippets'">
					<div class="flex gap-1.5">
						<select :id="`insp-${f.key}`" class="field h-9" :value="step.snippet || ''" @change="set('snippet', $event.target.value)">
							<option value="" disabled>Choose a snippet</option>
							<option v-for="s in snippets" :key="s" :value="s">{{ s }}</option>
						</select>
						<button v-if="step.snippet" class="icon-btn h-9 w-9 shrink-0" title="Open snippet" aria-label="Open snippet" @click="emit('open-snippet', step.snippet)"><ExternalLink class="h-4 w-4" /></button>
					</div>
				</template>
				<template v-else>
					<div class="flex gap-1.5">
						<input :id="`insp-${f.key}`" class="field h-9" :class="f.pick || /\{\{/.test(step[f.key]) ? 'font-mono text-xs' : ''"
							:type="f.secret && !/^\s*\{\{.*\}\}\s*$/.test(step[f.key] || '') && step[f.key] ? 'password' : 'text'"
							:value="step[f.key] || ''" :placeholder="f.placeholder" :list="f.suggest === 'fields' ? listId : undefined"
							spellcheck="false" autocomplete="off" @input="set(f.key, $event.target.value)" />
						<template v-if="f.pick">
							<button class="icon-btn h-9 w-9 shrink-0" :class="picking && 'bg-brand text-brand-ink hover:bg-brand hover:text-brand-ink'" title="Pick on the live page" aria-label="Pick element" @click="emit('pick')"><Crosshair class="h-4 w-4" /></button>
							<button class="icon-btn h-9 w-9 shrink-0" :disabled="!step.selector" title="Highlight what this matches" aria-label="Test selector" @click="emit('test', step.selector)"><ScanEye class="h-4 w-4" /></button>
						</template>
					</div>
					<p v-if="f.suggest === 'fields'" class="mt-1.5 text-xs leading-5 text-muted">
						<template v-if="doctype">Suggestions from <span class="text-ink">{{ doctype }}</span>. </template>Use the label you see on the form, or <code class="font-mono">items[1].qty</code> for a table row.
					</p>
					<p v-if="f.secret" class="mt-1.5 text-xs leading-5 text-muted">Put passwords in the suite's secret variables and refer to them here, like <code v-pre class="font-mono">{{exec_password}}</code>.</p>
				</template>
			</div>
			<div v-if="step.action === 'run_snippet' && step.snippet">
				<p class="label">Inputs for this use</p>
				<p v-if="!inputs.length" class="text-xs text-muted">This snippet doesn't need any inputs.</p>
				<div v-else class="divide-y divide-line overflow-hidden rounded-md border border-line">
					<label v-for="k in inputs" :key="k" class="flex items-center gap-3 px-3 py-1.5">
						<span class="w-32 shrink-0 truncate font-mono text-xs text-muted" :title="k">{{ k }}</span>
						<input class="field h-8 border-0 bg-transparent px-1.5 hover:bg-sunk focus:bg-sunk" :value="given[k] || ''"
							:placeholder="`from test or suite: {{${k}}}`" spellcheck="false" @input="setInput(k, $event.target.value)" />
					</label>
				</div>
				<p v-if="inputs.length" class="mt-1.5 text-xs leading-5 text-muted">Leave blank to use the test's or suite's variable. Values can use other variables, like <code v-pre class="font-mono">{{vip_customer}}</code>.</p>
			</div>
			<datalist :id="listId"><option v-for="f in fields" :key="f.key" :value="f.key">{{ f.label }}</option></datalist>

			<label class="block">
				<span class="label">Note</span>
				<input class="field h-9" :value="step.note || ''" placeholder="Why this step matters (optional)" @input="set('note', $event.target.value)" />
			</label>

			<div>
				<button class="text-xs font-medium text-muted hover:text-ink" :aria-expanded="showAdvanced" @click="showAdvanced = !showAdvanced">{{ showAdvanced ? 'Hide' : 'Show' }} advanced options</button>
				<div v-if="showAdvanced" class="mt-3 space-y-4">
					<label class="block">
						<span class="label">Timeout (ms)</span>
						<input class="field h-9 w-40" type="number" min="0" step="500" :value="step.timeout_ms || ''" placeholder="Suite default" @input="set('timeout_ms', parseInt($event.target.value, 10) || null)" />
					</label>
					<label class="flex items-center gap-2 text-sm">
						<input type="checkbox" class="accent-[rgb(var(--brand))]" :checked="!!step.continue_on_failure" @change="set('continue_on_failure', $event.target.checked ? 1 : 0)" />
						Keep going if this step fails
					</label>
					<label class="block">
						<span class="label">Known failure</span>
						<input class="field h-9" :value="step.known_issue || ''" placeholder="e.g. Actual value: 9" @input="set('known_issue', $event.target.value)" />
						<span class="mt-1 block text-xs text-muted">If the step fails with this text, the run records a known issue and carries on. Any other failure still fails.</span>
					</label>
				</div>
			</div>
		</div>
	</div>
</template>
