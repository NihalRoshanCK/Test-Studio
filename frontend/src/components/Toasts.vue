<script setup>
import { toasts } from "../toast";
import { CheckCircle2, XCircle, Info } from "lucide-vue-next";
const icon = { success: CheckCircle2, error: XCircle, info: Info };
</script>
<template>
	<div class="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2" aria-live="polite">
		<TransitionGroup enter-from-class="opacity-0 translate-y-2" enter-active-class="transition duration-200" leave-to-class="opacity-0" leave-active-class="transition duration-150">
			<div v-for="t in toasts" :key="t.id" class="pointer-events-auto flex items-start gap-2.5 rounded-md border border-line bg-panel p-3 text-sm shadow-pop">
				<component :is="icon[t.kind] || Info" class="mt-0.5 h-4 w-4 shrink-0" :class="{ 'text-pass': t.kind === 'success', 'text-fail': t.kind === 'error', 'text-run': t.kind === 'info' }" />
				<span class="whitespace-pre-line break-words">{{ t.message }}</span>
			</div>
		</TransitionGroup>
	</div>
</template>
