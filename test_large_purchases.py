import io
import re
import requests

from bs4 import BeautifulSoup
from datetime import datetime
from pypdf import PdfReader


BASE_URL = "https://disclosures-clerk.house.gov"
MAIN_URL = f"{BASE_URL}/FinancialDisclosure/ViewSearch"
SEARCH_URL = f"{BASE_URL}/FinancialDisclosure/ViewMemberSearchResult"


def get_all_ptr_filings():
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

    filings = []

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

        if "Pelosi" in member_name:
            continue

        href = link.get("href")

        pdf_url = BASE_URL + "/" + href.lstrip("/")
        filing_id = pdf_url.split("/")[-1].replace(".pdf", "")

        filings.append({
            "member": member_name,
            "id": filing_id,
            "type": filing_type,
            "url": pdf_url
        })

    return filings


def download_pdf_text(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    reader = PdfReader(io.BytesIO(response.content))

    text = "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )

    return text.replace("\x00", "")


def minimum_amount(amount):
    numbers = re.findall(r"\$([\d,]+)", amount)

    if not numbers:
        return 0

    first = int(numbers[0].replace(",", ""))

    if "Over" in amount:
        return first + 1

    return first


def parse_transactions(text):
    lines = [
        " ".join(line.split())
        for line in text.splitlines()
        if line.strip()
    ]

    asset_type_pattern = re.compile(
        r"\[([A-Z]{2})\]$"
    )

    transaction_pattern = re.compile(
        r"(P|S|E)\s+"
        r"(\d{2}/\d{2}/\d{4})\s+"
        r"(\d{2}/\d{2}/\d{4})\s+"
        r"(\$[\d,]+\s*-\s*\$[\d,]+|Over\s+\$[\d,]+)"
    )

    transactions = []

    for i, line in enumerate(lines):
        asset_type_match = asset_type_pattern.search(line)

        if not asset_type_match:
            continue

        asset_type = asset_type_match.group(1)

        asset_lines = [
            re.sub(r"\s*\[[A-Z]{2}\]$", "", line)
        ]

        j = i - 1

        while j >= 0:
            previous = lines[j]

            if (
                previous.startswith("D:")
                or previous.startswith("S O:")
                or previous.startswith("F S:")
                or previous.startswith("ID Owner Asset")
                or re.match(r"^[PSE]\s+\d{2}/\d{2}/\d{4}", previous)
                or previous.startswith("$")
            ):
                break

            asset_lines.insert(0, previous)
            j -= 1

        asset = " ".join(asset_lines).strip()

        forward = " ".join(lines[i + 1:i + 4])

        match = transaction_pattern.search(forward)

        if not match:
            continue

        transactions.append({
            "asset": asset,
            "asset_type": asset_type,
            "transaction_type": match.group(1),
            "date": match.group(2),
            "notification_date": match.group(3),
            "amount": match.group(4)
        })

    return transactions


filings = get_all_ptr_filings()

print(f"Found {len(filings)} non-Pelosi PTR filings.")
print("Searching for the first 3 qualifying purchases...\n")

found = 0
checked = 0

for filing in filings[:100]:
    checked += 1

    try:
        text = download_pdf_text(
            filing["url"]
        )

        transactions = parse_transactions(
            text
        )

        for transaction in transactions:
            if (
                transaction["transaction_type"] == "P"
                and minimum_amount(transaction["amount"]) >= 100001
            ):
                print("🚨 QUALIFYING PURCHASE")
                print("Member:", filing["member"])
                print("Filing ID:", filing["id"])
                print("Asset:", transaction["asset"])
                print("Asset type:", transaction["asset_type"])
                print("Date:", transaction["date"])
                print("Amount:", transaction["amount"])
                print("PDF:", filing["url"])
                print()

                found += 1

                if found >= 3:
                    break

        if found >= 3:
            break

    except Exception as error:
        print(
            f"Error reading {filing['id']}:",
            error
        )

print()
print(f"Checked {checked} filings.")
print(f"Found {found} qualifying purchases.")
