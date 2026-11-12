<script setup>
import { ref } from "vue";
import Modal from "./Modal.vue";
const props = defineProps({ title: String, suites: Array, defaultSuite: String, needsSuite: Boolean, confirmLabel: String, snippet: Boolean });
const description = ref("");
const emit = defineEmits(["close", "create"]);
const name = ref("");
const suite = ref(props.defaultSuite || props.suites?.[0]?.name || "");
const submit = () => name.value.trim() && (!props.needsSuite || suite.value) && emit("create", { title: name.value.trim(), suite: suite.value, description: description.value.trim() });
</script>
<template>
	<Modal :title="title" @close="emit('close')">
		<form id="new-item" class="grid gap-4" @submit.prevent="submit">
			<label><span class="label">Name</span><input v-model="name" class="field" required autofocus :placeholder="snippet ? 'e.g. Log in as Sales Manager' : 'e.g. Customer can check out'" /></label>
			<template v-if="snippet">
				<label><span class="label">What it does <span class="font-normal text-faint">(shown wherever it's used)</span></span>
					<textarea v-model="description" rows="2" class="field h-auto py-2" placeholder="e.g. Creates a Sales Order for {{customer}} and approves it" /></label>
				<p class="text-xs leading-5 text-muted">Tip: you can also turn steps you already have into a snippet. Open a test, then use ⋯ → Save steps as snippet.</p>
			</template>
			<label v-if="needsSuite"><span class="label">Suite</span>
				<select v-model="suite" class="field" required><option v-for="s in suites" :key="s.name" :value="s.name">{{ s.name }}</option></select>
				<span v-if="!suites?.length" class="mt-1 block text-xs text-fail">Create a suite first.</span></label>
		</form>
		<template #footer>
			<button class="btn-ghost" @click="emit('close')">Cancel</button>
			<button class="btn-primary" form="new-item" type="submit" :disabled="!name.trim() || (needsSuite && !suite)">{{ confirmLabel || 'Create' }}</button>
		</template>
	</Modal>
</template>
