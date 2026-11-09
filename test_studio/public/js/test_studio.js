frappe.provide("test_studio");

const esc = (s) => frappe.utils.escape_html(s == null ? "" : String(s));
const fmt_ms = (ms) => (ms >= 1000 ? (ms / 1000).toFixed(1) + "s" : (ms || 0) + "ms");

// Start a run via API and jump to the result (single run) or the list (many runs).
test_studio.run = (method, name, extra = {}) => {
	frappe.call({
		method,
		args: { name, ...extra },
		freeze: true,
		freeze_message: __("Queuing…"),
		callback: ({ message }) => {
			if (Array.isArray(message)) {
				frappe.show_alert({ message: __("{0} test runs queued", [message.length]), indicator: "blue" });
				frappe.set_route("List", "Test Run", { name: ["in", message] });
			} else if (method.endsWith("run_pipeline")) {
				frappe.set_route("Form", "Test Pipeline Run", message);
			} else {
				frappe.set_route("Form", "Test Run", message);
			}
		},
	});
};

// Fallback when socketio realtime is unavailable: re-fetch while a run is in progress.
test_studio.poll_while_running = (frm) => {
	clearTimeout(frm.__ts_poll);
	if (!["Queued", "Running"].includes(frm.doc.status)) return;
	frm.__ts_poll = setTimeout(() => {
		if (frappe.get_route_str() === `Form/${frm.doctype}/${frm.docname}`) frm.reload_doc();
	}, 3000);
};

test_studio.export_ts = (name) => {
	frappe.call({ method: "test_studio.runner.export_playwright", args: { name } }).then(({ message }) => {
		const d = new frappe.ui.Dialog({
			title: __("Playwright Test (TypeScript)"),
			size: "extra-large",
			fields: [
				{ fieldtype: "HTML", options: `<p class="text-muted small">${__("Save as <code>tests/{0}.spec.ts</code> and run <code>npx playwright test</code>. Secret variables are read from environment variables.", [esc(name)])}</p>` },
				{ fieldname: "code", fieldtype: "Code", options: "JavaScript", default: message, read_only: 1 },
			],
			primary_action_label: __("Copy"),
			primary_action: () => frappe.utils.copy_to_clipboard(message),
			secondary_action_label: __("Download"),
			secondary_action: () => {
				const a = document.createElement("a");
				a.href = URL.createObjectURL(new Blob([message], { type: "text/plain" }));
				a.download = `${name}.spec.ts`;
				a.click();
				URL.revokeObjectURL(a.href);
			},
		});
		d.show();
	});
};

const summary = (doc, stats) => {
	const live = ["Queued", "Running"].includes(doc.status);
	return `
		<div class="ts-summary ts-${esc(doc.status).toLowerCase()}">
			<div class="ts-status">${live ? '<span class="ts-spinner" aria-hidden="true"></span>' : ""}${esc(__(doc.status))}</div>
			<div class="ts-stats">${stats}<span>${fmt_ms(doc.duration_ms)}</span></div>
		</div>`;
};

test_studio.render_run = (doc) => {
	const steps = doc.steps || [];
	const count = (s) => steps.filter((r) => r.status === s).length;
	const head = summary(
		doc,
		`<span><b>${count("Passed")}</b> ${__("passed")}</span>
		 <span><b>${count("Failed")}</b> ${__("failed")}</span>
		 <span><b>${count("Skipped")}</b> ${__("skipped")}</span>
		 <span>${esc(doc.browser || "")}</span>`
	);
	if (!steps.length) {
		const live = ["Queued", "Running"].includes(doc.status);
		return head + `<p class="text-muted">${live ? __("Waiting for the browser… this page updates automatically.") : __("No steps were executed.")}</p>`;
	}
	const rows = steps
		.map(
			(r) => `
		<li class="ts-step ts-${esc(r.status).toLowerCase()}">
			<span class="ts-dot" title="${esc(__(r.status))}"></span>
			<div class="ts-step-body">
				<div class="ts-step-head">
					<span class="ts-no">${esc(r.step_no)}</span>
					<code>${esc(r.action)}</code>
					<span class="ts-target">${esc(r.target)}</span>
					<span class="ts-time">${r.status === "Skipped" ? __("skipped") : fmt_ms(r.duration_ms)}</span>
				</div>
				${r.error ? `<pre class="ts-error">${esc(r.error)}</pre>` : ""}
				${r.screenshot ? `<a href="${esc(r.screenshot)}" target="_blank" rel="noopener"><img class="ts-shot" loading="lazy" src="${esc(r.screenshot)}" alt="${esc(__("Screenshot after step {0}", [r.step_no]))}"></a>` : ""}
			</div>
		</li>`
		)
		.join("");
	return head + `<ol class="ts-timeline">${rows}</ol>`;
};

test_studio.render_funnel = (doc) => {
	const stages = doc.stages || [];
	if (!stages.length) return `<p class="text-muted">${__("No stages.")}</p>`;
	const max = Math.max(1, ...stages.map((s) => s.total || 0));
	const bars = stages
		.map((s, i) => {
			const label =
				s.status === "Skipped" ? __("skipped")
				: s.status === "Pending" ? __("pending")
				: __("{0} / {1} passed", [s.passed || 0, s.total || 0]);
			return `
			<div class="ts-funnel-row ts-${esc(s.status).toLowerCase()}">
				<div class="ts-funnel-name"><span class="ts-no">${i + 1}</span>${esc(s.stage_name)}<div class="text-muted small">${esc(s.suite)}</div></div>
				<div class="ts-funnel-lane">
					<div class="ts-funnel-track" style="width:${Math.max(8, (100 * (s.total || 0)) / max)}%" role="img" aria-label="${esc(s.stage_name)}: ${esc(label)}">
						<div class="ts-bar-pass" style="width:${(100 * (s.passed || 0)) / (s.total || 1)}%"></div>
						<div class="ts-bar-fail" style="width:${(100 * (s.failed || 0)) / (s.total || 1)}%"></div>
					</div>
				</div>
				<div class="ts-funnel-label">${esc(label)}${s.duration_ms ? ` · ${fmt_ms(s.duration_ms)}` : ""}</div>
			</div>`;
		})
		.join("");
	return summary(doc, "") + `<div class="ts-funnel">${bars}</div>`;
};
