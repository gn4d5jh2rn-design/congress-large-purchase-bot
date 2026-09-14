import json
import os
import re
import requests

API_URL = "https://quantengines.com/api/v1/trades/recent/list"
STATE_FILE = "seen_senate_trades.json"

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def trade_id(trade):
    return str(trade["id"])


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
            "limit": 100,
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()
    trades = data["trades"]

    return [
        trade
        for trade in trades
        if str(trade.get("chamber", "")).lower() == "senate"
        and str(trade.get("transaction_type", "")).lower() == "purchase"
    ]


def minimum_amount(amount_range):
    numbers = re.findall(r"\$([\d,]+)", amount_range or "")

    if not numbers:
        return 0

    return int(numbers[0].replace(",", ""))


def main():
    trades = get_senate_purchases()

    print(f"Senate purchases returned: {len(trades)}")

    seen = load_seen()

    # First run: seed current records without sending historical alerts.
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
            amount_range = trade.get("amount_range", "")
            amount_low = minimum_amount(amount_range)

            if amount_low >= 100001:
                message = "\n".join([
                    "🚨 LARGE CONGRESSIONAL PURCHASE",
                    "",
                    f"Member: {trade.get('politician')}",
                    "Chamber: Senate",
                    "",
                    f"Ticker: {trade.get('ticker') or 'N/A'}",
                    f"Asset: {trade.get('company') or 'N/A'}",
                    f"Asset type: {trade.get('asset_type') or 'N/A'}",
                    f"Trade date: {trade.get('transaction_date')}",
                    f"Disclosure date: {trade.get('disclosure_date')}",
                    f"Amount: {trade.get('amount_range')}",
                ])

                send_telegram(message)

                print(
                    "Telegram alert:",
                    trade.get("politician"),
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
