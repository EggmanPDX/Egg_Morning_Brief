# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

# Notion
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
MORNING_BRIEFING_PAGE_ID = os.getenv("MORNING_BRIEFING_PAGE_ID")
D8_TASKS_SOURCE_ID = os.getenv("D8_TASKS_SOURCE_ID")
BGC_TASKS_SOURCE_ID = os.getenv("BGC_TASKS_SOURCE_ID")

# Database page IDs (used by notion-client SDK for creating pages)
D8_DB_PAGE_ID = os.getenv("D8_DB_PAGE_ID")
BGC_DB_PAGE_ID = os.getenv("BGC_DB_PAGE_ID")

# Apify
APIFY_TOKEN = os.getenv("APIFY_TOKEN")

# Gmail
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GOOGLE_CREDENTIALS_PATH = os.getenv(
    "GOOGLE_CREDENTIALS_PATH",
    os.path.expanduser("~/.config/morning-brief/credentials.json"),
)
GOOGLE_TOKEN_PATH = os.getenv(
    "GOOGLE_TOKEN_PATH",
    os.path.expanduser("~/.config/morning-brief/token.json"),
)

# D8 Task property values (exact strings from Notion schema)
D8_STATUS_OPTIONS = ["To-do", "In Progress", "Done", "Blocked"]
D8_PRIORITY_OPTIONS = ["High", "Medium", "Low"]
D8_PROJECT_AREA_OPTIONS = ["Enablement", "Client Work", "Marketing", "Internal Systems"]

# BGC Task property values (exact strings from Notion schema)
BGC_STATUS_OPTIONS = ["To-do", "In Progress", "Done", "Blocked"]
BGC_PRIORITY_OPTIONS = ["High", "Medium", "Low"]
BGC_CATEGORY_OPTIONS = ["Content & LinkedIn", "Workshops", "Frameworks", "Personal Projects"]

# Key people whose emails always get analyzed (comma-separated in .env)
KEY_SENDERS = [s.strip() for s in os.getenv("KEY_SENDERS", "").split(",") if s.strip()]

# Business context injected into the email-analysis prompt (kept out of source)
BUSINESS_CONTEXT = os.getenv("BUSINESS_CONTEXT", "")
