# claude_analyzer.py
import anthropic
import json
import re
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, BUSINESS_CONTEXT

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def _response_text(response) -> str:
    """Return the first text block's content, skipping any leading thinking blocks."""
    for block in response.content:
        if block.type == "text":
            return block.text
    raise ValueError("No text block in response")


def analyze_email(email: dict) -> dict:
    """
    Send an email to Claude for analysis.
    Returns: {
        has_action_item: bool,
        action_items: list of str,
        workspace: "D8TAOPS" | "BGC" | "Personal" | "None",
        project_area: str (D8) or None,
        category: str (BGC) or None,
        priority: "High" | "Medium" | "Low",
        summary: str (one sentence),
    }
    """
    prompt = f"""You are analyzing an email for Gregg Eiler. He runs two businesses:
{BUSINESS_CONTEXT}

Analyze this email and return ONLY a JSON object with these exact fields:

{{
  "has_action_item": true/false,
  "action_items": ["string describing what Gregg needs to do", ...],
  "workspace": "D8TAOPS" or "BGC" or "Personal" or "None",
  "project_area": one of ["Enablement", "Client Work", "Marketing", "Internal Systems"] if D8TAOPS, else null,
  "category": one of ["Content & LinkedIn", "Workshops", "Frameworks", "Personal Projects"] if BGC, else null,
  "priority": "High" or "Medium" or "Low",
  "summary": "one sentence describing what this email is about"
}}

Rules:
- has_action_item is true ONLY if the email explicitly or implicitly asks Gregg to DO something
- A reply request = action item. A FYI with no ask = not an action item.
- Priority High: deadline within 48 hours or from CEO/COO/client. Medium: deadline this week. Low: no deadline stated.
- Determine workspace from sender and content context
- If multiple action items, list each separately

Email:
From: {email['sender']}
Subject: {email['subject']}
Date: {email['date']}

Body:
{email['body']}

Return ONLY the JSON object. No preamble, no explanation."""

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    try:
        text = _response_text(response).strip()
        text = text.replace("```json", "").replace("```", "").strip()
        return json.loads(text)
    except (json.JSONDecodeError, IndexError, ValueError):
        return {
            "has_action_item": False,
            "action_items": [],
            "workspace": "None",
            "project_area": None,
            "category": None,
            "priority": "Low",
            "summary": f"[Parse error] {email['subject']}",
        }


def generate_gmail_digest(analyzed_emails: list) -> str:
    """
    Generate a clean digest summary of all emails for the Morning Briefing page.
    Returns plain text string suitable for a Notion paragraph block.
    """
    if not analyzed_emails:
        return "No new emails since last check."

    lines = []
    for item in analyzed_emails:
        email = item["email"]
        analysis = item["analysis"]
        action_tag = "🔴 Action needed" if analysis["has_action_item"] else "📨 FYI"
        lines.append(
            f"{action_tag} — {email['subject']}\n"
            f"From: {email['sender']}\n"
            f"{analysis['summary']}"
        )

    return "\n\n---\n\n".join(lines)


def summarize_newsletter(newsletter: dict) -> list:
    """
    Summarize a newsletter email into up to 7 stories.
    Returns a list of {headline, gist, url} dicts.
    url is the best-matching link from the newsletter HTML, or "" if none found.
    Falls back to a single-item error list on failure.
    """
    if not newsletter or not newsletter.get("body"):
        return [{"headline": "No content available.", "gist": "", "url": ""}]

    links = newsletter.get("links", {})
    links_section = ""
    if links:
        entries = "\n".join(f'  "{text}": "{url}"' for text, url in list(links.items())[:60])
        links_section = f"""
Available links extracted from the newsletter HTML (anchor text → URL):
{entries}

For each story, set "url" to the best-matching link above. Prefer the link whose anchor
text most closely matches the story headline. Use "" if no good match exists."""

    prompt = f"""You are summarizing a newsletter for Gregg Eiler's morning brief.
Extract every distinct story, article, or insight from this issue, up to a maximum of 12.
Include sponsored content and tutorials if they have real informational value. Don't pad
to 12 if the issue only has 4-5 real stories — fewer, real stories beats padded filler.

Newsletter: {newsletter['name']}
Subject: {newsletter['subject']}

Body:
{newsletter['body']}
{links_section}

Return ONLY a JSON array, no preamble, no markdown fences:
[
  {{"headline": "Story headline", "gist": "One-sentence gist, ≤25 words.", "url": "https://..."}}
]

Be concrete. Name the actual topic, company, or finding. No vague summaries."""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = _response_text(response).strip()
        raw = re.sub(r'^```[a-z]*\n?', '', raw).rstrip('`').strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Salvage complete objects from a truncated or malformed array
            objects = re.findall(r'\{[^{}]+\}', raw, re.DOTALL)
            results = []
            for obj in objects:
                try:
                    results.append(json.loads(obj))
                except json.JSONDecodeError:
                    pass
            if results:
                return results
            raise
    except Exception as e:
        return [{"headline": f"[Summary error: {e}]", "gist": "", "url": ""}]


