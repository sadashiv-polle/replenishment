from frappe.model.document import Document
import frappe
import pandas as pd
import os
from frappe.utils import generate_hash, now

class UploadFilesCustom(Document):
    pass

def clean_value(val):
    """Convert NaN to None and strip strings."""
    if pd.isna(val):
        return None
    return str(val).strip()

@frappe.whitelist()
def import_excel_and_create_locations(docname):
    doc = frappe.get_doc("Upload Files Custom", docname)

    doc.status = "Pending"
    doc.log = "Starting import...\n"
    doc.save(ignore_permissions=True)

    try:
        file_url = doc.upload_location_master

        if not file_url:
            doc.status = "Failed"
            doc.log += "❌ No file attached.\n"
            doc.save(ignore_permissions=True)
            return "❌ No file attached."

        file_doc = frappe.get_doc("File", {"file_url": file_url})
        file_path = file_doc.get_full_path()

        if not os.path.exists(file_path):
            doc.status = "Failed"
            doc.log += f"❌ File not found at path: {file_path}\n"
            doc.save(ignore_permissions=True)
            return f"❌ File not found at path: {file_path}"

        # Read Excel/CSV
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            try:
                df = pd.read_excel(file_path, sheet_name="Location Master")
            except ValueError:
                doc.status = "Failed"
                doc.log += "❌ Sheet 'Location Master' not found in the Excel file.\n"
                doc.save(ignore_permissions=True)
                return doc.log

        doc.log += f"✅ File read successfully. Rows: {len(df)}\n"
        doc.log += "🚀 Starting row processing...\n"
        doc.save(ignore_permissions=True)

        # Track counts
        count_inserted = 0
        count_updated = 0
        count_skipped = 0
        processed_bins = set()
        bulk_data = []

        for index, row in df.iterrows():
            raw_bin = row.get("Storage Bin")
            if not raw_bin:
                continue

            storage_bin = clean_value(raw_bin).upper()
            if storage_bin in processed_bins:
                doc.log += f"🔁 Duplicate bin in file skipped: {storage_bin}\n"
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
                has_changes = False

                for field, new_value in new_data.items():
                    existing_value = str(getattr(existing_doc, field) or "").strip()
                    if existing_value != (new_value or ""):
                        has_changes = True
                        break

                if has_changes:
                    for field, value in new_data.items():
                        setattr(existing_doc, field, value)
                    existing_doc.save(ignore_permissions=True)
                    count_updated += 1
                else:
                    count_skipped += 1
            else:
                current_time = now()
                owner = frappe.session.user or "Administrator"

                bulk_data.append({
                    "name": storage_bin,
                    "storage_bin": storage_bin,
                    **new_data,
                    "creation": current_time,
                    "modified": current_time,
                    "owner": owner,
                    "modified_by": owner,
                })
                count_inserted += 1

        if bulk_data:
            fields = list(bulk_data[0].keys())
            values = [tuple(row[field] for field in fields) for row in bulk_data]
            frappe.db.bulk_insert("Location Master", fields=fields, values=values)

        frappe.db.commit()

        # Count total in system after commit
        total_processed = count_inserted + count_updated + count_skipped
        total_in_system = frappe.db.count("Location Master")

        doc.status = "Completed"
        doc.log += (
            f"\n✅ Import Summary:\n"
            f"✔️ New Records: {count_inserted}\n"
            f"🛠️ Updated: {count_updated}\n"
            f"⏭️ Skipped (no change): {count_skipped}\n"
            f"📊 Total Processed: {total_processed}\n"
            f"🗃️ Total in System: {total_in_system}\n"
        )
        doc.save(ignore_permissions=True)

        return doc.log


    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Upload Files Custom Import Error")
        doc.status = "Failed"
        doc.log += f"❌ Import failed with exception:\n{frappe.get_traceback()}\n"
        doc.save(ignore_permissions=True)
        return doc.log
