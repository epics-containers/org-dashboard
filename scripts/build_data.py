#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///
"""Build site/open-items.json: every open issue and PR across the org, plus
what closed or merged recently and what opened recently.

Queries GitHub's search API via `gh api graphql` (the workflow's
GITHUB_TOKEN is enough -- these repos are public, and search only needs read
access to what it is searching). Run locally with a `gh`-authenticated user
that can see the org, e.g.:

    uv run scripts/build_data.py

Change CLOSED_WINDOW_DAYS / NEW_WINDOW_DAYS below to change the windows.
"""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ORG = "epics-containers"
CLOSED_WINDOW_DAYS = 14  # items closed or merged in the last N days are kept, struck through
NEW_WINDOW_DAYS = 7  # items opened in the last N days are marked "new"
OUT_PATH = Path(__file__).resolve().parent.parent / "site" / "open-items.json"

QUERY = """
query($q: String!, $cursor: String) {
  search(query: $q, type: ISSUE, first: 100, after: $cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes {
      __typename
      ... on Issue {
        repository { name }
        number
        title
        url
        author { login }
        createdAt
        updatedAt
        closedAt
        stateReason
        labels(first: 20) { nodes { name } }
      }
      ... on PullRequest {
        repository { name }
        number
        title
        url
        author { login }
        createdAt
        updatedAt
        closedAt
        mergedAt
        isDraft
        labels(first: 20) { nodes { name } }
      }
    }
  }
}
"""


def search(query: str) -> list[dict]:
    """Run a GitHub search query via GraphQL, following pagination."""
    nodes = []
    cursor = None
    while True:
        args = ["api", "graphql", "-f", f"query={QUERY}", "-f", f"q={query}"]
        if cursor:
            args += ["-F", f"cursor={cursor}"]
        out = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
        page = json.loads(out.stdout)["data"]["search"]
        nodes.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            if page["issueCount"] > len(nodes):
                # GitHub search caps results at 1,000 regardless of the true
                # match count -- fail loudly rather than publish a partial list.
                raise SystemExit(
                    f"search truncated: got {len(nodes)}/{page['issueCount']} "
                    f"results for {query!r} (GitHub search caps at 1000; "
                    "split the query, e.g. by repository or date, to fetch more)")
            return nodes
        cursor = page["pageInfo"]["endCursor"]


def row(node: dict, kind: str, new_cutoff: str) -> dict:
    if kind == "pr" and node.get("mergedAt"):
        state, at = "merged", node["mergedAt"]
    elif node.get("closedAt"):
        reason = node.get("stateReason") or "closed"
        state = "not_planned" if reason == "NOT_PLANNED" else "closed"
        at = node["closedAt"]
    else:
        state, at = "open", None
    return {
        "r": node["repository"]["name"],
        "n": node["number"],
        "k": kind,
        "t": node["title"],
        "u": node["url"],
        "a": node["author"]["login"] if node.get("author") else "ghost",
        "c": node["createdAt"][:10],
        "up": node["updatedAt"][:10],
        "l": [lb["name"] for lb in node["labels"]["nodes"]],
        "d": bool(node.get("isDraft")),
        "s": state,
        "at": at[:10] if at else "",
        "isNew": node["createdAt"] >= new_cutoff,
    }


def main() -> None:
    now = datetime.now(timezone.utc)
    closed_since = (now - timedelta(days=CLOSED_WINDOW_DAYS)).strftime("%Y-%m-%d")
    new_cutoff = (now - timedelta(days=NEW_WINDOW_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = []
    for kind, is_kind in (("issue", "is:issue"), ("pr", "is:pull-request")):
        for node in search(f"org:{ORG} {is_kind} is:open"):
            rows.append(row(node, kind, new_cutoff))
        for node in search(f"org:{ORG} {is_kind} closed:>={closed_since}"):
            rows.append(row(node, kind, new_cutoff))

    data = {
        "generatedAt": now.strftime("%Y-%m-%dT%H:%MZ"),
        "org": ORG,
        "windowDays": {"closed": CLOSED_WINDOW_DAYS, "new": NEW_WINDOW_DAYS},
        "rows": rows,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(data, separators=(",", ":")))

    n_open = sum(1 for r in rows if r["s"] == "open")
    n_done = sum(1 for r in rows if r["s"] != "open")
    n_new = sum(1 for r in rows if r["isNew"])
    print(f"{len(rows)} rows: {n_open} open, {n_done} closed/merged in last "
          f"{CLOSED_WINDOW_DAYS}d, {n_new} opened in last {NEW_WINDOW_DAYS}d "
          f"-> {OUT_PATH}")


if __name__ == "__main__":
    main()
