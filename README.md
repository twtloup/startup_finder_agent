# Venture Funding Monitor

An automated system that monitors RSS feeds from tech/startup news sources, identifies companies that have recently received funding (Seed to Series C), and emails you a daily or weekly digest of relevant opportunities.

**Geographic Focus:** UK (priority), Europe, and Middle East
**Industry Focus:** Fintech, SaaS, and tech-enabled companies
**Funding Stages:** Seed, Series A, Series B, Series C

## Features

- Monitors RSS feeds from TechCrunch, Sifted, VentureBeat, and Crunchbase News
- Uses regex-based pattern matching to detect funding announcements (no LLM API required)
- Extracts company name, funding stage, amount, location, and industry
- Stores data in SQLite database to avoid duplicate processing
- Sends beautiful HTML email digests via Gmail SMTP
- Runs automatically on GitHub Actions (or locally)
- Scores relevance based on location and industry priorities

## Project Structure

```
startup_finder_agent/
├── src/
│   ├── config.py              # Configuration and regex patterns
│   ├── rss_fetcher.py         # Fetch and parse RSS feeds
│   ├── funding_detector.py    # Detect and extract funding details
│   ├── data_manager.py        # SQLite database operations
│   ├── email_sender.py        # Generate and send email digests
│   └── main.py                # Main orchestration script
├── templates/
│   └── email_digest.html      # Email template
├── data/
│   └── funding_monitor.db     # SQLite database (auto-created)
├── tests/
│   └── (test files)
├── .env                       # Your email credentials (create this)
├── .env.example               # Template for .env file
├── .gitignore
├── requirements.txt           # Python dependencies
├── CLAUDE.md                  # Project brief
└── README.md                  # This file
```

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- A Gmail account (for sending emails)
- Git (optional, for GitHub Actions deployment)

### Step 1: Clone or Download the Project

```bash
git clone <repository-url>
cd startup_finder_agent
```

### Step 2: Set Up Python Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `feedparser` - RSS feed parsing
- `requests` - HTTP requests with retry logic
- `python-dotenv` - Environment variable management
- `jinja2` - HTML templating for emails
- `pytest` - Testing framework
- `python-dateutil` - Flexible date parsing

### Step 4: Configure Gmail App Password

1. **Enable 2-Factor Authentication** on your Google Account:
   - Go to https://myaccount.google.com/security
   - Enable "2-Step Verification"

2. **Generate an App Password**:
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Other (Custom name)"
   - Name it "Venture Funding Monitor"
   - Copy the 16-character password (remove spaces)

