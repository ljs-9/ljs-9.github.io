import json
import requests
from datetime import datetime
import os

# Google Scholar ID
SCHOLAR_ID = "UdIP7WoAAAAJ"

# 从 GitHub Secret 读取 SerpAPI key
API_KEY = os.getenv("SERPAPI_KEY")

if not API_KEY:
    raise ValueError("❌ Missing SERPAPI_KEY. Please add it as a GitHub Secret.")

URL = f"https://serpapi.com/search.json?engine=google_scholar_author&author_id={SCHOLAR_ID}&api_key={API_KEY}"

print("🔍 Fetching publications from SerpAPI...")

r = requests.get(URL)
if r.status_code != 200:
    raise Exception(f"❌ API request failed: {r.status_code} - {r.text}")

data = r.json()
articles = data.get("articles", [])

publications = []
for pub in articles:
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

# 输出路径
output_path = "data/publications.json"
os.makedirs(os.path.dirname(output_path), exist_ok=True)

# 保存为 JSON 文件
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(publications, f, ensure_ascii=False, indent=2)

print(f"✅ Updated {len(publications)} publications.")
print(f"📅 Last updated: {datetime.now()}")
