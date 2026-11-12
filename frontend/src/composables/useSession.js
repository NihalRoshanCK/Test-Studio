import { reactive } from "vue";
import { api } from "../api";
import { toast, toastError } from "../toast";

// Live remote browser (recorder / picker). Polls frames + state; emits recorded steps via callbacks.
export function useSession({ onSteps, onFillUpdate, onPick, onSelect }) {
	const s = reactive({ id: null, starting: false, frame: null, seq: 0, state: {}, mode: "interact", recording: false, consumed: null, pickSeq: 0, selectSeq: 0, notice: null, error: null });
	let timer = null;

	async function start(suite, { recording = false, existingSteps = 0 } = {}) {
		if (s.id) return;
		s.starting = true;
		s.error = null;
		try {
			s.id = await api.startSession(suite);
			Object.assign(s, { seq: 0, frame: null, state: {}, mode: "interact", recording, consumed: null, existing: existingSteps, pickSeq: 0, selectSeq: 0 });
			if (!recording) await cmd({ type: "record", value: false });
			poll();
		} catch (e) {
			toastError(e);
		} finally {
			s.starting = false;
		}
	}

	function stop() {
		if (!s.id) return;
		const id = s.id;
		s.id = null;
		clearTimeout(timer);
		s.frame = null;
		s.recording = false;
		api.sessionCmd(id, { type: "stop" }).catch(() => {});
	}

	function cmd(c) {
		if (!s.id) return Promise.resolve();
		return api.sessionCmd(s.id, c).catch(toastError);
	}

	async function poll() {
		const id = s.id;
		if (!id) return;
		try {
			const { state, frame } = await api.sessionPoll(id, s.seq);
			if (s.id !== id) return;
			if (frame) { s.seq = frame.seq; s.frame = frame.img; }
			apply(state);
			if (state.status === "closed") { stop(); toast("The live browser closed after 10 idle minutes.", "info"); return; }
		} catch (e) {
			if (s.id !== id) return;
			s.error = e.message;
			s.id = null;
			return;
		}
		timer = setTimeout(poll, 280);
	}

	function apply(st) {
		s.state = st;
		if (st.status !== "ready") return;
		const rec = st.steps || [];
		// the initial goto only belongs in a test that is still empty
		if (s.consumed === null) s.consumed = s.existing ? rec.length : 0;
		const last = rec[s.consumed - 1];
		if (last && last.action === "fill") onFillUpdate?.(last.value);
		const fresh = rec.slice(s.consumed);
		s.consumed = rec.length;
		if (fresh.length) onSteps?.(fresh);
		if (st.picked && st.picked.seq > s.pickSeq) { s.pickSeq = st.picked.seq; onPick?.(st.picked); }
		if (st.select_prompt && st.select_prompt.seq > s.selectSeq) { s.selectSeq = st.select_prompt.seq; onSelect?.(st.select_prompt); }
		if (st.notice && st.notice !== s.notice) { s.notice = st.notice; toast(st.notice, "info", 8000); }
	}

	const setMode = (mode) => { s.mode = mode; return cmd({ type: "mode", value: mode }); };
	const setRecording = (on) => { s.recording = on; return cmd({ type: "record", value: on }); };

	return { s, start, stop, cmd, setMode, setRecording };
}
