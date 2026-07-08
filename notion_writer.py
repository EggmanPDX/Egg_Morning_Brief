# notion_client.py
from __future__ import annotations
import os
from datetime import date
from notion_client import Client
from config import (
    NOTION_API_KEY,
    MORNING_BRIEFING_PAGE_ID,
    D8_DB_PAGE_ID,
    BGC_DB_PAGE_ID,
)

notion = Client(auth=NOTION_API_KEY)

# Heading text to find the Gmail Digest section on the Morning Briefing page
GMAIL_DIGEST_HEADING = "📬 Gmail Digest"

NOTION_RICH_TEXT_LIMIT = 2000


def _chunked_rich_text(text: str) -> list:
    """Split text into rich_text objects respecting Notion's 2000-char-per-item limit."""
    chunks = [text[i:i + NOTION_RICH_TEXT_LIMIT] for i in range(0, len(text), NOTION_RICH_TEXT_LIMIT)]
    return [{"type": "text", "text": {"content": c}} for c in chunks] or [{"type": "text", "text": {"content": ""}}]


def create_d8_task(task_name: str, priority: str, project_area: str, source_context: str = "") -> str:
    """Create a task in D8 Tasks & Projects. Returns created page ID."""
    props = {
        "Task / Project": {"title": [{"text": {"content": task_name}}]},
        "Status": {"select": {"name": "To-do"}},
        "Priority": {"select": {"name": priority}},
        "Type": {"select": {"name": "Task"}},
        "Source / Context": {"rich_text": [{"text": {"content": source_context}}]},
    }
    if project_area and project_area in ["Enablement", "Client Work", "Marketing", "Internal Systems"]:
        props["Project Area"] = {"select": {"name": project_area}}

    response = notion.pages.create(
        parent={"database_id": D8_DB_PAGE_ID},
        properties=props,
    )
    return response["id"]


def create_bgc_task(task_name: str, priority: str, category: str, source_context: str = "") -> str:
    """Create a task in BGC Tasks & Projects. Returns created page ID."""
    props = {
        "Task / Project": {"title": [{"text": {"content": task_name}}]},
        "Status": {"select": {"name": "To-do"}},
        "Priority": {"select": {"name": priority}},
        "Type": {"select": {"name": "Task"}},
        "Source / Context": {"rich_text": [{"text": {"content": source_context}}]},
    }
    if category and category in ["Content & LinkedIn", "Workshops", "Frameworks", "Personal Projects"]:
        props["Category"] = {"select": {"name": category}}

    response = notion.pages.create(
        parent={"database_id": BGC_DB_PAGE_ID},
        properties=props,
    )
    return response["id"]


def _find_gmail_digest_block(blocks):
    """Find the Gmail Digest heading block ID and the IDs of content blocks below it."""
    results = blocks.get("results", [])
    heading_id = None
    content_block_ids = []
    found = False

    for block in results:
        if found:
            btype = block.get("type", "")
            if btype in ["heading_1", "heading_2", "heading_3", "divider"]:
                break
            content_block_ids.append(block["id"])
            continue

        if block.get("type") == "heading_2":
            text = "".join(
                rt.get("plain_text", "")
                for rt in block["heading_2"].get("rich_text", [])
            )
            if GMAIL_DIGEST_HEADING in text:
                heading_id = block["id"]
                found = True

    return heading_id, content_block_ids


def update_gmail_digest_on_briefing_page(digest_text: str, run_timestamp: str):
    """
    Replace the content under the Gmail Digest heading with fresh digest output.
    If the section doesn't exist, appends it to the page.
    """
    blocks = notion.blocks.children.list(block_id=MORNING_BRIEFING_PAGE_ID)
    heading_id, old_content_ids = _find_gmail_digest_block(blocks)

    # Delete old content blocks under the heading
    for block_id in old_content_ids:
        try:
            notion.blocks.delete(block_id=block_id)
        except Exception:
            pass

    new_blocks = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": f"Last updated: {run_timestamp}"}}],
                "icon": {"emoji": "🕗"},
                "color": "gray_background",
            },
        },
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": _chunked_rich_text(digest_text)
            },
        },
    ]

    if heading_id:
        # Insert right after the heading so the digest stays in its own section.
        # (Other sections like Job Radar now follow it on the page, so appending to
        # the page end would misplace the content and let it be clobbered.)
        notion.blocks.children.append(
            block_id=MORNING_BRIEFING_PAGE_ID, children=new_blocks, after=heading_id
        )
    else:
        # Section missing — append heading + content to end of page
        notion.blocks.children.append(
            block_id=MORNING_BRIEFING_PAGE_ID,
            children=[
                {
                    "object": "block",
                    "type": "divider",
                    "divider": {},
                },
                {
                    "object": "block",
                    "type": "heading_2",
                    "heading_2": {
                        "rich_text": [{"type": "text", "text": {"content": GMAIL_DIGEST_HEADING}}]
                    },
                },
                *new_blocks,
            ],
        )


