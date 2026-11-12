export const ms = (v) => (v == null ? "—" : v >= 60000 ? `${(v / 60000).toFixed(1)}m` : v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`);

export function ago(ts) {
	if (!ts) return "";
	const d = (Date.now() - new Date(ts.replace(" ", "T")).getTime()) / 1000;
	if (d < 60) return "just now";
	if (d < 3600) return `${Math.floor(d / 60)}m ago`;
	if (d < 86400) return `${Math.floor(d / 3600)}h ago`;
	return `${Math.floor(d / 86400)}d ago`;
}

export const DONE = ["Passed", "Known Issue", "Failed", "Error"];
export const statusTone = (s) => ({ Passed: "pass", "Known Issue": "warn", Failed: "fail", Error: "warn", Running: "run", Queued: "faint", Skipped: "faint", Pending: "faint" })[s] || "faint";

export const store = {
	get(k, d) { try { return JSON.parse(localStorage.getItem("ts:" + k)) ?? d; } catch (e) { return d; } },
	set(k, v) { try { localStorage.setItem("ts:" + k, JSON.stringify(v)); } catch (e) { /* storage blocked */ } },
};
