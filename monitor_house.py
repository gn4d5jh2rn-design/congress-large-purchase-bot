import io
import json
import os
import re
import requests

from bs4 import BeautifulSoup
from datetime import datetime
from pypdf import PdfReader


BASE_URL = "https://disclosures-clerk.house.gov"
MAIN_URL = f"{BASE_URL}/FinancialDisclosure/ViewSearch"
SEARCH_URL = f"{BASE_URL}/FinancialDisclosure/ViewMemberSearchResult"

STATE_FILE = "seen_house_filings.json"
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def load_seen():
    if not os.path.exists(STATE_FILE):
        return set()

    with open(STATE_FILE, "r") as f:
        return set(json.load(f))


def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


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

def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID"
        )

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    response = requests.post(
        url,
        data={
            "chat_id": CHAT_ID,
            "text": message
        },
        timeout=30
    )

    response.raise_for_status()
seen = load_seen()
filings = get_all_ptr_filings()

print(f"Found {len(filings)} current non-Pelosi House PTR filings.")
print(f"Already seen: {len(seen)}")

# FIRST RUN:
# Seed all existing filings without sending alerts
if not seen:
    for filing in filings:
        seen.add(filing["id"])

    save_seen(seen)

    print()
    print("Initial setup complete.")
    print(f"Seeded {len(seen)} existing filings.")
    print("No historical alerts were generated.")
    print("Future runs will only process new filings.")

else:
    unseen = [
        filing
        for filing in filings
        if filing["id"] not in seen
    ]

    print()
    print(f"New filings found: {len(unseen)}")

    for filing in unseen:
        print()
        print("NEW PTR:")
        print("Member:", filing["member"])
        print("Filing ID:", filing["id"])

        try:
            text = download_pdf_text(
                filing["url"]
            )

            transactions = parse_transactions(
                text
            )

            purchases = [
                transaction
                for transaction in transactions
                if transaction["transaction_type"] == "P"
            ]

            groups = {}

            for index, transaction in enumerate(purchases):
                ticker_match = re.search(
                    r"\(([A-Z][A-Z0-9.\-]{0,14})\)",
                    transaction["asset"]
                )

                if ticker_match:
                    ticker = ticker_match.group(1)
                    group_key = ("ticker", ticker)
                else:
                    ticker = None
                    group_key = ("single", index)

                if group_key not in groups:
                    groups[group_key] = {
                        "ticker": ticker,
                        "transactions": [],
                        "minimum_total": 0
                    }

                groups[group_key]["transactions"].append(
                    transaction
                )

                groups[group_key]["minimum_total"] += (
                    minimum_amount(transaction["amount"])
                )

            qualifying_groups = [
                group
                for group in groups.values()
                if group["minimum_total"] >= 100001
            ]

            if qualifying_groups:
                print("🚨 QUALIFYING PURCHASE(S):")

                lines = [
                    "🚨 LARGE CONGRESSIONAL PURCHASE",
                    "",
                    f"Member: {filing['member']}",
                    "Chamber: House",
                    f"Filing ID: {filing['id']}",
                    ""
                ]

                for group in qualifying_groups:
                    transactions_in_group = group["transactions"]

                    if group["ticker"]:
                        lines.append(
                            f"Ticker: {group['ticker']}"
                        )

                    if len(transactions_in_group) > 1:
                        lines.append(
                            "Combined minimum disclosed: "
                            f"${group['minimum_total']:,}"
                        )
                        lines.append(
                            "Transactions in filing: "
                            f"{len(transactions_in_group)}"
                        )
                        lines.append("")

                    for transaction in transactions_in_group:
                        print(
                            transaction["asset"],
                            "|",
                            transaction["date"],
                            "|",
                            transaction["amount"]
                        )

                        lines.append(
                            f"Asset: {transaction['asset']}"
                        )
                        lines.append(
                            f"Asset type: "
                            f"{transaction['asset_type']}"
                        )
                        lines.append(
                            f"Trade date: {transaction['date']}"
                        )
                        lines.append(
                            f"Amount: {transaction['amount']}"
                        )
                        lines.append("")

                    lines.append("")

                lines.append(
                    f"PDF: {filing['url']}"
                )

                message = "\n".join(lines)

                send_telegram(message)

                print("Telegram alert sent.")

            else:
                print("No qualifying purchases.")

            seen.add(filing["id"])
        
        except Exception as error:
            print("Error processing filing:", error)
     
    save_seen(seen)
