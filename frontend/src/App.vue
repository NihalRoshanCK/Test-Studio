<script setup>
import { ref } from "vue";
import { useRoute } from "vue-router";
import { Moon, Sun, ChevronDown, LayoutGrid, ExternalLink, Activity, FlaskConical, Puzzle, Workflow, Menu, ShieldCheck, Settings2 } from "lucide-vue-next";
import Toasts from "./components/Toasts.vue";

const route = useRoute();
const boot = window.studio_boot || {};
const dark = ref(document.documentElement.classList.contains("dark"));
const showMenu = ref(false);
const navOpen = ref(false);
function toggleTheme() {
	dark.value = !dark.value;
	document.documentElement.classList.toggle("dark", dark.value);
	try { localStorage.setItem("ts-theme", dark.value ? "dark" : "light"); } catch (e) { /* not remembered; still applies */ }
}
// grouped by what you come to do, like QCS Flow: watch results, build tests
const groups = [
	{ title: "Monitor", items: [
		{ to: "/runs", label: "Runs", icon: Activity, match: ["runs", "run"] },
		{ to: "/checks", label: "Data checks", icon: ShieldCheck, match: ["checks"] },
	] },
	{ title: "Build", items: [
		{ to: "/", label: "Tests", icon: FlaskConical, match: ["tests", "test"] },
		{ to: "/snippets", label: "Snippets", icon: Puzzle, match: ["snippets", "snippet"] },
		{ to: "/pipelines", label: "Pipelines", icon: Workflow, match: ["pipelines", "pipeline-run"] },
	] },
	{ title: "Admin", items: [{ to: "/settings", label: "Settings", icon: Settings2, match: ["settings"] }] },
];
const initials = (boot.full_name || boot.user || "?").split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase();
</script>

<template>
	<div class="h-full">
	<div v-if="route.meta.fullscreen" class="h-full"><router-view /></div>
	<div v-else class="flex h-full">
		<button v-if="!navOpen" class="fixed left-3 top-3 z-30 rounded-md border border-line bg-panel p-2 shadow-sm md:hidden" aria-label="Open menu" @click="navOpen = true"><Menu class="h-4 w-4" /></button>
		<div v-if="navOpen" class="fixed inset-0 z-20 bg-black/30 md:hidden" aria-hidden="true" @click="navOpen = false" />
		<aside class="z-20 w-56 shrink-0 flex-col border-r border-line bg-menu p-3 md:static md:flex" :class="navOpen ? 'fixed inset-y-0 left-0 flex' : 'hidden'">
			<div class="relative">
				<button class="flex w-full items-center gap-2 rounded-md px-2 py-2 text-sm font-semibold hover:bg-sunk" :aria-expanded="showMenu" @click="showMenu = !showMenu">
					<svg viewBox="0 0 32 32" class="h-7 w-7 shrink-0" aria-hidden="true"><rect width="32" height="32" rx="8" class="fill-brand" /><path d="M7 19h4l3-8 4 12 3-6h4" fill="none" stroke="white" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
					<span class="truncate">Test Studio</span>
					<ChevronDown class="ml-auto h-4 w-4 text-faint" />
				</button>
				<div v-if="showMenu" class="fixed inset-0 z-40" @click="showMenu = false" />
				<div v-if="showMenu" class="absolute left-0 right-0 top-12 z-50 rounded-lg border border-line bg-panel p-1 shadow-xl">
					<a href="/apps" class="flex h-8 items-center gap-2 rounded px-2 text-sm hover:bg-sunk"><LayoutGrid class="h-4 w-4" />Apps</a>
					<a href="/desk/test-case" class="flex h-8 items-center gap-2 rounded px-2 text-sm hover:bg-sunk"><ExternalLink class="h-4 w-4" />Open in desk</a>
				</div>
			</div>
			<nav class="mt-4 flex flex-col gap-4" aria-label="Main">
				<div v-for="g in groups" :key="g.title">
					<div class="mb-1 px-2 text-xs font-medium text-faint">{{ g.title }}</div>
					<div class="flex flex-col gap-0.5">
						<router-link v-for="i in g.items" :key="i.to" :to="i.to" class="nav-item" :class="i.match.includes(route.name) && 'nav-item-active'"
							:aria-current="i.match.includes(route.name) ? 'page' : undefined" @click="navOpen = false">
							<component :is="i.icon" class="h-4 w-4 shrink-0" /><span class="truncate">{{ i.label }}</span>
						</router-link>
					</div>
				</div>
			</nav>
			<div class="mt-auto flex items-center gap-2 border-t border-line pt-3">
				<span class="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-sunk text-xs font-semibold text-muted">{{ initials }}</span>
				<div class="min-w-0 flex-1">
					<div class="truncate text-sm font-medium">{{ boot.full_name }}</div>
					<div class="truncate text-xs text-faint">{{ boot.user }}</div>
				</div>
				<button class="icon-btn" :aria-label="dark ? 'Light mode' : 'Dark mode'" :title="dark ? 'Light mode' : 'Dark mode'" @click="toggleTheme"><Sun v-if="dark" class="h-4 w-4" /><Moon v-else class="h-4 w-4" /></button>
			</div>
		</aside>
		<main class="min-w-0 flex-1 overflow-y-auto max-md:pt-12"><router-view /></main>
	</div>
	<Toasts />
	</div>
</template>
