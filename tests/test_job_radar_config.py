import job_radar_config as cfg


def test_config_has_expected_shape():
    assert cfg.APIFY_ACTOR == "valig~linkedin-jobs-scraper"
    assert isinstance(cfg.QUERIES, list) and cfg.QUERIES
    assert isinstance(cfg.LOCATIONS, list) and cfg.LOCATIONS
    # every location entry needs a label + location string
    for loc in cfg.LOCATIONS:
        assert "label" in loc and "location" in loc
    assert cfg.FILTERS["contractType"] == ["F"]
    assert cfg.FILTERS["datePosted"] == "r86400"
    assert isinstance(cfg.LIMIT, int) and cfg.LIMIT > 0
    assert isinstance(cfg.TOP_N, int) and cfg.TOP_N > 0
    assert 0 <= cfg.SHOW_THRESHOLD <= 100
    assert "AI-forward" in cfg.FIT_PROFILE
