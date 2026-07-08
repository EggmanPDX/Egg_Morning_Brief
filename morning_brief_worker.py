#!/usr/bin/env python3
# morning_brief_worker.py

import json
from datetime import datetime
from pathlib import Path

from config import GMAIL_ADDRESS, ANTHROPIC_API_KEY, NOTION_API_KEY
from gmail_client import get_gmail_service, get_unread_emails_since, mark_as_read, fetch_all_newsletters
from claude_analyzer import analyze_email, generate_gmail_digest, summarize_newsletter
from notion_writer import (
    create_d8_task,
    create_bgc_task,
    update_gmail_digest_on_briefing_page,
    update_newsletter_digest_on_briefing_page,
    update_morning_briefing_header,
    check_and_append_session_end_reminder,
)

RUN_LOG_PATH = Path(__file__).parent / "run_log.json"


def load_run_log():
    if RUN_LOG_PATH.exists():
        with open(RUN_LOG_PATH) as f:
            return json.load(f)
    return {"last_run": None, "tasks_created": 0, "emails_processed": 0,
            "jobs_found": 0, "jobs_shown": 0}


def save_run_log(log):
    with open(RUN_LOG_PATH, "w") as f:
        json.dump(log, f, indent=2)


def main():
    print(f"\n🧠 Morning Brief Worker — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    # Validate required config
    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY not set in .env — aborting")
        return
    if not NOTION_API_KEY:
        print("❌ NOTION_API_KEY not set in .env — aborting")
        return

    run_log = load_run_log()
    run_timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    tasks_created = 0
    analyzed_emails = []

    # 1. Fetch Gmail
    print(f"📨 Fetching Gmail for {GMAIL_ADDRESS}...")
    try:
        gmail_service = get_gmail_service()
        emails = get_unread_emails_since(gmail_service, hours_back=24)
        print(f"   Found {len(emails)} unread emails")
    except Exception as e:
        print(f"   ❌ Gmail error: {e}")
        emails = []

    # 2. Analyze each email with Claude
    if emails:
        print("🤖 Analyzing emails with Claude...")
    for email in emails:
        print(f"   → {email['subject'][:60]}...")
        try:
            analysis = analyze_email(email)
            analyzed_emails.append({"email": email, "analysis": analysis})

            # 3. Create Notion tasks for action items
            if analysis["has_action_item"] and analysis["action_items"]:
                for action_item in analysis["action_items"]:
                    source_context = f"Email from {email['sender']} — Subject: {email['subject']}"
                    priority = analysis.get("priority", "Medium")
                    workspace = analysis.get("workspace", "None")

                    if workspace == "D8TAOPS":
                        project_area = analysis.get("project_area") or "Client Work"
                        create_d8_task(action_item, priority, project_area, source_context)
                        print(f"   ✅ D8 task created: {action_item[:50]}")
                        tasks_created += 1

                    elif workspace == "BGC":
                        category = analysis.get("category") or "Personal Projects"
                        create_bgc_task(action_item, priority, category, source_context)
                        print(f"   ✅ BGC task created: {action_item[:50]}")
                        tasks_created += 1

                    elif workspace == "Personal":
                        create_bgc_task(action_item, priority, "Personal Projects", source_context)
                        print(f"   ✅ Personal task created: {action_item[:50]}")
                        tasks_created += 1

            # 4. Mark email as read after processing
            mark_as_read(gmail_service, email["id"])

        except Exception as e:
            print(f"   ❌ Analysis error for '{email['subject']}': {e}")
            continue

    # 5. Generate Gmail digest and write to Morning Briefing page
    print("📝 Updating Morning Briefing page...")
    try:
        digest = generate_gmail_digest(analyzed_emails)
        update_gmail_digest_on_briefing_page(digest, run_timestamp)
        print("   ✅ Digest written to Notion")
    except Exception as e:
        print(f"   ❌ Notion update error: {e}")

    # 7. Job Radar — LinkedIn enablement/training roles, scored by Claude
    print("💼 Running Job Radar...")
    try:
        from job_radar import run_job_radar
        radar = run_job_radar(run_timestamp)
        if radar.get("skipped"):
            print("   ⚠️  Job Radar skipped (APIFY_TOKEN not set)")
        else:
            print(f"   ✅ {radar['shown']} roles shown ({radar['found']} found)")
            run_log["jobs_found"] = radar["found"]
            run_log["jobs_shown"] = radar["shown"]
    except Exception as e:
        print(f"   ❌ Job Radar error: {e}")

    # 8. Newsletter Digest — The Rundown, The Neuron, TLDR (FIX 2)
    print("📰 Fetching newsletter digests...")
    newsletter_results = {}
    try:
        if emails is not None:  # gmail_service available
            raw_newsletters = fetch_all_newsletters(gmail_service)
            # Summarize each found newsletter
            for name, result in raw_newsletters.items():
                if result:
                    result["articles"] = summarize_newsletter(result)
                newsletter_results[name] = result

            update_newsletter_digest_on_briefing_page(newsletter_results, run_timestamp)
            found_count = sum(1 for v in newsletter_results.values() if v)
            print(f"   ✅ {found_count}/{len(newsletter_results)} newsletters found and written")
        else:
            print("   ⚠️  Gmail unavailable — newsletter digest skipped")
    except Exception as e:
        print(f"   ❌ Newsletter digest error: {e}")

    run_log["newsletter_digest"] = {
        name: ("found" if result else "not_found")
        for name, result in newsletter_results.items()
    }

    # 9. Update date header (FIX 3)
    print("📅 Updating date header...")
    try:
        update_morning_briefing_header()
    except Exception as e:
        print(f"   ❌ Date header error: {e}")

    # 10. Session end reminder check (FIX 4A)
    try:
        check_and_append_session_end_reminder()
    except Exception as e:
        print(f"   ❌ Session end reminder check error: {e}")

    # 11. Agentic_OS structure check (FIX 1 lock)
    import os as _os
    required_paths = [
        _os.path.expanduser("~/Projects/Egg/Agentic_OS/CLAUDE.md"),
        _os.path.expanduser("~/Projects/Egg/Agentic_OS/memory/last_handoff.md"),
    ]
    for path in required_paths:
        if not _os.path.exists(path):
            print(f"   ⚠️  WARNING: {path} missing from Agentic_OS — structure may be broken")

    # 12. Update run log
    run_log["last_run"] = run_timestamp
    run_log["tasks_created"] = run_log.get("tasks_created", 0) + tasks_created
    run_log["emails_processed"] = run_log.get("emails_processed", 0) + len(emails)
    save_run_log(run_log)

    print(f"\n✅ Done. {len(emails)} emails processed, {tasks_created} tasks created.")
    print("=" * 50)


if __name__ == "__main__":
    main()
