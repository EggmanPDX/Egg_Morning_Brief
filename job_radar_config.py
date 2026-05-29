# job_radar_config.py
# The single file to edit when tuning Job Radar (queries, locations, threshold, fit-profile).
from __future__ import annotations

APIFY_ACTOR = "valig~linkedin-jobs-scraper"

QUERIES = ["enablement", "training"]

LOCATIONS = [
    {"label": "Portland, OR", "location": "Portland, Oregon, United States"},
    {"label": "Remote-US", "location": "United States", "remote": ["2"]},
]

# Apify valig schema: contractType F=Full-time; datePosted r86400=past 24h
FILTERS = {"contractType": ["F"], "datePosted": "r86400"}

LIMIT = 40            # results per query x location
TOP_N = 5             # max roles shown in the brief
SHOW_THRESHOLD = 60   # only roles scoring >= this appear

FIT_PROFILE = """
Ideal: training, enablement, or L&D leadership roles (Lead / Manager / Director / Head) at
AI-forward companies - orgs building AI products or aggressively adopting AI internally.
Strong fit: "AI enablement", "GenAI training", enablement at an AI/ML company.
Weak fit: generic sales enablement at a non-tech company, IC / coordinator roles,
pure instructional-design with no strategy scope.

LOCATION IS HEAVILY WEIGHTED. Strongly boost roles that are fully remote (US) or based in
Portland, OR. Significantly downgrade roles that require on-site or hybrid presence outside
Portland, even at AI-forward companies. Infer remote/Portland from the location field AND
the title/description (look for "Remote", "Remote, US", "Portland", "work from anywhere"); a
generic "United States" location paired with remote language counts as remote. Full-time only.
"""
