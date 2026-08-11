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

Put `ADS_API_TOKEN=your-token-here` in a local `.env` file (gitignored, never
commit it). Then either:

- Run the pipeline once: `python scripts/fetch_and_analyze.py`
- Or serve the dashboard with `python scripts/dev_server.py` (instead of a
  plain `http.server`) — this also exposes `POST /api/refresh`, which powers
  the "Refrescar" button that only appears when the page is loaded from
  `localhost`/`127.0.0.1`. That endpoint re-runs the same pipeline synchronously
  and can take ~1 minute (one Meta API call per ad for delivery issues and
  creative-change history). The button is inert on GitHub Pages — there's no
  server there to answer `/api/refresh`, by design, so the Meta token never
  reaches the browser.

Full design rationale: see the design spec this plan implements,
`2026-08-10-meta-ads-health-dashboard-design.md`, in the `test claude code`
project repo.
