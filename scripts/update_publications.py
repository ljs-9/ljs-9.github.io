import json
import os
import re
import time
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import quote

import requests


# =========================
# Basic configuration
# =========================

SCHOLAR_ID = "UdIP7WoAAAAJ"
API_KEY = os.getenv("SERPAPI_KEY")

OUTPUT_PATH = "data/publications.json"
TEMP_PATH = "data/publications.tmp.json"
PAPERS_DIR = "papers"

# The threshold controls how strict the PDF-title matching is.
# 0.72 is usually suitable when PDF filenames are meaningful but not identical to paper titles.
PDF_MATCH_THRESHOLD = 0.72

SERPAPI_URL = (
    "https://serpapi.com/search.json"
    f"?engine=google_scholar_author&author_id={SCHOLAR_ID}&api_key={API_KEY}"
)


# =========================
# Utility functions
# =========================

def load_existing_publications(path: str) -> list:
    """
    Load existing publications from JSON.

    Existing data is used as a fallback so that manually maintained fields
    such as pages, DOI, scholar links, or PDF paths can be preserved.
    """
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


def normalise_title_key(title: str) -> str:
    """
    Create a stable matching key for publication titles.

    This removes punctuation, case differences, and spacing differences.
    """
    title = str(title).lower().strip()
    title = title.replace("–", "-").replace("—", "-")
    title = re.sub(r"[^a-z0-9\s]", " ", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip()


def normalise_filename_key(filename: str) -> str:
    """
    Convert a PDF filename into a matching key.

    Example:
    'geopolitical-risk-us-stock-market-volatility.pdf'
    becomes
    'geopolitical risk us stock market volatility'
    """
    name = os.path.splitext(os.path.basename(filename))[0]
    name = name.lower().strip()
    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()


def build_old_data_map(old_publications: list) -> dict:
    """
    Build a title-based cache for DOI, PDF, pages, and scholar metadata.
    """
    old_data = {}

    for pub in old_publications:
        title = str(pub.get("title", "")).strip()
        key = normalise_title_key(title)

        if key:
            old_data[key] = pub

    return old_data


def clean_text(text: str) -> str:
    """
    Clean text for CrossRef queries.
    """
    if not text:
        return ""

    return re.sub(r"[^A-Za-z0-9\s\-&:]", "", str(text)).strip()


def normalise_local_pdf_path(pdf: str) -> str:
    """
    Normalise local PDF paths.

    If the user writes only 'paper-name.pdf', this function converts it to
    'papers/paper-name.pdf'. If the path already starts with 'papers/',
    './', '/', 'http://', or 'https://', it is kept unchanged.
    """
    if not pdf:
        return ""

    pdf = str(pdf).strip()

    if not pdf:
        return ""

    if (
        pdf.startswith("http://")
        or pdf.startswith("https://")
        or pdf.startswith("./")
        or pdf.startswith("/")
        or pdf.startswith("papers/")
    ):
        return pdf

    if pdf.lower().endswith(".pdf"):
        return f"papers/{pdf}"

    return pdf


def scan_papers_folder(papers_dir: str = PAPERS_DIR) -> list:
    """
    Scan the papers folder and return all PDF files.

    Returned format:
    [
        {
            "filename": "paper.pdf",
            "path": "papers/paper.pdf",
            "key": "paper"
        }
    ]
    """
    if not os.path.isdir(papers_dir):
        print(f"⚠️ Papers folder not found: {papers_dir}")
        return []

    pdf_files = []

    for filename in os.listdir(papers_dir):
        if filename.lower().endswith(".pdf"):
            path = f"{papers_dir}/{filename}"
            pdf_files.append({
                "filename": filename,
                "path": path,
                "key": normalise_filename_key(filename),
            })

    print(f"✅ Found {len(pdf_files)} PDF file(s) in {papers_dir}/.")
    return pdf_files


def similarity(a: str, b: str) -> float:
    """
    Calculate text similarity between two normalised strings.
    """
    if not a or not b:
        return 0.0

    return SequenceMatcher(None, a, b).ratio()


def find_matching_pdf(title: str, pdf_files: list) -> str:
    """
    Find the most likely PDF file for a publication title.

    Matching is based on:
    1. Exact containment after normalisation;
    2. Fuzzy similarity score.
    """
    title_key = normalise_title_key(title)

    if not title_key or not pdf_files:
        return ""

    best_path = ""
    best_score = 0.0

    for pdf in pdf_files:
        pdf_key = pdf.get("key", "")
        pdf_path = pdf.get("path", "")

        if not pdf_key:
            continue

        # Strong match: filename key contains title key or title key contains filename key.
        if pdf_key in title_key or title_key in pdf_key:
            print(f"📎 Exact PDF match for '{title}': {pdf_path}")
            return pdf_path

        score = similarity(title_key, pdf_key)

        if score > best_score:
            best_score = score
            best_path = pdf_path

    if best_score >= PDF_MATCH_THRESHOLD:
        print(f"📎 Fuzzy PDF match for '{title}': {best_path} | score={best_score:.2f}")
        return best_path

    print(f"⚠️ No PDF match for '{title}'. Best score={best_score:.2f}")
    return ""


def fetch_doi_from_crossref(title: str, authors: str = "", year: str = "") -> str:
    """
    Fetch DOI from CrossRef using title, author, and year.

    If no reliable DOI is found, return an empty string instead of failing the
    whole update process.
    """
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
                f"?query={quote(query)}&rows=1"
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
    """
    Fetch publications from SerpAPI.

    If SerpAPI returns zero articles, stop the workflow and keep the existing
    publications.json unchanged.
    """
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


def normalise_publication(
    pub: dict,
    old_data: dict,
    pdf_files: list,
    index: int,
    total: int
) -> dict:
    """
    Convert SerpAPI publication data into the website JSON format.

    Important:
    - The local PDF path is automatically matched from the papers/ folder.
    - If automatic matching fails, existing PDF path is preserved.
    - The Google Scholar link is stored in the 'scholar' field.
    - The 'pdf' field is reserved only for local or direct PDF links.
    """
    title = str(pub.get("title", "")).strip()
    authors = str(pub.get("authors", "")).strip()
    year = str(pub.get("year", "")).strip()
    journal = str(pub.get("publication", "")).strip()
    citations = pub.get("cited_by", {}).get("value", 0)
    scholar_link = str(pub.get("link", "")).strip()

    if citations is None:
        citations = 0

    title_key = normalise_title_key(title)
    old_pub = old_data.get(title_key, {})

    old_doi = str(old_pub.get("doi", "")).strip()
    old_pdf = normalise_local_pdf_path(str(old_pub.get("pdf", "")).strip())
    old_scholar = str(old_pub.get("scholar", "")).strip()
    old_pages = str(old_pub.get("pages", "")).strip()

    matched_pdf = find_matching_pdf(title, pdf_files)
    pdf_path = matched_pdf or old_pdf

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
        "pages": old_pages,
        "citations": citations,
        "doi": doi,
        "pdf": pdf_path,
        "scholar": scholar_link or old_scholar,
    }


def save_publications_safely(publications: list, output_path: str, temp_path: str) -> None:
    """
    Save publications atomically.

    The script never overwrites publications.json with empty data.
    """
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

    pdf_files = scan_papers_folder(PAPERS_DIR)
    articles = fetch_articles_from_serpapi()

    publications = []

    for i, pub in enumerate(articles, start=1):
        normalised = normalise_publication(
            pub=pub,
            old_data=old_data,
            pdf_files=pdf_files,
            index=i,
            total=len(articles),
        )

        if normalised["title"]:
            publications.append(normalised)

    save_publications_safely(publications, OUTPUT_PATH, TEMP_PATH)


if __name__ == "__main__":
    main()
