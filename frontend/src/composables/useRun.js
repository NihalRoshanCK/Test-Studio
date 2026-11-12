import { reactive } from "vue";
import { api } from "../api";
import { DONE } from "../format";
import { toast, toastError } from "../toast";

// Polls a test run for status, step results, live frames and debugger pauses.
export function useRun(onDone) {
	const r = reactive({ name: null, caseName: null, status: null, steps: [], frame: null, frameUrl: "", seq: 0, pausedAt: null, error: null, trace: null, duration: null, debug: false });
	let timer = null;

	async function start(caseName, { debug = false, breakpoints = [] } = {}) {
		clear();
		try {
			const name = await api.runCase(caseName, debug, breakpoints);
			Object.assign(r, { name, caseName, status: "Queued", debug });
			poll();
		} catch (e) {
			toastError(e);
		}
	}

	// follow a run that was started some other way (e.g. a snippet run)
	function follow(name, caseName) {
		clear();
		Object.assign(r, { name, caseName, status: "Queued", debug: false });
		poll();
	}

	async function poll() {
		const name = r.name;
		if (!name) return;
		try {
			const m = await api.runPoll(name, r.seq);
			if (r.name !== name) return;
			Object.assign(r, { status: m.status, steps: m.steps, pausedAt: m.paused_at, error: m.error, trace: m.trace, duration: m.duration_ms });
			if (m.frame) { r.seq = m.frame.seq; r.frame = m.frame.img; r.frameUrl = m.frame.url; }
			if (DONE.includes(m.status)) {
				r.pausedAt = null;
				toast(`${name} ${m.status.toLowerCase()}`, m.status === "Passed" ? "success" : "error");
				onDone?.(r);
				return;
			}
		} catch (e) {
			if (r.name !== name) return;
		}
		timer = setTimeout(poll, 450);
	}

	function debug(command) {
		if (!r.name) return;
		r.pausedAt = null;
		api.debug(r.name, command).catch(toastError);
	}

	function clear() {
		clearTimeout(timer);
		Object.assign(r, { name: null, caseName: null, status: null, steps: [], frame: null, frameUrl: "", seq: 0, pausedAt: null, error: null, trace: null, duration: null });
	}

	return { r, start, follow, debug, clear };
}
