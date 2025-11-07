
"""
MongoDB connection helper for database module.

This module reads `config/settings.yaml` for Mongo settings but allows
overrides through environment variables `MONGO_URI` and `MONGO_DB`.

Exports:
 - `get_collections()` -> (invoices_collection, embeddings_collection)
 - `get_collection(name)` -> arbitrary collection
 - `get_client()` -> raw pymongo.MongoClient
 - `ping()` -> simple health check
"""
from pathlib import Path
from typing import Any, Tuple
import os

import yaml
from pymongo import MongoClient

# Load config from project root
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"
if not CONFIG_PATH.exists():
    raise FileNotFoundError(f"Config not found: {CONFIG_PATH}")

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CFG = yaml.safe_load(f) or {}

# Allow environment overrides for CI / runtime convenience
MONGO_URI = os.environ.get("MONGO_URI") or CFG.get("mongo", {}).get("uri")
MONGO_DB = os.environ.get("MONGO_DB") or CFG.get("mongo", {}).get("db")

# Defaults (explicit per user's preference)
INVOICES_COLL = CFG.get("mongo", {}).get("collection_invoices", "invoices")
EMBEDDINGS_COLL = CFG.get("mongo", {}).get("collection_embeddings", "invoice_to_embeddings")

if not MONGO_URI:
    raise RuntimeError("MongoDB URI is not configured. Set MONGO_URI env or mongo.uri in config/settings.yaml")
if not MONGO_DB:
    raise RuntimeError("MongoDB database name is not configured. Set MONGO_DB env or mongo.db in config/settings.yaml")

# Create client and collections
_client: MongoClient = MongoClient(MONGO_URI)
_db = _client[MONGO_DB]

invoices_collection = _db[INVOICES_COLL]
embeddings_collection = _db[EMBEDDINGS_COLL]


def get_collections() -> Tuple[Any, Any]:
    """Return (invoices_collection, embeddings_collection)."""
    return invoices_collection, embeddings_collection


def get_collection(name: str):
    """Return a collection by name from the configured database.

    Use this when you need to access other collections in the same DB.
    """
    return _db[name]


def get_client() -> MongoClient:
    """Return the underlying MongoClient instance."""
    return _client


def ping(timeout_ms: int = 2000) -> bool:
    """Return True if the server responds to a ping within timeout_ms."""
    try:
        # serverSelectionTimeoutMS only affects initial server selection; use admin ping
        _client.admin.command("ping")
        return True
    except Exception:
        return False
