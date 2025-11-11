import json
import requests
from datetime import datetime
import os
import time

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

# 输出路径
output_path = "data/publications.json"
os.makedirs(os.path.dirname(output_path), exist_ok=True)

# 如果之前有文件，先加载
if os.path.exists(output_path):
    with open(output_path, "r", encoding="utf-8") as f:
        old_data = {pub["title"]: pub for pub in json.load(f)}
else:
    old_data = {}

def fetch_doi_from_crossref(title, authors=""):
    """通过 CrossRef API 根据标题和作者获取 DOI"""
    try:
        first_author = authors.split(",")[0] if authors else ""
        url = f"https://api.crossref.org/works?query.title={title}&query.author={first_author}&rows=1"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            items = res.json().get("message", {}).get("items", [])
            if items:
                return items[0].get("DOI", "")
    except Exception as e:
        print(f"⚠️ DOI fetch failed for '{title}': {e}")
    return ""

publications = []
for i, pub in enumerate(articles, start=1):
    title = pub.get("title", "")
    authors = pub.get("authors", "")
    year = pub.get("year", "")
    journal = pub.get("publication", "")
    citations = pub.get("cited_by", {}).get("value", 0)
    pdf = pub.get("link", "")

    # 如果旧数据中已有 DOI，直接用
    doi = ""
    if title in old_data and old_data[title].get("doi"):
        doi = old_data[title]["doi"]
        print(f"🟢 [{i}/{len(articles)}] Cached DOI found for: {title}")
    else:
        print(f"🔹 [{i}/{len(articles)}] Fetching DOI for: {title}")
        doi = fetch_doi_from_crossref(title, authors)
        time.sleep(1.2)  # 防止 CrossRef 限流

    publications.append({
        "title": title,
        "authors": authors,
        "year": year,
        "journal": journal,
        "pages": "",
        "citations": citations,
        "doi": doi,
        "pdf": pdf
    })

# 保存更新后的 JSON
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(publications, f, ensure_ascii=False, indent=2)

print(f"\n✅ Updated {len(publications)} publications (DOI included where available).")
print(f"📅 Last updated: {datetime.now()}")
