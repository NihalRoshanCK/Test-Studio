<script setup>
import { computed, ref } from "vue";
import { ArrowLeft, ArrowRight, RotateCw, X, Maximize2, Minimize2, MousePointerClick, Crosshair, Eye, Type, Play, StepForward, Square, Globe } from "lucide-vue-next";
import RunRibbon from "./RunRibbon.vue";

const props = defineProps({ session: Object, run: Object, total: Number, wide: Boolean, hasTest: Boolean, selected: String });
const emit = defineEmits(["start", "stop", "cmd", "mode", "debug", "wide", "select-step"]);

const live = computed(() => !!props.session.id);
const showRun = computed(() => !live.value && !!props.run.name);
const frame = computed(() => (live.value ? props.session.frame : showRun.value ? props.run.frame : null));
const url = computed(() => (live.value ? props.session.state.url : props.run.frameUrl) || "");
const typedUrl = ref("");
const editingUrl = ref(false);
const modes = [
	{ k: "interact", label: "Use page", icon: MousePointerClick, tip: "Click and type on the page. Actions are recorded when recording is on." },
	{ k: "pick", label: "Pick", icon: Crosshair, tip: "Click an element to use its selector" },
	{ k: "assert_visible", label: "Check visible", icon: Eye, tip: "Click an element to add a visibility check" },
	{ k: "assert_text", label: "Check text", icon: Type, tip: "Click an element to add a text check" },
];

