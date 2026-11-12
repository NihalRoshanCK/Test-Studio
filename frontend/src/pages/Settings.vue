<script setup>
import { onMounted, ref } from "vue";
import { Save, Trash2, CircleCheck, CircleAlert } from "lucide-vue-next";
import { api } from "../api";
import { toast, toastError } from "../toast";

const s = ref(null);
const saving = ref(false);
const pruning = ref(false);

async function load() {
	try { s.value = await api.getSettings(); } catch (e) { toastError(e); }
}
async function save() {
	saving.value = true;
	try {
		const { mcp_status, run_count, ...doc } = s.value;
		await api.save({ ...doc, doctype: "Test Studio Settings", name: "Test Studio Settings" });
		toast("Settings saved", "success");
		await load();
	} catch (e) { toastError(e); } finally { saving.value = false; }
}
async function prune() {
	pruning.value = true;
	try {
		const n = await api.pruneNow();
		toast(n ? `Deleted ${n} old run${n > 1 ? "s" : ""} and their files` : "Nothing to clean up", "success");
		await load();
	} catch (e) { toastError(e); } finally { pruning.value = false; }
}
onMounted(load);
</script>

<template>
	<div class="h-full overflow-y-auto">
		<div class="max-w-3xl px-8 py-7 max-sm:px-4">
			<h1 class="page-title">Settings</h1>
			<p class="page-sub">For all of Test Studio. Each suite has its own settings too (browser, video, schedule, logins): open a suite's Suite settings.</p>

			<form v-if="s" class="mt-6 space-y-6" @submit.prevent="save">
				<section class="table-card">
					<div class="table-head px-4 py-2.5">Keeping old runs</div>
					<div class="grid gap-4 p-4 sm:grid-cols-2">
						<label><span class="label">Keep the last runs of each test</span>
							<input v-model.number="s.keep_runs_per_test" type="number" min="0" class="field" />
							<span class="mt-1 block text-xs text-muted">0 keeps all.</span></label>
						<label><span class="label">Delete runs older than (days)</span>
							<input v-model.number="s.delete_runs_after_days" type="number" min="0" class="field" />
							<span class="mt-1 block text-xs text-muted">0: never by age.</span></label>
					</div>
					<div class="flex flex-wrap items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm sm:flex-nowrap">
						<span class="min-w-0 text-muted">{{ s.run_count ?? '–' }} runs kept now. Old runs go every night, with their screenshots, traces and videos.</span>
						<button type="button" class="btn-outline h-8" :disabled="pruning" @click="prune"><Trash2 class="h-4 w-4" />Clean up now</button>
					</div>
				</section>

				<section class="table-card">
					<div class="table-head px-4 py-2.5">New suites start with</div>
					<div class="grid gap-4 p-4 sm:grid-cols-2">
						<label><span class="label">Step timeout (ms)</span><input v-model.number="s.new_suite_timeout_ms" type="number" min="500" step="500" class="field" /></label>
						<div class="space-y-2 text-sm sm:pt-6">
							<label class="flex items-center gap-2"><input v-model="s.new_suite_record_trace" type="checkbox" :true-value="1" :false-value="0" class="accent-[rgb(var(--brand))]" />Save a Playwright trace</label>
							<label class="flex items-center gap-2"><input v-model="s.new_suite_record_video" type="checkbox" :true-value="1" :false-value="0" class="accent-[rgb(var(--brand))]" />Record a video</label>
							<label class="flex items-center gap-2"><input v-model="s.new_suite_screenshot_each_step" type="checkbox" :true-value="1" :false-value="0" class="accent-[rgb(var(--brand))]" />Screenshot after every step</label>
						</div>
					</div>
				</section>

				<section class="table-card">
					<div class="table-head px-4 py-2.5">MCP server</div>
					<div class="grid gap-4 p-4 sm:grid-cols-[2fr_1fr] sm:items-end">
						<label><span class="label">HTTP address</span><input v-model="s.mcp_url" class="field-mono" placeholder="http://127.0.0.1:8765/mcp" /></label>
						<p class="flex items-center gap-1.5 pb-2 text-sm" :class="s.mcp_status === 'running' ? 'text-pass' : 'text-warn'">
							<component :is="s.mcp_status === 'running' ? CircleCheck : CircleAlert" class="h-4 w-4" />{{ s.mcp_status || 'unknown' }}</p>
					</div>
					<p class="border-t border-line px-4 py-3 text-xs text-muted">AI agents (Claude Code, QCS Flow…) use Test Studio through it. Its API key and token are on the server, in ~/.config/test-studio/mcp.env.</p>
				</section>

				<div class="flex justify-end"><button class="btn-primary" type="submit" :disabled="saving"><Save class="h-4 w-4" />Save settings</button></div>
			</form>
		</div>
	</div>
</template>
