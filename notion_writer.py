# notion_client.py
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
                "rich_text": [{"type": "text", "text": {"content": digest_text}}]
            },
        },
    ]

    if heading_id:
        # Heading blocks don't support children — append to page instead
        # (Gmail Digest is always the last section so appending to page puts content right after heading)
        notion.blocks.children.append(block_id=MORNING_BRIEFING_PAGE_ID, children=new_blocks)
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


def _find_section(blocks, heading_text: str):
    """Generic version of _find_gmail_digest_block: find a heading_2 by text and
    return (heading_id, [content_block_ids]) up to the next heading/divider."""
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
