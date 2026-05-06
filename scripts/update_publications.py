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

PROFILE_PATH = "data/profile.json"
API_KEY = os.getenv("SERPAPI_KEY")
OUTPUT_PATH = "data/publications.json"
TEMP_PATH = "data/publications.tmp.json"
PAPERS_DIR = "papers"
PUBLICATION_IMAGES_DIR = "images/publications"
PUBLICATION_ATTACHMENTS_DIR = "attachments/publications"
PUBLICATION_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}

# The threshold controls how strict the PDF-title matching is.
# 0.72 is usually suitable when PDF filenames are meaningful but not identical to paper titles.
PDF_MATCH_THRESHOLD = 0.72
IMAGE_MATCH_THRESHOLD = 0.72
ATTACHMENT_MATCH_THRESHOLD = 0.72


# =========================
# Utility functions
# =========================

def load_profile(path: str = PROFILE_PATH) -> dict:
    """
    Load site profile metadata.

    The Google Scholar author id is kept in data/profile.json so personal
    profile changes can be made in one place.
    """
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return data if isinstance(data, dict) else {}

    except Exception as e:
        print(f"⚠️ Failed to load profile metadata: {e}")
        return {}


def get_google_scholar_id(profile: dict) -> str:
    """
    Resolve the Google Scholar author id from profile.json.
    """
    scholar_id = str(profile.get("googleScholarId", "")).strip()

    if scholar_id:
        return scholar_id

    raise ValueError("❌ Missing googleScholarId in data/profile.json.")


def build_serpapi_url(scholar_id: str) -> str:
    """
    Build the SerpAPI URL for a Google Scholar author profile.
    """
    return (
        "https://serpapi.com/search.json"
        f"?engine=google_scholar_author&author_id={scholar_id}&api_key={API_KEY}"
    )


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
    Build a title-based cache for DOI, PDF, image, attachment, pages, and scholar metadata.
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


def normalise_local_image_path(image: str) -> str:
    """
    Normalise local publication image paths.

    Uploaded publication images live in images/publications/. If only a
    filename is stored, this function expands it to that folder.
    """
    if not image:
        return ""

    image = str(image).strip()

    if not image:
        return ""

    if (
        image.startswith("http://")
        or image.startswith("https://")
        or image.startswith("./")
        or image.startswith("/")
        or image.startswith("images/")
    ):
        return image

    extension = os.path.splitext(image)[1].lower()

    if extension in PUBLICATION_IMAGE_EXTENSIONS:
        return f"{PUBLICATION_IMAGES_DIR}/{image}"

    return image


def normalise_local_attachment_path(file_path: str) -> str:
    """
    Normalise local publication attachment paths.

    Uploaded attachment files live in attachments/publications/. If only a
    filename is stored, this function expands it to that folder.
    """
    if not file_path:
        return ""

    file_path = str(file_path).strip()

    if not file_path:
        return ""

    if (
        file_path.startswith("http://")
        or file_path.startswith("https://")
        or file_path.startswith("./")
        or file_path.startswith("/")
        or file_path.startswith("attachments/")
    ):
        return file_path

    return f"{PUBLICATION_ATTACHMENTS_DIR}/{file_path}"


def normalise_attachment_item(attachment, index: int = 0, total: int = 1) -> dict:
    """
    Convert a string or object attachment into the website JSON format.
    """
    if isinstance(attachment, str):
        file_path = normalise_local_attachment_path(attachment)
        label = f"Supplementary {index + 1}" if total > 1 else "Supplementary"
    elif isinstance(attachment, dict):
        file_path = normalise_local_attachment_path(
            attachment.get("file")
            or attachment.get("path")
            or attachment.get("url")
            or attachment.get("href")
            or ""
        )
        label = str(
            attachment.get("label")
            or attachment.get("name")
            or attachment.get("title")
            or ""
        ).strip()
    else:
        return {}

    if not file_path:
        return {}

    if not label:
        label = f"Supplementary {index + 1}" if total > 1 else "Supplementary"

    return {
        "label": label,
        "file": file_path,
    }


def normalise_attachments(raw_attachments) -> list:
    """
    Normalise a publication's existing attachments.
    """
    if not raw_attachments:
        return []

    attachments = raw_attachments if isinstance(raw_attachments, list) else [raw_attachments]
    normalised = []

    for index, attachment in enumerate(attachments):
        item = normalise_attachment_item(attachment, index, len(attachments))

        if item:
            normalised.append(item)

    return normalised


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


def scan_publication_images_folder(images_dir: str = PUBLICATION_IMAGES_DIR) -> list:
    """
    Scan the local uploaded publication-image folder.

    The folder is created if it does not already exist. Images are matched to
    publication titles by filename, so a file named after the paper title works
    best.
    """
    os.makedirs(images_dir, exist_ok=True)

    image_files = []

    for filename in os.listdir(images_dir):
        extension = os.path.splitext(filename)[1].lower()

        if extension in PUBLICATION_IMAGE_EXTENSIONS and filename != "default.svg":
            path = f"{images_dir}/{filename}"
            image_files.append({
                "filename": filename,
                "path": path,
                "key": normalise_filename_key(filename),
            })

    print(f"✅ Found {len(image_files)} publication image file(s) in {images_dir}/.")
    return image_files


def make_attachment_label(filename: str) -> str:
    """
    Create a website label for an attachment.
    """
    return "Supplementary"


