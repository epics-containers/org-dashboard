# org-dashboard

**Dashboard: <https://epics-containers.github.io/org-dashboard/>**

A dashboard, published on GitHub Pages, listing every open issue and pull
request across the `epics-containers` GitHub organisation: grouped by repo,
filterable by issue/PR and state, with bot PRs hidden by default and a search
box. Items closed or merged recently stay listed, struck through and dated;
items opened recently are marked "new".

## How it's refreshed

`.github/workflows/pages.yml` runs `scripts/build_data.py` on a schedule
(every 30 minutes), on `workflow_dispatch`, and on every push to `main`. The
script queries the GitHub search API (via `gh api graphql`, using the
workflow's own `GITHUB_TOKEN` -- these repos are public, so no extra token is
needed) and writes `site/open-items.json`. The workflow then uploads
`site/` (the JSON plus a copy of `index.html`) as a Pages artifact and
deploys it.

`index.html` fetches `open-items.json` at load time and renders it client
side; there is no server and no database.

To trigger a refresh outside the schedule, use the "Run a refresh now" link
on the page, or `gh workflow run pages.yml`.

## Running locally

```
uv run scripts/build_data.py
```

This writes `site/open-items.json` from the repo root. Open `index.html` via
a local web server (a `file://` URL won't allow the `fetch`), e.g.:

```
cp site/open-items.json .
python3 -m http.server
```

then browse to `index.html`.

## Changing the windows

`CLOSED_WINDOW_DAYS` (how long a closed/merged item stays listed) and
`NEW_WINDOW_DAYS` (how long an item is marked "new") are constants at the top
of `scripts/build_data.py`.

## One-time setup

In the repo's Settings -> Pages, set Source to "GitHub Actions".
