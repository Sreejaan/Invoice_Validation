"""
Bulk load all JSON files in database/data into MongoDB (no transformation).
"""


import json
import logging
from pathlib import Path
from pymongo.errors import BulkWriteError
from connection import get_collections
import sys
from sentence_transformers import SentenceTransformer

DATA_DIR = Path(__file__).resolve().parent / "data"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
invoices_collection, embeddings_collection = get_collections()
model = SentenceTransformer("all-MiniLM-L6-v2")

def compute_embedding(doc):
    try:
        # Remove '_id' if present, without error
        doc = dict(doc)  # make a copy to avoid mutating the original
        doc.pop('_id', None)
        text = json.dumps(doc, sort_keys=True)
        return model.encode(text).tolist()
    except Exception as e:
        logging.error(f"Error computing embedding: {e}")
        return None

    

def insert_one_json(file_path):
    """Insert a single JSON file into MongoDB and its embedding into invoice_to_embeddings."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            doc = json.load(f)
        result = invoices_collection.insert_one(doc)
        logging.info(f"Inserted {file_path} as _id={result.inserted_id}")
        # Store embedding
        emb = compute_embedding(doc)
        print("ResultID", str(result.inserted_id))
        emb_doc = {
            "invoice_id": str(result.inserted_id),  # always store as string for serialization
            "embedding": emb
        }
        embeddings_collection.insert_one(emb_doc)
        logging.info(f"Stored embedding for {file_path.name}")
    except Exception as e:
        logging.error(f"Error inserting {file_path}: {e}")

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
            operations.append(doc)
            logging.info(f"Loaded {file_path.name}")
        except Exception as e:
            logging.error(f"Error reading {file_path.name}: {e}")

    if not operations:
        logging.info("No valid documents to insert.")
        return

    try:
        result = invoices_collection.insert_many(operations, ordered=False)
        logging.info(f"Inserted {len(result.inserted_ids)} documents into MongoDB.")
        # Store embeddings for all
        for doc, file_path, inserted_id in zip(operations, json_files, result.inserted_ids):
            emb = compute_embedding(doc)
            invoice_id_str = str(inserted_id)
            emb_doc = {
                "invoice_id": invoice_id_str,
                "embedding": emb
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
    if len(sys.argv) == 2:
        # Usage: python load_jsons.py path/to/file.json
        insert_one_json(sys.argv[1])
    else:
        # Usage: python load_jsons.py (bulk insert)
        insert_all_jsons()
