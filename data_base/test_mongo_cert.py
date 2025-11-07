import yaml
from pathlib import Path
import certifi
from pymongo import MongoClient

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

uri = cfg["mongo"]["uri"]
print("Using URI:", uri)
print("Using certifi CA:", certifi.where())

client = MongoClient(uri, tls=True, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=20000)
try:
    print("Pinging...")
    print(client.admin.command("ping"))
    print("Ping succeeded")
except Exception as e:
    print("Ping failed:", repr(e))
    raise
finally:
    client.close()
