# job_radar.py
# Orchestrates the daily Job Radar: search -> score -> rank -> Notion + JSON log.
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import config
import job_radar_config as cfg
from linkedin_jobs import search_jobs, rank_jobs
from claude_analyzer import score_jobs
from notion_writer import update_job_radar_on_briefing_page

DEFAULT_JOB_RUNS_DIR = Path(__file__).parent / "job_runs"


def run_job_radar(run_timestamp: str, job_runs_dir=None) -> dict:
    """Run one Job Radar cycle. Returns {found, shown, skipped}. Never raises for
    expected failure modes (missing token); search/score degrade internally."""
    if not config.APIFY_TOKEN:
        return {"found": 0, "shown": 0, "skipped": True}

    found = search_jobs(
        config.APIFY_TOKEN, cfg.APIFY_ACTOR, cfg.QUERIES, cfg.LOCATIONS, cfg.FILTERS, cfg.LIMIT
    )
    scored = score_jobs(found, cfg.FIT_PROFILE)
    ranked = rank_jobs(scored, cfg.SHOW_THRESHOLD, cfg.TOP_N)

    out_dir = Path(job_runs_dir) if job_runs_dir else DEFAULT_JOB_RUNS_DIR
    out_dir.mkdir(exist_ok=True)
    (out_dir / f"{datetime.now():%Y-%m-%d}.json").write_text(json.dumps(scored, indent=2))

    update_job_radar_on_briefing_page(ranked, run_timestamp)

    return {"found": len(found), "shown": len(ranked), "skipped": False}
