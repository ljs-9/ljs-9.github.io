Publication attachments live in this folder.

Upload supplementary files here, preferably with filenames close to the paper
title, for example:

`ESG performance digital transformation and green innovation supplementary data.xlsx`

Supported files can be PDFs, spreadsheets, ZIP archives, documents, or other
downloadable research materials. When `scripts/update_publications.py` runs, it
scans this folder, matches filenames to Google Scholar publication titles, and
writes matched files into the publication's `attachments` list in
`data/publications.json`.

You can also manually edit `data/publications.json`:

```json
"attachments": [
  {
    "label": "Supplementary",
    "file": "attachments/publications/example.xlsx"
  }
]
```
