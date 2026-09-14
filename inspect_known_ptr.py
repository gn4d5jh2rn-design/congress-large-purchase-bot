import io
import requests
from pypdf import PdfReader

URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20035235.pdf"

response = requests.get(URL, timeout=30)
response.raise_for_status()

reader = PdfReader(io.BytesIO(response.content))

for page_number, page in enumerate(reader.pages, start=1):
    text = page.extract_text() or ""
    text = text.replace("\x00", "")

    print(f"\n===== PAGE {page_number} =====\n")
    print(text)
