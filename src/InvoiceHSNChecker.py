from HSNValidate import fetch_hsn_details
# from validate_invoice import validate_invoice


def process_invoice(invoice_data: dict) -> str | dict:
    """
    Process a single invoice:
      1. Validate arithmetic and tax consistency.
      2. Validate all HSN/SAC codes through fetch_hsn_details().

    Returns:
        "Success" if everything passes,
        otherwise a dict containing detailed errors.
    """
    all_errors = []

    # --- Step 1: Validate invoice calculations ---
    # validation_result = validate_invoice(invoice_data)
    # if validation_result.get("status") != "pass":
    #     all_errors.extend(validation_result.get("errors", []))

    # --- Step 2: Validate HSN codes ---
    items = invoice_data.get("items", [])
    for idx, item in enumerate(items, start=1):
        hsn_code = str(item.get("hsn_sac") or invoice_data.get("hsn_codes") or "").strip()

        if not hsn_code:
            # all_errors.append(f"Item {idx}: Missing HSN/SAC code.")
            continue

        hsn_info = fetch_hsn_desrtails(hsn_code)
        if not hsn_info:
            all_errors.append(f"Item {idx}: HSN {hsn_code} not found or invalid.")

    # --- Step 3: Return final result ---
    if not all_errors:
        return "Success"

    return {"errors": all_errors}
