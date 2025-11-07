import os
import time
import json
import google.generativeai as genai

# --- Configuration ---
# API_KEY = "AIzaSyCkgv8vv9lvS1X_ZBD38BGK0nhRbkXwSug"
API_KEY = "AIzaSyCwWoaxIg06OXIuBhX5PzFRlnXk9pOYkrA"
genai.configure(api_key=API_KEY)

MODEL_NAME = "models/gemini-2.5-pro"
model = genai.GenerativeModel(MODEL_NAME)

# --- Enhanced Prompt ---
PROMPT = """
You are an invoice extraction assistant.

Read the entire document and output **only** one valid JSON object following this schema exactly. Do NOT output any text, explanation, or markdown.

Rules:
1. Do NOT invent or infer values. If a value is not present in the document, set it to null.
2. Do NOT add extra fields or rename keys.
3. Numbers must be numeric. Dates must be "DD-MMM-YY" (e.g., "20-Aug-25").
4. For taxes, include cgst, sgst, igst fields (numeric percent values) where present; otherwise null.
5. hsn_codes should be a comma-separated string if multiple.
6. "Description" must be a 1–2 sentence summary written by you based only on content present in the document.

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

def clean_json_text(text: str) -> str:
    """Remove markdown/code formatting and trim."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    if text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return text


def extract_invoice_data(file_path: str):
    """
    Extracts structured JSON data from a document (PDF, image, text, etc.)
    using Gemini. Returns JSON data on success, or "Failed Extraction" on failure.
    """
    fname = os.path.basename(file_path)
    print(f"\n📄 Extracting data from: {fname}")

    try:
        # 1. Upload file to Gemini
        uploaded_file = genai.upload_file(file_path)
        print(f"  ⬆️ Uploaded: {uploaded_file.display_name}, state: {uploaded_file.state.name}")

        # Wait for processing
        while uploaded_file.state.name == "PROCESSING":
            print("  ⏳ Waiting for file to finish processing...")
            time.sleep(2)
            uploaded_file = genai.get_file(uploaded_file.name)

        if uploaded_file.state.name != "ACTIVE":
            print(f"  ❌ Upload failed or not active: {uploaded_file.state.name}")
            return "Failed Extraction"

        # 2. Ask Gemini to extract JSON
        response = model.generate_content([uploaded_file, PROMPT])
        raw_text = response.text.strip() if response.text else ""

        # 3. Clean the text and parse JSON
        cleaned_text = clean_json_text(raw_text)
        try:
            json_data = json.loads(cleaned_text)
        except json.JSONDecodeError:
            print("  ⚠️ Warning: Model output not valid JSON.")
            json_data = {"raw_text": cleaned_text}

        # 4. Return extracted JSON data
        return json_data

    except Exception as e:
        print(f"  ❌ Error while processing {fname}: {e}")
        return "Failed Extraction"

    finally:
        # Always cleanup uploaded file
        if 'uploaded_file' in locals():
            genai.delete_file(uploaded_file.name)
            print("  🗑️ Cleaned up uploaded file.")


# --- Example Usage ---
if __name__ == "__main__":
    file_path = "sample_invoice.pdf"  # replace with your file path
    result = extract_invoice_data(file_path)
    print("\n🔹 Extraction Result:")
    print(result)
