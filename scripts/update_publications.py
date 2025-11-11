import json
import scholarly
from datetime import datetime

SCHOLAR_ID = "UdIP7WoAAAAJ"  # 你的 Google Scholar ID

print("🔍 Fetching publications from Google Scholar...")

author = scholarly.search_author_id(SCHOLAR_ID)
author = scholarly.fill(author, sections=['publications'])

publications = []
for pub in author['publications']:
    info = scholarly.fill(pub)
    bib = info.get('bib', {})

    publications.append({
        "title": bib.get('title', ''),
        "authors": bib.get('author', ''),
        "year": bib.get('pub_year', ''),
        "journal": bib.get('venue', ''),
        "pages": bib.get('pages', ''),
        "citations": info.get('num_citations', 0),
        "doi": "",
        "pdf": ""
    })

output_path = "data/publications.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(publications, f, ensure_ascii=False, indent=2)

print(f"✅ Updated {len(publications)} publications.")
print(f"📅 Last updated: {datetime.now()}")
