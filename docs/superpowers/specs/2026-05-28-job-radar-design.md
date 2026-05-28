# Job Radar — Design Spec

- **Date:** 2026-05-28
- **Project:** Egg_MORNING_BRIEF
- **Status:** Draft for review

## 1. Goal

Add a daily **Job Radar** to the existing Morning Brief: surface the top LinkedIn
roles in **training / enablement at AI-forward companies**, posted in the last 24h,
ranked by fit, written into the Morning Briefing Notion page so they appear in the
brief wherever Gregg reads it.

## 2. How it runs (confirmed)

- Job Radar is a **new step inside `morning_brief_worker.py`** — not a separate script or cron.
- Triggered by the **existing** crontab entry:
  `30 8 * * 1-5` → `python3 morning_brief_worker.py` — **8:30 AM, Mon–Fri, local on Gregg's Mac**.
- It writes a `💼 Job Radar` section to the Notion Morning Briefing page
  (`MORNING_BRIEFING_PAGE_ID`, set in `.env`).
- Because the output lives on that Notion page, it appears automatically when Gregg reads
  his brief in **Claude Code** (the "Good morning" ritual) **and Claude Cowork**.
  The radar logic runs locally via cron; Code/Cowork only *read* the resulting page.
- **Cadence note:** cron is weekdays-only. Weekend postings are not captured until the cron
  is changed to 7-day. Out of scope for v1 (one-line change later).

## 3. Pipeline

```
Apify broad search  →  normalize  →  Claude batch-score vs FIT_PROFILE  →  threshold + rank  →  top 5
                                                                                              ├→ Notion "💼 Job Radar" section
                                                                                              └→ dated JSON log (job_runs/<date>.json)
```

The engine decides "fit" by having **Claude score each role 0–100 against an editable
plain-English profile** (chosen approach). Apify keeps searches broad and cheap; Claude does
the "AI-forward + leadership" judgment.

## 4. Components

### 4.1 `linkedin_jobs.py` (new)

- `search_jobs(config) -> list[dict]`
  - For each `query × location`: start an Apify run of `valig~linkedin-jobs-scraper` with input
    `{title: query, ...location, contractType: ["F"], datePosted: "r86400", limit: LIMIT}`.
    - Portland location → `{"location": "Portland, Oregon, United States"}`
    - Remote-US → `{"location": "United States", "remote": ["2"]}`
  - Poll each run until terminal (SUCCEEDED/FAILED/ABORTED/TIMED-OUT), then fetch dataset items (`clean=true`).
  - Merge all items; **dedupe by `id`** (merge `src` location tags).
  - Normalize each item →
    `{id, title, company, location, salary, applicants_raw, applicants, posted_date, posted_ago, url, apply_url, description, src}`.
  - Applicants normalization: `"Be among the first 25 applicants"` → `"<25"`;
    `"Over 200 applicants"` → `"200+"`; `"162 applicants"` → `"162"`; missing → `"n/a"`.
- `__main__`: run search + score + **print the ranked table to stdout (no Notion write)**.
  This is the tuning view used during collaborative tuning.

### 4.2 `job_radar_config.py` (new) — the one file edited when tuning

```python
APIFY_ACTOR    = "valig~linkedin-jobs-scraper"
QUERIES        = ["enablement", "training"]
LOCATIONS      = [
    {"label": "Portland, OR", "location": "Portland, Oregon, United States"},
    {"label": "Remote-US",    "location": "United States", "remote": ["2"]},
]
FILTERS        = {"contractType": ["F"], "datePosted": "r86400"}  # full-time, last 24h
LIMIT          = 40   # per query × location
TOP_N          = 5
SHOW_THRESHOLD = 60   # only roles scoring >= this appear
FIT_PROFILE    = """
Ideal: training, enablement, or L&D leadership roles (Lead / Manager / Director / Head) at
AI-forward companies — orgs building AI products or aggressively adopting AI internally.
Strong fit: "AI enablement", "GenAI training", enablement at an AI/ML company.
Weak fit: generic sales enablement at a non-tech company, IC / coordinator roles,
pure instructional-design with no strategy scope.
Location: remote-US or Portland, OR. Full-time.
"""
```

### 4.3 `claude_analyzer.py` (extend)

