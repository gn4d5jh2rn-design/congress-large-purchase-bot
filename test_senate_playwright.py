from playwright.sync_api import sync_playwright

URL = "https://efdsearch.senate.gov/search/home/"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    page = browser.new_page()

    page.goto(URL, wait_until="domcontentloaded", timeout=60000)

    print("Initial title:", page.title())
    print("Initial URL:", page.url)

    checkbox = page.locator(
        'input[name="prohibition_agreement"]'
    )

    checkbox.check()

    page.wait_for_timeout(1000)

    print("After agreement URL:", page.url)
    print(
        "Search page visible:",
        page.get_by_text("Search Options").count() > 0
    )

    browser.close()
