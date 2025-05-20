frappe.ui.form.on('Inventory Upload', {
    refresh(frm) {
        if (frm.doc.status === "Draft") {
            frm.add_custom_button('Run Replenishment', () => {
                frappe.call({
                    method: 'replenishment.replenishment.doctype.inventory_upload.inventory_upload.process_inventory_upload',
                    args: {
                        docname: frm.doc.name
                    },
                    callback: function(r) {
                        if (!r.exc) {
                            frm.reload_doc();
                        }
                    }
                });
            });
        }
    }
});
