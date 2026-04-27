import json
import os
import re
import time
from datetime import datetime

import requests


# =========================
# Basic configuration
# =========================

SCHOLAR_ID = "UdIP7WoAAAAJ"
API_KEY = os.getenv("SERPAPI_KEY")

OUTPUT_PATH = "data/publications.json"
TEMP_PATH = "data/publications.tmp.json"

SERPAPI_URL = (
    "https://serpapi.com/search.json"
    f"?engine=google_scholar_author&author_id={SCHOLAR_ID}&api_key={API_KEY}"
)


# =========================
# Utility functions
# =========================

def load_existing_publications(path: str) -> list:
    """Load existing publications from JSON. Return an empty list if unavailable."""
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        print("⚠️ Existing publications.json is not a list. It will not be used as cache.")
        return []

    except Exception as e:
        print(f"⚠️ Failed to load existing publications.json: {e}")
        return []


def build_old_data_map(old_publications: list) -> dict:
    """Build a title-based cache for DOI and other existing metadata."""
    old_data = {}

    for pub in old_publications:
        title = str(pub.get("title", "")).strip()
        if title:
            old_data[title] = pub

    return old_data


def clean_text(text: str) -> str:
    """Clean text for CrossRef queries."""
    if not text:
        return ""

    return re.sub(r"[^A-Za-z0-9\s\-&:]", "", str(text)).strip()


def fetch_doi_from_crossref(title: str, authors: str = "", year: str = "") -> str:
    """Fetch DOI from CrossRef using title, author, and year."""
    title_clean = clean_text(title)
    author_first = authors.split(",")[0].strip() if authors else ""

    if not title_clean:
        return ""

    queries = [
        f"{title_clean} {author_first} {year}".strip(),
        title_clean,
    ]

    for query in queries:
        try:
            url = (
                "https://api.crossref.org/works"
                f"?query={requests.utils.quote(query)}&rows=1"
            )

            response = requests.get(url, timeout=15)

            if response.status_code != 200:
                print(f"⚠️ CrossRef request failed ({response.status_code}) for: {title}")
                continue

            items = response.json().get("message", {}).get("items", [])

            if not items:
                continue

            item = items[0]
            doi = item.get("DOI", "")
            found_title = item.get("title", [""])[0]

            if doi:
                print(f"✅ Found DOI for: {title}")
                print(f"   DOI: {doi}")
                print(f"   Matched title: {found_title}")
                return doi

        except Exception as e:
            print(f"⚠️ Error while fetching DOI for '{title}': {e}")

    print(f"❌ No DOI match found for: {title}")
    return ""


def fetch_articles_from_serpapi() -> list:
    """Fetch publications from SerpAPI."""
    if not API_KEY:
        raise ValueError("❌ Missing SERPAPI_KEY. Please add it as a GitHub Secret.")

    print("Fetching publications from SerpAPI...")

    response = requests.get(SERPAPI_URL, timeout=30)

    if response.status_code != 200:
        raise RuntimeError(
            f"❌ SerpAPI request failed: {response.status_code} - {response.text}"
        )

    data = response.json()
    articles = data.get("articles", [])

    if not isinstance(articles, list):
        raise RuntimeError("❌ SerpAPI returned an invalid articles field.")

    if len(articles) == 0:
        raise RuntimeError(
            "❌ SerpAPI returned zero articles. Existing publications.json will be kept unchanged."
        )

    print(f"✅ Fetched {len(articles)} articles from SerpAPI.")
    return articles


def normalise_publication(pub: dict, old_data: dict, index: int, total: int) -> dict:
    """Convert SerpAPI publication data into the website JSON format."""
    title = str(pub.get("title", "")).strip()
    authors = str(pub.get("authors", "")).strip()
    year = str(pub.get("year", "")).strip()
    journal = str(pub.get("publication", "")).strip()
    citations = pub.get("cited_by", {}).get("value", 0)
    link = str(pub.get("link", "")).strip()

    if citations is None:
        citations = 0

    old_pub = old_data.get(title, {})
    old_doi = str(old_pub.get("doi", "")).strip()

    if old_doi:
        doi = old_doi
        print(f"[{index}/{total}] Cached DOI found for: {title}")
    else:
        print(f"[{index}/{total}] Fetching DOI for: {title}")
        doi = fetch_doi_from_crossref(title, authors, year)
        time.sleep(1.5)

    return {
        "title": title,
        "authors": authors,
        "year": year,
        "journal": journal,
        "pages": str(old_pub.get("pages", "")).strip(),
        "citations": citations,
        "doi": doi,
        "pdf": link,
    }


def save_publications_safely(publications: list, output_path: str, temp_path: str) -> None:
    """Save publications atomically. Never overwrite with empty data."""
    if not isinstance(publications, list) or len(publications) == 0:
        raise RuntimeError(
            "❌ No valid publications generated. Existing publications.json will be kept unchanged."
        )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(publications, f, ensure_ascii=False, indent=2)

    os.replace(temp_path, output_path)

    print(f"\n✅ Updated {len(publications)} publications.")
    print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# =========================
# Main process
# =========================

def main():
    old_publications = load_existing_publications(OUTPUT_PATH)
    old_data = build_old_data_map(old_publications)

    articles = fetch_articles_from_serpapi()

    publications = []

    for i, pub in enumerate(articles, start=1):
        normalised = normalise_publication(pub, old_data, i, len(articles))

        if normalised["title"]:
            publications.append(normalised)

    save_publications_safely(publications, OUTPUT_PATH, TEMP_PATH)


if __name__ == "__main__":
    main()
