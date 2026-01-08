"""
Main orchestration script for Venture Funding Monitor
Coordinates RSS fetching, funding detection, database storage, and email sending.
"""

import logging
import sys
import os
from datetime import datetime
from typing import List, Dict

# Add src directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config
from src.rss_fetcher import RSSFetcher
from src.funding_detector import FundingDetector
from src.data_manager import DatabaseManager
from src.email_sender import EmailSender

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('funding_monitor.log')
    ]
)

logger = logging.getLogger(__name__)


class FundingMonitor:
    """
    Main controller class for the Venture Funding Monitor.

    Orchestrates the complete workflow:
    1. Fetch RSS feeds
    2. Detect funding announcements
    3. Store in database
    4. Generate and send email digest
    """

    def __init__(self):
        """Initialize all components."""
        logger.info("Initializing Venture Funding Monitor")

        self.fetcher = RSSFetcher()
        self.detector = FundingDetector()
        self.db = DatabaseManager()
        self.email_sender = EmailSender()

        # Get digest type from environment or default to daily
        self.digest_type = os.getenv('DIGEST_TYPE', 'daily')

    def run(self):
        """
        Execute the complete monitoring workflow.

        Returns:
            True if successful, False if critical error occurred
        """
        try:
            logger.info("=" * 60)
            logger.info("Starting Venture Funding Monitor")
            logger.info("=" * 60)

            # Step 1: Fetch RSS feeds
            logger.info("Step 1: Fetching RSS feeds...")
            articles = self.fetcher.fetch_all_feeds()

            if not articles:
                logger.warning("No articles fetched from RSS feeds")
                return False

            logger.info(f"Fetched {len(articles)} total articles")

            # Step 2: Filter out already-processed articles
            logger.info("Step 2: Filtering for new articles...")
            new_articles = self._filter_new_articles(articles)

            if not new_articles:
                logger.info("No new articles to process")
                # Still check for pending announcements from previous runs
                pending_count = self._check_and_send_digest()
                if pending_count == 0:
                    logger.info("No pending announcements to send")
                return True

            logger.info(f"Found {len(new_articles)} new articles to process")

            # Step 3: Detect funding announcements
            logger.info("Step 3: Detecting funding announcements...")
            funding_announcements = self._detect_funding(new_articles)

            logger.info(f"Detected {len(funding_announcements)} funding announcements")

            # Step 4: Store results in database
            logger.info("Step 4: Storing results in database...")
            self._store_results(new_articles, funding_announcements)

            # Step 5: Generate and send email digest
            logger.info("Step 5: Generating and sending email digest...")
            email_sent = self._check_and_send_digest()

            # Step 6: Cleanup old entries
            logger.info("Step 6: Cleaning up old database entries...")
            self.db.cleanup_old_entries()

            # Print summary
            self._print_summary(len(articles), len(new_articles), len(funding_announcements), email_sent)

            logger.info("=" * 60)
            logger.info("Venture Funding Monitor completed successfully")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"Critical error in main workflow: {e}", exc_info=True)
            return False

        finally:
            # Close database connection
            self.db.close()

    def _filter_new_articles(self, articles: List[Dict]) -> List[Dict]:
        """
        Filter out articles that have already been processed.

        Args:
            articles: List of all articles from RSS feeds

        Returns:
            List of new articles not in database
        """
        new_articles = []

        for article in articles:
            url = article.get('url')
            if not self.db.is_article_processed(url):
                new_articles.append(article)
            else:
                logger.debug(f"Skipping already processed article: {url}")

        return new_articles

    def _detect_funding(self, articles: List[Dict]) -> List[Dict]:
        """
        Run funding detection on all new articles.

        Args:
            articles: List of new articles

        Returns:
            List of funding announcement dictionaries
        """
        funding_announcements = []

        for article in articles:
            result = self.detector.analyze_article(article)
            if result:
                funding_announcements.append(result)

        return funding_announcements

    def _store_results(
        self,
        articles: List[Dict],
        funding_announcements: List[Dict]
    ):
        """
        Store articles and funding announcements in database.

        Args:
            articles: List of all new articles
            funding_announcements: List of detected funding announcements
        """
        # Create a lookup map for funding announcements by URL
        funding_map = {fa['url']: fa for fa in funding_announcements}

        # Store each article
        for article in articles:
            url = article['url']
            is_funding = url in funding_map

            # Store article
            article_id = self.db.store_article(
                url=url,
                title=article['title'],
                source=article['source'],
                published_date=article['published_date'],
                is_funding_related=is_funding,
                relevance_score=funding_map[url]['relevance_score'] if is_funding else 0
            )

            # If article has funding announcement, store it
            if is_funding and article_id:
                fa = funding_map[url]
                self.db.store_funding_announcement(
                    article_id=article_id,
                    company_name=fa['company_name'],
                    funding_stage=fa['funding_stage'],
                    funding_amount=fa['funding_amount'],
                    location=fa['location'],
                    industry=fa['industry'],
                    description=fa['description']
                )

    def _check_and_send_digest(self) -> int:
        """
        Check for pending announcements and send digest if any exist.

        Returns:
            Number of announcements sent (0 if none)
        """
        # Determine lookback days based on digest type
        days = 7 if self.digest_type == 'weekly' else 1

        # Get pending announcements
        pending = self.db.get_pending_announcements(days)

        if not pending:
            logger.info("No pending announcements for digest")
            return 0

        logger.info(f"Found {len(pending)} pending announcements")

        # Send digest
        success = self.email_sender.send_digest(pending, self.digest_type)

        if success:
            # Mark announcements as sent
            announcement_ids = [a['id'] for a in pending]
            self.db.mark_as_digested(announcement_ids)
            logger.info(f"Successfully sent digest with {len(pending)} announcements")
            return len(pending)
        else:
            logger.error("Failed to send digest")
            return 0

    def _print_summary(
        self,
        total_articles: int,
        new_articles: int,
        funding_count: int,
        email_sent: int
    ):
        """
        Print summary statistics.

        Args:
            total_articles: Total articles fetched
            new_articles: New articles processed
            funding_count: Funding announcements detected
            email_sent: Number of announcements sent via email
        """
        logger.info("")
        logger.info("SUMMARY:")
        logger.info(f"  Total articles fetched: {total_articles}")
        logger.info(f"  New articles processed: {new_articles}")
        logger.info(f"  Funding announcements detected: {funding_count}")
        logger.info(f"  Email digest sent: {'Yes' if email_sent > 0 else 'No'}")
        logger.info(f"  Announcements in digest: {email_sent}")

        # Get database stats
        stats = self.db.get_stats()
        logger.info("")
        logger.info("DATABASE STATS:")
        logger.info(f"  Total articles in DB: {stats.get('total_articles', 0)}")
        logger.info(f"  Funding-related articles: {stats.get('funding_articles', 0)}")
        logger.info(f"  Total announcements: {stats.get('total_announcements', 0)}")
        logger.info(f"  Pending announcements: {stats.get('pending_announcements', 0)}")
        logger.info("")


def main():
    """Main entry point for the script."""
    try:
        monitor = FundingMonitor()
        success = monitor.run()
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
