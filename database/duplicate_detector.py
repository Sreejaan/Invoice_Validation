"""
Duplicate detection utilities (exact + fuzzy) for invoices.

Usage:
    python database/duplicate_detector.py path/to/file.json [--insert]

- If --insert is provided, the invoice will be inserted when not an exact duplicate,
  and its embedding will be stored in the embeddings collection.

Defaults:
- fuzzy threshold: 0.88
- model: all-MiniLM-L6-v2

This is designed to be run independently from the loader.
"""
from pathlib import Path
import json
import sys
import logging
from typing import List, Dict, Tuple, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
from connection import get_collections

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

invoices_collection, embeddings_collection = get_collections()
MODEL_NAME = "all-MiniLM-L6-v2"
MODEL = SentenceTransformer(MODEL_NAME)
DEFAULT_THRESHOLD = 0.88


def normalize_for_embedding(doc: Dict) -> Dict:
    """Return a reduced version of the invoice to use for embedding.

    - Keep: vendor GSTIN (gstin_company), item descriptions, item hsn_sac, and
      company/client names/descriptions.
    - Remove: quantities, rates, amounts, invoice_no, invoice_date to reduce noise.
    """
    out = {}
    # vendor
    out["gstin_company"] = doc.get("gstin_company")
    out["company_name"] = doc.get("company_details", {}).get("name") if isinstance(doc.get("company_details"), dict) else None

    # items: keep only description and hsn_sac
    items = []
    for it in doc.get("items", []) or []:
        items.append({
            "description": it.get("description"),
            "hsn_sac": it.get("hsn_sac") or it.get("hsn")
        })
    out["items"] = items

    # summary: keep tax fields? we skip amounts to focus on structure
    out["summary"] = {
        "gst": doc.get("summary", {}).get("gst") if isinstance(doc.get("summary"), dict) else None,
        "cgst": doc.get("summary", {}).get("cgst") if isinstance(doc.get("summary"), dict) else None,
        "sgst": doc.get("summary", {}).get("sgst") if isinstance(doc.get("summary"), dict) else None,
    }

    return out


def compute_embedding_for_doc(doc: Dict) -> List[float]:
    norm = normalize_for_embedding(doc)
    text = json.dumps(norm, sort_keys=True)
    vec = MODEL.encode(text)
    return vec.tolist()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def is_exact_duplicate(doc: Dict) -> Optional[Dict]:
    """Check for exact duplicate on invoice_no + gstin_company + total_amount (null-safe).
    Returns the existing document if found, else None.
    """
    invoice_no = doc.get("invoice_no")
    gstin = doc.get("gstin_company")
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
    if total is not None:
        query["$or"] = [{"summary.total_amount": total}, {"invoice_amount": total}]

    if not query:
        return None

    # perform find_one
    existing = invoices_collection.find_one(query)
    return existing


def find_similar_embeddings(embedding: List[float], top_k: int = 5, threshold: float = DEFAULT_THRESHOLD) -> List[Tuple[str, float]]:
    """Linear scan for similar embeddings stored in embeddings_collection.
    Returns list of tuples (invoice_id, score) sorted by score desc where score >= threshold.
    """
    candidates = []
    for doc in embeddings_collection.find({}, {"invoice_id": 1, "embedding": 1, "file_name": 1}):
        other = doc.get("embedding")
        if not other:
            continue
        try:
            sim = cosine_similarity(embedding, other)
        except Exception:
            continue
        if sim >= threshold:
            candidates.append((str(doc.get("invoice_id")), sim))
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[:top_k]


def process_file(path: Path, insert: bool = False, threshold: float = DEFAULT_THRESHOLD) -> Dict:
    """Process a single invoice JSON file: exact check, (optional) insert, fuzzy check, store embedding.

    Returns a dict with results and candidate matches.
    """
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    result = {"file": str(path), "exact_duplicate": None, "fuzzy_matches": [], "inserted_id": None}

    existing = is_exact_duplicate(doc)
    if existing:
        logging.info("Exact duplicate found, skipping insert")
        result["exact_duplicate"] = str(existing.get("_id"))
        return result

    if insert:
        inserted = invoices_collection.insert_one(doc)
        inserted_id = inserted.inserted_id
        result["inserted_id"] = str(inserted_id)
        logging.info(f"Inserted invoice {path.name} -> _id={inserted_id}")
    else:
        # not inserting; but we still compute embedding for checking
        inserted_id = None

    emb = compute_embedding_for_doc(doc)
    if emb is None:
        logging.warning("Failed to compute embedding")
        return result

    matches = find_similar_embeddings(emb, threshold=threshold)
    result["fuzzy_matches"] = matches

    # store embedding if we inserted (or store anyway but link to None)
    emb_doc = {
        "invoice_id": str(inserted_id) if inserted_id is not None else None,
        "embedding": emb,
        "file_name": path.name,
    }
    embeddings_collection.insert_one(emb_doc)

    return result


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python database/duplicate_detector.py path/to/file.json [--insert] [--threshold=0.88]")
        sys.exit(1)
    p = Path(sys.argv[1])
    insert_flag = "--insert" in sys.argv
    # parse threshold
    threshold = DEFAULT_THRESHOLD
    for arg in sys.argv[2:]:
        if arg.startswith("--threshold="):
            try:
                threshold = float(arg.split("=", 1)[1])
            except Exception:
                pass

    res = process_file(p, insert=insert_flag, threshold=threshold)
    print(json.dumps(res, indent=2))
