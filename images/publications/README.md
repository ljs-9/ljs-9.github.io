Publication images for the website live in this folder.

Upload one image per paper here, preferably with a filename close to the paper
title, for example:

`Geopolitical risk and US stock market volatility.jpg`

Supported formats: `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, and `.svg`.
When `scripts/update_publications.py` runs, it scans this folder, matches image
filenames to Google Scholar publication titles, and writes the matched local
path into `data/publications.json`.
