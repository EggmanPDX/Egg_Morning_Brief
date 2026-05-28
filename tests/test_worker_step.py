import morning_brief_worker as worker


def test_load_run_log_defaults_include_job_counters(tmp_path, monkeypatch):
    # point the run log at a non-existent temp file so defaults are returned
    monkeypatch.setattr(worker, "RUN_LOG_PATH", tmp_path / "nope.json")
    log = worker.load_run_log()
    assert log["jobs_found"] == 0
    assert log["jobs_shown"] == 0