const img = ref(null);
const vp = ref(null);
const ripple = ref(null);
function point(e) {
	const r = img.value.getBoundingClientRect();
	return { x: ((e.clientX - r.left) / r.width) * img.value.naturalWidth, y: ((e.clientY - r.top) / r.height) * img.value.naturalHeight };
}
function onClick(e) {
	if (!live.value || !img.value?.naturalWidth) return;
	vp.value.focus();
	emit("cmd", { type: "click", ...point(e) });
	const r = vp.value.getBoundingClientRect();
	const k = Date.now();
	ripple.value = { x: e.clientX - r.left + vp.value.scrollLeft, y: e.clientY - r.top + vp.value.scrollTop, k };
	setTimeout(() => ripple.value?.k === k && (ripple.value = null), 500);
}
let buf = "", typeT = null, dy = 0, wheelT = null;
const flush = () => { clearTimeout(typeT); if (buf) emit("cmd", { type: "type", text: buf }); buf = ""; };
const SPECIAL = ["Enter", "Tab", "Backspace", "Delete", "Escape", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown"];
function onKey(e) {
	if (!live.value || e.ctrlKey || e.metaKey || e.altKey) return;
	if (e.key.length === 1) { buf += e.key; clearTimeout(typeT); typeT = setTimeout(flush, 140); }
	else if (SPECIAL.includes(e.key)) { flush(); emit("cmd", { type: "press", key: e.key }); }
	else return;
	e.preventDefault();
}
function onWheel(e) {
	if (!live.value) return;
	e.preventDefault();
	dy += e.deltaY;
	wheelT = wheelT || setTimeout(() => { emit("cmd", { type: "scroll", dy }); dy = 0; wheelT = null; }, 110);
}
function onPaste(e) {
	if (!live.value) return;
	e.preventDefault();
	flush();
	emit("cmd", { type: "type", text: e.clipboardData.getData("text") });
}
function go() { editingUrl.value = false; if (typedUrl.value) emit("cmd", { type: "goto", url: typedUrl.value }); }
const st = computed(() => props.session.state || {});
</script>

<template>
	<section class="flex h-full min-h-0 flex-col bg-sunk/60" aria-label="Live browser">
		<!-- address bar -->
		<div class="flex h-12 shrink-0 items-center gap-1 border-b border-line bg-panel px-2">
			<button class="icon-btn" :disabled="!live" aria-label="Back" @click="emit('cmd', { type: 'back' })"><ArrowLeft class="h-4 w-4" /></button>
			<button class="icon-btn" :disabled="!live" aria-label="Forward" @click="emit('cmd', { type: 'forward' })"><ArrowRight class="h-4 w-4" /></button>
			<button class="icon-btn" :disabled="!live" aria-label="Reload" @click="emit('cmd', { type: 'reload' })"><RotateCw class="h-4 w-4" /></button>
			<form class="relative min-w-0 flex-1" @submit.prevent="go">
				<Globe class="pointer-events-none absolute left-2.5 top-2 h-4 w-4 text-faint" />
				<input class="field h-8 rounded-full bg-sunk pl-8 font-mono text-xs" :disabled="!live" aria-label="Address"
					:value="editingUrl ? typedUrl : url" placeholder="Start the browser to browse"
					@focus="editingUrl = true; typedUrl = url" @blur="editingUrl = false" @input="typedUrl = $event.target.value" />
			</form>
			<button class="icon-btn" :aria-label="wide ? 'Narrow browser' : 'Widen browser'" :title="wide ? 'Narrow browser' : 'Widen browser'" @click="emit('wide')">
				<Minimize2 v-if="wide" class="h-4 w-4" /><Maximize2 v-else class="h-4 w-4" />
			</button>
			<button v-if="live" class="icon-btn" aria-label="Close browser" title="Close browser" @click="emit('stop')"><X class="h-4 w-4" /></button>
		</div>

		<!-- mode bar / debugger bar -->
		<div v-if="run.pausedAt && !live" class="flex h-11 shrink-0 items-center gap-2 border-b border-run/30 bg-run/10 px-3">
			<span class="h-2 w-2 animate-pulse rounded-full bg-run" />
			<span class="flex-1 text-sm font-medium">Paused before step {{ run.pausedAt }}</span>
			<button class="btn-primary h-7 bg-run hover:bg-run/90" @click="emit('debug', 'continue')"><Play class="h-3.5 w-3.5" />Continue <span class="kbd ml-1 border-white/30 bg-white/10 text-white">F8</span></button>
			<button class="btn-outline h-7" @click="emit('debug', 'step')"><StepForward class="h-3.5 w-3.5" />Step <span class="kbd ml-1">F10</span></button>
			<button class="btn-ghost h-7" @click="emit('debug', 'stop')"><Square class="h-3.5 w-3.5" />Stop</button>
		</div>
		<div v-else-if="live" class="flex h-11 shrink-0 items-center gap-1 border-b border-line bg-panel px-2" role="radiogroup" aria-label="What a click does">
			<button v-for="m in modes" :key="m.k" role="radio" :aria-checked="session.mode === m.k" :title="m.tip"
				class="btn h-7 px-2.5 text-xs" :class="session.mode === m.k ? 'bg-ink text-paper' : 'text-muted hover:bg-sunk hover:text-ink'"
				@click="emit('mode', m.k)"><component :is="m.icon" class="h-3.5 w-3.5" />{{ m.label }}</button>
			<span class="ml-auto flex items-center gap-1.5 pr-1 text-xs" :class="session.recording ? 'text-rec' : 'text-faint'">
				<span class="h-2 w-2 rounded-full" :class="session.recording ? 'animate-pulse bg-rec' : 'bg-line'" />{{ session.recording ? 'Recording' : 'Not recording' }}
			</span>
		</div>

		<!-- viewport -->
		<div ref="vp" class="relative min-h-0 flex-1 overflow-auto p-4 outline-none" tabindex="0"
			:aria-label="live ? 'Live page. Click to interact; type to send keys.' : 'Browser preview'"
			@keydown="onKey" @wheel="onWheel" @paste="onPaste">
			<div v-if="frame" class="relative mx-auto w-fit max-w-full">
				<img ref="img" :src="'data:image/jpeg;base64,' + frame" alt="" draggable="false"
					class="block h-auto max-w-full select-none rounded-md bg-white shadow-pop ring-1 ring-line"
					:class="live && 'cursor-crosshair'" @click="onClick" />
				<span v-if="showRun && !run.pausedAt && !['Passed','Known Issue','Failed','Error'].includes(run.status)" class="absolute left-3 top-3 flex items-center gap-1.5 rounded-full bg-ink/80 px-2.5 py-1 text-2xs font-medium text-paper backdrop-blur">
					<span class="h-1.5 w-1.5 animate-pulse rounded-full bg-run" />Running
				</span>
			</div>
			<span v-if="ripple" :key="ripple.k" class="pointer-events-none absolute h-6 w-6 -translate-x-1/2 -translate-y-1/2 animate-[ping_.5s_ease-out_1] rounded-full border-2 border-rec" :style="{ left: ripple.x + 'px', top: ripple.y + 'px' }" />
			<div v-if="!frame" class="grid h-full place-items-center">
				<div class="max-w-xs text-center">
					<div v-if="session.starting || (showRun && !run.frame)" class="mx-auto mb-3 h-6 w-6 animate-spin rounded-full border-2 border-brand/25 border-t-brand" />
					<template v-if="session.starting"><p class="font-medium">Opening a browser…</p></template>
					<template v-else-if="showRun && !run.frame"><p class="font-medium">Starting the run…</p><p class="mt-1 text-sm text-muted">The page appears here as soon as the browser loads it.</p></template>
					<template v-else>
						<svg viewBox="0 0 120 80" class="mx-auto mb-4 w-28 text-line" aria-hidden="true"><rect x="2" y="2" width="116" height="76" rx="8" fill="none" stroke="currentColor" stroke-width="3"/><path d="M2 18h116" stroke="currentColor" stroke-width="3"/><circle cx="12" cy="10" r="2.5" fill="currentColor"/><circle cx="21" cy="10" r="2.5" fill="currentColor"/><path d="M22 52h14l6-16 8 24 6-12h14" fill="none" class="stroke-brand" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>
						<p class="font-medium">Live browser</p>
						<p class="mt-1 text-sm text-muted">Open the site to explore it, pick elements, or check a selector. Runs play here too.</p>
						<button class="btn-outline mt-4" :disabled="!hasTest" @click="emit('start')">Open browser</button>
					</template>
				</div>
			</div>
		</div>

		<!-- status line -->
		<div v-if="live" class="shrink-0 border-t border-line bg-panel px-3 py-2 text-xs" aria-live="polite">
			<p v-if="st.error" class="text-fail">{{ st.error }}</p>
			<slot v-else name="status" />
		</div>
		<RunRibbon v-if="showRun" :results="run.steps" :total="total" :paused-at="run.pausedAt" :selected="selected" :report="['Passed', 'Failed', 'Error'].includes(run.status) ? run.name : null" @select="emit('select-step', $event)" />
	</section>
</template>
