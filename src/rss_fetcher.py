"""
RSS Fetcher for Venture Funding Monitor
Fetches and parses RSS feeds from tech/startup news sources.
Handles network errors gracefully with retry logic.
"""

import logging
import time
from typing import List, Dict, Optional
from datetime import datetime

import requests
import feedparser
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dateutil import parser as date_parser

from src import config

# Set up logging
logger = logging.getLogger(__name__)


class RSSFetcher:
    """
    Fetches and parses RSS feeds from configured sources.

    Why feedparser?
    - Industry-standard library for RSS/Atom feeds
    - Handles various feed formats automatically
    - Robust error handling (doesn't crash on malformed XML)

    Why requests?
    - Clean API for HTTP requests
    - Easy retry configuration
    - Better error handling than built-in urllib
    """

    def __init__(self):
        """Initialize RSS fetcher with retry logic."""
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """
        Create requests session with retry configuration.

        Retry strategy:
        - 3 total attempts
        - Exponential backoff: 1s, 2s, 4s
        - Retry on connection errors and 5xx server errors
        """
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=config.REQUEST_RETRIES,
            backoff_factor=config.REQUEST_BACKOFF,
            status_forcelist=[429, 500, 502, 503, 504],  # HTTP codes to retry
            allowed_methods=["GET"]  # Only retry GET requests
        )

        # Mount adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set user agent to identify our bot
        session.headers.update({
            'User-Agent': config.USER_AGENT
        })

        return session

    def fetch_feed(self, url: str, source_name: str) -> Optional[str]:
        """
        Fetch RSS feed XML from a URL.

        Args:
            url: RSS feed URL
            source_name: Name of the source (for logging)

        Returns:
            RSS feed XML content as string, or None if failed
        """
        try:
            logger.info(f"Fetching RSS feed: {source_name} ({url})")

            response = self.session.get(
                url,
                timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()  # Raise exception for bad status codes

            logger.info(f"Successfully fetched {source_name}")
            return response.text

        except requests.exceptions.Timeout:
            logger.error(f"Timeout fetching {source_name}: {url}")
            return None

        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error fetching {source_name}: {url}")
            return None

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching {source_name}: {e}")
            return None

        except Exception as e:
            logger.error(f"Unexpected error fetching {source_name}: {e}")
            return None

    def parse_feed(self, xml_content: str, source_name: str) -> List[Dict]:
        """
        Parse RSS feed XML into structured article data.

        Args:
            xml_content: RSS feed XML string
            source_name: Name of the source (for logging)

        Returns:
            List of article dictionaries with title, link, description, published_date
        """
        if not xml_content:
            return []

        try:
            # Parse RSS feed
            # Note: feedparser doesn't raise exceptions, it sets 'bozo' flag for errors
            feed = feedparser.parse(xml_content)

            # Check for parsing errors
            if feed.bozo:
                logger.warning(
                    f"RSS parsing issue for {source_name}: {feed.get('bozo_exception', 'Unknown error')}"
                )

            # Extract articles from feed entries
            articles = []
            for entry in feed.entries:
                article = self._extract_article_data(entry, source_name)
                if article:
                    articles.append(article)

            logger.info(f"Parsed {len(articles)} articles from {source_name}")
            return articles

        except Exception as e:
            logger.error(f"Error parsing RSS feed for {source_name}: {e}")
            return []

    def _extract_article_data(self, entry, source_name: str) -> Optional[Dict]:
        """
        Extract article data from a single RSS entry.

        Args:
            entry: feedparser entry object
            source_name: Name of the source

        Returns:
            Dictionary with article data, or None if required fields missing
        """
        # Required fields: title and link
        if not hasattr(entry, 'title') or not hasattr(entry, 'link'):
            logger.debug(f"Skipping entry without title or link from {source_name}")
            return None

        # Extract title (required)
        title = entry.title.strip()

        # Extract link (required)
        link = entry.link.strip()

        # Extract description (optional, may be summary or content)
        description = ""
        if hasattr(entry, 'description'):
            description = entry.description
        elif hasattr(entry, 'summary'):
            description = entry.summary
        elif hasattr(entry, 'content'):
            # Some feeds use 'content' instead
            description = entry.content[0].value if entry.content else ""

        # Remove HTML tags from description (simple approach)
        description = self._strip_html(description)

        # Extract published date
        published_date = self._extract_date(entry)

        return {
            'title': title,
            'url': link,
            'description': description,
            'published_date': published_date,
            'source': source_name
        }

    def _extract_date(self, entry) -> str:
        """
        Extract and normalize publication date from RSS entry.

        RSS feeds use various date formats (RFC 822, ISO 8601, etc.)
        We use dateutil.parser to handle all formats automatically.

        Args:
            entry: feedparser entry object

        Returns:
            ISO format datetime string, or current time if parsing fails
        """
        # Try different date fields
        date_fields = ['published', 'updated', 'created']

        for field in date_fields:
            if hasattr(entry, field):
                date_str = getattr(entry, field)
                try:
                    # Parse date string (handles multiple formats)
                    dt = date_parser.parse(date_str)
                    # Return as ISO format string
                    return dt.isoformat()

                except (ValueError, TypeError) as e:
                    logger.debug(f"Could not parse date '{date_str}': {e}")
                    continue

        # If no date found, use current time
        logger.debug(f"No valid date found for entry, using current time")
        return datetime.now().isoformat()

    def _strip_html(self, text: str) -> str:
        """
        Remove HTML tags from text (simple approach).

        For more complex HTML, could use BeautifulSoup, but this simple
        regex approach works well for RSS descriptions.

        Args:
            text: Text with HTML tags

        Returns:
            Text without HTML tags
        """
        import re
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def fetch_all_feeds(self) -> List[Dict]:
        """
        Fetch and parse all configured RSS feeds.

        Returns:
            List of all articles from all feeds
        """
        all_articles = []

        for source_name, feed_url in config.RSS_FEEDS.items():
            # Fetch feed
            xml_content = self.fetch_feed(feed_url, source_name)

            if xml_content:
                # Parse feed
                articles = self.parse_feed(xml_content, source_name)
                all_articles.extend(articles)

                # Be polite: wait between requests
                time.sleep(config.REQUEST_DELAY)
            else:
                logger.warning(f"Skipping {source_name} due to fetch error")

        logger.info(f"Total articles fetched: {len(all_articles)}")
        return all_articles


# Example usage and testing
if __name__ == "__main__":
    # Configure logging for testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test RSS fetcher
    fetcher = RSSFetcher()

    print("Fetching RSS feeds...")
    articles = fetcher.fetch_all_feeds()

    print(f"\nFetched {len(articles)} total articles")

    # Display first few articles
    print("\nSample articles:")
    for i, article in enumerate(articles[:5], 1):
        print(f"\n{i}. {article['title']}")
        print(f"   Source: {article['source']}")
        print(f"   URL: {article['url'][:60]}...")
        print(f"   Published: {article['published_date']}")
        print(f"   Description: {article['description'][:100]}...")
