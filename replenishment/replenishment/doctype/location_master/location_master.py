import frappe
import pandas as pd
import os
from frappe.utils import generate_hash
from frappe.model.document import Document

class LocationMaster(Document):
    pass

def clean_value(val):
    """Convert NaN to None and strip strings."""
    if pd.isna(val):
        return None
    return str(val).strip()

@frappe.whitelist()
def import_from_uploaded_file(docname):
    try:
        # Fetch your Upload Files Custom doc using the passed docname
        upload_doc = frappe.get_doc("Upload Files Custom", docname)
        file_url = upload_doc.upload_location_master  # your Attach field in Upload Files Custom

        if not file_url:
            return "❌ No file attached."

        file_doc = frappe.get_doc("File", {"file_url": file_url})
        file_path = file_doc.get_full_path()

        if not os.path.exists(file_path):
            return f"❌ File not found at path: {file_path}"

        # Read Excel (or CSV if needed)
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path, sheet_name="Location Master")

        count_inserted, count_updated, count_skipped = 0, 0, 0
        processed_bins = set()
        bulk_data = []

        for _, row in df.iterrows():
            raw_bin = row.get("Storage Bin")
            if not raw_bin:
                continue

            storage_bin = clean_value(raw_bin).upper()
            if storage_bin in processed_bins:
                frappe.logger().info(f"Duplicate bin skipped: {storage_bin}")
                continue

            processed_bins.add(storage_bin)

            existing_name = frappe.db.get_value("Location Master", {"storage_bin": storage_bin})

            new_data = {
                "type": clean_value(row.get("Type")),
                "typee": clean_value(row.get("Type.1")),
                "storage_type": clean_value(row.get("Storage Type")),
                "storage_typee": clean_value(row.get("Storage Type.1")),
                "wh_block": clean_value(row.get("WH Block")),
                "storage_level": clean_value(row.get("Storage Level"))
            }

            if existing_name:
                existing_doc = frappe.get_doc("Location Master", existing_name)
                has_changes = any(
                    str(getattr(existing_doc, f) or "").strip() != str(v or "").strip()
                    for f, v in new_data.items()
                )
                if has_changes:
                    for f, v in new_data.items():
                        setattr(existing_doc, f, v)
                    existing_doc.save(ignore_permissions=True)
                    count_updated += 1
                else:
                    count_skipped += 1
            else:
                bulk_data.append({
                    "name": generate_hash(length=10),
                    "storage_bin": storage_bin,
                    **new_data
                })
                count_inserted += 1

        if bulk_data:
            fields = list(bulk_data[0].keys())
            values = [tuple(d[f] for f in fields) for d in bulk_data]
            frappe.db.bulk_insert("Location Master", fields=fields, values=values)

        frappe.db.commit()

        return (
            "✅ Import Summary:\n"
            f"✔️ Inserted: {count_inserted}\n"
            f"🛠️ Updated: {count_updated}\n"
            f"⏭️ Skipped (no change): {count_skipped}"
        )

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Location Master Import Error")
        return f"❌ Failed to import: {str(e)}"
