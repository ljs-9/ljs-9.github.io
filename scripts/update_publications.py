import os
import json
import requests
from serpapi import GoogleSearch

# ================= 配置 =================
GOOGLE_SCHOLAR_ID = "UdIP7WoAAAAJ"
SERPAPI_KEY = os.getenv("SERPAPI_KEY")  # GitHub Secret

if not SERPAPI_KEY:
    raise ValueError("❌ Missing SERPAPI_KEY. Please add it as a GitHub Secret.")

DATA_PATH = "data/publications.json"
PDF_FOLDER = "papers"  # 本地 PDF 文件夹

# ================= 读取旧数据 =================
if os.path.exists(DATA_PATH):
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            old_data = json.load(f)
    except json.JSONDecodeError:
        old_data = []
else:
    old_data = []

old_map = {item["title"]: item for item in old_data}

# ================= 从 Google Scholar 获取数据 =================
print("🔍 Fetching Google Scholar data...")
search = GoogleSearch({
    "engine": "google_scholar_author",
    "author_id": GOOGLE_SCHOLAR_ID,
    "api_key": SERPAPI_KEY,
    "num": "100"
})
results = search.get_dict()

if "articles" not in results:
    raise RuntimeError("❌ Failed to fetch from Google Scholar API.")

articles = results["articles"]

# ================= CrossRef 获取 DOI =================
def fetch_doi(title):
    """使用 CrossRef API 自动查找 DOI"""
    url = "https://api.crossref.org/works"
    params = {"query.title": title, "rows": 1}
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        items = data.get("message", {}).get("items", [])
        if items:
            return items[0].get("DOI", "")
    except Exception:
        return ""
    return ""

# ================= 合并数据 =================
new_data = []

for art in articles:
    title = art.get("title", "").strip()
    year = art.get("year", "")
    authors = art.get("authors", "")
    journal = art.get("publication", "")
    pages = art.get("pages", "")
    citations = art.get("cited_by", {}).get("value", 0)

    old_entry = old_map.get(title, {})
    old_pdf = old_entry.get("pdf", "")

    # 自动抓 DOI，如果旧的没有
    doi = old_entry.get("doi", "")
    if not doi:
        doi = fetch_doi(title)

    # PDF 文件路径优先保留旧的
    pdf_path = old_pdf or f"{PDF_FOLDER}/{title.replace(' ', '_')}.pdf"

    new_data.append({
        "title": title,
        "authors": authors,
        "year": year,
        "journal": journal,
        "pages": pages,
        "citations": citations,
        "doi": f"https://doi.org/{doi}" if doi else "",
        "pdf": pdf_path
    })

# ================= 写回 JSON =================
os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
with open(DATA_PATH, "w", encoding="utf-8") as f:
    json.dump(new_data, f, ensure_ascii=False, indent=2)

print(f"✅ Successfully updated {len(new_data)} publications.")
print(f"📚 DOI auto-fetched, PDF links preserved in '{PDF_FOLDER}/'.")
