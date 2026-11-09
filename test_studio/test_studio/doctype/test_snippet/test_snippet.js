frappe.ui.form.on("Test Snippet", {
	refresh(frm) {
		frm.set_intro(__("Snippets are reusable step groups. Use them in any test case with the <b>run_snippet</b> action."), "blue");
	},
});
