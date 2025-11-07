"""
Bulk load all JSON files in database/data into MongoDB (no transformation).
"""


import json
from typing import Dict, Optional
import logging
from pathlib import Path
from pymongo.errors import BulkWriteError
from connection import get_collections
from duplicate_utils import is_exact_duplicate
from embedding_utils import compute_embedding_for_doc as compute_embedding, find_similar_embeddings
import sys

DATA_DIR = Path(__file__).resolve().parent / "data"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
invoices_collection, embeddings_collection = get_collections()
print("Using invoices collection:", invoices_collection.name)
print("Using embeddings collection:", embeddings_collection.name)

def insert_one_json(file_path):
    """Insert a single JSON file into MongoDB and its embedding into invoice_to_embeddings."""
    try:
        # accept either Path or string
        file_path = Path(file_path)
        with open(file_path, "r", encoding="utf-8") as f:
            doc = json.load(f)

        # Check exact duplicate before inserting
        existing = is_exact_duplicate(doc)
        if existing:
            logging.info(f"Exact duplicate found for {file_path.name}, existing _id={existing.get('_id')}. Skipping insert.")
            print(f"Duplicate: {file_path} -> existing_id={existing.get('_id')}")
            return

        # Compute embedding and check fuzzy similarity against stored embeddings
        emb = compute_embedding(doc)
        if emb:
            matches = find_similar_embeddings(emb)
            if matches:
                logging.info(f"Fuzzy matches found for {file_path.name}: {matches}. Skipping insert.")
                print(f"FuzzyDuplicate: {file_path} -> matches={matches}")
                return

        result = invoices_collection.insert_one(doc)
        logging.info(f"Inserted {file_path} as _id={result.inserted_id}")
        # Store embedding
        print("ResultID", str(result.inserted_id))
        emb_doc = {
            "invoice_id": str(result.inserted_id),  # always store as string for serialization
            "embedding": emb,
            "file_name": file_path.name
        }
        embeddings_collection.insert_one(emb_doc)
        logging.info(f"Stored embedding for {file_path.name}")
    except Exception as e:
        logging.error(f"Error inserting {file_path}: {e}")


def insert_doc(doc: Dict, file_name: Optional[str] = None) -> Dict:
    """Insert a Python dict representing an invoice into the DB.

    This mirrors the behavior of `insert_one_json`:
    - performs an exact-duplicate check
    - inserts the document if no duplicate
    - computes and stores the embedding linking to the inserted id

    Returns a dict with keys: `inserted_id` (str) or `duplicate_id` (str) and `error` if any.
    """
    try:
        # Check exact duplicate first
        existing = is_exact_duplicate(doc)
        if existing:
            logging.info(f"Exact duplicate found for in-memory doc, existing _id={existing.get('_id')}. Skipping insert.")
            return {"duplicate_id": str(existing.get("_id")), "status":"420"}
        
        if file_name is None:
            file_name = doc["invoice_number"] +';'+ doc["invoiced_date"]

        # Compute embedding and run fuzzy similarity search before inserting
        emb = compute_embedding(doc)
        if emb:
            matches = find_similar_embeddings(emb)
            if matches:
                logging.info(f"Fuzzy matches found for in-memory doc: {matches}. Skipping insert.")
                return {"fuzzy_matches": matches, "status": "420"}

        result = invoices_collection.insert_one(doc)
        inserted_id = result.inserted_id
        # compute and store embedding
        emb = compute_embedding(doc)
        emb_doc = {"invoice_id": str(inserted_id), "embedding": emb, "file_name": file_name}
        embeddings_collection.insert_one(emb_doc)
        logging.info(f"Inserted in-memory doc -> _id={inserted_id}")
        return {"status": str(200)}
    except Exception as e:
        logging.error(f"Error inserting in-memory doc: {e}")
        return {"error": str(e)}

def insert_all_jsons():
    """Bulk insert all JSON files in DATA_DIR into MongoDB and their embeddings into invoice_to_embeddings."""
    json_files = list(DATA_DIR.glob("*.json"))
    if not json_files:
        logging.warning(f"No JSON files found in {DATA_DIR}")
        return

    operations = []
    emb_operations = []
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                doc = json.load(f)
            # No invoice_key needed
            # Check for exact duplicate; if duplicate, skip and notify
            existing = is_exact_duplicate(doc)
            if existing:
                logging.info(f"Exact duplicate detected for {file_path.name}; skipping insertion (existing _id={existing.get('_id')})")
                print(f"Duplicate: {file_path} -> existing_id={existing.get('_id')}")
                continue

            # Compute embedding and check for fuzzy matches; skip if similar
            emb = compute_embedding(doc)
            if emb:
                matches = find_similar_embeddings(emb)
                if matches:
                    logging.info(f"Fuzzy duplicate detected for {file_path.name}; skipping insertion. Matches: {matches}")
                    print(f"FuzzyDuplicate: {file_path} -> matches={matches}")
                    continue
            operations.append((doc, file_path))
            logging.info(f"Loaded {file_path.name}")
        except Exception as e:
            logging.error(f"Error reading {file_path.name}: {e}")

    if not operations:
        logging.info("No valid documents to insert.")
        return

    try:
        # operations is now list of (doc, file_path)
        docs_to_insert = [t[0] for t in operations]
        paths_for_docs = [t[1] for t in operations]
        if not docs_to_insert:
            logging.info("No new documents to insert after duplicate filtering.")
            return

        result = invoices_collection.insert_many(docs_to_insert, ordered=False)
        logging.info(f"Inserted {len(result.inserted_ids)} documents into MongoDB.")
        # Store embeddings for the inserted docs
        for doc, file_path, inserted_id in zip(docs_to_insert, paths_for_docs, result.inserted_ids):
            emb = compute_embedding(doc)
            invoice_id_str = str(inserted_id)
            emb_doc = {
                "invoice_id": invoice_id_str,
                "embedding": emb, 
                "file_name": file_path.name
            }
            emb_operations.append(emb_doc)
        if emb_operations:
            embeddings_collection.insert_many(emb_operations, ordered=False)
            logging.info(f"Stored {len(emb_operations)} embeddings in invoice_to_embeddings.")
    except BulkWriteError as bwe:
        logging.warning(f"Partial import: {bwe.details}")
        logging.info(f"Inserted: {bwe.details.get('nInserted', 0)}")
    except Exception as e:
        logging.error(f"Insert failed: {e}")

if __name__ == "__main__":
    
    # Convert dict to json and insert
    # Example in-memory invoice document (converted from JSON -> Python dict)
    # Note: JSON `null` must be Python `None`.
    
    if len(sys.argv) == 2:
        # Usage: python load_jsons.py path/to/file.json
        print(f"Loading single JSON file: {sys.argv[1]}\n")
        insert_one_json(sys.argv[1])
    else:
        # Usage: python load_jsons.py (bulk insert)
        print("SKIP: Loading all JSON files in data directory.\n")
        # insert_all_jsons()
