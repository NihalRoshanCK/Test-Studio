<script setup>
import { onMounted, onBeforeUnmount, ref, nextTick } from "vue";
import { X } from "lucide-vue-next";
defineProps({ title: String, wide: Boolean });
const emit = defineEmits(["close"]);
const box = ref(null);
let opener = null;
const onKey = (e) => e.key === "Escape" && emit("close");
onMounted(async () => {
	opener = document.activeElement;
	document.addEventListener("keydown", onKey);
	await nextTick();
	(box.value.querySelector("[autofocus], input, select, textarea, button.btn-primary") || box.value).focus();
});
onBeforeUnmount(() => { document.removeEventListener("keydown", onKey); opener?.focus?.(); });
</script>
<template>
	<Teleport to="body">
		<div class="fixed inset-0 z-40 grid place-items-center bg-ink/30 p-4 backdrop-blur-[1px]" @mousedown.self="emit('close')">
			<div ref="box" role="dialog" aria-modal="true" :aria-label="title" tabindex="-1"
				class="flex max-h-[90vh] w-full flex-col rounded-lg border border-line bg-panel shadow-pop outline-none" :class="wide ? 'max-w-3xl' : 'max-w-md'">
				<div class="flex items-center justify-between border-b border-line px-5 py-3">
					<h2 class="text-lg font-semibold">{{ title }}</h2>
					<button class="icon-btn -mr-2" aria-label="Close" @click="emit('close')"><X class="h-4 w-4" /></button>
				</div>
				<div class="min-h-0 flex-1 overflow-auto px-5 py-4"><slot /></div>
				<div v-if="$slots.footer" class="flex justify-end gap-2 border-t border-line px-5 py-3"><slot name="footer" /></div>
			</div>
		</div>
	</Teleport>
</template>
