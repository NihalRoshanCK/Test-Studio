<script setup>
import { statusTone } from "../format";
defineProps({ status: String, size: { type: String, default: "h-2 w-2" } });
</script>
<template>
	<span class="inline-block shrink-0 rounded-full" :class="[size, status ? `bg-${statusTone(status)}` : 'bg-line', status === 'Running' && 'animate-pulse']" :title="status || 'Not run yet'" />
</template>
