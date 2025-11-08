# app.py
import streamlit as st
import os
import zipfile
import tempfile
import json
import sqlite3
import pandas as pd
from invoice_extracter import extract_invoice_data

# ---- Try flexible imports for validators ----

# GST verifier (DISABLED COMPLETELY)
try:
    from GSTValidate import verify_gstin as gst_verify
except Exception:
    def gst_verify(gstin):
        return {"status": False, "error": "gst validator not available"}

# Arithmetic validator
try:
    from arthimeticCheck import validate_invoice as arithmetic_validate
except Exception:
    def arithmetic_validate(inv):
        return {"status": False, "errors": ["arithmetic validator not available"]}

# HSN / invoice HSN checker
try:
    from InvoiceHSNChecker import process_invoice as hsn_process
except Exception:
    def hsn_process(inv):
        return {"status": False, "errors": ["hsn checker not available"]}

# ---- MongoDB insert ----
try:
    from load_jsons import insert_doc
except Exception as e:
    st.warning(f"⚠️ MongoDB insert module not found: {e}")
    def insert_doc(doc, file_name=None):
        return {"status": "500", "error": "Mongo insert not available"}

# ---------------------------
# Helper functions / DB
# ---------------------------

def run_inference(file_obj):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_obj.read())
        tmp.flush()
        tmp_path = tmp.name
    try:
        result = extract_invoice_data(tmp_path)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    return result

def normalize_invoice_data(data_dict):
    summary = data_dict.get("summary", {}) if isinstance(data_dict, dict) else {}
    return {
        "file_name": data_dict.get("file_name") if isinstance(data_dict, dict) else None,
        "invoice_number": data_dict.get("invoice_no") if isinstance(data_dict, dict) else None,
        "gstin": data_dict.get("gstin_company") if isinstance(data_dict, dict) else None,
        "total_amount": summary.get("total_amount"),
        "tax": summary.get("tax_amount"),
    }

def check_invoice_data_schema(data_dict):
    errors = []
    if not data_dict.get("invoice_number"):
        errors.append("Missing invoice number")
    gstin = data_dict.get("gstin", "")
    if gstin and len(gstin) != 15:
        errors.append("Invalid GSTIN length")
    if not data_dict.get("total_amount") or (isinstance(data_dict.get("total_amount"), (int,float)) and data_dict.get("total_amount",0) <= 0):
        errors.append("Total amount should be positive or present")
    if data_dict.get("tax") is not None and data_dict.get("tax", 0) < 0:
        errors.append("Tax cannot be negative")
    return errors

def init_db():
    conn = sqlite3.connect("invoices.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            invoice_number TEXT,
            gstin TEXT,
            total_amount REAL,
            tax REAL
        )
    """)
    conn.commit()
    conn.close()

def save_to_db(data_dict):
    conn = sqlite3.connect("invoices.db")
    conn.execute("""
        INSERT INTO invoices (file_name, invoice_number, gstin, total_amount, tax)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data_dict.get("file_name"),
        data_dict.get("invoice_number"),
        data_dict.get("gstin"),
        data_dict.get("total_amount"),
        data_dict.get("tax"),
    ))
    conn.commit()
    conn.close()

def extract_zip(zip_file):
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_file, "r") as zip_ref:
        zip_ref.extractall(temp_dir)
    return [os.path.join(temp_dir, f) for f in os.listdir(temp_dir)]

# ---------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="Invoice Validator", page_icon="📊", layout="wide")
st.title("📂 Invoice File Uploader → JSON Extractor → Validator → MongoDB Saver")

upload_type = st.radio("Choose upload type:", ["File(s)", "ZIP Folder"], horizontal=True)

uploaded_files = []
if upload_type == "File(s)":
    uploaded_files = st.file_uploader("Upload PDF files", accept_multiple_files=True, type=["pdf"])
else:
    zip_file = st.file_uploader("Upload ZIP file", type=["zip"])
    if zip_file:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_zip:
            tmp_zip.write(zip_file.read())
            tmp_zip.flush()
            extracted_paths = extract_zip(tmp_zip.name)
        st.success(f"Extracted {len(extracted_paths)} files from ZIP.")
        uploaded_files = [open(path, "rb") for path in extracted_paths]

