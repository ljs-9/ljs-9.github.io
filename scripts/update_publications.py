import json
import requests
from datetime import datetime

SCHOLAR_ID = "UdIP7WoAAAAJ"
URL = f"https://serpapi.com/search.json?engine=google_scholar_author&author_id={SCHOLAR_ID}&api_key=${{ secrets.SERPAPI_KEY }}"

r = requests.get(URL)
data = r.json()

publications = []
for pub in data.get("articles", []):
    publications.append({
        "title": pub.get("title", ""),
        "authors": pub.get("authors", ""),
        "year": pub.get("year", ""),
        "journal": pub.get("publication", ""),
        "pages": "",
        "citations": pub.get("cited_by", {}).get("value", 0),
        "doi": "",
        "pdf": pub.get("link", "")
    })

with open("data/publications.json", "w", encoding="utf-8") as f:
    json.dump(publications, f, ensure_ascii=False, indent=2)

print(f"✅ Updated {len(publications)} publications at {datetime.now()}")
