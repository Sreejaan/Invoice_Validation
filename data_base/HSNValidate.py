from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
import pandas as pd
import time


def fetch_hsn_details(hsn_value):
    # Setup headless Chrome
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    driver.get("https://eztax.in/gst/gst-rate-hsn-sac-finder")

    # Wait for page to load
    time.sleep(1)

    # Locate the input field
    search_box = driver.find_element(By.ID, "i5i")

    # Enter search term, e.g. "milk"
    search_term = hsn_value
    search_box.send_keys(search_term)
    time.sleep(1)  # wait for results to appear

    # Extract table
    rows = driver.find_elements(By.CSS_SELECTOR, "table tbody tr")
    

    data = []
    for row in rows:
        cols = [td.text.strip() for td in row.find_elements(By.TAG_NAME, "td")]
        data.append(cols)

    # Convert to DataFrame
    columns = ["#", "HSN", "Description", "IGST", "CGST", "SGST", "Condition"]
    df = pd.DataFrame(data, columns=columns)

    result = df[df["HSN"] == str(hsn_value)]
    driver.quit()
    # Display the record if found
    if not result.empty:
        description = result.iloc[0]["Description"]
        igst = result.iloc[0]["IGST"]
        cgst = result.iloc[0]["CGST"]
        sgst = result.iloc[0]["SGST"]

        # print("HSN found:")
        # print(description)
        # print(igst)
        # print(cgst)
        # print(sgst)
        return {
            "description": description,
            "igst": igst,
            "cgst": cgst,
            "sgst": sgst
        }
    else:
        # print("HSN not found in DataFrame.")
        return None

# print(fetch_hsn_details(997314))


