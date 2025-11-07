"""Small DB-only utilities shared between loader and duplicate detector.

Keep lightweight functions here so importing this module does not load ML models.
"""
from typing import Optional, Dict
from connection import get_collections

invoices_collection, embeddings_collection = get_collections()


def is_exact_duplicate(doc: Dict) -> Optional[Dict]:
    """Check for exact duplicate on invoice_no + gstin_company + invoice_date + total_amount (null-safe).
    Returns the existing document if found, else None.
    """
    invoice_no = doc.get("invoice_no")
    gstin = doc.get("gstin_company")
    invoice_date = doc.get("invoice_date")
    # prefer summary total_amount, fallback to invoice_amount
    total = None
    if isinstance(doc.get("summary"), dict):
        total = doc["summary"].get("total_amount")
    if total is None:
        total = doc.get("invoice_amount")

    query = {}
    if invoice_no:
        query["invoice_no"] = invoice_no
    if gstin:
        query["gstin_company"] = gstin
    if invoice_date:
        query["invoice_date"] = invoice_date
    if total is not None:
        query["$or"] = [{"summary.total_amount": total}, {"invoice_amount": total}]

    if not query:
        return None

    return invoices_collection.find_one(query)