def scan_publication_attachments_folder(attachments_dir: str = PUBLICATION_ATTACHMENTS_DIR) -> list:
    """
    Scan the local uploaded publication-attachment folder.

    The folder is created if it does not already exist. Hidden files and this
    folder's README are ignored.
    """
    os.makedirs(attachments_dir, exist_ok=True)

    attachment_files = []

    for filename in os.listdir(attachments_dir):
        path = os.path.join(attachments_dir, filename)

        if (
            filename.startswith(".")
            or filename.lower() == "readme.md"
            or not os.path.isfile(path)
        ):
            continue

        attachment_files.append({
            "filename": filename,
            "path": f"{attachments_dir}/{filename}",
            "key": normalise_filename_key(filename),
            "label": make_attachment_label(filename),
        })

    print(f"✅ Found {len(attachment_files)} publication attachment file(s) in {attachments_dir}/.")
    return attachment_files


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


def find_matching_image(title: str, image_files: list) -> str:
    """
    Find the most likely locally uploaded image for a publication title.

    Matching is intentionally local-only: publication images should be uploaded
    to images/publications/ rather than fetched from Google Scholar or remote
    pages.
    """
    title_key = normalise_title_key(title)

    if not title_key or not image_files:
        return ""

    best_path = ""
    best_score = 0.0

    for image in image_files:
        image_key = image.get("key", "")
        image_path = image.get("path", "")

        if not image_key:
            continue

        if image_key in title_key or title_key in image_key:
            print(f"🖼️ Exact image match for '{title}': {image_path}")
            return image_path

        score = similarity(title_key, image_key)

        if score > best_score:
            best_score = score
            best_path = image_path

    if best_score >= IMAGE_MATCH_THRESHOLD:
        print(f"🖼️ Fuzzy image match for '{title}': {best_path} | score={best_score:.2f}")
        return best_path

    print(f"⚠️ No image match for '{title}'. Best score={best_score:.2f}")
    return ""


def find_matching_attachments(title: str, attachment_files: list) -> list:
    """
    Find locally uploaded attachments for a publication title.

    Multiple exact filename matches are allowed. If there are no exact matches,
    a single high-confidence fuzzy match is used.
    """
    title_key = normalise_title_key(title)

    if not title_key or not attachment_files:
        return []

    exact_matches = []
    best_attachment = None
    best_score = 0.0

    for attachment in attachment_files:
        attachment_key = attachment.get("key", "")

        if not attachment_key:
            continue

        is_exact_match = (
            title_key in attachment_key
            or (len(attachment_key) >= 18 and attachment_key in title_key)
        )

        if is_exact_match:
            exact_matches.append({
                "label": attachment.get("label", "Supplementary"),
                "file": attachment.get("path", ""),
            })
            continue

        score = similarity(title_key, attachment_key)

        if score > best_score:
            best_score = score
            best_attachment = attachment

    if exact_matches:
        print(f"📎 Found {len(exact_matches)} attachment(s) for '{title}'.")
        return exact_matches

    if best_attachment and best_score >= ATTACHMENT_MATCH_THRESHOLD:
        print(
            f"📎 Fuzzy attachment match for '{title}': "
            f"{best_attachment.get('path', '')} | score={best_score:.2f}"
        )
        return [{
            "label": best_attachment.get("label", "Supplementary"),
            "file": best_attachment.get("path", ""),
        }]

    print(f"⚠️ No attachment match for '{title}'. Best score={best_score:.2f}")
    return []


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


def fetch_articles_from_serpapi(scholar_id: str) -> list:
    """
    Fetch publications from SerpAPI.

    If SerpAPI returns zero articles, stop the workflow and keep the existing
    publications.json unchanged.
    """
    if not API_KEY:
        raise ValueError("❌ Missing SERPAPI_KEY. Please add it as a GitHub Secret.")

    print(f"Fetching publications from SerpAPI for Google Scholar id: {scholar_id}")

    response = requests.get(build_serpapi_url(scholar_id), timeout=30)

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
    image_files: list,
    attachment_files: list,
    index: int,
    total: int
) -> dict:
    """
    Convert SerpAPI publication data into the website JSON format.

    Important:
    - The local PDF path is automatically matched from the papers/ folder.
    - The local image path is automatically matched from images/publications/.
    - Local attachments are automatically matched from attachments/publications/.
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
    old_image = normalise_local_image_path(str(old_pub.get("image", "")).strip())
    old_attachments = normalise_attachments(
        old_pub.get("attachments") or old_pub.get("attachment")
    )

    matched_pdf = find_matching_pdf(title, pdf_files)
    pdf_path = matched_pdf or old_pdf
    matched_image = find_matching_image(title, image_files)
    image_path = matched_image or old_image
    matched_attachments = find_matching_attachments(title, attachment_files)
    attachments = matched_attachments or old_attachments

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
        "image": image_path,
        "attachments": attachments,
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
    profile = load_profile(PROFILE_PATH)
    scholar_id = get_google_scholar_id(profile)

    old_publications = load_existing_publications(OUTPUT_PATH)
    old_data = build_old_data_map(old_publications)

    pdf_files = scan_papers_folder(PAPERS_DIR)
    image_files = scan_publication_images_folder(PUBLICATION_IMAGES_DIR)
    attachment_files = scan_publication_attachments_folder(PUBLICATION_ATTACHMENTS_DIR)
    articles = fetch_articles_from_serpapi(scholar_id)

    publications = []

    for i, pub in enumerate(articles, start=1):
        normalised = normalise_publication(
            pub=pub,
            old_data=old_data,
            pdf_files=pdf_files,
            image_files=image_files,
            attachment_files=attachment_files,
            index=i,
            total=len(articles),
        )

        if normalised["title"]:
            publications.append(normalised)

    save_publications_safely(publications, OUTPUT_PATH, TEMP_PATH)


if __name__ == "__main__":
    main()
