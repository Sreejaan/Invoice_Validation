
"""
MongoDB connection helper for database module
"""
from pymongo import MongoClient
import yaml
from pathlib import Path

# Load config from project root
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"
with open(CONFIG_PATH) as f:
    CFG = yaml.safe_load(f)


_client = MongoClient(CFG["mongo"]["uri"])
db = _client[CFG["mongo"]["db"]]
invoices_collection = db[CFG["mongo"]["collection_invoices"]]
embeddings_collection = db[CFG["mongo"]["collection_embeddings"]]

def get_collections():
    """Return both invoices and embeddings collections."""
    return invoices_collection, embeddings_collection
