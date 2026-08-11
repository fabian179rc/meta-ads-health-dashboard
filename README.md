# Meta Ads Health Dashboard

Static dashboard, updated once a day by GitHub Actions, that classifies every
active campaign in Meta ad account `1899970234248234` as good, needs-creative-
refresh, kill-candidate, or insufficient-data — with the metric behind each
verdict. Read-only: this project never modifies anything in Meta.

## How it works

A GitHub Action runs `scripts/fetch_and_analyze.py` once a day, using a
read-only Meta access token stored in the `ADS_API_TOKEN` repository secret.
It writes `data/latest.json`, which `index.html`/`app.js` render — no backend,
no calls to Meta from the browser.

## Local development

```bash
pip install -r requirements-dev.txt
pytest
```

To run the pipeline locally against the real Meta account (never commit the
token):

```bash
export ADS_API_TOKEN=your-token-here
python scripts/fetch_and_analyze.py
```

Full design rationale: see the design spec this plan implements,
`2026-08-10-meta-ads-health-dashboard-design.md`, in the `test claude code`
project repo.
