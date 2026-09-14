import requests
from bs4 import BeautifulSoup

HOME_URL = "https://efdsearch.senate.gov/search/home/"
SEARCH_URL = "https://efdsearch.senate.gov/search/"

session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
})

response = session.get(HOME_URL, timeout=30)
response.raise_for_status()

soup = BeautifulSoup(response.text, "html.parser")

token = soup.find("input", {"name": "csrfmiddlewaretoken"})

if not token:
    raise RuntimeError("Could not find Senate CSRF token.")

csrf = token["value"]

response = session.post(
    HOME_URL,
    data={
        "csrfmiddlewaretoken": csrf,
        "prohibition_agreement": "1",
    },
    headers={
        "Referer": HOME_URL,
    },
    timeout=30,
)

response.raise_for_status()

search = session.get(SEARCH_URL, timeout=30)
search.raise_for_status()

print("Final URL:", search.url)
print("Status:", search.status_code)
print("Senate search page reached:", "Search Reports" in search.text)
