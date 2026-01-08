"""
Configuration file for the Venture Funding Monitor
Contains RSS feed URLs, regex patterns, and all configuration settings.
"""

import os
import re
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ====================
# RSS FEED SOURCES
# ====================
# These are the main tech/startup news sources we'll monitor for funding announcements

RSS_FEEDS = {
    'TechCrunch': 'https://techcrunch.com/feed/',
    'Sifted': 'https://sifted.eu/feed',
    'VentureBeat': 'https://venturebeat.com/feed/',
    'Crunchbase News': 'https://news.crunchbase.com/feed/'
}

# ====================
# EMAIL CONFIGURATION
# ====================
# Gmail SMTP settings for sending digest emails

SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587  # TLS port for secure connection

# Email credentials from environment variables (stored in .env file)
GMAIL_ADDRESS = os.getenv('GMAIL_ADDRESS')
GMAIL_APP_PASSWORD = os.getenv('GMAIL_APP_PASSWORD')
RECIPIENT_EMAIL = os.getenv('RECIPIENT_EMAIL', GMAIL_ADDRESS)  # Default to sender if not specified

# Email subject templates
EMAIL_SUBJECT_DAILY = 'Daily Funding Digest - {count} New Opportunities - {date}'
EMAIL_SUBJECT_WEEKLY = 'Weekly Funding Digest - {count} New Opportunities - Week of {date}'

# ====================
# DATABASE CONFIGURATION
# ====================

DATABASE_PATH = os.path.join('data', 'funding_monitor.db')
DATABASE_CLEANUP_DAYS = 90  # Delete articles older than 90 days

# ====================
# FILTERING CONFIGURATION
# ====================
# Geographic and industry focus

LOOKBACK_DAYS = 60  # Only process articles from the last 60 days
RELEVANCE_THRESHOLD = 50  # Minimum score (0-100) to include an article in the digest

# ====================
# REGEX PATTERNS
# ====================
# These patterns detect and extract funding information from article text

# 1. FUNDING KEYWORDS
# Detect general funding announcements
FUNDING_KEYWORDS_PATTERN = re.compile(
    r'\b(raises?|raised|secures?|secured|closes?|closed|funding|investment|backs?|backed)\b',
    re.IGNORECASE
)

# 2. FUNDING STAGES
# Detect specific funding rounds
FUNDING_STAGES = {
    'Seed': re.compile(r'\b(seed\s+round|seed\s+funding|pre-seed)\b', re.IGNORECASE),
    'Series A': re.compile(r'\b(series\s+a|series-a)\b', re.IGNORECASE),
    'Series B': re.compile(r'\b(series\s+b|series-b)\b', re.IGNORECASE),
    'Series C': re.compile(r'\b(series\s+c|series-c)\b', re.IGNORECASE),
}

# 3. FUNDING AMOUNT EXTRACTION
# Extract amounts like "$10M", "£5 million", "€20 million"
AMOUNT_PATTERNS = [
    # Pattern 1: $10M, £5m, €20B format
    re.compile(r'[\$£€]\s*(\d+(?:\.\d+)?)\s*(m(?:illion)?|b(?:illion)?|k(?:thousand)?)\b', re.IGNORECASE),
    # Pattern 2: "10 million dollars" format
    re.compile(r'(\d+(?:\.\d+)?)\s*(million|billion)\s*(dollars?|pounds?|euros?)', re.IGNORECASE),
]

# 4. COMPANY NAME EXTRACTION
# Extract company names from article titles
COMPANY_NAME_PATTERNS = [
    # Pattern 1: "CompanyName raises $X" (high confidence)
    re.compile(r'^([A-Z][A-Za-z0-9\s&.\'-]{2,40}?)\s+(?:raises?|secures?|closes?|lands?)'),
    # Pattern 2: "CompanyName, a [description], raises $X" (high confidence)
    re.compile(r'^([A-Z][A-Za-z0-9\s&.\'-]{2,40}?),\s+an?\s+'),
    # Pattern 3: "CompanyName has raised" (medium confidence)
    re.compile(r'([A-Z][A-Za-z0-9\s&.\'-]{2,40}?)\s+(?:has\s+)?(?:raised|secured)'),
]

# 5. LOCATION DETECTION
# Geographic focus: UK (priority), Europe, and Middle East

UK_KEYWORDS_PATTERN = re.compile(
    r'\b(UK|U\.K\.|United Kingdom|London|Manchester|Edinburgh|Bristol|Cambridge|Oxford|Birmingham|Leeds|Glasgow)\b',
    re.IGNORECASE
)

EU_KEYWORDS_PATTERN = re.compile(
    r'\b(Europe|European|Berlin|Paris|Amsterdam|Stockholm|Dublin|Copenhagen|Zurich|Barcelona|Madrid|Milan|Lisbon|Brussels|Munich|Hamburg|Vienna)\b',
    re.IGNORECASE
)

ME_KEYWORDS_PATTERN = re.compile(
    r'\b(Middle East|Dubai|Abu Dhabi|UAE|U\.A\.E\.|Tel Aviv|Israel|Israeli|Riyadh|Saudi Arabia|Bahrain|Qatar|Doha|Kuwait)\b',
    re.IGNORECASE
)

# 6. INDUSTRY DETECTION
# Priority industries: Fintech and SaaS

FINTECH_KEYWORDS_PATTERN = re.compile(
    r'\b(fintech|financial\s+technology|payments?|banking|digital\s+bank|neobank|crypto(?:currency)?|blockchain|digital\s+wallet|wealthtech)\b',
    re.IGNORECASE
)

SAAS_KEYWORDS_PATTERN = re.compile(
    r'\b(SaaS|software-as-a-service|B2B\s+software|enterprise\s+software|cloud\s+software|cloud\s+platform)\b',
    re.IGNORECASE
)

TECH_KEYWORDS_PATTERN = re.compile(
    r'\b(tech-enabled|proptech|healthtech|edtech|insurtech|AI|artificial\s+intelligence|machine\s+learning|data\s+analytics|cybersecurity)\b',
    re.IGNORECASE
)

# ====================
# SCORING WEIGHTS
# ====================
# Points awarded for each criteria (out of 100 total)

SCORE_FUNDING_KEYWORDS = 30  # Has funding-related keywords
SCORE_FUNDING_STAGE = 20     # Mentions specific funding stage
SCORE_UK_LOCATION = 30       # UK location (highest priority)
SCORE_EU_LOCATION = 15       # European location
SCORE_ME_LOCATION = 15       # Middle East location
SCORE_FINTECH = 20           # Fintech industry
SCORE_SAAS = 20              # SaaS industry
SCORE_TECH = 10              # Other tech sectors

# ====================
# HTTP REQUEST CONFIGURATION
# ====================

REQUEST_TIMEOUT = 10  # Seconds to wait for RSS feed response
REQUEST_RETRIES = 3   # Number of retry attempts for failed requests
REQUEST_BACKOFF = 1   # Exponential backoff factor (1s, 2s, 4s)
REQUEST_DELAY = 2     # Seconds to wait between feed requests (be polite)

# User agent to identify our bot
USER_AGENT = 'VentureFundingMonitor/1.0 (Educational project; +https://github.com/yourusername/startup_finder_agent)'
