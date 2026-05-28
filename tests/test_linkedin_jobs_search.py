import linkedin_jobs as lj


def test_search_jobs_orchestrates_and_dedupes(monkeypatch):
    calls = {"start": 0}

    def fake_start_run(actor, run_input, token):
        calls["start"] += 1
        return ("run-id", "dataset-id")

    def fake_wait(run_id, token, timeout=300, interval=10):
        return "SUCCEEDED"

    def fake_fetch(dataset_id, token):
        # same job id returned for both queries -> should dedupe to 1
        return [{"id": "111", "title": "Enablement Lead", "companyName": "AI Co"}]

    monkeypatch.setattr(lj, "_start_run", fake_start_run)
    monkeypatch.setattr(lj, "_wait_for_run", fake_wait)
    monkeypatch.setattr(lj, "_fetch_items", fake_fetch)

    locations = [{"label": "Remote-US", "location": "United States", "remote": ["2"]}]
    out = lj.search_jobs("tok", "actor", ["enablement", "training"], locations,
                         {"contractType": ["F"]}, 40)
    assert calls["start"] == 2          # 2 queries x 1 location
    assert len(out) == 1                # deduped by id
    assert out[0]["company"] == "AI Co"


def test_search_jobs_skips_failed_runs(monkeypatch):
    monkeypatch.setattr(lj, "_start_run", lambda a, i, t: ("r", "d"))
    monkeypatch.setattr(lj, "_wait_for_run", lambda r, t, timeout=300, interval=10: "FAILED")
    monkeypatch.setattr(lj, "_fetch_items", lambda d, t: [{"id": "1"}])
    out = lj.search_jobs("tok", "actor", ["enablement"],
                         [{"label": "X", "location": "US"}], {}, 10)
    assert out == []  # failed run contributes nothing


def test_search_jobs_one_bad_query_does_not_kill_others(monkeypatch):
    def fake_start(actor, run_input, token):
        if run_input["title"] == "boom":
            raise RuntimeError("apify down")
        return ("r", "d")

    monkeypatch.setattr(lj, "_start_run", fake_start)
    monkeypatch.setattr(lj, "_wait_for_run", lambda r, t, timeout=300, interval=10: "SUCCEEDED")
    monkeypatch.setattr(lj, "_fetch_items", lambda d, t: [{"id": "ok1", "title": "Good"}])
    out = lj.search_jobs("tok", "actor", ["boom", "enablement"],
                         [{"label": "X", "location": "US"}], {}, 10)
    assert len(out) == 1 and out[0]["id"] == "ok1"