3. **Create `.env` file** (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

4. **Edit `.env` file** with your credentials:
   ```
   GMAIL_ADDRESS=your.email@gmail.com
   GMAIL_APP_PASSWORD=your16charpassword
   RECIPIENT_EMAIL=your.email@gmail.com
   DIGEST_TYPE=daily
   ```

### Step 5: Test Locally

Run the monitor manually to test:

```bash
python src/main.py
```

**What happens:**
1. Fetches RSS feeds from TechCrunch, Sifted, VentureBeat, Crunchbase
2. Detects funding announcements using regex patterns
3. Stores results in `data/funding_monitor.db`
4. Sends email digest if funding announcements found
5. Logs output to console and `funding_monitor.log`

**First Run:**
- Expect to process 50-100 articles from RSS feeds
- Should find 2-5 relevant funding announcements
- Check your email for the digest

## GitHub Actions Deployment (Automated)

To run automatically in the cloud every day:

### Step 1: Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit: Venture Funding Monitor"
git remote add origin <your-github-repo-url>
git push -u origin main
```

### Step 2: Add Secrets to GitHub

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add these three secrets:
   - `GMAIL_ADDRESS`: Your Gmail address
   - `GMAIL_APP_PASSWORD`: Your Gmail app password
   - `RECIPIENT_EMAIL`: Where to send digests

### Step 3: Create GitHub Actions Workflow

Create `.github/workflows/funding_monitor.yml`:

```yaml
name: Venture Funding Monitor

on:
  schedule:
    - cron: '0 8 * * *'  # Daily at 8 AM UTC
  workflow_dispatch:      # Allow manual trigger

jobs:
  monitor_funding:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Create data directory
        run: mkdir -p data

      - name: Restore database
        uses: actions/cache@v3
        with:
          path: data/funding_monitor.db
          key: funding-db-${{ github.run_id }}
          restore-keys: funding-db-

      - name: Run funding monitor
        env:
          GMAIL_ADDRESS: ${{ secrets.GMAIL_ADDRESS }}
          GMAIL_APP_PASSWORD: ${{ secrets.GMAIL_APP_PASSWORD }}
          RECIPIENT_EMAIL: ${{ secrets.RECIPIENT_EMAIL }}
        run: python src/main.py

      - name: Save database
        uses: actions/cache/save@v3
        if: always()
        with:
          path: data/funding_monitor.db
          key: funding-db-${{ github.run_id }}
```

### Step 4: Test Manual Run

1. Go to **Actions** tab in your GitHub repository
2. Click "Venture Funding Monitor" workflow
3. Click "Run workflow" → "Run workflow"
4. Check logs and email

### Step 5: Monitor Automated Runs

- GitHub Actions will run daily at 8 AM UTC
- Check the **Actions** tab for logs
- Failed runs will show in red
- Email yourself when issues occur

## How It Works

### 1. RSS Fetching (src/rss_fetcher.py)
- Fetches RSS feeds from configured sources
- Parses XML using `feedparser` library
- Handles network errors with retry logic (3 attempts)
- Extracts title, link, description, published date

### 2. Funding Detection (src/funding_detector.py)
- Combines title + description for full text analysis
- Applies regex patterns to detect:
  - **Funding keywords:** raises, secures, closes, funding, investment
  - **Funding stages:** Seed, Series A, Series B, Series C
  - **Amounts:** $10M, £5 million, €20B formats
  - **Locations:** UK, London, Berlin, Dubai, Tel Aviv, etc.
  - **Industries:** Fintech, SaaS, healthtech, proptech, etc.
  - **Company names:** Extracted from article titles

### 3. Relevance Scoring (0-100 points)
- **+30 points:** Has funding keywords
- **+20 points:** Has funding stage
- **+30 points:** UK location (highest priority)
- **+15 points:** Europe or Middle East location
- **+20 points:** Fintech or SaaS industry
- **+10 points:** Other tech industries
- **Threshold:** Only process articles scoring 50+

### 4. Database Storage (src/data_manager.py)
- Uses SQLite (no separate database server needed)
- Two tables:
  - `articles`: Tracks all processed articles (prevents duplicates)
  - `funding_announcements`: Stores extracted funding details
- Automatically cleans up entries older than 90 days

### 5. Email Digest (src/email_sender.py)
- Generates HTML email from Jinja2 template
- Includes plain text fallback
- Sends via Gmail SMTP with TLS encryption
- Professional design with funding cards and badges
- If email fails, saves HTML backup to `backup_digests/`

## Configuration

### RSS Feeds

Edit `src/config.py` to add/remove RSS feeds:

```python
RSS_FEEDS = {
    'TechCrunch': 'https://techcrunch.com/feed/',
    'Sifted': 'https://sifted.eu/feed',
    'VentureBeat': 'https://venturebeat.com/feed/',
    'Crunchbase News': 'https://news.crunchbase.com/feed/'
}
```

### Regex Patterns

Customize detection patterns in `src/config.py`:

```python
# Example: Add more location keywords
UK_KEYWORDS_PATTERN = re.compile(
    r'\b(UK|London|Manchester|YourCity)\b',
    re.IGNORECASE
)
```

### Relevance Scoring

Adjust scoring weights in `src/config.py`:

```python
SCORE_UK_LOCATION = 30  # Change to prioritize differently
SCORE_FINTECH = 25      # Increase fintech priority
```

## Testing

### Run Individual Components

**Test RSS Fetcher:**
```bash
python src/rss_fetcher.py
```

**Test Funding Detector:**
```bash
python src/funding_detector.py
```

**Test Database:**
```bash
python src/data_manager.py
```

**Test Email Sender:**
```bash
python src/email_sender.py
```

### Run Full Workflow

```bash
python src/main.py
```

### Check Logs

```bash
cat funding_monitor.log
```

### Inspect Database

```bash
sqlite3 data/funding_monitor.db

# Example queries:
SELECT * FROM articles LIMIT 10;
SELECT * FROM funding_announcements;
SELECT COUNT(*) FROM articles WHERE is_funding_related = 1;
```

## Troubleshooting

### No Email Received

1. **Check Gmail credentials:**
   - Verify `.env` file has correct `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD`
   - Ensure 2FA is enabled and you're using an app password (not regular password)

2. **Check logs:**
   ```bash
   tail -f funding_monitor.log
   ```

3. **Check backup digests:**
   - If email failed, check `backup_digests/` folder
   - Open HTML file in browser

### No Funding Announcements Found

1. **Lower relevance threshold:**
   - Edit `src/config.py`: `RELEVANCE_THRESHOLD = 40`

2. **Check regex patterns:**
   - Patterns might be too strict
   - Test with `python src/funding_detector.py`

3. **Expand geographic focus:**
   - Add more location keywords to config

### GitHub Actions Failing

1. **Check secrets:**
   - Verify all three secrets are set in repository settings
   - No spaces or extra characters

2. **Check workflow file:**
   - Ensure `.github/workflows/funding_monitor.yml` exists
   - Check YAML syntax

3. **View logs:**
   - Go to Actions tab → Click on failed run → View logs

## Expected Results

### First Run
- 50-100 articles fetched from RSS feeds
- 2-5 relevant funding announcements detected
- Email digest with 2-5 companies

### Daily Runs
- 1-3 new funding announcements per day
- Some days may have zero (normal)
- Mostly Series A/B (Series C less frequent)
- Mix of UK, European, and Middle Eastern companies

## Maintenance

### Weekly
- Check GitHub Actions logs for errors
- Review email digest quality

### Monthly
- Tune regex patterns if missing relevant articles
- Update RSS feed URLs if any have changed
- Review relevance threshold

### Quarterly
- Update Python dependencies:
  ```bash
  pip install --upgrade -r requirements.txt
  pip freeze > requirements.txt
  ```
- Review database size (should stay under 10 MB)

## Future Enhancements

- [ ] Add more RSS feeds (regional tech blogs)
- [ ] Web dashboard to browse all announcements
- [ ] Export to CSV for analysis in Power BI
- [ ] Slack/Discord notifications
- [ ] LLM API integration for better extraction (if budget allows)
- [ ] Company website scraping for additional details
- [ ] Track company growth over time

## Technical Details

### Why These Technologies?

**Python**: Easy to learn, great libraries, widely used in data pipelines

**SQLite**: No separate database server, lightweight, perfect for single-user apps

**feedparser**: Industry standard for RSS parsing, handles various formats

**requests**: Better than urllib, built-in retry logic, cleaner API

**Jinja2**: Powerful templating, separates logic from presentation

**Gmail SMTP**: Free, reliable, easy to set up with app passwords

**GitHub Actions**: Free tier (2000 minutes/month), no server maintenance

### Security Notes

- Never commit `.env` file to Git (already in `.gitignore`)
- Use GitHub Secrets for sensitive data, not environment variables in workflow files
- Gmail app passwords are safer than regular passwords
- SQLite database is local and not exposed to internet

## Support

If you encounter issues:

1. Check logs: `tail -f funding_monitor.log`
2. Run tests: `python src/main.py`
3. Review this README troubleshooting section
4. Check [GitHub Issues](https://github.com/yourusername/startup_finder_agent/issues)

## License

This project is for personal/educational use.

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes with clear commit messages
4. Submit a pull request

---

**Built with Claude Code** - An automated venture funding monitor for discovering Series A-C opportunities in UK, Europe, and Middle East.
