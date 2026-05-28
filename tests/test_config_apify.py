import config


def test_config_exposes_apify_token_attr():
    # APIFY_TOKEN must exist as an attribute (value may be None if .env unset)
    assert hasattr(config, "APIFY_TOKEN")