# Run processing
if st.button("🚀 Run Inference and Validate"):
    if not uploaded_files:
        st.warning("Please upload at least one file.")
    else:
        init_db()
        st.write("Processing files...")

        anomalies = []
        summary_rows = []

        for file in uploaded_files:
            filename = getattr(file, "name", str(file))
            st.write(f"Processing: {filename}")

            # 1) Extract
            result = run_inference(file)
            if result == "Failed Extraction":
                err_msg = "Extraction failed"
                st.error(f"❌ {filename}: {err_msg}")
                anomalies.append({"File": filename, "Error": err_msg})
                summary_rows.append({"File": filename, "Status": "Failed"})
                continue

            # 2) Normalize & schema checks
            normalized = normalize_invoice_data(result)
            schema_errors = check_invoice_data_schema(normalized)

            # 3) External validators
            extra_errors = []

            # --- GST CHECK ---
            try:
                gst_res = gst_verify(result.get("gstin_company") if isinstance(result, dict) else None)
                if isinstance(gst_res, dict):
                    gst_ok = gst_res.get("status") is True
                else:
                    gst_ok = bool(gst_res)
            except Exception as e:
                gst_ok = False
                extra_errors.append(f"GST check error: {e}")

            if not gst_ok:
                extra_errors.append("GSTIN validation failed")

            # --- Arithmetic check ---
            try:
                arith_res = arithmetic_validate(result)
                if isinstance(arith_res, dict):
                    arith_ok = arith_res.get("status") in (True, "pass", "Pass")
                    arith_errors = arith_res.get("errors") or []
                else:
                    arith_ok = False
                    arith_errors = ["Arithmetic validator returned unexpected type"]
            except Exception as e:
                arith_ok = False
                arith_errors = [f"Arithmetic check exception: {e}"]

            if not arith_ok:
                extra_errors.append("Arithmetic check failed: " + "; ".join(map(str, arith_errors)))

            # --- HSN check ---
            try:
                hsn_res = hsn_process(result)
                if isinstance(hsn_res, dict):
                    hsn_ok = hsn_res.get("status") is True
                    if not hsn_ok:
                        hsn_errors = hsn_res.get("errors") or []
                        extra_errors.append("HSN check failed: " + "; ".join(map(str, hsn_errors)))
                elif isinstance(hsn_res, str):
                    if hsn_res.lower() == "success":
                        hsn_ok = True
                    else:
                        hsn_ok = False
                        extra_errors.append(f"HSN check: {hsn_res}")
                else:
                    hsn_ok = False
                    extra_errors.append("HSN checker returned unexpected type")
            except Exception as e:
                hsn_ok = False
                extra_errors.append(f"HSN check exception: {e}")

            # collect all errors
            all_errors = []
            if schema_errors:
                all_errors.extend(schema_errors)
            if extra_errors:
                all_errors.extend(extra_errors)

            # ---- FINAL VALIDATION OUTCOME ----
            if all_errors:
                summary_rows.append({"File": filename, "Status": "Failed"})
                anomalies.append({"File": filename, "Error": "; ".join(all_errors)})
                st.error(f"❌ {filename}: Validation Failed → {all_errors}")
                with st.expander(f"📄 {filename} → Extracted JSON (for debugging)"):
                    if isinstance(result, dict):
                        st.json(result)
                    else:
                        st.code(str(result))
            else:
                # ✅ Call MongoDB insertion function
                mongo_status = insert_doc(result, filename)

                if str(mongo_status.get("status")) == "200":
                    st.success(f"✅ {filename}: Valid & Saved to MongoDB")
                    summary_rows.append({"File": filename, "Status": "Success"})
                    save_to_db(normalized)  # optional local backup
                elif str(mongo_status.get("status")) == "420":
                    st.warning(f"⚠️ {filename}: Duplicate or fuzzy match found, skipped insertion.")
                    summary_rows.append({"File": filename, "Status": "Duplicate"})
                else:
                    err = mongo_status.get("error", "Unknown error")
                    st.error(f"❌ {filename}: Mongo insert failed → {err}")
                    anomalies.append({"File": filename, "Error": err})
                    summary_rows.append({"File": filename, "Status": "Failed"})

        # ---- Cleanup ----
        for f in uploaded_files:
            try:
                if hasattr(f, "close") and not f.closed:
                    f.close()
            except Exception:
                pass

        # ---- Dashboard ----
        st.subheader("📊 Validation Summary Dashboard")
        df_summary = pd.DataFrame(summary_rows)

        total_files = len(df_summary)
        success_count = (df_summary["Status"] == "Success").sum()
        failed_count = (df_summary["Status"] == "Failed").sum()
        duplicate_count = (df_summary["Status"] == "Duplicate").sum()
        success_percent = (success_count / total_files * 100) if total_files > 0 else 0
        failed_percent = (failed_count / total_files * 100) if total_files > 0 else 0

        col1, col2, col3 = st.columns(3)
        col1.metric("📦 Total Files Processed", total_files)
        col2.metric("✅ Successfully Validated", success_count, f"{success_percent:.1f}%")
        col3.metric("🚨 Failed Validations", failed_count, f"{failed_percent:.1f}%")

        # --- Bar Chart ---
        chart_data = pd.DataFrame({
            "Status": ["Success", "Failed", "Duplicate"],
            "Count": [success_count, failed_count, duplicate_count]
        })
        st.bar_chart(chart_data.set_index("Status"), use_container_width=True)

        # ---- Anomalies ----
        if anomalies:
            st.subheader("🚨 Anomalies Detected")
            df_anom = pd.DataFrame(anomalies)
            st.dataframe(df_anom, use_container_width=True)
            st.warning(f"Total anomalies: {len(anomalies)}")

            # Error breakdown
            error_types = []
            for e in df_anom["Error"]:
                for part in str(e).split(";"):
                    part = part.strip()
                    if part:
                        error_types.append(part.split(":")[0])
            error_df = pd.DataFrame({"Error Type": error_types})

            st.write("**Error Category Breakdown**")
            st.bar_chart(error_df["Error Type"].value_counts(), use_container_width=True)

            # Pie chart
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots()
            counts = error_df["Error Type"].value_counts()
            ax.pie(counts, labels=counts.index, autopct="%1.1f%%", startangle=90)
            ax.axis("equal")
            st.pyplot(fig)

            csv = df_anom.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Download Anomaly Report (CSV)", csv, "anomalies.csv", "text/csv")
        else:
            st.success("🎉 No anomalies found! All invoices are valid.")

# View stored invoices
if st.button("📋 View Stored Invoices"):
    conn = sqlite3.connect("invoices.db")
    df = pd.read_sql_query("SELECT * FROM invoices", conn)
    st.dataframe(df, use_container_width=True)
    conn.close()
