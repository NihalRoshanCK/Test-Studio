<script setup>
import { ref } from "vue";
import { Copy, Download, Check } from "lucide-vue-next";
import Modal from "./Modal.vue";
const props = defineProps({ name: String, code: String });
const emit = defineEmits(["close"]);
const copied = ref(false);
async function copy() {
	try { await navigator.clipboard.writeText(props.code); copied.value = true; setTimeout(() => (copied.value = false), 1600); } catch (e) { /* clipboard blocked */ }
}
function download() {
	const a = document.createElement("a");
	a.href = URL.createObjectURL(new Blob([props.code], { type: "text/plain" }));
	a.download = `${props.name}.spec.ts`;
	a.click();
	URL.revokeObjectURL(a.href);
}
</script>
<template>
	<Modal title="Export to Playwright" wide @close="emit('close')">
		<p class="mb-3 text-sm text-muted">Save as <code class="font-mono text-ink">tests/{{ name }}.spec.ts</code> and run <code class="font-mono text-ink">npx playwright test</code>. Secret variables are read from environment variables.</p>
		<pre class="max-h-[55vh] overflow-auto rounded-md bg-ink p-4 font-mono text-xs leading-relaxed text-paper">{{ code }}</pre>
		<template #footer>
			<button class="btn-outline" @click="download"><Download class="h-4 w-4" />Download</button>
			<button class="btn-primary" @click="copy"><Check v-if="copied" class="h-4 w-4" /><Copy v-else class="h-4 w-4" />{{ copied ? 'Copied' : 'Copy code' }}</button>
		</template>
	</Modal>
</template>
