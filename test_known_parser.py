import io
import re
import requests
from pypdf import PdfReader


URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20035235.pdf"


response = requests.get(URL, timeout=30)
response.raise_for_status()

reader = PdfReader(io.BytesIO(response.content))

text = "\n".join(
    page.extract_text() or ""
    for page in reader.pages
)

text = text.replace("\x00", "")

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

    # Look at the next few lines for transaction details
    forward = " ".join(lines[i + 1:i + 4])

    match = transaction_pattern.search(forward)

    if not match:
        continue

    transaction_type = match.group(1)
    date = match.group(2)
    notification_date = match.group(3)
    amount = match.group(4)

    transactions.append({
        "asset": asset,
        "asset_type": asset_type,
        "transaction_type": transaction_type,
        "date": date,
        "notification_date": notification_date,
        "amount": amount
    })


print(f"Found {len(transactions)} transactions.\n")


for transaction in transactions:

    print(
        "Transaction type:",
        transaction["transaction_type"]
    )

    print(
        "Asset type:",
        transaction["asset_type"]
    )

    print(
        "Asset:",
        transaction["asset"]
    )

    print(
        "Date:",
        transaction["date"]
    )

    print(
        "Amount:",
        transaction["amount"]
    )

    print()
