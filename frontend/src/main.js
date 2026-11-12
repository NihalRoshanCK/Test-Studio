import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import "./style.css";
import App from "./App.vue";

const router = createRouter({
	history: createWebHistory("/studio"),
	routes: [
		{ path: "/", name: "tests", component: () => import("./pages/TestList.vue") },
		{ path: "/snippets", name: "snippets", component: () => import("./pages/TestList.vue") },
		{ path: "/test/:name", name: "test", component: () => import("./pages/Workspace.vue"), meta: { fullscreen: true } },
		{ path: "/snippet/:name", name: "snippet", component: () => import("./pages/Workspace.vue"), meta: { fullscreen: true } },
		{ path: "/runs", name: "runs", component: () => import("./pages/Runs.vue") },
		{ path: "/runs/:name", name: "run", component: () => import("./pages/RunReport.vue") },
		{ path: "/checks", name: "checks", component: () => import("./pages/Checks.vue") },
		{ path: "/settings", name: "settings", component: () => import("./pages/Settings.vue") },
		{ path: "/pipelines", name: "pipelines", component: () => import("./pages/Pipelines.vue") },
		{ path: "/pipelines/runs/:name", name: "pipeline-run", component: () => import("./pages/PipelineRun.vue") },
		{ path: "/:rest(.*)*", redirect: "/" },
	],
});

createApp(App).use(router).mount("#app");
