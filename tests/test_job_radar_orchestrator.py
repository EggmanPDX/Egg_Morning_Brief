import json
import config
import job_radar


def test_run_job_radar_skips_when_no_token(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "APIFY_TOKEN", None)
    result = job_radar.run_job_radar("ts", job_runs_dir=tmp_path)
    assert result == {"found": 0, "shown": 0, "skipped": True}


def test_run_job_radar_happy_path(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "APIFY_TOKEN", "tok")
    found = [
        {"id": "1", "title": "AI Enablement Lead", "posted_date": "2026-05-28"},
        {"id": "2", "title": "Generic Manager", "posted_date": "2026-05-28"},
    ]
    monkeypatch.setattr(job_radar, "search_jobs", lambda *a, **k: found)

    def fake_score(jobs, profile):
        jobs[0]["score"], jobs[0]["reason"] = 90, "great"
        jobs[1]["score"], jobs[1]["reason"] = 20, "nope"
        return jobs

    monkeypatch.setattr(job_radar, "score_jobs", fake_score)
    written = {}
    monkeypatch.setattr(job_radar, "update_job_radar_on_briefing_page",
                        lambda ranked, ts: written.update({"n": len(ranked), "ts": ts}))

    result = job_radar.run_job_radar("ts", job_runs_dir=tmp_path)
    assert result == {"found": 2, "shown": 1, "skipped": False}  # only score>=60 shown
    assert written["n"] == 1
    # full scored list (both jobs) dumped to dated json
    dumps = list(tmp_path.glob("*.json"))
    assert len(dumps) == 1
    saved = json.loads(dumps[0].read_text())
    assert len(saved) == 2


def test_run_job_radar_writes_json_log_before_notion(monkeypatch, tmp_path):
    import pytest
    monkeypatch.setattr(config, "APIFY_TOKEN", "tok")
    found = [{"id": "1", "title": "X", "posted_date": "2026-05-28"}]
    monkeypatch.setattr(job_radar, "search_jobs", lambda *a, **k: found)

    def fake_score(jobs, profile):
        jobs[0]["score"], jobs[0]["reason"] = 90, "great"
        return jobs

    monkeypatch.setattr(job_radar, "score_jobs", fake_score)

    def boom(ranked, ts):
        raise RuntimeError("notion down")

    monkeypatch.setattr(job_radar, "update_job_radar_on_briefing_page", boom)

    # Notion write fails, but the JSON log must already be on disk.
    with pytest.raises(RuntimeError):
        job_radar.run_job_radar("ts", job_runs_dir=tmp_path)
    dumps = list(tmp_path.glob("*.json"))
    assert len(dumps) == 1
    assert len(json.loads(dumps[0].read_text())) == 1
