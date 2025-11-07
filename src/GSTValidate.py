import requests

# generate gst api value : https://gstincheck.co.in/    (b6f9782c4777c1da8f0846874eaaebb7)
API_KEY = "c3009ee35ebeeed90a55a2428659864d"

def verify_gstin(gstin_number: str) -> bool:
    """
    Verifies a GSTIN number using the gstincheck.co.in API.
    Returns True if valid, False otherwise.
    """
    url = f"https://sheet.gstincheck.co.in/check/{API_KEY}/{gstin_number}"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            return False

        data = response.json()

        # Check validity flag or equivalent field
        if data.get("flag") is True or data.get("valid") is True:
            return True
        else:
            return False

    except Exception:
        return False