JOB_RADAR_HEADING = "💼 Job Radar"


def _find_section(blocks, heading_text: str, stop_types=("heading_1", "heading_2", "heading_3", "divider")):
    """Generic version of _find_gmail_digest_block: find a heading_2 by text and
    return (heading_id, [content_block_ids]) up to the next block type in stop_types.
    Sections that use heading_3 internally (e.g. Newsletter Digest) should pass a
    stop_types that excludes heading_3, or old sub-sections never get deleted."""
    results = blocks.get("results", [])
    heading_id = None
    content_block_ids = []
    found = False
    for block in results:
        if found:
            btype = block.get("type", "")
            if btype in stop_types:
                break
            content_block_ids.append(block["id"])
            continue
        if block.get("type") == "heading_2":
            text = "".join(
                rt.get("plain_text", "")
                for rt in block["heading_2"].get("rich_text", [])
            )
            if heading_text in text:
                heading_id = block["id"]
                found = True
    return heading_id, content_block_ids


def build_job_radar_blocks(ranked_jobs: list, run_timestamp: str) -> list:
    """Build the Notion blocks for the Job Radar section."""
    blocks = [{
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {"content": f"Last updated: {run_timestamp}"}}],
            "icon": {"emoji": "🕗"},
            "color": "gray_background",
        },
    }]
    if not ranked_jobs:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": "No strong matches today."}}]},
        })
        return blocks

    for j in ranked_jobs:
        link = j.get("apply_url") or j.get("url") or ""
        posted = j.get("posted_ago") or j.get("posted_date") or ""
        meta = (f"  ·  {j.get('location','')}  ·  {posted}  ·  "
                f"{j.get('applicants','n/a')} applicants  ·  {j.get('score',0)}/100 — "
                f"{j.get('reason','')}  ·  ")
        rich = [
            {"type": "text",
             "text": {"content": f"{j.get('title','')} — {j.get('company','')}"},
             "annotations": {"bold": True}},
            {"type": "text", "text": {"content": meta}},
            {"type": "text", "text": {"content": "Apply", "link": {"url": link}}},
        ]
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": rich},
        })
    return blocks


# ── Newsletter Digest ───────────────────────────────────────────────────────

NEWSLETTER_DIGEST_HEADING = "📰 Newsletter Digest"


def build_newsletter_digest_blocks(newsletter_results: dict, run_timestamp: str) -> list:
    """Build Notion blocks for the Newsletter Digest section."""
    blocks = [
        {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{"type": "text", "text": {"content": f"Last updated: {run_timestamp}"}}],
                "icon": {"emoji": "🕗"},
                "color": "gray_background",
            },
        }
    ]

    for name, result in newsletter_results.items():
        # Newsletter sub-heading
        blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{"type": "text", "text": {"content": name}}]
            },
        })

        if result is None:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": "No issue found in last 24h."}}]
                },
            })
        else:
            subject_line = f"{result.get('subject', '')}  ·  {result.get('sender', '')}"
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": subject_line},
                                   "annotations": {"color": "gray"}}]
                },
            })
            articles = result.get("articles") or []
            # Fall back to legacy summary string if articles list is missing
            if not articles and result.get("summary"):
                articles = [
                    {"headline": line.lstrip("• ").split(": ")[0],
                     "gist": ": ".join(line.lstrip("• ").split(": ")[1:]),
                     "url": ""}
                    for line in result["summary"].split("\n") if line.strip()
                ]
            for article in articles:
                headline = article.get("headline", "")
                gist = article.get("gist", "")
                url = article.get("url", "")
                headline_run = {
                    "type": "text",
                    "text": {"content": headline, **({"link": {"url": url}} if url else {})},
                    "annotations": {"bold": True},
                }
                sep_run = {"type": "text", "text": {"content": f": {gist}" if gist else ""}}
                blocks.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [headline_run, sep_run] if gist else [headline_run]
                    },
                })

    return blocks


