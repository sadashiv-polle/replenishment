frappe.ui.form.on("Upload Files Custom", {
    refresh: function (frm) {
        // Show button only if import is not completed
        if (frm.doc.status !== "Completed") {
            let is_import_running = false;

            frm.add_custom_button("📥 Import Location Data", function () {
                if (is_import_running) {
                    frappe.msgprint({
                        title: "Import In Progress",
                        message: "⚠️ Import is already running. Please wait for it to complete.",
                        indicator: "yellow"
                    });
                    return;
                }

                is_import_running = true;

                frappe.call({
                    method: "replenishment.replenishment.doctype.upload_files_custom.upload_files_custom.import_excel_and_create_locations",
                    args: {
                        docname: frm.doc.name
                    },
                    callback: function (r) {
                        is_import_running = false;

                        if (r.message) {
                            const message = r.message;
                            frappe.show_alert(message);

                            frappe.msgprint({
                                title: message.startsWith("✅") ? "Import Summary" : "Import Failed",
                                message: `<div style="padding: 8px;">${message.replace(/\n/g, "<br>")}</div>`,
                                indicator: message.startsWith("✅") ? "green" : "red"
                            });

                            frm.reload_doc(); // Button will disappear after reload if status is Completed
                        }
                    },
                    error: function (err) {
                        is_import_running = false;
                        frappe.msgprint({
                            title: "Import Error",
                            message: "An error occurred while importing. Check console for details.",
                            indicator: "red"
                        });
                        console.error("Import error:", err);
                    }
                });
            });
        }
    }
});
