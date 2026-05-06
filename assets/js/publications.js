const PUBLICATIONS_URL = "./data/publications.json";
const DEFAULT_PUBLICATION_IMAGE = "images/publications/default.svg";
const container = document.getElementById("publications-container");
let publicationLightbox = null;
let lightboxImage = null;
let lightboxCaption = null;

function escapeHTML(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normaliseDOI(doi) {
  if (!doi) return "";
  const clean = String(doi).trim();
  if (!clean) return "";
  if (clean.startsWith("http://") || clean.startsWith("https://")) return clean;
  return `https://doi.org/${clean}`;
}

function normalisePDFPath(pdf) {
  if (!pdf) return "";
  const clean = String(pdf).trim();
  if (!clean) return "";
  if (clean.startsWith("http://") || clean.startsWith("https://") || clean.startsWith("./") || clean.startsWith("/")) return clean;
  return clean.startsWith("papers/") ? clean : `papers/${clean}`;
}

function normalisePublicationImage(image) {
  if (!image) return "";
  const clean = String(image).trim();
  if (!clean) return "";
  if (clean.startsWith("http://") || clean.startsWith("https://") || clean.startsWith("./") || clean.startsWith("/") || clean.startsWith("images/")) return clean;
  return `images/publications/${clean}`;
}

function getPublicationImage(pub) {
  const localImage = normalisePublicationImage(pub.image);
  if (localImage) return localImage;
  if (pub.slug && String(pub.slug).trim()) return `images/publications/${String(pub.slug).trim()}.jpg`;
  return DEFAULT_PUBLICATION_IMAGE;
}

function ensureLightbox() {
  if (publicationLightbox) return;

  publicationLightbox = document.createElement("div");
  publicationLightbox.className = "image-lightbox";
  publicationLightbox.id = "publication-lightbox";
  publicationLightbox.setAttribute("role", "dialog");
  publicationLightbox.setAttribute("aria-label", "Publication image preview");
  publicationLightbox.setAttribute("aria-hidden", "true");
  publicationLightbox.hidden = true;
  publicationLightbox.innerHTML = `
    <button class="lightbox-backdrop" type="button" data-lightbox-close aria-label="Close image preview"></button>
    <figure class="lightbox-panel">
      <button class="lightbox-close" type="button" data-lightbox-close aria-label="Close image preview">
        <i class="fa-solid fa-xmark"></i>
      </button>
      <img id="lightbox-image" alt="" />
      <figcaption id="lightbox-caption"></figcaption>
    </figure>
  `;

  document.body.appendChild(publicationLightbox);
  lightboxImage = publicationLightbox.querySelector("#lightbox-image");
  lightboxCaption = publicationLightbox.querySelector("#lightbox-caption");

  publicationLightbox.addEventListener("click", event => {
    if (event.target.closest("[data-lightbox-close]")) {
      closePublicationImage();
    }
  });
}

function openPublicationImage(src, alt) {
  if (!src) return;

  ensureLightbox();
  lightboxImage.src = src;
  lightboxImage.alt = alt || "Publication image";
  lightboxCaption.textContent = alt || "";
  publicationLightbox.hidden = false;
  publicationLightbox.setAttribute("aria-hidden", "false");
  document.body.classList.add("lightbox-open");
  publicationLightbox.querySelector(".lightbox-close").focus();
}

function closePublicationImage() {
  if (!publicationLightbox) return;

  publicationLightbox.hidden = true;
  publicationLightbox.setAttribute("aria-hidden", "true");
  document.body.classList.remove("lightbox-open");
  if (lightboxImage) lightboxImage.removeAttribute("src");
}

function sortYearsDescending(years) {
  return years.sort((a, b) => {
    const yearA = parseInt(a, 10);
    const yearB = parseInt(b, 10);
    if (Number.isNaN(yearA) && Number.isNaN(yearB)) return a.localeCompare(b);
    if (Number.isNaN(yearA)) return 1;
    if (Number.isNaN(yearB)) return -1;
    return yearB - yearA;
  });
}

function renderPublications(data) {
  if (!Array.isArray(data) || data.length === 0) {
    container.innerHTML = `<p class="publication-meta">Publication information is currently unavailable.</p>`;
    return;
  }

  const grouped = data.reduce((acc, pub) => {
    const year = String(pub.year || "Forthcoming").trim() || "Forthcoming";
    if (!acc[year]) acc[year] = [];
    acc[year].push(pub);
    return acc;
  }, {});

  let html = "";
  sortYearsDescending(Object.keys(grouped)).forEach(year => {
    html += `<div class="publication-year"><h3>${escapeHTML(year)}</h3><ul class="publication-list">`;
    grouped[year].forEach(pub => {
      const doiURL = normaliseDOI(pub.doi);
      const pdfURL = normalisePDFPath(pub.pdf);
      const imageURL = getPublicationImage(pub);
      const citations = Number(pub.citations) > 0 ? `<span class="publication-meta">Citations: ${Number(pub.citations)}</span>` : "";
      html += `
        <li class="publication-item">
          <div class="publication-thumb">
            <button
              class="publication-thumb-button"
              type="button"
              data-image-preview
              data-image-src="${escapeHTML(imageURL)}"
              data-image-alt="${escapeHTML(pub.title || "Publication image")}"
              aria-label="View larger image for ${escapeHTML(pub.title || "Publication image")}"
            >
              <img
                src="${escapeHTML(imageURL)}"
                alt="${escapeHTML(pub.title || "Publication image")}"
                loading="lazy"
                onerror="this.onerror=null;this.src='${DEFAULT_PUBLICATION_IMAGE}';this.closest('[data-image-preview]').dataset.imageSrc='${DEFAULT_PUBLICATION_IMAGE}';"
              />
            </button>
          </div>
          <div class="publication-content">
            <div>
              ${pub.authors ? `${escapeHTML(pub.authors)} ` : ""}(${escapeHTML(pub.year || year)}).
              <span class="publication-title">${escapeHTML(pub.title || "Untitled")}</span>.
              ${pub.journal ? `<em>${escapeHTML(pub.journal)}</em>.` : ""}
            </div>
            <div class="publication-links">
              ${doiURL ? `<a href="${escapeHTML(doiURL)}" target="_blank" rel="noopener noreferrer"><i class="fa-solid fa-link"></i> DOI</a>` : ""}
              ${pdfURL ? `<a href="${escapeHTML(pdfURL)}" target="_blank" rel="noopener noreferrer"><i class="fa-regular fa-file-pdf"></i> PDF</a>` : ""}
              ${citations}
            </div>
          </div>
        </li>
      `;
    });
    html += `</ul></div>`;
  });
  container.innerHTML = html;
}

container.addEventListener("click", event => {
  const trigger = event.target.closest("[data-image-preview]");

  if (!trigger) return;

  openPublicationImage(trigger.dataset.imageSrc, trigger.dataset.imageAlt);
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape" && publicationLightbox && !publicationLightbox.hidden) {
    closePublicationImage();
  }
});

fetch(PUBLICATIONS_URL, { cache: "no-store" })
  .then(response => {
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  })
  .then(renderPublications)
  .catch(error => {
    console.error("Failed to load publications:", error);
    container.innerHTML = `<p class="publication-meta">Publication information is temporarily unavailable. Please visit Google Scholar for the latest list.</p>`;
  });
