import os
import time
import json
import google.generativeai as genai
from PIL import Image

# --- CONFIGURATION ---

# 🗝️ Multiple API keys to rotate
API_KEYS = [
    "AIzaSyA8XiHHeGweJYXj1J07qGoikjRYwRSFWxk",
    "AIzaSyBeuNIOapTVonYQhjDkccqX9TF6KnOCRl8",
    "AIzaSyB93lfT6JudpEzD9GIrOwR9urrfsmgD3to",
    "AIzaSyAEM5knLLNZrjbVSisB-2keJ5CnO10u7jw",
    "AIzaSyDSyQJZCDoZjR96B6truM5XO0D_hLk0ShY",
    "AIzaSyATpgDDjQ-uixhw3EhxbzOEJJuf_sWueHc",
    "AIzaSyCBl91ne2JwQV4YMSFyqlnl0eVSXNF_L5s",
    "AIzaSyDfukYq76rser0U9B-bDajV3BP41ZtiwNk",
    "AIzaSyDUcTUz9WZVMeIS9KJIkz34_OzibdGvt-k",
    "AIzaSyA6O_sapsJnM4bTA6Q50oA3F3Kg3pkRHXA"
]

MODEL_NAME = "models/gemini-2.5-pro"
SAVE_INTERVAL = 2  # ✅ Save output JSON after every 2 files
OUTPUT_FILE = "extracted_invoices copy.json"


# --- Prompt Definition ---
PROMPT = """
You are a professional invoice data extraction and analysis assistant.

Your task is to carefully read and analyze the *entire* content of the given document (invoice or billing file) and extract **all relevant details** in the JSON format strictly defined below.

You must read every visible text on all pages and extract information with maximum completeness, accuracy, and consistency — do not skip or ignore any part of the document.

---

### 🎯 OUTPUT RULES
1. Always follow the JSON schema provided below — no extra fields, no Markdown, no explanations.
2. If a particular value is missing in the invoice, set it to `null` (do NOT remove the key).
3. Always fill `"Description"` with your own brief 1–2 sentence summary describing what this invoice is about.
4. Ensure all numbers are numeric (not strings).
5. Dates should be in `"DD-MMM-YY"` format (e.g., `"20-Aug-25"`).
6. Ensure all amounts match the invoice values exactly.
7. Extract GST, CGST, and SGST as numeric percent values (no '%' symbol).
8. If any tax value is not explicitly mentioned, infer it logically (e.g., from totals or summary).
9. Output must be a **valid JSON object only** — no extra text, markdown, or code formatting.

---

### 🧾 JSON OUTPUT FORMAT

{
  "Description": "String — A short summary describing what this invoice is about.",
  "invoice_no": "String",
  "invoice_date": "Date (DD-MMM-YY)",
  "invoice_amount": Number,
  "gstin_company": "String",
  "gstin_client": "String",
  "hsn_codes": "String (comma-separated if multiple)",
  "items": [
    {
      "description": "String",
      "hsn_sac": "String",
      "quantity": Number,
      "rate": Number,
      "amount": Number,
      "tax_percent": Number,
      "cgst": Number,
      "sgst": Number,
      "igst": Number,
      "total": Number
    }
  ],
  "summary": {
    "subtotal": Number,
    "tax_amount": Number,
    "total_amount": Number,
    "gst": Number,
    "cgst": Number,
    "sgst": Number,
    "igst": Number
  }
}
"""


# --- Helper functions ---
def rotate_key(index: int) -> str:
    """Rotate between multiple API keys."""
    key = API_KEYS[index % len(API_KEYS)]
    genai.configure(api_key=key)
    print(f"\n🔑 Using API Key #{(index % len(API_KEYS)) + 1}")
    return key