def update_newsletter_digest_on_briefing_page(newsletter_results: dict, run_timestamp: str):
    """
    Replace the Newsletter Digest section on the Morning Briefing page.
    Creates the section if it doesn't exist.
    """
    try:
        blocks = notion.blocks.children.list(block_id=MORNING_BRIEFING_PAGE_ID)
        heading_id, old_content_ids = _find_section(
            blocks, NEWSLETTER_DIGEST_HEADING, stop_types=("heading_1", "heading_2", "divider")
        )

        for block_id in old_content_ids:
            try:
                notion.blocks.delete(block_id=block_id)
            except Exception:
                pass

        new_blocks = build_newsletter_digest_blocks(newsletter_results, run_timestamp)

        if heading_id:
            notion.blocks.children.append(
                block_id=MORNING_BRIEFING_PAGE_ID, children=new_blocks, after=heading_id
            )
        else:
            notion.blocks.children.append(
                block_id=MORNING_BRIEFING_PAGE_ID,
                children=[
                    {"object": "block", "type": "divider", "divider": {}},
                    {
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"type": "text", "text": {"content": NEWSLETTER_DIGEST_HEADING}}]
                        },
                    },
                    *new_blocks,
                ],
            )
    except Exception as e:
        print(f"   ❌ Newsletter digest Notion error: {e}")


# ── Date Header Update (FIX 3) ──────────────────────────────────────────────

def update_morning_briefing_header(today_str: str | None = None):
    """
    Update the date line in the Morning Briefing page's top callout block.
    Finds the first callout whose text starts with 📅 and replaces line 0.
    Leaves all other lines (Active workstreams, Last session, etc.) untouched.
    """
    if today_str is None:
        today_str = date.today().strftime("%A, %B %-d, %Y")

    try:
        blocks = notion.blocks.children.list(block_id=MORNING_BRIEFING_PAGE_ID)
        for block in blocks.get("results", []):
            if block.get("type") != "callout":
                continue

            rich_text = block["callout"].get("rich_text", [])
            full_text = "".join(t.get("plain_text", "") for t in rich_text)

            if not full_text.strip().startswith("📅"):
                continue

            lines = full_text.split("\n")
            lines[0] = f"📅 **{today_str}**"
            new_text = "\n".join(lines)

            notion.blocks.update(
                block_id=block["id"],
                callout={
                    "rich_text": [{"type": "text", "text": {"content": new_text}}],
                    "icon": block["callout"].get("icon", {"emoji": "📅"}),
                    "color": block["callout"].get("color", "gray_background"),
                },
            )
            print(f"   ✅ Date header updated: {today_str}")
            return

        print("   ⚠️  Date header callout (📅) not found on Morning Briefing page")
    except Exception as e:
        print(f"   ❌ Date header update error: {e}")


# ── Session End Reminder (FIX 4A) ───────────────────────────────────────────

HANDOFF_PATH = os.path.expanduser("~/Projects/Egg/Agentic_OS/memory/last_handoff.md")


def check_and_append_session_end_reminder():
    """
    Check whether last_handoff.md was written today.
    If not, prepend a warning callout to the Morning Briefing page.
    """
    reminder_needed = True

    if os.path.exists(HANDOFF_PATH):
        mtime = os.path.getmtime(HANDOFF_PATH)
        if date.fromtimestamp(mtime) == date.today():
            reminder_needed = False

    if not reminder_needed:
        return

    try:
        warning_block = {
            "object": "block",
            "type": "callout",
            "callout": {
                "rich_text": [{
                    "type": "text",
                    "text": {
                        "content": (
                            "⚠️ Session end protocol not run yesterday — handoff is stale. "
                            "Run 'session end' before closing today."
                        )
                    },
                }],
                "icon": {"emoji": "⚠️"},
                "color": "yellow_background",
            },
        }
        # Prepend to top of page (after title) so it's the first thing seen
        notion.blocks.children.append(
            block_id=MORNING_BRIEFING_PAGE_ID,
            children=[warning_block],
        )
        print("   ⚠️  Session end reminder added to Morning Briefing (handoff is stale)")
    except Exception as e:
        print(f"   ❌ Session end reminder error: {e}")


def update_job_radar_on_briefing_page(ranked_jobs: list, run_timestamp: str):
    """Replace the Job Radar section content. Inserts new blocks right after the
    heading (via the API 'after' param) so ordering is correct even with other sections."""
    blocks = notion.blocks.children.list(block_id=MORNING_BRIEFING_PAGE_ID)
    heading_id, old_content_ids = _find_section(blocks, JOB_RADAR_HEADING)

    for block_id in old_content_ids:
        try:
            notion.blocks.delete(block_id=block_id)
        except Exception:
            pass

    new_blocks = build_job_radar_blocks(ranked_jobs, run_timestamp)

    if heading_id:
        notion.blocks.children.append(
            block_id=MORNING_BRIEFING_PAGE_ID, children=new_blocks, after=heading_id
        )
    else:
        notion.blocks.children.append(
            block_id=MORNING_BRIEFING_PAGE_ID,
            children=[
                {"object": "block", "type": "divider", "divider": {}},
                {"object": "block", "type": "heading_2",
                 "heading_2": {"rich_text": [{"type": "text", "text": {"content": JOB_RADAR_HEADING}}]}},
                *new_blocks,
            ],
        )
