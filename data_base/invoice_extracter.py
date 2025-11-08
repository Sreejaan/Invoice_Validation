import os
import time
import json
import google.generativeai as genai

# ================================
# 🔐 API Setup
# ================================
API_KEY = "AIzaSyCwWoaxIg06OXIuBhX5PzFRlnXk9pOYkrA"  # safer than hardcoding
genai.configure(api_key=API_KEY)
MODEL_NAME = "models/gemini-2.5-pro"
model = genai.GenerativeModel(MODEL_NAME)

# ================================
# 🧠 Extraction Prompt
# ================================
PROMPT = """
You are an invoice extraction assistant.

Read the entire document and output **only** one valid JSON object following this schema exactly. Do NOT output any text, explanation, or markdown.

Rules:
1. Do NOT invent or infer values. If a value is not present, set it to null.
2. Do NOT add or rename keys.
3. Numbers must be numeric. Dates must be "DD-MMM-YY".
4. Taxes: include cgst, sgst, igst fields if present; else null.
5. hsn_codes: comma-separated string if multiple.
6. Description: 1–2 sentence summary based on document content only.

Required JSON schema:
{
  "Description": "String",
  "invoice_no": "String or null",
  "invoice_date": "String (DD-MMM-YY) or null",
  "invoice_amount": Number or null,
  "gstin_company": "String or null",
  "gstin_client": "String or null",
  "hsn_codes": "String or null",
  "items": [
    {
      "description": "String or null",
      "hsn_sac": "String or null",
      "quantity": Number or null,
      "rate": Number or null,
      "amount": Number or null,
      "cgst": Number or null,
      "sgst": Number or null,
      "igst": Number or null,
      "total": Number or null
    }
  ],
  "summary": {
    "subtotal": Number or null,
    "tax_amount": Number or null,
    "total_amount": Number or null,
    "gst": Number or null,
    "cgst": Number or null,
    "sgst": Number or null,
    "igst": Number or null
  }
}
"""

# ================================
# 🧹 Helper: Clean JSON text
# ================================
def clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    if text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


# ================================
# 📄 Main Extraction Function
# ================================
def extract_invoice_data(file_path: str):
    fname = os.path.basename(file_path)
    print(f"\n📄 Extracting data from: {fname}")

    try:
        uploaded_file = genai.upload_file(file_path)
        print(f"  ⬆️ Uploaded: {uploaded_file.display_name}, state: {uploaded_file.state.name}")

        # Wait until processing completes
        while uploaded_file.state.name == "PROCESSING":
            print("  ⏳ Waiting for file to finish processing...")
            time.sleep(2)
            uploaded_file = genai.get_file(uploaded_file.name)

        if uploaded_file.state.name != "ACTIVE":
            print(f"  ❌ Upload failed or not active: {uploaded_file.state.name}")
            return "Failed Extraction"

        # Run Gemini inference
        response = model.generate_content([uploaded_file, PROMPT])
        raw_text = response.text.strip() if response.text else ""

        cleaned_text = clean_json_text(raw_text)
        try:
            json_data = json.loads(cleaned_text)
        except json.JSONDecodeError:
            print("  ⚠️ Warning: Model output not valid JSON.")
            json_data = {"raw_text": cleaned_text}

        return json_data

    except Exception as e:
        print(f"  ❌ Error while processing {fname}: {e}")
        return "Failed Extraction"

    finally:
        if 'uploaded_file' in locals():
            genai.delete_file(uploaded_file.name)
            print("  🗑️ Cleaned up uploaded file.")
