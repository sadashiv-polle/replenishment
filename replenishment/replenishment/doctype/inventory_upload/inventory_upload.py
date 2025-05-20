# Copyright (c) 2025, you and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import pandas as pd
import io
import os
import openpyxl
from frappe.utils.file_manager import save_file
from frappe.utils import now_datetime
import random
import string

class InventoryUpload(Document):
    pass

@frappe.whitelist()
def process_inventory_upload(docname):
    doc = frappe.get_doc("Inventory Upload", docname)
    run_replenishment(doc)

def run_replenishment(doc):
    try:
        # 1. Read uploaded inventory file
        file_url = doc.upload_inventory_file
        file_doc = frappe.get_doc("File", {"file_url": file_url})

        if file_doc.is_private:
            file_path = frappe.get_site_path("private", "files", file_doc.file_name)
        else:
            file_path = frappe.get_site_path("public", file_doc.file_url.lstrip("/"))

        if not os.path.exists(file_path):
            raise Exception(f"File not found: {file_path}")

        wb = openpyxl.load_workbook(file_path)
        sheet_name = wb.sheetnames[0]
        inventory_df = pd.read_excel(file_path, engine="openpyxl", sheet_name=sheet_name)

        # Normalize column names
        cols = pd.Series(inventory_df.columns)
        for dup in cols[cols.duplicated()].unique():
            cols[cols[cols == dup].index.values.tolist()] = [f"{dup}_{i}" if i != 0 else dup for i in range(sum(cols == dup))]
        inventory_df.columns = cols
        inventory_df.columns = [col.lower().replace(" ", "") for col in inventory_df.columns]

        inventory_df = inventory_df[inventory_df["material"] != "<<empty>>"]

        required_columns = ["material", "storagebin", "pickquantity", "availablestock"]
        missing_cols = [col for col in required_columns if col not in inventory_df.columns]
        if missing_cols:
            raise Exception(f"Missing columns: {', '.join(missing_cols)}")

        inventory_df["pickquantity"] = pd.to_numeric(inventory_df["pickquantity"], errors="coerce").fillna(0)
        inventory_df["availablestock"] = pd.to_numeric(inventory_df["availablestock"], errors="coerce").fillna(0)

        # 2. Fetch master data
        sku_docs = frappe.get_all("SKU Master", fields=[
            "material", "min_capacity_at_pick_face", "max_capacity_at_pick_face", 
            "pick_face_location_dest_bin", "fast_moving"
        ])
        sku_df = pd.DataFrame(sku_docs)

        if sku_df.empty:
            raise Exception("SKU Master is empty")

        location_docs = frappe.get_all("Location Master", fields=["storage_bin", "storage_type"])
        location_df = pd.DataFrame(location_docs)

        output_rows = []
        log = []
        repl_count = 0
        skip_count = 0

        for _, sku_info in sku_df.iterrows():
            sku = sku_info["material"]
            fast_moving = sku_info.get("fast_moving", 1)
            if not fast_moving:
                continue

            min_qty = float(sku_info.get("min_capacity_at_pick_face") or 0)
            max_qty = float(sku_info.get("max_capacity_at_pick_face") or 0)
            pick_face = sku_info.get("pick_face_location_dest_bin")

            if not pick_face:
                log.append(f"⚠️ Missing Pick Face for SKU {sku}")
                skip_count += 1
                continue

            item_inv = inventory_df[inventory_df["material"] == sku]
            hand_pick_qty = item_inv[item_inv["storagebin"] == pick_face]["pickquantity"].sum()

            if hand_pick_qty < min_qty:
                repl_qty = max_qty - hand_pick_qty
                source_bins = item_inv[item_inv["storagebin"] != pick_face].sort_values("availablestock")
                if not source_bins.empty:
                    source_bin = source_bins.iloc[0]["storagebin"]

                    source_row = location_df[location_df["storage_bin"] == source_bin]
                    dest_row = location_df[location_df["storage_bin"] == pick_face]
                    source_type = source_row["storage_type"].iloc[0] if not source_row.empty else "SPR"
                    dest_type = dest_row["storage_type"].iloc[0] if not dest_row.empty else "SPR"

                    # Only SPR to SPR
                    if source_type == "SPR" and dest_type == "SPR":
                        output_rows.append({
                            "Warehouse No": 21,
                            "Movement type 999": 999,
                            "Material No": sku,
                            "Replenishment Qty": repl_qty,
                            "Plant": 4460,
                            "Storage location": 1,
                            "Storage unit type": "E1",
                            "Source Storage Type": source_type,
                            "Source storage bin": source_bin,
                            "Destination Storage Type": dest_type,
                            "Pick Face storage bin": pick_face
                        })
                        repl_count += 1
                    else:
                        log.append(f"⛔ Not SPR→SPR for SKU {sku} (From: {source_type}, To: {dest_type})")
                        skip_count += 1
                else:
                    log.append(f"⚠️ No source bin found for SKU {sku}")
                    skip_count += 1
            else:
                log.append(f"⏭️ Replenishment not required for SKU {sku}")
                skip_count += 1

        output_df = pd.DataFrame(output_rows)

        # Save output Excel
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
            output_df.to_excel(writer, index=False, sheet_name="Replenishment Plan")
        buffer.seek(0)

        file_name = f"replenishment_output_{doc.name}.xlsx"
        saved_file = save_file(file_name, buffer, doc.doctype, doc.name, is_private=0)

        # Run ID + Timestamp + User
        doc.status = "Completed"
        doc.run_id = f"RUN-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
        doc.generated_at = now_datetime()
        doc.created_by = frappe.session.user
        doc.log = f"✅ Replenishments: {repl_count}\n⏭️ Skipped: {skip_count}\n" + "\n".join(log)
        doc.output_file = saved_file.file_url
        doc.save()

    except Exception as e:
        doc.status = "Failed"
        doc.log = f"❌ Error: {str(e)}"
        doc.save()
        frappe.log_error(frappe.get_traceback(), "Inventory Upload Failure")
