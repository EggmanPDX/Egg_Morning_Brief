import claude_analyzer as ca


def _jobs():
    return [
        {"id": "1", "title": "AI Enablement Lead", "company": "Acme AI",
         "location": "United States", "description": "x" * 1000},
        {"id": "2", "title": "Sales Enablement Manager", "company": "Generic Co",
         "location": "United States", "description": "y"},
    ]


def test_build_scoring_prompt_includes_profile_and_jobs():
    prompt = ca.build_scoring_prompt(_jobs(), "MY_FIT_PROFILE_TEXT")
    assert "MY_FIT_PROFILE_TEXT" in prompt
    assert "AI Enablement Lead" in prompt
    assert "Acme AI" in prompt
    assert '"id"' in prompt  # asks for id in the JSON output
    # description must be truncated to exactly 600 chars (fixture has 1000)
    assert "x" * 600 in prompt
    assert "x" * 601 not in prompt


def test_parse_scoring_response_attaches_scores():
    jobs = _jobs()
    text = '[{"id":"1","score":88,"reason":"AI-forward enablement lead"},' \
           '{"id":"2","score":35,"reason":"generic sales enablement"}]'
    out = ca.parse_scoring_response(text, jobs)
    by_id = {j["id"]: j for j in out}
    assert by_id["1"]["score"] == 88
    assert by_id["1"]["reason"] == "AI-forward enablement lead"
    assert by_id["2"]["score"] == 35


def test_parse_scoring_response_handles_code_fences():
    jobs = [{"id": "1", "title": "T"}]
    text = '```json\n[{"id":"1","score":70,"reason":"ok"}]\n```'
    out = ca.parse_scoring_response(text, jobs)
    assert out[0]["score"] == 70


def test_parse_scoring_response_fallback_on_garbage():
    jobs = _jobs()
    out = ca.parse_scoring_response("not json at all", jobs)
    for j in out:
        assert j["score"] == 0
        assert j["reason"] == "scoring unavailable"


def test_score_jobs_empty_returns_empty():
    assert ca.score_jobs([], "profile") == []


def test_score_jobs_uses_client(monkeypatch):
    class FakeBlock:
        text = '[{"id":"1","score":91,"reason":"strong"}]'

    class FakeResp:
        content = [FakeBlock()]

    monkeypatch.setattr(ca.client.messages, "create", lambda **kw: FakeResp())
    out = ca.score_jobs([{"id": "1", "title": "AI Enablement Lead"}], "profile")
    assert out[0]["score"] == 91
    assert out[0]["reason"] == "strong"


def test_parse_scoring_response_matches_int_vs_str_ids():
    # Apify returns int ids; Claude returns string ids — must still match.
    jobs = [{"id": 4369282613, "title": "X"}]
    text = '[{"id":"4369282613","score":80,"reason":"good"}]'
    out = ca.parse_scoring_response(text, jobs)
    assert out[0]["score"] == 80
    assert out[0]["reason"] == "good"


def test_build_scoring_prompt_includes_source_signal():
    # The authoritative remote/Portland signal (src) must reach the model.
    jobs = [{"id": "1", "title": "Head of Sales Enablement", "company": "Cohere",
             "location": "San Francisco, CA", "src": "Remote-US", "description": ""}]
    prompt = ca.build_scoring_prompt(jobs, "profile")
    assert "Remote-US" in prompt   # the per-job source value is shown
    assert "source" in prompt      # the model is told the source field exists
