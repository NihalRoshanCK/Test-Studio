<script setup>
import { computed } from "vue";
import { sentence } from "../actions";
const props = defineProps({ step: Object });
const parts = computed(() => sentence(props.step));
// raw selectors read as code; labels and names read as words
const codey = (t) => /[[\]#.=>:()"]/.test(t) && !/^\{\{.*\}\}$/.test(t);
</script>
<template>
	<span class="min-w-0 leading-6">
		<template v-for="(p, i) in parts" :key="i">
			<span v-if="p.kind === 'verb'" class="font-medium text-ink">{{ p.text }}</span>
			<span v-else-if="p.kind === 'plain'" class="text-muted">{{ p.text }}</span>
			<template v-else-if="p.text">
				<code v-if="codey(p.text) || /\{\{/.test(p.text)" class="mx-0.5 rounded px-1.5 py-px font-mono text-[12px]"
					:class="p.kind === 'value' ? 'bg-brand/10 text-brand' : 'bg-sunk text-ink/80'">{{ p.text }}</code>
				<span v-else class="mx-0.5 rounded px-1.5 py-px" :class="p.kind === 'value' ? 'bg-brand/10 text-brand' : 'bg-sunk text-ink'">{{ p.text }}</span>
			</template>
			<span v-else class="italic text-faint">not set</span>
			{{ " " }}
		</template>
	</span>
</template>
