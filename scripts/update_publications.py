name: Update Google Scholar Citations

on:
  schedule:
    - cron: '0 0 * * *'   # 每天 UTC 00:00（北京时间 08:00）
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: pip install requests

      - name: Run update script
        env:
          SERPAPI_KEY: ${{ secrets.SERPAPI_KEY }}
        run: python scripts/update_publications.py

      - name: Commit and push changes
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/publications.json
          git commit -m "Auto update Google Scholar citations [$(date '+%Y-%m-%d')]"
          git push
