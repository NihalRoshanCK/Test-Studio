frappe.ui.form.on("Test Pipeline", {
	refresh(frm) {
		frm.set_intro(__("Stages run top to bottom. When a stage with <b>Stop Pipeline on Failure</b> fails, later stages are skipped."), "blue");
		if (frm.is_new()) return;
		frm.add_custom_button(__("Run Pipeline"), () => test_studio.run("test_studio.runner.run_pipeline", frm.doc.name)).addClass("btn-primary");
	},
});
