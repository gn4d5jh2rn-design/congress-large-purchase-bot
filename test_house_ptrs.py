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

soup = BeautifulSoup(response.text, "html.parser")

ptr_filings = []

for row in soup.find_all("tr"):
    cells = row.find_all("td")

    if len(cells) < 4:
        continue

    filing_type = cells[3].get_text(strip=True)

    if "PTR" not in filing_type:
        continue

    link = cells[0].find("a")

    if not link:
        continue

    member_name = link.get_text(" ", strip=True)
    href = link.get("href")

    pdf_url = BASE_URL + "/" + href.lstrip("/")

    filing_id = pdf_url.split("/")[-1].replace(".pdf", "")

    ptr_filings.append({
        "member": member_name,
        "id": filing_id,
        "type": filing_type,
        "url": pdf_url
    })

print(f"Found {len(ptr_filings)} PTR filings.\n")

for filing in ptr_filings[:20]:
    print(
        filing["member"],
        "|",
        filing["id"],
        "|",
        filing["type"]
    )
