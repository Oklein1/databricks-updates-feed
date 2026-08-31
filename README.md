# Databricks News

A tiny Hacker-News-style reader for the Databricks docs release-notes RSS feed
(`https://docs.databricks.com/aws/en/feed.xml`). Two ways to use it:

1. **Streamlit app** — an interactive app you run locally (search, category
   filter, live refresh).
2. **Static site** — a plain HTML/JS page in `docs/` you can publish for free
   with **GitHub Pages**, kept up to date by a scheduled GitHub Action.

## 1. Run the Streamlit app

```bash
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. Data is cached for 15 minutes; use the
"↻ Refresh" button to force a re-fetch.

## 2. Publish the static site on GitHub Pages

The `docs/` folder is a self-contained static site (`index.html` +
`data.json`) — GitHub Pages can serve it directly, no build step needed.

Steps:

1. Create a new GitHub repo and push this project to it:

   ```bash
   cd databricks-hn
   git init
   git add .
   git commit -m "Initial commit: Databricks News reader"
   git branch -M main
   git remote add origin https://github.com/<your-username>/<your-repo>.git
   git push -u origin main
   ```

2. In the repo, go to **Settings → Pages**, and under "Build and deployment"
   set **Source: Deploy from a branch**, **Branch: main**, **Folder: /docs**.
   Save.

3. GitHub will publish the site at
   `https://<your-username>.github.io/<your-repo>/` within a minute or two.

4. A GitHub Action (`.github/workflows/update-feed.yml`) is already wired up
   to re-fetch the feed every 6 hours (and on demand via the "Run workflow"
   button in the Actions tab) and commit a refreshed `docs/data.json`. No
   extra setup is required — it uses the repo's default `GITHUB_TOKEN`.

The `docs/data.json` checked into this project is a real snapshot fetched at
build time, so the site works immediately even before the first scheduled
Action run.

## How it works

- `scripts/fetch_feed.py` fetches and parses the RSS feed (via `feedparser`),
  strips HTML from descriptions, guesses a rough category from the URL
  (AI/BI, Lakebase, Lakeflow, Unity Catalog, etc.), and writes a normalized
  `data.json`.
- `app.py` (Streamlit) imports that same fetch logic directly and renders an
  HN-style list: rank number, title link, domain, category badge, "time ago",
  and a short summary — plus a search box and category filter.
- `docs/index.html` is a dependency-free HTML/CSS/JS page that fetches
  `data.json` client-side and renders the same style of list, so it can be
  hosted anywhere static files are served (GitHub Pages, S3, Netlify, …).

## Regenerating data.json manually

```bash
python scripts/fetch_feed.py --out docs/data.json
```
