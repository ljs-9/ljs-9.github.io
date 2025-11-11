import json
import requests
from datetime import datetime
import os
import time
import re

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

# 加载旧数据（缓存）
if os.path.exists(output_path):
    with open(output_path, "r", encoding="utf-8") as f:
        old_data = {pub["title"]: pub for pub in json.load(f)}
else:
    old_data = {}

def clean_text(s: str) -> str:
    """清理字符串中的特殊符号"""
    return re.sub(r"[^A-Za-z0-9\s\-&]", "", s).strip()

def fetch_doi_from_crossref(title, authors="", year=""):
    """通过 CrossRef 精准匹配 DOI"""
    title_clean = clean_text(title)
    author_first = authors.split(",")[0] if authors else ""

    # 第一次精确匹配：title + author + year
    query = f"{title_clean} {author_first} {year}".strip()
    url = f"https://api.crossref.org/works?query={requests.utils.quote(query)}&rows=1"

    try:
        res = requests.get(url, timeout=10)
        if res.status_code != 200:
            print(f"⚠️ CrossRef request failed ({res.status_code}) for: {title}")
            return ""

        items = res.json().get("message", {}).get("items", [])
        if items:
            item = items[0]
            doi = item.get("DOI", "")
            found_title = item.get("title", [""])[0]
            print(f"    ✅ Found DOI: {doi}")
            print(f"       ↳ Matched title: {found_title}")
            return doi

        # 第二次尝试：仅用标题模糊匹配
        fallback_url = f"https://api.crossref.org/works?query.title={requests.utils.quote(title_clean)}&rows=1"
        res2 = requests.get(fallback_url, timeout=10)
        items2 = res2.json().get("message", {}).get("items", [])
        if items2:
            item = items2[0]
            doi = item.get("DOI", "")
            found_title = item.get("title", [""])[0]
            print(f"    ✅ Found DOI (fallback): {doi}")
            print(f"       ↳ Matched title: {found_title}")
            return doi

        print("    ❌ No DOI match found.")
    except Exception as e:
        print(f"⚠️ Error while fetching DOI for '{title}': {e}")
    return ""

publications = []
for i, pub in enumerate(articles, start=1):
    title = pub.get("title", "")
    authors = pub.get("authors", "")
    year = str(pub.get("year", ""))
    journal = pub.get("publication", "")
    citations = pub.get("cited_by", {}).get("value", 0)
    pdf = pub.get("link", "")

    # 使用缓存中的 DOI
    doi = ""
    if title in old_data and old_data[title].get("doi"):
        doi = old_data[title]["doi"]
        print(f"🟢 [{i}/{len(articles)}] Cached DOI found for: {title}")
    else:
        print(f"🔹 [{i}/{len(articles)}] Fetching DOI for: {title}")
        doi = fetch_doi_from_crossref(title, authors, year)
        time.sleep(1.5)  # 防止 CrossRef 限流

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

# 保存 JSON 文件
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(publications, f, ensure_ascii=False, indent=2)

print(f"\n✅ Updated {len(publications)} publications (DOI included where available).")
print(f"📅 Last updated: {datetime.now()}")
