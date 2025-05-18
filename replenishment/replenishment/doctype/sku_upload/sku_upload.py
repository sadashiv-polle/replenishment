from frappe.model.document import Document
import frappe
import pandas as pd
import os
from frappe.utils import now

class SKUUpload(Document):
    pass

def clean_value(val):
    if pd.isna(val):
        return None
    return str(val).strip()

@frappe.whitelist()
def import_excel_and_create_skus(docname):
    doc = frappe.get_doc("SKU Upload", docname)

    doc.status = "Pending"
    doc.log = "Starting import...\n"
    doc.save(ignore_permissions=True)

    try:
        file_url = doc.upload_files_customs

        if not file_url:
            doc.status = "Failed"
            doc.log += "❌ No file attached.\n"
            doc.save(ignore_permissions=True)
            return "❌ No file attached."

        file_doc = frappe.get_doc("File", {"file_url": file_url})
        file_path = file_doc.get_full_path()

        if not os.path.exists(file_path):
            doc.status = "Failed"
            doc.log += f"❌ File not found at: {file_path}\n"
            doc.save(ignore_permissions=True)
            return doc.log

        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        else:
            df = pd.read_excel(file_path, sheet_name=1)  # Load second sheet


        doc.log += f"✅ File read successfully. Rows: {len(df)}\n"
        doc.log += "🚀 Starting row processing...\n"
        doc.save(ignore_permissions=True)

        count_inserted = 0
        count_updated = 0
        count_skipped = 0
        processed_materials = set()
        bulk_data = []

        for _, row in df.iterrows():
            raw_material = row.get("Material")
            if not raw_material:
                continue

            material = clean_value(raw_material).upper()
            if material in processed_materials:
                doc.log += f"🔁 Duplicate material skipped: {material}\n"
                continue

            processed_materials.add(material)

            new_data = {
                "description": clean_value(row.get("Description")),
                "velocity_fast__medium_slow": clean_value(row.get("Velocity (Fast / Medium/ Slow)")),
                "type": clean_value(row.get("Type")),
                "pick_face_location_dest_bin": clean_value(row.get("Pick Face Location (Dest. Bin)")),
                "max_capacity_at_pick_face": clean_value(row.get("Max Capacity at Pick Face")),
                "min_capacity_at_pick_face": clean_value(row.get("Min Capacity at Pick Face")),
                "remark": clean_value(row.get("Remark"))
            }

            existing_name = frappe.db.get_value("SKU Master", {"material": material})
            if existing_name:
                existing_doc = frappe.get_doc("SKU Master", existing_name)
                has_changes = any(str(getattr(existing_doc, field) or "").strip() != (val or "") for field, val in new_data.items())

                if has_changes:
                    for field, value in new_data.items():
                        setattr(existing_doc, field, value)
                    existing_doc.save(ignore_permissions=True)
                    count_updated += 1
                else:
                    count_skipped += 1
            else:
                bulk_data.append({
                    "name": material,
                    "material": material,
                    **new_data,
                    "creation": now(),
                    "modified": now(),
                    "owner": frappe.session.user or "Administrator",
                    "modified_by": frappe.session.user or "Administrator",
                })
                count_inserted += 1

        if bulk_data:
            fields = list(bulk_data[0].keys())
            values = [tuple(row[field] for field in fields) for row in bulk_data]
            frappe.db.bulk_insert("SKU Master", fields=fields, values=values)

        frappe.db.commit()
        total_in_system = frappe.db.count("SKU Master")

        doc.status = "Completed"
        doc.log += (
            f"\n✅ Import Summary:\n"
            f"✔️ New Records: {count_inserted}\n"
            f"🛠️ Updated: {count_updated}\n"
            f"⏭️ Skipped (no change): {count_skipped}\n"
            f"🗃️ Total in System: {total_in_system}\n"
        )
        doc.save(ignore_permissions=True)

        return doc.log

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "SKU Upload Import Error")
        doc.status = "Failed"
        doc.log += f"❌ Import failed:\n{frappe.get_traceback()}\n"
        doc.save(ignore_permissions=True)
        return doc.log