- `score_jobs(jobs, profile) -> list[dict]`
  - **One batched Claude call.** Prompt = the `FIT_PROFILE` + a numbered list of jobs
    (`id`, `title`, `company`, `location`, description truncated to ~600 chars).
  - Asks for ONLY a JSON array: `[{"id": ..., "score": 0-100, "reason": "<=12 words"}]`.
  - Reuses `client` + `CLAUDE_MODEL`; same fenced-JSON strip + `try/except` fallback as `analyze_email`.
  - On parse failure: every job gets `score 0`, `reason "scoring unavailable"`.
  - Attaches `score` + `reason` back onto each job by `id`.

### 4.4 `notion_writer.py` (extend)

- `JOB_RADAR_HEADING = "💼 Job Radar"`
- `update_job_radar_on_briefing_page(ranked_jobs, run_timestamp)`
  - **Mirrors** `_find_gmail_digest_block` / `update_gmail_digest_on_briefing_page` exactly:
    find the heading by text, delete the old content blocks beneath it, append fresh content.
  - Content:
    - A gray `Last updated: <run_timestamp>` callout.
    - If `ranked_jobs` is empty → one paragraph: **"No strong matches today."**
    - Else → one `bulleted_list_item` per role (≤ `TOP_N`):
      - bold `Title — Company` · `score/100`
      - `location · posted · applicants`
      - the one-line "why it fits"
      - an **Apply** link (Notion rich_text link annotation → `apply_url` or `url`)

### 4.5 `morning_brief_worker.py` (extend)

- New **"Step 7: Job Radar"** after the Gmail-digest step, wrapped in `try/except` so a
  Job Radar failure is logged but **never aborts** the Gmail/tasks brief.
  - `jobs = search_jobs(...)`
  - `scored = score_jobs(jobs, FIT_PROFILE)`
  - `ranked = [j for j in scored if j["score"] >= SHOW_THRESHOLD]`, sorted by
    **score desc, then posted_date desc (newest first)**, sliced to `TOP_N`.
  - `update_job_radar_on_briefing_page(ranked, run_timestamp)`
  - Dump the **full scored list** (not just top 5) to `job_runs/<YYYY-MM-DD>.json`.
- `run_log` gains `jobs_found` and `jobs_shown` counters.

### 4.6 `config.py` + secrets

- `config.py`: add `APIFY_TOKEN = os.getenv("APIFY_TOKEN")`.
- `.env`: add `APIFY_TOKEN=<token>` (moved from the temp `~/.apify_token`).
- `.env.example`: add `APIFY_TOKEN=your_apify_api_token_here`.
- **Delete `~/.apify_token`** after the move.
- If `APIFY_TOKEN` is missing at runtime: skip Job Radar with a logged warning; the rest of the brief continues.

## 5. Ranking rule

1. Keep roles with `score >= SHOW_THRESHOLD` (60).
2. Sort by `score` desc; tie-break `posted_date` desc (newest first).
3. Take the first `TOP_N` (5). Fewer than 5 above the bar is fine. Zero → "No strong matches today."

## 6. Cost / limits

- `valig` actor is pay-per-result; the Apify account is **FREE** (monthly credit ~$5).
- Worst case 2 queries × 2 locations × `LIMIT 40` = ≤160 result-events/day; realistically far
  fewer under the 24h filter. Dial `LIMIT` / `QUERIES` down if credit runs low.
- One batched Claude call per day with truncated descriptions — a few cents.

## 7. Failure handling (all degrade gracefully; brief never breaks)

| Failure | Behavior |
|---|---|
| Apify error / empty | Section shows "No strong matches today." Brief continues. |
| Claude scoring error | All scores 0 → "No strong matches today." Brief continues. |
| `APIFY_TOKEN` missing | Job Radar skipped with logged warning. Brief continues. |

## 8. Tuning workflow (collaborative — chosen approach)

Gregg says "tune it." Claude edits `job_radar_config.py` (`QUERIES`, `LOCATIONS`, `FILTERS`,
`SHOW_THRESHOLD`, `FIT_PROFILE`), runs `python3 linkedin_jobs.py` to print the ranked table,
and iterates with Gregg until the picks are right. No Notion write happens during tuning.

## 9. Out of scope (v1)

- Weekend runs (cron is Mon–Fri).
- Salary enrichment (LinkedIn hides it on most postings).
- De-duping roles across multiple days.
- A productized preview/CLI beyond the stdout print.
- Apply / outreach automation.

## 10. Assumptions

- Reuses `CLAUDE_MODEL` (`claude-sonnet-4-20250514`) — not upgrading the model as part of this work.
- `FIT_PROFILE` v1 prose is a starting point; it is expected to evolve through tuning.
