import requests

# generate gst api value : https://gstincheck.co.in/    (b6f9782c4777c1da8f0846874eaaebb7)
API_KEY = "a3089ddefceeae1487fab782919bad03"

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
        print("Response",data)
        # Check validity flag or equivalent field
        if data.get("flag") is True or data.get("valid") is True:
            return {"status":True}
        else:
            return {"status":False} 

    except Exception:
        return {"status":False} 
