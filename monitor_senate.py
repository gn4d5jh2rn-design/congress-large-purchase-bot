import hashlib
import json
import os
import requests

API_URL = "https://www.bargo.ai/free-apis/congress/v1/trades"

STATE_FILE = "seen_senate_trades.json"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def trade_id(trade):
    raw = "|".join([
        str(trade.get("member", "")),
        str(trade.get("ticker", "")),
        str(trade.get("asset", "")),
        str(trade.get("type", "")),
        str(trade.get("amount_low", "")),
        str(trade.get("amount_high", "")),
        str(trade.get("transaction_date", "")),
        str(trade.get("disclosure_date", "")),
    ])

    return hashlib.sha256(raw.encode()).hexdigest()


def load_seen():
    try:
        with open(STATE_FILE) as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()


def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


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
            "text": message,
        },
        timeout=30,
    )

    response.raise_for_status()


def get_senate_purchases():
    response = requests.get(
        API_URL,
        params={
            "chamber": "Senate",
            "type": "purchase",
            "limit": 100,
        },
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
        },
        timeout=30,
    )

    response.raise_for_status()

    return response.json()["trades"]

def main():
    trades = get_senate_purchases()

    print(f"Senate purchases returned: {len(trades)}")

    seen = load_seen()

    # First run: seed current records without generating alerts.
    if not seen:
        for trade in trades:
            seen.add(trade_id(trade))

        save_seen(seen)

        print("Initial Senate setup complete.")
        print(f"Seeded {len(seen)} existing trades.")
        print("No historical alerts generated.")
        return

    new_count = 0

    for trade in trades:
        identifier = trade_id(trade)

        if identifier in seen:
            continue

        new_count += 1

        try:
            amount_low = trade.get("amount_low") or 0

            if amount_low >= 100001:
                message = "\n".join([
                    "🚨 LARGE CONGRESSIONAL PURCHASE",
                    "",
                    f"Member: {trade.get('member')}",
                    "Chamber: Senate",
                    "",
                    f"Ticker: {trade.get('ticker') or 'N/A'}",
                    f"Asset: {trade.get('asset')}",
                    f"Trade date: {trade.get('transaction_date')}",
                    f"Disclosure date: {trade.get('disclosure_date')}",
                    f"Amount: {trade.get('amount_range')}",
                    "",
                    f"Senate filings: {trade.get('filing_portal')}",
                ])

                send_telegram(message)

                print(
                    "Telegram alert:",
                    trade.get("member"),
                    trade.get("ticker"),
                    trade.get("amount_range"),
                )

            seen.add(identifier)

        except Exception as error:
            print("Error processing trade:", error)
            continue

    save_seen(seen)

    print(f"New Senate trades processed: {new_count}")


if __name__ == "__main__":
    main()
