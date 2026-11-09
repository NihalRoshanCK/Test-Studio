frappe.ui.form.on("Test Run", {
	refresh(frm) {
		frm.disable_save();
		frm.get_field("results_html").$wrapper.html(test_studio.render_run(frm.doc));
		test_studio.poll_while_running(frm);
		frm.add_custom_button(__("Re-run"), () => test_studio.run("test_studio.runner.run_test_case", frm.doc.test_case));
		if (frm.doc.trace) {
			frm.add_custom_button(__("Download Trace"), () => {
				window.open(frm.doc.trace);
				frappe.msgprint(__("Open it with <code>npx playwright show-trace trace.zip</code> or drop it on <a href='https://trace.playwright.dev' target='_blank' rel='noopener'>trace.playwright.dev</a> (runs locally in your browser)."));
			});
		}
	},
});
