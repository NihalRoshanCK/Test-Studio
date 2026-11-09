frappe.ui.form.on("Test Pipeline Run", {
	refresh(frm) {
		frm.disable_save();
		frm.get_field("funnel_html").$wrapper.html(test_studio.render_funnel(frm.doc));
		test_studio.poll_while_running(frm);
		frm.add_custom_button(__("Test Runs"), () => frappe.set_route("List", "Test Run", { pipeline_run: frm.doc.name }));
		frm.add_custom_button(__("Run Again"), () => test_studio.run("test_studio.runner.run_pipeline", frm.doc.pipeline));
	},
});
