from invoice_extractor import extract_invoice_data
from GSTValidate import verify_gstin
from arthimeticCheck import validate_invoice
from InvoiceHSNChecker import process_invoice   

import json
# Example usage
result = extract_invoice_data("../16.pdf")

if result != "Failed Extraction":
    print("✅ Extraction successful!")
    with open("16.json", "w") as f:
        json.dump(result, f, indent=4)
    print(verify_gstin(result['gstin_company']))
    print(validate_invoice(result)['status'])
    print(process_invoice(result))
    
else:
    print("❌ Extraction failed.")
