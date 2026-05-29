import linkedin_jobs as lj


def test_normalize_applicants_variants():
    assert lj.normalize_applicants("Be among the first 25 applicants") == "<25"
    assert lj.normalize_applicants("Over 200 applicants") == "200+"
    assert lj.normalize_applicants("162 applicants") == "162"
    assert lj.normalize_applicants("") == "n/a"
    assert lj.normalize_applicants(None) == "n/a"


def test_build_run_input_portland_has_no_remote():
    loc = {"label": "Portland, OR", "location": "Portland, Oregon, United States"}
    filters = {"contractType": ["F"], "datePosted": "r86400"}
    inp = lj.build_run_input("enablement", loc, filters, 40)
    assert inp["title"] == "enablement"
    assert inp["location"] == "Portland, Oregon, United States"
    assert inp["limit"] == 40
    assert inp["contractType"] == ["F"]
    assert inp["datePosted"] == "r86400"
    assert "remote" not in inp
    assert "label" not in inp  # label must never be sent to Apify


def test_build_run_input_remote_includes_remote_flag():
    loc = {"label": "Remote-US", "location": "United States", "remote": ["2"]}
    inp = lj.build_run_input("training", loc, {"contractType": ["F"]}, 25)
    assert inp["remote"] == ["2"]


def test_normalize_job_maps_fields():
    raw = {
        "id": "123",
        "title": "Enablement Manager",
        "companyName": "Acme AI",
        "location": "United States",
        "salary": "",
        "applicationsCount": "162 applicants",
        "postedDate": "2026-05-28T10:00:00.000Z",
        "postedTimeAgo": "2 hours ago",
        "url": "https://linkedin.com/jobs/view/123",
        "applyUrl": "https://linkedin.com/apply/123",
        "description": "Build enablement.",
    }
    j = lj.normalize_job(raw, "Remote-US")
    assert j["id"] == "123"
    assert j["title"] == "Enablement Manager"
    assert j["company"] == "Acme AI"
    assert j["applicants"] == "162"
    assert j["applicants_raw"] == "162 applicants"
    assert j["posted_date"] == "2026-05-28"
    assert j["posted_ago"] == "2 hours ago"
    assert j["apply_url"] == "https://linkedin.com/apply/123"
    assert j["src"] == "Remote-US"


def test_normalize_job_apply_url_falls_back_to_url():
    raw = {"id": "9", "url": "https://linkedin.com/jobs/view/9"}
    j = lj.normalize_job(raw, "Portland, OR")
    assert j["apply_url"] == "https://linkedin.com/jobs/view/9"


def test_merge_dedupe_merges_src_for_same_id():
    a = lj.normalize_job({"id": "1", "title": "X"}, "Portland, OR")
    b = lj.normalize_job({"id": "1", "title": "X"}, "Remote-US")
    c = lj.normalize_job({"id": "2", "title": "Y"}, "Remote-US")
    out = lj.merge_dedupe([a, b, c])
    assert len(out) == 2
    by_id = {j["id"]: j for j in out}
    assert by_id["1"]["src"] == "Portland, OR+Remote-US"


def test_rank_jobs_threshold_and_order():
    jobs = [
        {"id": "a", "score": 40, "posted_date": "2026-05-28"},
        {"id": "b", "score": 80, "posted_date": "2026-05-27"},
        {"id": "c", "score": 60, "posted_date": "2026-05-28"},
        {"id": "d", "score": 75, "posted_date": "2026-05-28"},
    ]
    ranked = lj.rank_jobs(jobs, threshold=60, top_n=5)
    assert [j["id"] for j in ranked] == ["b", "d", "c"]  # a dropped (score<60); rest sorted score desc


def test_rank_jobs_tiebreak_newest_first():
    jobs = [
        {"id": "old", "score": 70, "posted_date": "2026-05-26"},
        {"id": "new", "score": 70, "posted_date": "2026-05-28"},
    ]
    ranked = lj.rank_jobs(jobs, threshold=60, top_n=5)
    assert [j["id"] for j in ranked] == ["new", "old"]


def test_merge_dedupe_does_not_mutate_inputs():
    a = lj.normalize_job({"id": "1", "title": "X"}, "Portland, OR")
    b = lj.normalize_job({"id": "1", "title": "X"}, "Remote-US")
    lj.merge_dedupe([a, b])
    assert a["src"] == "Portland, OR"  # original dict must be untouched


def test_normalize_job_stringifies_int_id():
    j = lj.normalize_job({"id": 4369282613, "title": "X"}, "Remote-US")
    assert j["id"] == "4369282613"
    assert isinstance(j["id"], str)


def test_normalize_job_keeps_none_id_as_none():
    j = lj.normalize_job({"title": "no id"}, "Remote-US")
    assert j["id"] is None
