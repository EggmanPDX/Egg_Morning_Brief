import notion_writer as nw


def test_empty_ranked_shows_no_matches():
    blocks = nw.build_job_radar_blocks([], "May 28, 2026 at 08:30 AM")
    assert blocks[0]["type"] == "callout"
    assert blocks[1]["type"] == "paragraph"
    para_text = blocks[1]["paragraph"]["rich_text"][0]["text"]["content"]
    assert para_text == "No strong matches today."


def test_ranked_jobs_render_as_bulleted_items_with_apply_link():
    ranked = [{
        "title": "AI Enablement Lead", "company": "Acme AI", "location": "United States",
        "posted_ago": "2 hours ago", "posted_date": "2026-05-28", "applicants": "162",
        "score": 88, "reason": "AI-forward enablement lead",
        "apply_url": "https://linkedin.com/apply/1", "url": "https://linkedin.com/jobs/1",
    }]
    blocks = nw.build_job_radar_blocks(ranked, "ts")
    assert blocks[0]["type"] == "callout"
    item = blocks[1]
    assert item["type"] == "bulleted_list_item"
    rich = item["bulleted_list_item"]["rich_text"]
    # title segment is bold
    assert rich[0]["annotations"]["bold"] is True
    assert "AI Enablement Lead" in rich[0]["text"]["content"]
    # an Apply link segment carries the apply_url
    apply_seg = [s for s in rich if s["text"].get("link")]
    assert apply_seg and apply_seg[0]["text"]["link"]["url"] == "https://linkedin.com/apply/1"


def test_render_falls_back_to_url_when_no_apply_url():
    ranked = [{
        "title": "T", "company": "C", "location": "US", "posted_ago": "", "posted_date": "",
        "applicants": "n/a", "score": 70, "reason": "ok",
        "apply_url": "", "url": "https://linkedin.com/jobs/9",
    }]
    rich = nw.build_job_radar_blocks(ranked, "ts")[1]["bulleted_list_item"]["rich_text"]
    apply_seg = [s for s in rich if s["text"].get("link")]
    assert apply_seg[0]["text"]["link"]["url"] == "https://linkedin.com/jobs/9"
