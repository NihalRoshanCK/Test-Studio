frappe.listview_settings["Test Run"] = {
	get_indicator(doc) {
		const c = { Queued: "gray", Running: "blue", Passed: "green", "Known Issue": "yellow", Failed: "red", Error: "orange" }[doc.status];
		return [__(doc.status), c || "gray", "status,=," + doc.status];
	},
};
