import requests

# Replace this with your actual AppyFlow key_secret
KEY_SECRET = "6iD06RSjjvNkO6RlT1oIw0CGll22"

def verify_gstin(gstin_number: str) -> dict:
    """
    Verifies a GSTIN number using the AppyFlow GST Verification API.
    Returns {'status': True} if valid, else {'status': False}.
    """
    url = "https://appyflow.in/api/verifyGST"
    params = {
        "key_secret": KEY_SECRET,
        "gstNo": gstin_number
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            return {"status": False}

        data = response.json()

        # AppyFlow returns 'error': False for valid GSTIN
        if not data.get("error", True):
            return {"status": True, "data": data.get("taxpayerInfo", {})}
        else:
            return {"status": False}

    except Exception:
        return {"status": False}
