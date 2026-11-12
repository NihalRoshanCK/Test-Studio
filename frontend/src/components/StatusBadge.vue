<script setup>
import { statusTone } from "../format";
defineProps({ status: String });
</script>
<template>
	<span class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
		:class="{ pass: 'bg-pass/10 text-pass', fail: 'bg-fail/10 text-fail', warn: 'bg-warn/10 text-warn', run: 'bg-run/10 text-run', faint: 'bg-sunk text-muted' }[statusTone(status)]">
		<span class="h-1.5 w-1.5 rounded-full bg-current" :class="status === 'Running' && 'animate-pulse'" />{{ status }}
	</span>
</template>
