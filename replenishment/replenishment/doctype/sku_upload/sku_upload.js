frappe.ui.form.on("SKU Upload", {
    refresh: function (frm) {
        if (frm.doc.status !== "Completed") {
            let is_import_running = false;

            frm.add_custom_button("📥 Import SKU Data", function () {
                if (is_import_running) {
                    frappe.msgprint({
                        title: "Import In Progress",
                        message: "⚠️ Import is already running. Please wait.",
                        indicator: "yellow"
                    });
                    return;
                }

                is_import_running = true;

                frappe.call({
                    method: "replenishment.replenishment.doctype.sku_upload.sku_upload.import_excel_and_create_skus",
                    args: { docname: frm.doc.name },
                    callback: function (r) {
                        is_import_running = false;

                        if (r.message) {
                            frappe.show_alert(r.message);
                            frappe.msgprint({
                                title: r.message.startsWith("✅") ? "Import Summary" : "Import Failed",
                                message: `<div style="padding: 8px;">${r.message.replace(/\n/g, "<br>")}</div>`,
                                indicator: r.message.startsWith("✅") ? "green" : "red"
                            });

                            frm.reload_doc();
                        }
                    },
                    error: function (err) {
                        is_import_running = false;
                        frappe.msgprint({
                            title: "Import Error",
                            message: "An error occurred. Check console for details.",
                            indicator: "red"
                        });
                        console.error("Import error:", err);
                    }
                });
            });
        }
    }
});
