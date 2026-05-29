# linkedin_jobs.py
# Apify LinkedIn job search + pure data shaping for Job Radar.
from __future__ import annotations

import re
import time

import requests

APIFY_BASE = "https://api.apify.com/v2"


def normalize_applicants(raw) -> str:
    """LinkedIn applicant text -> compact string. '' / None -> 'n/a'."""
    if not raw:
        return "n/a"
    text = str(raw)
    low = text.lower()
    if "first" in low:  # "Be among the first 25 applicants"
        m = re.search(r"(\d+)", text)
        return f"<{m.group(1)}" if m else "<25"
    if "over" in low:  # "Over 200 applicants"
        m = re.search(r"(\d+)", text)
        return f"{m.group(1)}+" if m else text
    m = re.search(r"(\d+)", text)  # "162 applicants"
    return m.group(1) if m else text


def build_run_input(query: str, location_cfg: dict, filters: dict, limit: int) -> dict:
    """Build the Apify valig actor input. Never leaks the 'label' key to Apify."""
    inp = {"title": query, "limit": limit, "location": location_cfg["location"]}
    if location_cfg.get("remote"):
        inp["remote"] = location_cfg["remote"]
    inp.update(filters)  # contractType, datePosted
    return inp


def normalize_job(item: dict, src_label: str) -> dict:
    """Map a raw valig dataset item to the Job Radar shape."""
    posted_date = (item.get("postedDate") or "")[:10]
    return {
        "id": None if item.get("id") is None else str(item.get("id")),
        "title": item.get("title") or "",
        "company": item.get("companyName") or "",
        "location": item.get("location") or "",
        "salary": item.get("salary") or "",
        "applicants_raw": item.get("applicationsCount") or "",
        "applicants": normalize_applicants(item.get("applicationsCount")),
        "posted_date": posted_date,
        "posted_ago": item.get("postedTimeAgo") or "",
        "url": item.get("url") or "",
        "apply_url": item.get("applyUrl") or item.get("url") or "",
        "description": item.get("description") or "",
        "src": src_label,
    }


def merge_dedupe(jobs: list) -> list:
    """Dedupe by job id; merge src labels for duplicates. Does not mutate inputs."""
    seen: dict = {}
    for j in jobs:
        jid = j["id"]
        if jid in seen:
            if j["src"] not in seen[jid]["src"].split("+"):
                seen[jid]["src"] += "+" + j["src"]
        else:
            seen[jid] = dict(j)
    return list(seen.values())


def rank_jobs(scored: list, threshold: int, top_n: int) -> list:
    """Keep score>=threshold, sort by score desc then posted_date desc, take top_n."""
    eligible = [j for j in scored if j.get("score", 0) >= threshold]
    eligible.sort(key=lambda j: (j.get("score", 0), j.get("posted_date", "")), reverse=True)
    return eligible[:top_n]


def _start_run(actor: str, run_input: dict, token: str):
    """Start an Apify actor run. Returns (run_id, dataset_id)."""
    r = requests.post(
        f"{APIFY_BASE}/acts/{actor}/runs",
        params={"token": token},
        json=run_input,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()["data"]
    return data["id"], data["defaultDatasetId"]


def _wait_for_run(run_id: str, token: str, timeout: int = 300, interval: int = 10) -> str:
    """Poll a run until terminal. Returns final status (or 'TIMED-OUT' on deadline)."""
    terminal = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}", params={"token": token}, timeout=30
        )
        r.raise_for_status()
        status = r.json()["data"]["status"]
        if status in terminal:
            return status
        time.sleep(interval)
    return "TIMED-OUT"


def _fetch_items(dataset_id: str, token: str) -> list:
    """Fetch all items from a dataset (clean view)."""
    r = requests.get(
        f"{APIFY_BASE}/datasets/{dataset_id}/items",
        params={"token": token, "clean": "true"},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()


def search_jobs(token, actor, queries, locations, filters, limit, poll_timeout: int = 300) -> list:
    """Run actor for each query x location, normalize, merge+dedupe. Robust per run."""
    collected = []
    for query in queries:
        for loc in locations:
            label = loc.get("label", loc.get("location", "?"))
            try:
                run_input = build_run_input(query, loc, filters, limit)
                run_id, dataset_id = _start_run(actor, run_input, token)
                status = _wait_for_run(run_id, token, poll_timeout)
                if status != "SUCCEEDED":
                    print(f"   ⚠️ Job Radar: run '{query}' @ {label} ended {status}")
                    continue
                for item in _fetch_items(dataset_id, token):
                    collected.append(normalize_job(item, label))
            except Exception as e:
                print(f"   ⚠️ Job Radar: search failed '{query}' @ {label}: {e}")
                continue
    return merge_dedupe(collected)


if __name__ == "__main__":
    # Tuning view: prints the ranked table to stdout. No Notion write.
    from config import APIFY_TOKEN
    from claude_analyzer import score_jobs
    import job_radar_config as cfg

    found = search_jobs(
        APIFY_TOKEN, cfg.APIFY_ACTOR, cfg.QUERIES, cfg.LOCATIONS, cfg.FILTERS, cfg.LIMIT
    )
    scored = score_jobs(found, cfg.FIT_PROFILE)
    ranked = rank_jobs(scored, cfg.SHOW_THRESHOLD, cfg.TOP_N)
    print(f"\nFound {len(found)} | above {cfg.SHOW_THRESHOLD}: {len(ranked)}\n")
    for j in ranked:
        link = j.get("apply_url") or j.get("url")
        print(f"[{j['score']}] {j['title']} — {j['company']} ({j['location']}) "
              f"| {j['posted_ago']} | {j['applicants']} applicants | {link}")
        print(f"      why: {j['reason']}")
