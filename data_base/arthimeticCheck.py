import json

def clean_number(value):
    """Safely convert string numbers like '1,70,632.00' to float."""
    if value in (None, "", "None"):
        return 0.0
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return 0.0


def validate_invoice(invoice_dict: dict) -> dict:
    """
    Validate invoice dictionary and return a structured summary.
    
    Parameters:
        invoice_dict (dict): Parsed JSON-like invoice data.
    
    Returns:
        dict: {
            "status": "pass" | "fail",
            "errors": [list of error messages],
            "calculated": {
                "subtotal": float,
                "tax_amount": float,
                "grand_total": float
            }
        }
    """
    errors = []

    summary = invoice_dict.get("summary", {})
    items = invoice_dict.get("items", [])

    # --- Item-level calculations ---
    subtotal_sum = 0.0
    calc_subtotal = 0.0
    status_grand_total = True
    status_subtotal = True
    status_tax_total = True
    status_data_extract = True
    expected_total = 0.0
    tax_amount = 0.0
    summary_subtotal = 0.0
    round_off = 0.0
    total_amount = 0.0 
     
    for item in items:
        desc = item.get("description", "Unknown Item")
        qty = clean_number(item.get("quantity"))
        rate = clean_number(item.get("rate"))
        amount = clean_number(item.get("amount"))

        subtotal_sum += amount

        # Handle missing qty/rate
        if qty == 0 and rate == 0 and amount != 0:
            qty = 1.0
            rate = amount

        if qty == 0 or rate == 0 or amount == 0:
            errors.append(f"Missing numeric value in item: {desc}")
            status_data_extract = False
            continue

        expected_amount = round(qty * rate, 2)
        calc_subtotal += expected_amount

        if abs(expected_amount - amount) > 0.01:
            errors.append(
                f"Item '{desc}' mismatch: {qty}×{rate} = {expected_amount:.2f}, found {amount:.2f}"
            )
            

    if calc_subtotal == 0:
        calc_subtotal = subtotal_sum

    # --- Subtotal validation ---
    summary_subtotal = clean_number(summary.get("subtotal"))
    if summary_subtotal and abs(summary_subtotal - calc_subtotal) > 0.01:
        errors.append(f"Subtotal mismatch: expected {calc_subtotal:.2f}, found {summary_subtotal:.2f}")
        status_subtotal = False
    else:
        summary_subtotal = calc_subtotal

    # --- Tax calculation ---
    cgst = clean_number(summary.get("cgst"))
    sgst = clean_number(summary.get("sgst"))
    igst = clean_number(summary.get("igst"))
    tax_amount = clean_number(summary.get("tax_amount"))

    # Case 1: values are amounts (usually >50 means not percentage)
    if cgst > 50 or sgst > 50 or igst > 50:
        total_tax_calc = cgst + sgst + igst
        if abs(total_tax_calc - tax_amount) > 0.01:
            errors.append(
                f"Tax total mismatch: CGST+SGST+IGST={total_tax_calc:.2f}, tax_amount={tax_amount:.2f}"
            )
            status_tax_total = False
        tax_amount = total_tax_calc
    else:
        # Case 2: values are percentages
        cgst_val = summary_subtotal * (cgst / 100)
        sgst_val = summary_subtotal * (sgst / 100)
        igst_val = summary_subtotal * (igst / 100)
        tax_amount = cgst_val + sgst_val + igst_val

    # --- Grand total check ---
    total_amount = clean_number(summary.get("total_amount"))
    round_off = clean_number(summary.get("round_off"))

    expected_total = round(summary_subtotal + tax_amount + round_off, 2)
    if total_amount and abs(expected_total - total_amount) > 1:
        errors.append(f"Grand total mismatch: expected {expected_total:.2f}, found {total_amount:.2f}")
        status_grand_total = False

    # --- Result ---
    result = {
        "status": True if not errors else False,
        "errors": errors,
        "calculated": {
            "subtotal": round(summary_subtotal, 2),
            "tax_amount": round(tax_amount, 2),
            "grand_total": round(expected_total, 2)
        },
        "status_grand_total":status_grand_total,
        "status_subtotal":status_subtotal,
        "status_tax_total":status_tax_total,
        "status_data_missing":status_data_extract
    }
    return result


# ✅ Example usage
if __name__ == "__main__":
    invoice_data = {
        "summary": {
            "subtotal": "1,00,000.00",
            "cgst": "9",
            "sgst": "9",
            "igst": "0",
            "tax_amount": "18,000.00",
            "round_off": "0",
            "total_amount": "1,18,000.00"
        },
        "items": [
            {"description": "Product A", "quantity": "10", "rate": "10000", "amount": "100000"}
        ]
    }

    result = validate_invoice(invoice_data)
    print(json.dumps(result, indent=4))