DESC_TRUNCATE = 600


def build_scoring_prompt(jobs: list, profile: str) -> str:
    """Build one prompt that scores every job against the fit-profile."""
    lines = []
    for j in jobs:
        desc = (j.get("description") or "")[:DESC_TRUNCATE]
        lines.append(
            f'- id: {j.get("id")}\n'
            f'  title: {j.get("title")}\n'
            f'  company: {j.get("company")}\n'
            f'  location: {j.get("location")}\n'
            f'  source: {j.get("src")}\n'
            f'  description: {desc}'
        )
    job_block = "\n".join(lines)
    return f"""You score job postings for Gregg Eiler against his ideal-role profile.

IDEAL ROLE PROFILE:
{profile}

Score each job 0-100 for fit against the profile (100 = perfect, 0 = irrelevant).
Be strict: "AI-forward company" and training/enablement leadership are what matter.

The `source` field is the AUTHORITATIVE location signal — it lists which LinkedIn searches
matched the role: "Remote-US" means LinkedIn flagged it remote-eligible (US); "Portland, OR"
means it matched the Portland-area search. Trust `source` over the `location` field for the
profile's location weighting (a role may show a city but still be Remote-US).

JOBS:
{job_block}

Return ONLY a JSON array, one object per job, using the SAME id given above:
[{{"id": "<id>", "score": <0-100 int>, "reason": "<=12 word why"}}]
No preamble, no explanation, no code fences."""


def parse_scoring_response(text: str, jobs: list) -> list:
    """Attach score+reason to each job by id (compared as strings, since Apify
    ids are ints but Claude returns them as strings). Garbage -> all score 0."""
    by_id = {str(j.get("id")): j for j in jobs}
    for j in jobs:  # defaults first so every job is covered
        j["score"] = 0
        j["reason"] = "scoring unavailable"
    matched = 0
    try:
        clean = (text or "").replace("```json", "").replace("```", "").strip()
        for entry in json.loads(clean):
            jid = str(entry.get("id"))
            if jid in by_id:
                by_id[jid]["score"] = int(entry.get("score", 0))
                reason = (entry.get("reason") or "").strip()
                by_id[jid]["reason"] = reason or "n/a"
                matched += 1
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as e:
        print(f"   ⚠️ Job Radar: scoring parse failed ({type(e).__name__}: {e})")
    if jobs and matched == 0:
        print(f"   ⚠️ Job Radar: scored 0 of {len(jobs)} jobs (id mismatch or empty response)")
    return jobs


SCORING_BATCH_SIZE = 40  # keeps each call's output well under the token cap regardless of total job count


def _score_batch(jobs: list, profile: str) -> list:
    """Score a single batch of jobs in one Claude call. Degrades to score 0 on any error."""
    prompt = build_scoring_prompt(jobs, profile)
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = _response_text(response).strip()
    except Exception as e:
        print(f"   ⚠️ Job Radar: scoring call failed ({e}); defaulting to score 0")
        text = ""
    return parse_scoring_response(text, jobs)


def score_jobs(jobs: list, profile: str) -> list:
    """Score all jobs, batching so no single call's output risks truncation."""
    if not jobs:
        return []
    scored = []
    for i in range(0, len(jobs), SCORING_BATCH_SIZE):
        scored.extend(_score_batch(jobs[i:i + SCORING_BATCH_SIZE], profile))
    return scored
