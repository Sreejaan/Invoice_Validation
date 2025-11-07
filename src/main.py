from src.invoice_extractor import extract_invoice_data
from src.GSTValidate import verify_gstin
from src.arthimeticCheck import validate_invoice
from src.InvoiceHSNChecker import process_invoice   

import json
# Example usage
# result = extract_invoice_data("../16.pdf")

import os

def validate_invoices_in_directory(directory = r"E:\Projects\Fintech\new"):
    # Path to directory containing JSON files
    
    file_statuses_pass = 0
    grand_total_pass = 0
    subtotal_pass = 0
    tax_total_pass = 0
    data_extract_pass = 0

    # Loop over all JSON files in the directory
    for filename in os.listdir(directory):
        if filename.lower().endswith(".json"):
            file_path = os.path.join(directory, filename)

            ## Remove this line, did this because it is a larger file
            # if filename == "14.json":
            #     continue

            print(f"\nProcessing file: {filename}")

            # Load JSON
            with open(file_path, "r", encoding="utf-8") as f:
                result = json.load(f)

            # Check result
            if result != "Failed Extraction":
                print("✅ Extraction successful!")
                # Example processing functions
                gst_status = verify_gstin(result["gstin_company"])['status']
                print("GSTIN Verification:", gst_status)
                invoice_validation_status = validate_invoice(result)
                print("Invoice Status:", invoice_validation_status["status"])
                process_invoice_status = process_invoice(result)['status']
                print("Processed Invoice:", process_invoice_status)
                if gst_status and invoice_validation_status and process_invoice_status:
                    file_statuses_pass += 1
                if invoice_validation_status["status_grand_total"]:
                    grand_total_pass += 1
                if invoice_validation_status["status_subtotal"]:
                    subtotal_pass += 1
                if invoice_validation_status["status_tax_total"]:
                    tax_total_pass += 1
                if invoice_validation_status["status_data_missing"]:
                    data_extract_pass += 1
            else:
                print("❌ Extraction failed.")
                

    return {
        "total_files": len(os.listdir(directory)),
        "files_passed": file_statuses_pass,
        "grand_total_passed": grand_total_pass,
        "subtotal_passed": subtotal_pass,
        "tax_total_passed": tax_total_pass,
        "data_extraction_passed": data_extract_pass
    }

