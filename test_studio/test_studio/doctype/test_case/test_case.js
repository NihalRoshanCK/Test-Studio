frappe.ui.form.on("Test Case", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Run Test"), () => test_studio.run("test_studio.runner.run_test_case", frm.doc.name)).addClass("btn-primary");
		frm.add_custom_button(__("Open in Studio"), () => window.open("/studio/test/" + encodeURIComponent(frm.doc.name), "_self"));
		frm.add_custom_button(__("Export to Playwright"), () => test_studio.export_ts(frm.doc.name), __("Actions"));
		frm.add_custom_button(__("Run History"), () => frappe.set_route("List", "Test Run", { test_case: frm.doc.name }), __("Actions"));
		if (frm.doc.last_status) {
			const color = { Passed: "green", "Known Issue": "yellow", Failed: "red", Error: "orange" }[frm.doc.last_status];
			frm.dashboard.set_headline_alert(__("Last run: {0}", [frm.doc.last_status]), color);
		}
	},
});
