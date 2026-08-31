# Databricks News

A tiny Hacker-News-style reader for the Databricks docs release-notes RSS
feed (`https://docs.databricks.com/aws/en/feed.xml`). It ships as two
independent front ends over the same parsing logic: an interactive
**Streamlit app** you run locally, and a **static site** (HTML/CSS/JS) meant
to be published for free on **GitHub Pages**.

---

## What this is (high level)

Databricks publishes an RSS feed of every docs release note — new features,
deprecations, quota changes, and so on — but there's no browsable, rankable
view of it anywhere. This project turns that feed into something you can
skim the way you'd skim Hacker News: a numbered list of titles, each with a
source domain, a category badge (guessed from the URL, e.g. AI/BI,
Lakebase, Lakeflow, Unity Catalog), a "time ago" stamp, and a short summary
— with search, category filtering, and pagination ("More" link, 20 items at
a time) so the page doesn't dump 70+ entries on you at once.

There is no backend server, no database, and no user accounts. The whole
system boils down to "fetch the feed periodically, parse it into JSON,
render that JSON as a list" — done twice, once for an interactive local app
and once for a static public page.

## How it works (high level)

Both front ends share one piece of logic — `scripts/fetch_feed.py` — which
downloads the RSS feed, strips HTML out of the descriptions, guesses a
category from each item's URL path, and normalizes everything into a
consistent list of `{title, link, summary, published, category, domain}`
records.

- **Streamlit app** (`app.py`): imports `fetch_feed.py` directly and calls
  it live, in-process, whenever you load or refresh the page. Streamlit
  caches the result for 15 minutes so repeated reloads don't hammer the
  Databricks server.

- **Static site** (`docs/index.html` + `docs/data.json`): GitHub Pages can
  only serve static files — it can't run Python, and a browser can't fetch
  `feed.xml` directly anyway, because Databricks' server doesn't send the
  CORS headers a cross-origin JavaScript `fetch()` needs. So a **GitHub
  Actions workflow** (`.github/workflows/update-feed.yml`) runs
  `fetch_feed.py` on GitHub's own servers (no CORS restriction there),
  writes the result to `docs/data.json`, and commits it. The static
  `index.html` page then just does a same-origin `fetch('data.json')` in
  the visitor's browser and renders it — no live connection to Databricks
  ever happens client-side.

In short: one script does the fetching and parsing; one interactive app
calls it live; one static page reads a pre-baked snapshot of its output.

## How to run it

### Option 1 — Streamlit app (interactive, local)

```bash
git clone <your-repo-url>
cd databricks-hn
pip install -r requirements.txt
streamlit run app.py
```

This opens at `http://localhost:8501`. Data is cached for 15 minutes; use
the "↻ Refresh" button in the app to force a re-fetch.

### Option 2 — Static site (GitHub Pages)

1. Push this repo to GitHub.
2. In the repo, go to **Settings → Pages**. Under "Build and deployment",
   set **Source: Deploy from a branch**, **Branch: main**, **Folder:
   /docs**, then **Save**.
3. GitHub publishes the site at
   `https://<your-username>.github.io/<your-repo>/` within a minute or two.
4. The bundled GitHub Action keeps `docs/data.json` current on whatever
   schedule you've set it to (or only when you manually run it from the
   **Actions** tab — see the workflow file for the current trigger
   configuration).

You can also regenerate `docs/data.json` by hand at any time:

```bash
python scripts/fetch_feed.py --out docs/data.json
```

## Dependencies

You need Python 3.9+ and `pip`. Nothing else is platform-specific — the
same `requirements.txt` (`streamlit`, `feedparser`, `requests`) installs
identically on Windows, macOS, and Linux. The differences are only in how
you get Python and `git` onto the machine in the first place.

**macOS**

```bash
# Homebrew (if you don't already have it): https://brew.sh
brew install python git

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows**

```powershell
# Install Python from https://python.org/downloads (check "Add python.exe to PATH")
# Install Git from https://git-scm.com/download/win

py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

The static site itself has **zero dependencies** to view — it's plain
HTML/CSS/JS with no build step and no npm packages. Python is only needed
if you want to run the Streamlit app locally or regenerate `data.json` by
hand instead of letting GitHub Actions do it.

## Large-scale architecture

As built, this is intentionally a "flat file" architecture — no database,
no API server, no message queue — because the data volume (one RSS feed,
tens of items, refreshed a few times a day) doesn't justify anything
heavier. If this were to grow — many feeds, many consumers, real-time
freshness, user accounts, alerting — here's the shape it would take on:

```
  SOURCES                       INGESTION

  +------------------+          +--------------------------+
  | Databricks       |--\       | Scheduler / queue        |
  | feed.xml         |   \      | (cron, SQS, Airflow)     |
  +------------------+    >---->|            |             |
                          /     |            v             |
  +------------------+   /      | Fetch worker             |
  | Other vendor     |--/       |            |             |
  | feeds...         |          |            v             |
  +------------------+          | Parse / normalize worker |
                                 +------------|-------------+
                                              |
                                              v
  STORAGE                       +--------------------------+
                                 | Database                 |
                                 | (Postgres / DynamoDB)    |
                                 +------------|-------------+
                                              |
                                              v
                                 +--------------------------+
                                 | Cache (Redis / CDN edge) |
                                 +------------|-------------+
                                              |
                    +-------------------------+-------------------------+
                    |                                                   |
                    v                                                   v
  SERVING  +--------------------+                          +--------------------------+
           | API layer          |------------------------->| Web front end            |
           | (REST / GraphQL)   |                          +--------------------------+
           +--------------------+
                    |
                    v
           +--------------------+
           | Alerting / digest  |
           | (email, Slack,     |
           |  RSS-out)          |
           +--------------------+
```

The key upgrades at each stage, if scale demanded them:

- **Ingestion**: replace the single GitHub Action with a proper scheduler
  (cron on a small VM, an AWS Lambda on an EventBridge schedule, or an
  Airflow DAG) feeding a queue, so fetch failures retry independently per
  source and adding a new feed doesn't mean editing a workflow file.
- **Storage**: replace the flat `data.json` with a real database (Postgres
  for relational querying, or a document store) so you can query by date
  range, category, or full-text search server-side instead of shipping the
  whole dataset to the browser and filtering client-side.
- **Caching**: put a CDN or Redis layer in front of the API so repeated
  reads don't hit the database on every request — this is what `data.json`
  effectively does today, just without a real cache-invalidation strategy.
- **Serving**: a proper API layer (REST/GraphQL) decouples the data from
  any one front end, so a mobile app, a Slack bot, and a web page can all
  read the same source without each re-implementing feed parsing.
- **Alerting**: a notification path (email digest, Slack webhook, RSS-out)
  keyed off new rows in storage, so consumers don't have to poll a page to
  notice new release notes.
- **Observability**: structured logging and metrics on the ingestion
  workers (fetch latency, parse failures, feed staleness) so a silently
  broken feed doesn't go unnoticed the way a failed cron job easily can.

None of this is needed at the current scale — it's included here as the
answer to "what would this look like if it had to grow," not as a todo
list for this project.
