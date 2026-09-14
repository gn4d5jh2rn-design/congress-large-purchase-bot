import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://disclosures-clerk.house.gov"
MAIN_URL = f"{BASE_URL}/FinancialDisclosure/ViewSearch"
SEARCH_URL = f"{BASE_URL}/FinancialDisclosure/ViewMemberSearchResult"

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.3 Safari/605.1.15"
    )
})

print("Opening House search page...")

response = session.get(MAIN_URL, timeout=30)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

token_input = soup.find(
    "input",
    {"name": "__RequestVerificationToken"}
)

if not token_input:
    raise RuntimeError("Could not find verification token")

token = token_input.get("value")

print("Searching current-year filings...")

data = {
    "LastName": "",
    "FilingYear": str(datetime.now().year),
    "State": "",
    "District": "",
    "__RequestVerificationToken": token
}

headers = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": MAIN_URL,
    "Origin": BASE_URL
}

response = session.post(
    SEARCH_URL,
    data=data,
    headers=headers,
    timeout=30
)

response.raise_for_status()

print("Response length:", len(response.text))
print()
print(response.text[:2000])
