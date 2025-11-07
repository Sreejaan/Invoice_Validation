"""
MongoDB connection helper
"""
from pymongo import MongoClient
import yaml

with open("../config/settings.yaml") as f:
    CFG = yaml.safe_load(f)

_client = MongoClient(CFG["mongo"]["uri"])
db = _client[CFG["mongo"]["db"]]
collection = db[CFG["mongo"]["collection"]]

def get_collection():
    return collection
