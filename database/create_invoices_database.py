#!/usr/bin/env python3
"""
Script to create MongoDB database with strict JSON schema validation
for Indian GST invoices (as per your spec).
"""

from pymongo import MongoClient
from pymongo.errors import CollectionInvalid, OperationFailure
import sys

# ==============================
# CONFIGURATION
# ==============================
MONGODB_URI = "mongodb://localhost:27017"  # Update if auth enabled
DB_NAME = "invoices_db"
COLLECTION_NAME = "invoices"

# ==============================
# JSON SCHEMA (Strict Validation)
# ==============================
INVOICE_SCHEMA = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["Description"],
        "properties": {
            "Description": {
                "bsonType": ["string"],
                "description": "Description is required and must be a string"
            },
            "invoice_no": {
                "bsonType": ["string", "null"],
                "description": "invoice_no must be string or null"
            },
            "invoice_date": {
                "bsonType": ["string", "null"],
                "pattern": "^[0-3]?[0-9]-(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-[0-9]{2}$",
                "description": "invoice_date must be in DD-MMM-YY format or null"
            },
            "invoice_amount": {
                "bsonType": ["double", "int", "null"],
                "description": "invoice_amount must be number or null"
            },
            "gstin_company": {
                "bsonType": ["string", "null"],
                "pattern": "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$",
                "description": "gstin_company must be valid 15-char GSTIN or null"
            },
            "gstin_client": {
                "bsonType": ["string", "null"],
                "pattern": "^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$",
                "description": "gstin_client must be valid 15-char GSTIN or null"
            },
            "hsn_codes": {
                "bsonType": ["string", "null"],
                "description": "hsn_codes must be string or null"
            },
            "items": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "properties": {
                        "description": {"bsonType": ["string", "null"]},
                        "hsn_sac": {"bsonType": ["string", "null"]},
                        "quantity": {"bsonType": ["double", "int", "null"]},
                        "rate": {"bsonType": ["double", "int", "null"]},
                        "amount": {"bsonType": ["double", "int", "null"]},
                        "cgst": {"bsonType": ["double", "int", "null"]},
                        "sgst": {"bsonType": ["double", "int", "null"]},
                        "igst": {"bsonType": ["double", "int", "null"]},
                        "total": {"bsonType": ["double", "int", "null"]}
                    }
                }
            },
            "summary": {
                "bsonType": "object",
                "properties": {
                    "subtotal": {"bsonType": ["double", "int", "null"]},
                    "tax_amount": {"bsonType": ["double", "int", "null"]},
                    "total_amount": {"bsonType": ["double", "int", "null"]},
                    "gst": {"bsonType": ["double", "int", "null"]},
                    "cgst": {"bsonType": ["double", "int", "null"]},
                    "sgst": {"bsonType": ["double", "int", "null"]},
                    "igst": {"bsonType": ["double", "int", "null"]}
                }
            }
        }
    }
}

# ==============================
# MAIN SCRIPT
# ==============================
def main():
    # Connect to MongoDB
    try:
        client = MongoClient(MONGODB_URI)
        print("Connected to MongoDB")
    except Exception as e:
        print(f"Failed to connect: {e}")
        sys.exit(1)

    db = client[DB_NAME]

    # Drop collection if exists (for clean re-run)
    if COLLECTION_NAME in db.list_collection_names():
        db[COLLECTION_NAME].drop()
        print(f"Dropped existing collection: {COLLECTION_NAME}")

    # Create collection with schema validation
    try:
        db.create_collection(
            COLLECTION_NAME,
            validator=INVOICE_SCHEMA,
            validationLevel="strict",
            validationAction="warning"
        )
        print(f"Collection '{COLLECTION_NAME}' created with schema validation")
    except CollectionInvalid:
        print("Collection already exists with schema")
    except OperationFailure as e:
        print(f"Schema validation error: {e}")
        sys.exit(1)

    # Insert sample valid document
    sample_invoice = {
        "Description": "Professional IT Services - June 2025",
        "invoice_no": "INV-2025-06-001",
        "invoice_date": "15-Jun-25",
        "invoice_amount": 11800.00,
        "gstin_company": "24AAACH7403R1ZV",
        "gstin_client": "24AABCU9603R1ZP",
        "hsn_codes": "998314, 998315",
        "items": [
            {
                "description": "Software Development",
                "hsn_sac": "998314",
                "quantity": 40,
                "rate": 250.00,
                "amount": 10000.00,
                "cgst": 900.00,
                "sgst": 900.00,
                "igst": None,
                "total": 11800.00
            }
        ],
        "summary": {
            "subtotal": 10000.00,
            "tax_amount": 1800.00,
            "total_amount": 11800.00,
            "gst": 1800.00,
            "cgst": 900.00,
            "sgst": 900.00,
            "igst": None
        }
    }

    try:
        result = db[COLLECTION_NAME].insert_one(sample_invoice)
        print(f"Sample invoice inserted with ID: {result.inserted_id}")
    except Exception as e:
        print(f"Failed to insert sample: {e}")

    # Final confirmation
    count = db[COLLECTION_NAME].count_documents({})
    print(f"\nDatabase '{DB_NAME}' is ready with {count} invoice(s).")
    print("Open MongoDB Compass → Connect to: mongodb://localhost:27017")
    print(f"→ Select database: {DB_NAME} → Collection: {COLLECTION_NAME}")

if __name__ == "__main__":
    main()