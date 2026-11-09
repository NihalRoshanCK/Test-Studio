frappe.listview_settings["Test Case"] = {
	add_fields: ["last_status", "enabled"],
	get_indicator(doc) {
		if (!doc.enabled) return [__("Disabled"), "gray", "enabled,=,0"];
		if (!doc.last_status) return [__("Not Run"), "gray", "last_status,is,not set"];
		const c = { Passed: "green", "Known Issue": "yellow", Failed: "red", Error: "orange" }[doc.last_status];
		return [__(doc.last_status), c, "last_status,=," + doc.last_status];
	},
};
