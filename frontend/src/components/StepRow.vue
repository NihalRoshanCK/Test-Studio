<script setup>
import { GripVertical, Copy, Trash2, ChevronRight, CircleAlert, Plus, LogIn, LogOut, FilePlus2, PenLine, Save, GitBranch, BadgeCheck, CopyPlus, Puzzle, Bookmark, Globe, MousePointerClick, Keyboard, CircleCheck, Clock, Camera } from "lucide-vue-next";
const ICONS = { login: LogIn, logout: LogOut, new_doc: FilePlus2, set_field: PenLine, save: Save, workflow: GitBranch, expect_status: BadgeCheck,
	create_from: CopyPlus, run_snippet: Puzzle, store_url: Bookmark, store_text: Bookmark, goto: Globe, click: MousePointerClick, dblclick: MousePointerClick,
	hover: MousePointerClick, fill: Keyboard, type: Keyboard, press: Keyboard, select: PenLine, check: CircleCheck, uncheck: CircleCheck, upload: FilePlus2,
	wait: Clock, wait_for: Clock, screenshot: Camera };
const iconFor = (a) => ICONS[a] || (a?.startsWith("assert") ? CircleCheck : PenLine);
import Sentence from "./Sentence.vue";
import { ms } from "../format";

defineProps({ step: Object, index: Number, selected: Boolean, breakpoint: Boolean, result: Object, running: Boolean, paused: Boolean, expanded: Boolean });
const emit = defineEmits(["select", "toggle-bp", "duplicate", "remove", "dragstart", "drop", "toggle-expand", "insert-before"]);
</script>

<template>
	<li class="group relative" @dragover.prevent @drop.prevent="emit('drop')">
		<!-- insert between steps -->
		<button class="absolute -top-3 left-12 z-10 hidden h-5 items-center gap-1 rounded-full bg-panel px-1.5 text-2xs text-muted shadow-sm ring-1 ring-line hover:text-brand hover:ring-brand group-hover:flex"
			:aria-label="`Add a step before step ${index + 1}`" @click.stop="emit('insert-before')"><Plus class="h-3 w-3" />add</button>
		<div class="flex min-h-[52px] cursor-pointer items-start gap-3 rounded-lg px-3 py-3 transition-colors"
			:class="[
				selected ? 'bg-brand/[0.08] ring-1 ring-inset ring-brand/30' : step.action === 'run_snippet' ? 'bg-brand/[0.035] hover:bg-brand/[0.06]' : 'hover:bg-sunk/70',
				result?.status === 'Failed' && !selected && 'bg-fail/[0.06]',
				result?.status === 'Known Issue' && !selected && 'bg-warn/[0.07]',
				(running || paused) && 'bg-run/[0.08]',
				result?.status === 'Skipped' && 'opacity-50',
			]"
			@click="emit('select')">
			<span class="mt-1 -ml-1 cursor-grab text-faint opacity-0 group-hover:opacity-100" draggable="true" title="Drag to reorder" @dragstart="emit('dragstart', $event)" @click.stop><GripVertical class="h-4 w-4" /></span>
			<button class="mt-0.5 h-6 min-w-[30px] shrink-0 rounded-full px-1.5 text-xs tabular-nums transition-colors"
				:class="paused ? 'bg-run text-white' : breakpoint ? 'bg-rec text-white' : result?.status === 'Passed' ? 'text-pass hover:bg-sunk' : result?.status === 'Failed' ? 'font-semibold text-fail hover:bg-sunk' : result?.status === 'Known Issue' ? 'font-semibold text-warn hover:bg-sunk' : 'text-faint hover:bg-sunk hover:text-ink'"
				:title="breakpoint ? 'Remove breakpoint' : 'Pause here when debugging'" :aria-pressed="breakpoint" @click.stop="emit('toggle-bp')">{{ index + 1 }}</button>
			<button v-if="step.action === 'run_snippet'" class="mt-1 shrink-0 text-faint hover:text-ink" :aria-label="expanded ? 'Hide snippet steps' : 'Show snippet steps'" @click.stop="emit('toggle-expand')">
				<ChevronRight class="h-4 w-4 transition-transform" :class="expanded && 'rotate-90'" />
			</button>
			<span class="grid h-7 w-7 shrink-0 place-items-center rounded-lg" :class="step.action === 'run_snippet' ? 'bg-brand/15 text-brand' : step.action?.startsWith('assert') || step.action === 'expect_status' ? 'bg-pass/10 text-pass' : 'bg-sunk text-muted'" aria-hidden="true">
				<component :is="iconFor(step.action)" class="h-4 w-4" />
			</span>
			<div class="min-w-0 flex-1 pt-0.5 text-[14px] leading-6">
				<button class="block w-full text-left outline-offset-4" :aria-pressed="selected" @click.stop="emit('select')"><Sentence :step="step" /></button>
				<p v-if="step.note" class="mt-0.5 truncate text-xs text-muted">{{ step.note }}</p>
				<p v-if="result?.error" class="mt-2 flex gap-1.5 whitespace-pre-wrap rounded-md bg-panel px-2.5 py-2 text-xs" :class="result.status === 'Failed' ? 'text-fail ring-1 ring-fail/20' : 'text-warn ring-1 ring-warn/30'"><CircleAlert class="mt-px h-3.5 w-3.5 shrink-0" />{{ result.error }}</p>
			</div>
			<span v-if="running" class="mt-1 h-3.5 w-3.5 animate-spin rounded-full border-2 border-run/30 border-t-run" aria-label="Running" />
			<span v-else-if="result" class="mt-1 shrink-0 text-xs tabular-nums" :class="result.status === 'Failed' ? 'text-fail' : result.status === 'Known Issue' ? 'text-warn' : 'text-faint'">{{ result.status === 'Skipped' ? 'skipped' : ms(result.duration_ms) }}</span>
			<span class="flex shrink-0 opacity-0 group-hover:opacity-100 focus-within:opacity-100">
				<button class="icon-btn h-7 w-7" title="Duplicate" aria-label="Duplicate step" @click.stop="emit('duplicate')"><Copy class="h-3.5 w-3.5" /></button>
				<button class="icon-btn h-7 w-7 hover:text-fail" title="Delete" aria-label="Delete step" @click.stop="emit('remove')"><Trash2 class="h-3.5 w-3.5" /></button>
			</span>
		</div>
		<slot />
	</li>
</template>
