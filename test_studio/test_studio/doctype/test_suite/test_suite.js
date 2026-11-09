frappe.ui.form.on("Test Suite", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Run Suite"), () => {
			frappe.prompt(
				{ fieldname: "tag", fieldtype: "Data", label: __("Only cases tagged (optional)") },
				(v) => test_studio.run("test_studio.runner.run_test_suite", frm.doc.name, { tag: v.tag }),
				__("Run Suite"), __("Run")
			);
		}).addClass("btn-primary");
		frm.add_custom_button(__("New Test Case"), () => frappe.new_doc("Test Case", { suite: frm.doc.name }));
	},
});
