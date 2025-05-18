frappe.ui.form.on("Location Master", {
    refresh: function (frm) {
        let is_import_running = false; // flag to track import status

        if (frm.doc.docstatus === 0 && frm.doc.upload_location_master_file) {
            frm.add_custom_button("📥 Import Attached Excel", () => {
                if (is_import_running) {
                    frappe.msgprint({
                        title: "Import In Progress",
                        message: "⚠️ Import is already running. Please wait for it to complete.",
                        indicator: "yellow"
                    });
                    return;
                }

                console.log("Import button clicked");
                is_import_running = true;

                frappe.call({
                    method: "replenishment.replenishment.doctype.location_master.location_master.import_excel_from_attached_file",
                    args: {
                        docname: frm.doc.name
                    },
                    callback: function (r) {
                        is_import_running = false;

                        if (r.message) {
                            frappe.show_alert(r.message);

                            const message = r.message;

                            if (message.startsWith("✅")) {
                                frappe.msgprint({
                                    title: "Import Successful",
                                    message: `
                                        <div style="padding: 8px;">
                                            ${message.replace(/\n/g, "<br>")}
                                        </div>
                                    `,
                                    indicator: "green"
                                });
                            } else {
                                frappe.msgprint({
                                    title: "Import Failed",
                                    message: message,
                                    indicator: "red"
                                });
                            }

                            frm.reload_doc();
                        } else {
                            frappe.msgprint({
                                title: "Import Error",
                                message: "No response received from the server. Please check the console for errors.",
                                indicator: "red"
                            });
                        }
                    },
                    error: function (err) {
                        is_import_running = false;

                        frappe.msgprint({
                            title: "Import Error",
                            message: "An error occurred while importing the file. Please check the browser console for details.",
                            indicator: "red"
                        });
                        console.error("Import error:", err);
                    }
                });
            });
        }
    }
});
