<script setup>
import { reactive, ref, computed, onMounted } from "vue";
import { Plus, Trash2, Lock } from "lucide-vue-next";
import Modal from "./Modal.vue";
import { api } from "../api";
import { toast, toastError } from "../toast";

const props = defineProps({ suite: Object }); // null = create
const emit = defineEmits(["close", "saved"]);
const isNew = !props.suite;
const d = reactive(props.suite ? JSON.parse(JSON.stringify(props.suite)) : {
	doctype: "Test Suite", title: "", base_url: "", browser: "chromium", headless: 1, default_timeout_ms: 10000,
	viewport_width: 1280, viewport_height: 720, record_trace: 1, screenshot_each_step: 0, variables: [],
});
d.variables = d.variables || [];
// a new suite starts from Test Studio Settings' defaults
onMounted(async () => {
	if (!isNew) return;
	try {
		const s = await api.getSettings();
		Object.assign(d, { default_timeout_ms: s.new_suite_timeout_ms || 10000, record_trace: s.new_suite_record_trace,
			record_video: s.new_suite_record_video, screenshot_each_step: s.new_suite_screenshot_each_step });
	} catch (e) { /* keep the built-in defaults */ }
});
const saving = ref(false);
const valid = computed(() => d.title?.trim() && (!d.base_url || /^https?:\/\//.test(d.base_url)));
async function save() {
	if (!valid.value) return;
	saving.value = true;
	try {
		const doc = isNew ? await api.insert(d) : await api.save(d);
		toast(isNew ? `Created ${doc.name}` : "Suite saved", "success");
		emit("saved", doc);
	} catch (e) { toastError(e); } finally { saving.value = false; }
}
</script>

<template>
	<Modal :title="isNew ? 'New suite' : `Suite settings`" wide @close="emit('close')">
		<form id="suite-form" class="grid gap-5" @submit.prevent="save">
			<div class="grid gap-4 sm:grid-cols-2">
				<label><span class="label">Name</span><input v-model="d.title" class="field" :disabled="!isNew" required autofocus placeholder="Checkout flow" /></label>
				<label><span class="label">Base URL</span><input v-model="d.base_url" class="field-mono" placeholder="https://staging.example.com" />
					<span v-if="d.base_url && !/^https?:\/\//.test(d.base_url)" class="mt-1 block text-xs text-fail">Start with http:// or https://</span></label>
			</div>
			<div class="grid gap-4 sm:grid-cols-4">
				<label><span class="label">Browser</span>
					<select v-model="d.browser" class="field"><option value="chromium">Chromium</option><option value="firefox">Firefox</option><option value="webkit">WebKit (Safari)</option></select></label>
				<label><span class="label">Step timeout (ms)</span><input v-model.number="d.default_timeout_ms" type="number" min="500" step="500" class="field" /></label>
				<label><span class="label">Width</span><input v-model.number="d.viewport_width" type="number" min="320" class="field" /></label>
				<label><span class="label">Height</span><input v-model.number="d.viewport_height" type="number" min="320" class="field" /></label>
			</div>
			<div class="flex flex-wrap gap-x-6 gap-y-2 text-sm">
				<label class="flex items-center gap-2"><input v-model="d.record_trace" type="checkbox" :true-value="1" :false-value="0" class="accent-[rgb(var(--brand))]" />Save a Playwright trace for every run</label>
				<label class="flex items-center gap-2"><input v-model="d.record_video" type="checkbox" :true-value="1" :false-value="0" class="accent-[rgb(var(--brand))]" />Record a video of every run</label>
				<label v-if="d.record_video" class="flex items-start gap-2"><input v-model="d.presentation_mode" type="checkbox" :true-value="1" :false-value="0" class="mt-1 accent-[rgb(var(--brand))]" /><span>Presentation mode<span class="block text-xs text-muted">Slower actions, a caption naming the test and step, and the element outlined, so the video can be followed.</span></span></label>
				<label class="flex items-center gap-2"><input v-model="d.screenshot_each_step" type="checkbox" :true-value="1" :false-value="0" class="accent-[rgb(var(--brand))]" />Screenshot after every step</label>
				<label class="flex items-center gap-2"><input v-model="d.keep_going" type="checkbox" :true-value="1" :false-value="0" class="accent-[rgb(var(--brand))]" />Keep going after a failure (run every step)</label>
				<label class="flex items-start gap-2"><input v-model="d.read_only" type="checkbox" :true-value="1" :false-value="0" class="mt-1 accent-[rgb(var(--brand))]" /><span>Read-only: block saves, submits, deletes and other writes from the browser<span class="block text-xs text-muted">For running against a live site. Blocked calls are listed on the step.</span></span></label>
			</div>
			<div class="grid gap-4 sm:grid-cols-[1fr_1fr_1fr_2fr]">
				<label><span class="label">Run automatically</span>
					<select v-model="d.schedule" class="field"><option value="">Never</option><option>Hourly</option><option>Daily</option><option>Weekly</option></select></label>
				<label v-if="d.schedule === 'Daily' || d.schedule === 'Weekly'"><span class="label">At hour (0–23)</span><input v-model.number="d.schedule_hour" type="number" min="0" max="23" class="field" /></label>
				<label v-if="d.schedule === 'Weekly'"><span class="label">On</span>
					<select v-model="d.schedule_weekday" class="field"><option v-for="w in ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']" :key="w">{{ w }}</option></select></label>
				<label class="sm:col-start-4"><span class="label">Tell these users when a run fails</span>
					<textarea v-model="d.notify_users" rows="2" class="field field-mono py-1.5" placeholder="one email per line" /></label>
			</div>
			<p v-if="d.schedule" class="-mt-3 text-xs text-muted">Scheduled runs need the site's scheduler (bench --site … enable-scheduler).<template v-if="d.last_scheduled_at"> Last scheduled run: {{ d.last_scheduled_at }}.</template></p>
			<div>
				<div class="mb-2 flex items-center justify-between">
					<div><h3 class="text-sm font-semibold">Variables</h3><p class="text-xs text-muted">Use as <code v-pre class="font-mono">{{name}}</code> in any step. Secrets are encrypted and hidden in reports.</p></div>
					<button type="button" class="btn-ghost h-7" @click="d.variables.push({ key: '', value: '' })"><Plus class="h-3.5 w-3.5" />Add</button>
				</div>
				<div class="overflow-hidden rounded-md border border-line">
					<div v-for="(v, i) in d.variables" :key="i" class="grid grid-cols-[1fr_1.4fr_1.2fr_32px] items-center gap-2 border-b border-line px-2 py-1.5 last:border-0">
						<input v-model="v.key" class="field-mono" placeholder="name" aria-label="Variable name" />
						<input v-model="v.value" class="field-mono" placeholder="value" aria-label="Value" />
						<label class="relative"><Lock class="pointer-events-none absolute left-2 top-2 h-4 w-4 text-faint" />
							<input v-model="v.secret_value" type="password" autocomplete="new-password" class="field-mono pl-7" placeholder="or secret value" aria-label="Secret value" /></label>
						<button type="button" class="icon-btn h-7 w-7 hover:text-fail" aria-label="Remove variable" @click="d.variables.splice(i, 1)"><Trash2 class="h-3.5 w-3.5" /></button>
					</div>
					<p v-if="!d.variables.length" class="px-3 py-3 text-sm text-faint">No variables yet.</p>
				</div>
			</div>
		</form>
		<template #footer>
			<button class="btn-ghost" @click="emit('close')">Cancel</button>
			<button class="btn-primary" form="suite-form" type="submit" :disabled="!valid || saving">{{ isNew ? 'Create suite' : 'Save suite' }}</button>
		</template>
	</Modal>
</template>