def clean_json_text(text: str) -> str:
    """Remove markdown/code formatting."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    if text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


from PIL import Image  # <-- add this import at the top
import tempfile

def extract_invoice_data(file_path: str, model) -> dict:
    """Extracts structured JSON data from a single file, auto-converting TIFFs."""
    fname = os.path.basename(file_path)
    print(f"\n📄 Extracting data from: {fname}")

    temp_converted_path = None

    try:
        # --- Convert TIFF/TIF to PNG if needed ---
        if file_path.lower().endswith((".tif", ".tiff")):
            print("  🔄 Converting TIFF to PNG...")
            image = Image.open(file_path)
            temp_converted_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
            image.save(temp_converted_path, format="PNG")
            file_path = temp_converted_path
            print(f"  ✅ Converted to temporary PNG: {os.path.basename(file_path)}")

        # --- Upload to Gemini ---
        uploaded_file = genai.upload_file(file_path)
        print(f"  ⬆️ Uploaded: {uploaded_file.display_name}, state: {uploaded_file.state.name}")

        # Wait until ready
        while uploaded_file.state.name == "PROCESSING":
            print("  ⏳ Waiting for file to finish processing...")
            time.sleep(2)
            uploaded_file = genai.get_file(uploaded_file.name)

        if uploaded_file.state.name != "ACTIVE":
            print(f"  ❌ Upload failed: {uploaded_file.state.name}")
            return {"file": fname, "error": "Upload failed"}

        # --- Ask Gemini to extract JSON ---
        response = model.generate_content([uploaded_file, PROMPT])
        raw_text = response.text.strip() if response.text else ""
        cleaned_text = clean_json_text(raw_text)

        try:
            json_data = json.loads(cleaned_text)
        except json.JSONDecodeError:
            print(f"  ⚠️ Invalid JSON for {fname}")
            json_data = {"file": fname, "raw_text": cleaned_text}

        return json_data

    except Exception as e:
        print(f"  ❌ Error while processing {fname}: {e}")
        return {"file": fname, "error": str(e)}

    finally:
        # --- Clean up Gemini upload ---
        if 'uploaded_file' in locals():
            try:
                genai.delete_file(uploaded_file.name)
                print("  🗑️ Cleaned up uploaded file.")
            except Exception:
                pass

        # --- Delete temp converted PNG file ---
        if temp_converted_path and os.path.exists(temp_converted_path):
            os.remove(temp_converted_path)
            print(f"  🧹 Deleted temp file: {os.path.basename(temp_converted_path)}")

def extract_invoices_from_folder(folder_path: str):
    """Process all invoices in a folder, rotating API keys and saving every 2 files."""
    supported_exts = (".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff")
    files = [os.path.join(folder_path, f) for f in os.listdir(folder_path)
             if f.lower().endswith(supported_exts)]

    if not files:
        print(f"⚠️ No supported files found in: {folder_path}")
        return

    print(f"\n📂 Found {len(files)} files to process in '{folder_path}'\n")

    # Load previous progress (if any)
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            results = json.load(f)
    else:
        results = {}

    for i, file_path in enumerate(files):
        # Skip already processed files
        fname = os.path.basename(file_path)
        if fname in results:
            print(f"  ⏭️ Skipping already processed: {fname}")
            continue

        # Rotate API key
        current_key = rotate_key(i)
        model = genai.GenerativeModel(MODEL_NAME)

        # Extract data
        result = extract_invoice_data(file_path, model)
        results[fname] = result
        print(f"  ✅ Completed: {fname}")

        # Save every SAVE_INTERVAL files
        if (i + 1) % SAVE_INTERVAL == 0 or i == len(files) - 1:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            print(f"  💾 Progress saved after {i + 1} files to '{OUTPUT_FILE}'")

    print(f"\n✅ All extraction results saved to '{OUTPUT_FILE}'")
    return results


# --- Example usage ---
if __name__ == "__main__":
    folder_path = r"C:\Users\shanb\Downloads\Hackathon\data4hack"  # 📁 Change to your folder
    extract_invoices_from_folder(folder_path)
