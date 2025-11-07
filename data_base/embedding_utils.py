"""Embedding and fuzzy-duplicate utilities.

Provides lazy model loading and functions used across the project:
- normalize_for_embedding
- compute_embedding_for_doc
- cosine_similarity
- find_similar_embeddings
- process_invoice (DB insert + embedding + fuzzy search)

This module imports the DB connection utilities but loads the SentenceTransformer model lazily
so importing this module is cheap until an embedding is actually computed.
"""
from typing import List, Tuple, Dict, Optional
import json
import logging
import numpy as np
from sentence_transformers import SentenceTransformer
from connection import get_collections
from duplicate_utils import is_exact_duplicate

logging.getLogger(__name__).addHandler(logging.NullHandler())

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
DEFAULT_THRESHOLD = 0.95

# lazy model cache
_MODEL: Optional[SentenceTransformer] = None


def get_model(name: str = DEFAULT_MODEL_NAME) -> SentenceTransformer:
    global _MODEL
    if _MODEL is None:
        _MODEL = SentenceTransformer(name)
    return _MODEL


def normalize_for_embedding(doc: Dict) -> Dict:
    out = {}
    out["gstin_company"] = doc.get("gstin_company")
    out["company_name"] = doc.get("company_details", {}).get("name") if isinstance(doc.get("company_details"), dict) else None

    items = []
    for it in doc.get("items", []) or []:
        items.append({
            "description": it.get("description"),
            "hsn_sac": it.get("hsn_sac") or it.get("hsn")
        })
    out["items"] = items

    out["summary"] = {
        "gst": doc.get("summary", {}).get("gst") if isinstance(doc.get("summary"), dict) else None,
        "cgst": doc.get("summary", {}).get("cgst") if isinstance(doc.get("summary"), dict) else None,
        "sgst": doc.get("summary", {}).get("sgst") if isinstance(doc.get("summary"), dict) else None,
    }

    return out


def compute_embedding_for_doc(doc: Dict) -> List[float]:
    # drop _id if present
    try:
        doc = dict(doc)
        if "_id" in doc:
            doc.pop("_id")
        # normalize
        norm = normalize_for_embedding(doc)
        text = json.dumps(norm, sort_keys=True) # consistent serialization
        model = get_model() # default model
        vec = model.encode(text) 
        return vec.tolist()
    except Exception as e:
        logging.error(f"Error computing embedding: {e}")
        return []


def cosine_similarity(a: List[float], b: List[float]) -> float:
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def find_similar_embeddings(embedding: List[float], top_k: int = 5, threshold: float = DEFAULT_THRESHOLD) -> List[Tuple[str, float]]:
    invoices_collection, embeddings_collection = get_collections()
    candidates: List[Tuple[str, float]] = []
    for doc in embeddings_collection.find({}, {"invoice_id": 1, "embedding": 1, "file_name": 1}):
        other = doc.get("embedding")
        if not other:
            continue
        try:
            sim = cosine_similarity(embedding, other)
        except Exception:
            continue
        if sim >= threshold:
            candidates.append((str(doc.get("file_name")), sim))
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[:top_k]


def process_invoice(doc: Dict, insert: bool = False, threshold: float = DEFAULT_THRESHOLD, file_name: Optional[str] = None) -> Dict:
    """Process an invoice dict: exact duplicate check, optional insert, compute embedding, fuzzy search, store embedding."""
    invoices_collection, embeddings_collection = get_collections()

    result = {"file": file_name or "<in-memory>", "exact_duplicate": None, "fuzzy_matches": [], "inserted_id": None}

    existing = is_exact_duplicate(doc)
    if existing:
        logging.info("Exact duplicate found, skipping insert")
        result["exact_duplicate"] = str(existing.get("_id"))
        return result

    inserted_id = None
    if insert:
        inserted = invoices_collection.insert_one(doc)
        inserted_id = inserted.inserted_id
        result["inserted_id"] = str(inserted_id)
        logging.info(f"Inserted invoice {file_name or '<doc>'} -> _id={inserted_id}")

    emb = compute_embedding_for_doc(doc)
    if emb is None:
        logging.warning("Failed to compute embedding")
        return result

    matches = find_similar_embeddings(emb, threshold=threshold)
    result["fuzzy_matches"] = matches

    emb_doc = {
        "invoice_id": str(inserted_id) if inserted_id is not None else None,
        "embedding": emb,
        "file_name": file_name,
    }
    embeddings_collection.insert_one(emb_doc)

    return result
